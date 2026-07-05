"""Artifact persistence for trained models.

Dev: local `artifacts/` directory (git-ignored). Production: object storage,
behind the same interface (callers never touch paths). A model is any object
joblib can pickle — the yield/demand wrappers below.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import joblib

from saig.shared.config import API_DIR

ARTIFACT_ROOT = API_DIR / "artifacts"


def _resolve(artifact_key: str) -> Path:
    return ARTIFACT_ROOT / artifact_key


def save_artifact(model: Any, model_name: str) -> str:
    """Persist a model, returning an opaque artifact key."""
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    key = f"{model_name}/{uuid.uuid4().hex}.joblib"
    path = _resolve(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return key


def load_artifact(artifact_key: str) -> Any:
    path = _resolve(artifact_key)
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {artifact_key}")
    return joblib.load(path)


def artifact_exists(artifact_key: str) -> bool:
    return _resolve(artifact_key).exists()
