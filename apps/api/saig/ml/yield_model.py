"""Yield prediction: gradient-boosted trees with quantile heads.

sklearn baseline (ADR-0003); XGBoost is a drop-in behind this interface.
Point estimate + 80% prediction interval + a calibrated confidence score.
Features are limited to inputs available for BOTH historical production
records and active crop cycles, so training and scoring stay aligned:
variety agronomic traits + planted area. Soil/weather enrichment is the
documented accuracy upgrade (needs historical weather, deferred).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

YIELD_FEATURES = [
    "yield_potential_kg_ha",
    "maturity_days",
    "drought_tolerance",
    "disease_tolerance",
    "area_ha",
]
LOWER_Q, UPPER_Q = 0.1, 0.9  # 80% prediction interval
MIN_TRAINING_ROWS = 8


@dataclass
class YieldPrediction:
    predicted_yield_kg_ha: float
    pi_low_kg_ha: float
    pi_high_kg_ha: float
    confidence: float
    low_confidence: bool


class YieldModel:
    """Serializable via joblib. Holds three fitted quantile regressors plus
    the imputation medians and feature order captured at fit time."""

    def __init__(self) -> None:
        self._median: GradientBoostingRegressor | None = None
        self._lower: GradientBoostingRegressor | None = None
        self._upper: GradientBoostingRegressor | None = None
        self._feature_medians: dict[str, float] = {}
        self.metrics: dict[str, float] = {}
        self.n_training_rows: int = 0

    # --- training ------------------------------------------------------------

    @staticmethod
    def _prepare(df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()
        for col in YIELD_FEATURES:
            if col not in frame.columns:
                frame[col] = np.nan
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        return frame[YIELD_FEATURES]

    def fit(self, df: pd.DataFrame) -> YieldModel:
        if len(df) < MIN_TRAINING_ROWS:
            raise ValueError(
                f"Need at least {MIN_TRAINING_ROWS} rows to train; got {len(df)}."
            )
        x = self._prepare(df)
        self._feature_medians = {c: float(x[c].median()) for c in YIELD_FEATURES}
        x = x.fillna(self._feature_medians)
        y = pd.to_numeric(df["yield_kg_ha"], errors="coerce").fillna(
            df["yield_kg_ha"].median()
        )

        common = dict(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42)
        self._median = GradientBoostingRegressor(loss="squared_error", **common).fit(x, y)
        self._lower = GradientBoostingRegressor(
            loss="quantile", alpha=LOWER_Q, **common
        ).fit(x, y)
        self._upper = GradientBoostingRegressor(
            loss="quantile", alpha=UPPER_Q, **common
        ).fit(x, y)

        preds = self._median.predict(x)
        residuals = np.abs(y.to_numpy() - preds)
        mae = float(np.mean(residuals))
        mape = float(np.mean(residuals / np.clip(np.abs(y.to_numpy()), 1e-6, None)))
        yv = y.to_numpy()
        in_band = float(
            np.mean((yv >= self._lower.predict(x)) & (yv <= self._upper.predict(x)))
        )
        self.metrics = {"mae": round(mae, 2), "mape": round(mape, 4),
                        "pi_coverage": round(in_band, 3)}
        self.n_training_rows = len(df)
        return self

    # --- scoring -------------------------------------------------------------

    def predict_one(self, features: dict) -> YieldPrediction:
        return self.predict([features])[0]

    def predict(self, rows: list[dict]) -> list[YieldPrediction]:
        if self._median is None:
            raise RuntimeError("Model is not fitted.")
        x = self._prepare(pd.DataFrame(rows)).fillna(self._feature_medians)
        low = np.asarray(self._lower.predict(x), dtype=float)
        mid = np.asarray(self._median.predict(x), dtype=float)
        high = np.asarray(self._upper.predict(x), dtype=float)

        out: list[YieldPrediction] = []
        for lo, m, hi in zip(low, mid, high, strict=True):
            lo, m, hi = float(lo), float(m), float(hi)
            lo, hi = min(lo, m), max(hi, m)  # keep interval well-ordered
            m = max(m, 0.0)
            width = hi - lo
            # Confidence falls as the relative interval widens.
            rel = width / (m + 1e-6)
            confidence = float(np.clip(1.0 - rel / 2.0, 0.05, 0.95))
            out.append(
                YieldPrediction(
                    predicted_yield_kg_ha=round(m, 2),
                    pi_low_kg_ha=round(max(lo, 0.0), 2),
                    pi_high_kg_ha=round(hi, 2),
                    confidence=round(confidence, 3),
                    low_confidence=confidence < 0.4,
                )
            )
        return out
