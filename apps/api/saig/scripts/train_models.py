"""Train and promote the yield and demand models from database data.

Usage:
    python -m saig.scripts.train_models            # all orgs
    python -m saig.scripts.train_models --score    # also run batch scoring after training

Offline MLOps step (ADR-0003): reads production/sales history, fits the
sklearn baselines, registers + promotes a new model version, and stores the
artifact. Idempotent-ish: each run creates a fresh promoted version and
retires the previous one.
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from saig.modules.iam.models import Organization
from saig.modules.predictions.service import PredictionService, TrainingService
from saig.modules.risk.service import RiskService
from saig.modules.weather.provider import OpenMeteoProvider
from saig.shared.config import get_settings
from saig.shared.database import create_engine_and_sessionmaker
from saig.shared.errors import AppError


async def main(also_score: bool) -> None:
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings.database_url)
    async with session_factory() as session:
        orgs = (
            await session.execute(
                select(Organization).where(Organization.deleted_at.is_(None))
            )
        ).scalars().all()

        for org in orgs:
            training = TrainingService(session)
            for name, trainer in (("yield", training.train_yield),
                                  ("demand", training.train_demand)):
                try:
                    version = await trainer(org.id, None)
                    print(f"[{org.name}] trained {name} v{version.version} "
                          f"metrics={version.metrics}")
                except AppError as exc:
                    print(f"[{org.name}] skipped {name}: {exc.detail}", file=sys.stderr)

            if also_score:
                service = PredictionService(session)
                try:
                    n = await service.score_yield(org.id, None, None, run_type="scheduled")
                    print(f"[{org.name}] scored yield for {n} crop cycles")
                except AppError as exc:
                    print(f"[{org.name}] yield scoring skipped: {exc.detail}", file=sys.stderr)
                try:
                    n = await service.run_demand_forecast(org.id, None)
                    print(f"[{org.name}] generated {n} demand forecast points")
                except AppError as exc:
                    print(f"[{org.name}] demand forecast skipped: {exc.detail}", file=sys.stderr)

                # Refresh the risk board now that prediction signals are fresh.
                n = await RiskService(session, OpenMeteoProvider()).recompute(org.id, None)
                print(f"[{org.name}] recomputed {n} risk assessments")

    await engine.dispose()
    print("Training complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score", action="store_true", help="run batch scoring after training")
    args = parser.parse_args()
    asyncio.run(main(args.score))
