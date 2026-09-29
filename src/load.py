"""
src/load.py — Raw file loaders with schema validation.

Rules:
- Raw files are NEVER modified.
- Schema validation fails loudly (no silent coercion).
- Returns plain DataFrames with dtypes left as-is for clean.py to handle.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

from src.config import RAW_FILES, REQUIRED_COLUMNS, VALID_CHANNELS, VALID_STATUSES, VALID_SOURCE_SYSTEMS


class SchemaError(RuntimeError):
    """Raised when a CSV does not meet the expected schema."""


def _check_required_columns(df: pd.DataFrame, name: str) -> None:
    required = REQUIRED_COLUMNS.get(name, [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SchemaError(
            f"{name}.csv is missing required columns: {missing}\n"
            f"Found: {list(df.columns)}"
        )


def _load(name: str) -> pd.DataFrame:
    path = RAW_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Raw file not found: {path}")
    df = pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
    _check_required_columns(df, name)
    return df


def load_tickets() -> pd.DataFrame:
    df = _load("tickets")
    # Validate key categoricals
    bad_channel = set(df["channel"].dropna().unique()) - VALID_CHANNELS
    if bad_channel:
        raise SchemaError(f"tickets.channel has unexpected values: {bad_channel}")
    bad_status = set(df["status"].dropna().unique()) - VALID_STATUSES
    if bad_status:
        raise SchemaError(f"tickets.status has unexpected values: {bad_status}")
    bad_source = set(df["source_system"].dropna().unique()) - VALID_SOURCE_SYSTEMS
    if bad_source:
        raise SchemaError(f"tickets.source_system has unexpected values: {bad_source}")
    return df


def load_agents() -> pd.DataFrame:
    return _load("agents")


def load_orders() -> pd.DataFrame:
    return _load("orders")


def load_customers() -> pd.DataFrame:
    return _load("customers")


def load_products() -> pd.DataFrame:
    return _load("products")


def load_all() -> dict[str, pd.DataFrame]:
    """Load all five reference datasets. Fails loudly on schema errors."""
    return {
        "tickets":   load_tickets(),
        "agents":    load_agents(),
        "orders":    load_orders(),
        "customers": load_customers(),
        "products":  load_products(),
    }
