"""Demand forecasting: seasonal index x linear trend per region-variety.

A classical, dependency-light baseline (ADR-0003) that beats seasonal-naive
when a trend is present; per-segment gradient boosting is the documented
upgrade. Produces a 12-month horizon with prediction intervals from the
residual spread and a confidence that reflects history length + noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

MIN_MONTHS_FOR_SEASONAL = 12


@dataclass
class DemandPoint:
    period_month: date
    forecast_qty_kg: float
    pi_low_kg: float
    pi_high_kg: float
    confidence: float
    seasonal_component: float


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


class DemandModel:
    """Serializable. Stores per (region_id, variety_id) segment parameters."""

    def __init__(self) -> None:
        # (region_id, variety_id) -> params
        self._segments: dict[tuple[str, str], dict] = {}
        self.metrics: dict[str, float] = {}
        self.n_segments: int = 0

    def fit(self, df: pd.DataFrame) -> DemandModel:
        """df columns: region_id, variety_id, period_month (date), quantity_kg."""
        frame = df.copy()
        frame["period_month"] = pd.to_datetime(frame["period_month"])
        frame["quantity_kg"] = pd.to_numeric(frame["quantity_kg"], errors="coerce").fillna(0.0)

        maes: list[float] = []
        for (region_id, variety_id), grp in frame.groupby(["region_id", "variety_id"]):
            grp = grp.sort_values("period_month")
            qty = grp["quantity_kg"].to_numpy(dtype=float)
            months = grp["period_month"].dt.month.to_numpy()
            params, mae = self._fit_segment(qty, months)
            self._segments[(str(region_id), str(variety_id))] = params
            if mae is not None:
                maes.append(mae)

        self.n_segments = len(self._segments)
        self.metrics = {"mean_mae": round(float(np.mean(maes)), 2) if maes else 0.0,
                        "segments": self.n_segments}
        return self

    @staticmethod
    def _fit_segment(qty: np.ndarray, months: np.ndarray) -> tuple[dict, float | None]:
        n = len(qty)
        overall_mean = float(np.mean(qty)) if n else 0.0

        if n < MIN_MONTHS_FOR_SEASONAL:
            # Too little history: flat mean, wide band, low confidence.
            resid_std = float(np.std(qty)) if n > 1 else overall_mean * 0.5
            return (
                {"mode": "mean", "level": overall_mean, "resid_std": resid_std,
                 "seasonal": [1.0] * 12, "slope": 0.0, "n": n},
                None,
            )

        # Seasonal index per calendar month (ratio to overall mean).
        seasonal = np.ones(12)
        for m in range(1, 13):
            vals = qty[months == m]
            if len(vals) and overall_mean > 0:
                seasonal[m - 1] = float(np.mean(vals) / overall_mean)
        # De-seasonalise, fit linear trend.
        deseason = qty / np.clip(seasonal[months - 1], 1e-6, None)
        t = np.arange(n)
        slope, intercept = np.polyfit(t, deseason, 1)
        fitted = (intercept + slope * t) * seasonal[months - 1]
        resid = qty - fitted
        resid_std = float(np.std(resid))
        mae = float(np.mean(np.abs(resid)))
        return (
            {"mode": "seasonal", "intercept": float(intercept), "slope": float(slope),
             "seasonal": [float(s) for s in seasonal], "resid_std": resid_std, "n": n},
            mae,
        )

    def forecast(
        self, region_id: str, variety_id: str, start_month: date, horizon: int = 12
    ) -> list[DemandPoint]:
        params = self._segments.get((region_id, variety_id))
        if params is None:
            return []
        z = 1.2816  # ~80% interval
        points: list[DemandPoint] = []
        for h in range(horizon):
            month = _add_months(start_month, h)
            seasonal = params["seasonal"][month.month - 1]
            if params["mode"] == "seasonal":
                base = params["intercept"] + params["slope"] * (params["n"] + h)
                point = max(base * seasonal, 0.0)
            else:
                point = max(params["level"] * seasonal, 0.0)
            band = z * params["resid_std"]
            # Confidence shrinks with noise-to-signal and grows with history.
            rel_noise = params["resid_std"] / (point + 1e-6)
            hist_factor = min(params["n"] / 24.0, 1.0)
            confidence = float(np.clip((1.0 - rel_noise) * hist_factor, 0.05, 0.95))
            points.append(
                DemandPoint(
                    period_month=month,
                    forecast_qty_kg=round(point, 2),
                    pi_low_kg=round(max(point - band, 0.0), 2),
                    pi_high_kg=round(point + band, 2),
                    confidence=round(confidence, 3),
                    seasonal_component=round(seasonal, 4),
                )
            )
        return points
