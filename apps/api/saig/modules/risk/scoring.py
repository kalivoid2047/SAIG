"""Pure risk-scoring functions.

Each domain scorer takes plain signal values and returns a 0-100 score plus a
factor decomposition (US-RISK-1). Kept free of DB/framework so the risk logic
is unit-testable in isolation; the service gathers the signals and calls these.

Convention: a *factor* is {factor, weight, value, contribution} where
`contribution` is the points that factor added to the 0-100 score, and the
weights within a domain sum to 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass

RISK_DOMAINS = (
    "climate",
    "disease",
    "supply_chain",
    "inventory",
    "production",
    "financial",
)


@dataclass
class DomainScore:
    score: int  # 0..100, higher = worse
    factors: list[dict]


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _factor(name: str, weight: float, value: float, sub_score: float) -> dict:
    """sub_score is that factor's own 0..100 risk; contribution = weight*sub."""
    return {
        "factor": name,
        "weight": round(weight, 3),
        "value": round(value, 3),
        "contribution": round(weight * sub_score, 1),
    }


def _combine(factors: list[dict]) -> DomainScore:
    score = round(_clamp(sum(f["contribution"] for f in factors)))
    return DomainScore(score=score, factors=factors)


# --- Domain scorers ----------------------------------------------------------

def score_climate(heat_stress_days: int, rainfall_30d_mm: float | None,
                  data_available: bool) -> DomainScore:
    if not data_available:
        # Unknown climate → moderate baseline, flagged as low-information.
        return DomainScore(
            score=40,
            factors=[_factor("weather_data", 1.0, 0.0, 40.0)],
        )
    # Heat stress: 0 days → 0 risk, >=10 days → full.
    heat_sub = _clamp(heat_stress_days / 10.0 * 100.0)
    # Rainfall deficit: below ~40mm/30d is drought-stress territory.
    rain = rainfall_30d_mm if rainfall_30d_mm is not None else 40.0
    drought_sub = _clamp((40.0 - min(rain, 40.0)) / 40.0 * 100.0)
    factors = [
        _factor("heat_stress_days", 0.5, heat_stress_days, heat_sub),
        _factor("rainfall_deficit_30d", 0.5, rain, drought_sub),
    ]
    return _combine(factors)


def score_disease(active_reports: int, outbreaks: int, avg_severity: float) -> DomainScore:
    density_sub = _clamp(active_reports / 8.0 * 100.0)  # 8+ active reports → full
    outbreak_sub = _clamp(outbreaks * 50.0)             # each outbreak is severe
    severity_sub = _clamp((avg_severity / 5.0) * 100.0)
    factors = [
        _factor("active_reports", 0.35, active_reports, density_sub),
        _factor("active_outbreaks", 0.45, outbreaks, outbreak_sub),
        _factor("avg_severity", 0.20, avg_severity, severity_sub),
    ]
    return _combine(factors)


def score_supply_chain(failed_deliveries: int, in_transit: int,
                       available_vehicles: int, total_vehicles: int) -> DomainScore:
    total_active = failed_deliveries + in_transit
    fail_ratio = (failed_deliveries / total_active) if total_active else 0.0
    fail_sub = _clamp(fail_ratio * 100.0)
    # Fleet availability: fewer available vehicles → higher risk.
    avail_ratio = (available_vehicles / total_vehicles) if total_vehicles else 1.0
    fleet_sub = _clamp((1.0 - avail_ratio) * 100.0)
    factors = [
        _factor("delivery_failure_ratio", 0.6, fail_ratio, fail_sub),
        _factor("fleet_unavailability", 0.4, 1.0 - avail_ratio, fleet_sub),
    ]
    return _combine(factors)


def score_inventory(min_coverage_ratio: float | None, near_expiry_lots: int,
                    covered_segments: int) -> DomainScore:
    if min_coverage_ratio is None:
        coverage_sub = 30.0  # no forecast/stock to compare → mild uncertainty
        coverage_val = 0.0
    else:
        # coverage >=1.0 → 0 risk; 0 coverage → full risk.
        coverage_sub = _clamp((1.0 - min(min_coverage_ratio, 1.0)) * 100.0)
        coverage_val = min_coverage_ratio
    expiry_sub = _clamp(near_expiry_lots / 5.0 * 100.0)  # 5+ near-expiry lots → full
    factors = [
        _factor("min_coverage_ratio", 0.7, coverage_val, coverage_sub),
        _factor("near_expiry_lots", 0.3, near_expiry_lots, expiry_sub),
    ]
    return _combine(factors)


def score_production(low_confidence_ratio: float, failed_cycles: int,
                     total_cycles: int) -> DomainScore:
    conf_sub = _clamp(low_confidence_ratio * 100.0)
    failed_ratio = (failed_cycles / total_cycles) if total_cycles else 0.0
    failed_sub = _clamp(failed_ratio * 100.0)
    factors = [
        _factor("low_confidence_predictions", 0.5, low_confidence_ratio, conf_sub),
        _factor("failed_cycles_ratio", 0.5, failed_ratio, failed_sub),
    ]
    return _combine(factors)


def score_financial(inventory_score: int, supply_chain_score: int,
                    demand_confidence: float) -> DomainScore:
    """Composite exposure: inventory + logistics risk, tempered by how
    confident we are in the demand outlook."""
    demand_sub = _clamp((1.0 - demand_confidence) * 100.0)
    factors = [
        _factor("inventory_exposure", 0.4, inventory_score, float(inventory_score)),
        _factor("supply_chain_exposure", 0.3, supply_chain_score, float(supply_chain_score)),
        _factor("demand_uncertainty", 0.3, 1.0 - demand_confidence, demand_sub),
    ]
    return _combine(factors)


def band(score: int) -> str:
    """Fixed risk band used across UI (design-system): low/medium/high."""
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"
