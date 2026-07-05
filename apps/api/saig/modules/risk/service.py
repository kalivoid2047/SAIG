import logging
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from saig.modules.iam.services.audit_service import AuditService
from saig.modules.risk import scoring
from saig.modules.risk.repository import RiskRepository
from saig.modules.risk.scoring import DomainScore
from saig.modules.weather.provider import WeatherProvider
from saig.modules.weather.service import WeatherService

logger = logging.getLogger("saig.risk")

# Domains computed per-region (clear regional signal) vs. org-only.
REGIONAL_DOMAINS = ("climate", "disease", "production")


class RiskService:
    """Derives the six-domain risk board from operational + predictive signals
    (US-RISK-1). Recompute is idempotent per (scope, domain, day)."""

    def __init__(self, session: AsyncSession, weather_provider: WeatherProvider | None = None):
        self.session = session
        self.repo = RiskRepository(session)
        self.audit = AuditService(session)
        self.weather = WeatherService(session, weather_provider) if weather_provider else None

    async def recompute(self, organization_id: str, actor_id: str | None) -> int:
        today = date.today()
        written = 0

        # Gather org-scope signals once.
        disease = await self.repo.disease_signals(organization_id)
        supply = await self.repo.supply_signals(organization_id)
        inventory = await self.repo.inventory_signals(organization_id)
        production = await self.repo.production_signals(organization_id)
        demand_conf = await self.repo.demand_confidence(organization_id)
        climate_org = await self._climate(organization_id, None)

        s_climate = climate_org
        s_disease = scoring.score_disease(*disease)
        s_supply = scoring.score_supply_chain(*supply)
        s_inventory = scoring.score_inventory(*inventory)
        s_production = scoring.score_production(*production)
        s_financial = scoring.score_financial(
            s_inventory.score, s_supply.score, demand_conf
        )

        org_scores = {
            "climate": s_climate,
            "disease": s_disease,
            "supply_chain": s_supply,
            "inventory": s_inventory,
            "production": s_production,
            "financial": s_financial,
        }
        for domain, ds in org_scores.items():
            await self.repo.upsert_assessment(
                organization_id, None, domain, ds.score, ds.factors, today
            )
            written += 1

        # Per-region for the spatial domains.
        for region_id, _lat, _lng in await self.repo.region_centroids(organization_id):
            r_disease = await self.repo.disease_signals(organization_id, region_id)
            r_production = await self.repo.production_signals(organization_id, region_id)
            r_climate = await self._climate(organization_id, region_id)
            region_scores = {
                "climate": r_climate,
                "disease": scoring.score_disease(*r_disease),
                "production": scoring.score_production(*r_production),
            }
            for domain, ds in region_scores.items():
                await self.repo.upsert_assessment(
                    organization_id, region_id, domain, ds.score, ds.factors, today
                )
                written += 1

        self.audit.record("risk.recompute", actor_id=actor_id, organization_id=organization_id,
                          after={"assessments": written})
        await self.session.commit()
        return written

    async def _climate(self, organization_id: str, region_id: str | None) -> DomainScore:
        """Climate risk from agro-indicators at the scope centroid. Degrades
        gracefully to 'unknown' if weather data can't be fetched (offline)."""
        if self.weather is None:
            return scoring.score_climate(0, None, data_available=False)
        centroids = await self.repo.region_centroids(organization_id)
        if region_id is not None:
            centroids = [c for c in centroids if c[0] == region_id]
        if not centroids:
            return scoring.score_climate(0, None, data_available=False)
        # Org scope: average lat/lng of regions as a representative point.
        lat = sum(c[1] for c in centroids) / len(centroids)
        lng = sum(c[2] for c in centroids) / len(centroids)
        try:
            agro = await self.weather.get_agro_indicators(lat, lng, window_days=30)
            return scoring.score_climate(
                agro.heatStressDays, agro.rainfall30dMm, data_available=agro.dataPoints > 0
            )
        except Exception as exc:  # degrade to unknown, never fail recompute
            logger.warning("climate signal unavailable: %s", exc)
            return scoring.score_climate(0, None, data_available=False)

    # --- reads ---------------------------------------------------------------

    async def board(self, organization_id: str, region_id: str | None) -> dict:
        assessments = await self.repo.board(organization_id, region_id)
        if not assessments:
            return {"assessedDate": None, "domains": [], "highRiskCount": 0}
        assessed_date = assessments[0].assessed_date
        previous = await self.repo.previous_scores(organization_id, region_id, assessed_date)
        domains = []
        high = 0
        for a in sorted(assessments, key=lambda x: x.domain):
            prev = previous.get(a.domain)
            if a.score >= 70:
                high += 1
            domains.append(
                {
                    "domain": a.domain,
                    "score": a.score,
                    "band": scoring.band(a.score),
                    "previousScore": prev,
                    "trend": (a.score - prev) if prev is not None else 0,
                    "factors": a.factors,
                }
            )
        return {"assessedDate": assessed_date, "domains": domains, "highRiskCount": high}

    async def history(
        self, organization_id: str, region_id: str | None, domain: str, days: int = 90
    ) -> list[dict]:
        since = date.today() - timedelta(days=days)
        rows = await self.repo.history(organization_id, region_id, domain, since)
        return [{"assessedDate": r.assessed_date, "score": r.score} for r in rows]
