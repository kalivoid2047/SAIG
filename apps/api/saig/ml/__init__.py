"""SAIG machine-learning core (ADR-0003).

Pure, framework-free: feature engineering, model wrappers and an artifact
registry. No FastAPI, no DB session — takes DataFrames/dicts, returns
predictions. Kept extractable to a separate service without a rewrite.
"""
