from datetime import date

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from saig.ml import registry
from saig.ml.demand_model import DemandModel
from saig.ml.yield_model import YIELD_FEATURES, YieldModel
from saig.modules.iam.services.audit_service import AuditService
from saig.modules.predictions.models import (
    DemandForecastRow,
    FeatureSnapshot,
    ModelVersion,
    PredictionRun,
    YieldPredictionRow,
)
from saig.modules.predictions.repository import PredictionsRepository
from saig.shared.database import utcnow
from saig.shared.errors import DomainError, NotFoundError


def _version_str() -> str:
    # Microsecond precision so retraining within the same second never collides
    # on the (org, model_name, version) unique key.
    now = utcnow()
    return f"{now.strftime('%Y%m%d.%H%M%S')}.{now.microsecond:06d}"


class TrainingService:
    """Offline training: read DB → fit → register → promote (ADR-0003)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PredictionsRepository(session)
        self.audit = AuditService(session)

    async def train_yield(self, organization_id: str, actor_id: str | None) -> ModelVersion:
        rows = await self.repo.yield_training_rows(organization_id)
        if len(rows) < 8:
            raise DomainError(
                f"Not enough historical production records to train "
                f"(have {len(rows)}, need 8+)."
            )
        model = YieldModel().fit(pd.DataFrame(rows))
        return await self._register(
            organization_id, actor_id, "yield", model, model.metrics, model.n_training_rows
        )

    async def train_demand(self, organization_id: str, actor_id: str | None) -> ModelVersion:
        rows = await self.repo.sales_history_rows(organization_id)
        if not rows:
            raise DomainError("No sales history to train the demand model.")
        model = DemandModel().fit(pd.DataFrame(rows))
        return await self._register(
            organization_id, actor_id, "demand", model, model.metrics, len(rows)
        )

    async def _register(
        self, organization_id: str, actor_id: str | None, model_name: str,
        model: object, metrics: dict, training_rows: int,
    ) -> ModelVersion:
        artifact_key = registry.save_artifact(model, model_name)
        await self.repo.demote_promoted(organization_id, model_name)
        version = ModelVersion(
            organization_id=organization_id,
            model_name=model_name,
            version=_version_str(),
            status="promoted",  # baseline auto-promotes; champion/challenger is a later gate
            metrics=metrics,
            artifact_key=artifact_key,
            training_rows=training_rows,
            promoted_at=utcnow(),
            promoted_by=actor_id,
        )
        self.session.add(version)
        await self.session.flush()
        self.audit.record(
            f"models.train.{model_name}", actor_id=actor_id, organization_id=organization_id,
            entity_table="model_versions", entity_id=version.id,
            after={"version": version.version, "metrics": metrics},
        )
        await self.session.commit()
        return version


class PredictionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PredictionsRepository(session)
        self.audit = AuditService(session)

    async def _load(self, organization_id: str, model_name: str):
        version = await self.repo.get_promoted(organization_id, model_name)
        if version is None:
            raise DomainError(
                f"No promoted '{model_name}' model. Train one first "
                f"(python -m saig.scripts.train_models)."
            )
        model = registry.load_artifact(version.artifact_key)
        return version, model

    # --- yield ---------------------------------------------------------------

    async def score_yield(
        self, organization_id: str, actor_id: str | None,
        crop_cycle_ids: list[str] | None, run_type: str = "manual",
    ) -> int:
        version, model = await self._load(organization_id, "yield")
        feature_rows = await self.repo.active_cycle_features(organization_id, crop_cycle_ids)
        if not feature_rows:
            return 0

        run = PredictionRun(
            organization_id=organization_id, model_version_id=version.id,
            run_type=run_type, triggered_by=actor_id,
        )
        self.session.add(run)
        await self.session.flush()

        predictions = model.predict(
            [{k: r[k] for k in YIELD_FEATURES} for r in feature_rows]
        )
        for feat, pred in zip(feature_rows, predictions, strict=True):
            snapshot = FeatureSnapshot(
                entity_type="crop_cycle", entity_id=feat["crop_cycle_id"],
                features={k: feat[k] for k in YIELD_FEATURES},
            )
            self.session.add(snapshot)
            await self.session.flush()
            self.session.add(
                YieldPredictionRow(
                    prediction_run_id=run.id,
                    crop_cycle_id=feat["crop_cycle_id"],
                    feature_snapshot_id=snapshot.id,
                    predicted_yield_kg_ha=pred.predicted_yield_kg_ha,
                    pi_low_kg_ha=pred.pi_low_kg_ha,
                    pi_high_kg_ha=pred.pi_high_kg_ha,
                    confidence=pred.confidence,
                    low_confidence=pred.low_confidence,
                )
            )
        run.completed_at = utcnow()
        run.stats = {"scored": len(feature_rows)}
        self.audit.record("predictions.yield.run", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="prediction_runs", entity_id=run.id,
                          after={"scored": len(feature_rows)})
        await self.session.commit()
        return len(feature_rows)

    # --- demand --------------------------------------------------------------

    async def run_demand_forecast(
        self, organization_id: str, actor_id: str | None, horizon: int = 12,
    ) -> int:
        version, model = await self._load(organization_id, "demand")
        segments = await self.repo.sales_segments(organization_id)
        if not segments:
            return 0

        run = PredictionRun(
            organization_id=organization_id, model_version_id=version.id,
            run_type="manual", triggered_by=actor_id,
        )
        self.session.add(run)
        await self.session.flush()

        start = date.today().replace(day=1)
        count = 0
        for region_id, variety_id in segments:
            for point in model.forecast(region_id, variety_id, start, horizon):
                self.session.add(
                    DemandForecastRow(
                        prediction_run_id=run.id,
                        organization_id=organization_id,
                        region_id=region_id,
                        variety_id=variety_id,
                        period_month=point.period_month,
                        forecast_qty_kg=point.forecast_qty_kg,
                        pi_low_kg=point.pi_low_kg,
                        pi_high_kg=point.pi_high_kg,
                        confidence=point.confidence,
                        seasonal_component=point.seasonal_component,
                    )
                )
                count += 1
        run.completed_at = utcnow()
        run.stats = {"segments": len(segments), "points": count}
        self.audit.record("predictions.demand.run", actor_id=actor_id,
                          organization_id=organization_id,
                          entity_table="prediction_runs", entity_id=run.id,
                          after={"segments": len(segments)})
        await self.session.commit()
        return count

    async def demand_series(
        self, organization_id: str, region_id: str, variety_id: str
    ) -> list[DemandForecastRow]:
        rows = await self.repo.latest_demand_series(organization_id, region_id, variety_id)
        if not rows:
            raise NotFoundError("No demand forecast for this region and variety yet.")
        return rows
