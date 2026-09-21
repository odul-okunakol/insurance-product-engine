"""Load and validate product specifications (YAML).

The engine never contains product parameters. Everything a product needs is in
its specification file, and a specification is checked here before it is used,
so that a broken configuration fails with a message that names the field.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PRODUCT_TYPES = ("term_life", "hospital_cash")
INSTALMENTS_PER_YEAR = {"annual": 1, "semiannual": 2, "monthly": 12}


class SpecError(ValueError):
    """A product specification is missing a field or has an invalid value."""


@dataclass(frozen=True)
class Product:
    name: str
    type: str
    version: str
    currency: str
    spec: dict[str, Any]


# ----------------------------------------------------------------- helpers
def _get(d: dict, path: str, kind: type | tuple[type, ...]):
    """Fetch a nested value ('a.b.c'), checking that it exists and has the right type."""
    cur: Any = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            raise SpecError(f"missing field: {path}")
        cur = cur[key]
    if isinstance(cur, bool) or not isinstance(cur, kind):
        raise SpecError(f"field {path}: expected {kind}, got {type(cur).__name__}")
    return cur


def _number_between(d: dict, path: str, lo: float, hi: float) -> float:
    value = _get(d, path, (int, float))
    if not lo <= value <= hi:
        raise SpecError(f"field {path}: {value} is outside the allowed range [{lo}, {hi}]")
    return float(value)


def _range(d: dict, path: str) -> tuple[float, float]:
    lo = _get(d, f"{path}.min", (int, float))
    hi = _get(d, f"{path}.max", (int, float))
    if lo > hi:
        raise SpecError(f"field {path}: min ({lo}) is greater than max ({hi})")
    return lo, hi


def _payment_modes(d: dict) -> None:
    modes = _get(d, "payment_modes", dict)
    if not modes:
        raise SpecError("field payment_modes: at least one payment mode is required")
    for mode in modes:
        if mode not in INSTALMENTS_PER_YEAR:
            raise SpecError(f"field payment_modes: unknown mode '{mode}'")
        _number_between(d, f"payment_modes.{mode}", 1.0, 2.0)


# --------------------------------------------------------- per-type checks
def _validate_term_life(d: dict) -> None:
    _range(d, "eligibility.entry_age")
    _range(d, "eligibility.term_years")
    _range(d, "eligibility.sum_insured")
    _get(d, "eligibility.max_age_at_expiry", int)
    _number_between(d, "basis.interest_rate", 0.0, 0.10)
    if _get(d, "basis.mortality.model", str) != "gompertz_makeham":
        raise SpecError("field basis.mortality.model: only 'gompertz_makeham' is supported")
    _number_between(d, "basis.mortality.A", 0.0, 0.01)
    _number_between(d, "basis.mortality.B", 0.0, 0.001)
    _number_between(d, "basis.mortality.c", 1.0001, 1.5)
    _number_between(d, "basis.mortality.multiplier", 0.5, 3.0)
    _number_between(d, "loadings.acquisition_pct_of_sum_insured", 0.0, 0.20)
    _number_between(d, "loadings.admin_pct_of_sum_insured_per_year", 0.0, 0.05)
    _number_between(d, "loadings.premium_proportional", 0.0, 0.50)
    _payment_modes(d)


def _validate_hospital_cash(d: dict) -> None:
    age_lo, age_hi = _range(d, "eligibility.age")
    _range(d, "eligibility.daily_benefit")
    for key in ("deductible_days_allowed", "max_days_per_stay_allowed"):
        values = _get(d, f"eligibility.{key}", list)
        if not values or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values):
            raise SpecError(f"field eligibility.{key}: expected a non-empty list of non-negative integers")

    bands = _get(d, "basis.age_bands", list)
    if not bands:
        raise SpecError("field basis.age_bands: at least one age band is required")
    previous_to = None
    for i, band in enumerate(bands):
        prefix = f"basis.age_bands[{i}]"
        for key in ("from", "to", "admission_rate", "mean_length_of_stay_days"):
            if not isinstance(band, dict) or key not in band:
                raise SpecError(f"missing field: {prefix}.{key}")
        if band["from"] > band["to"]:
            raise SpecError(f"field {prefix}: 'from' is greater than 'to'")
        if previous_to is not None and band["from"] != previous_to + 1:
            raise SpecError(f"field {prefix}: age bands must be contiguous and sorted")
        if not 0 < band["admission_rate"] <= 1:
            raise SpecError(f"field {prefix}.admission_rate: must be in (0, 1]")
        if band["mean_length_of_stay_days"] <= 1:
            raise SpecError(f"field {prefix}.mean_length_of_stay_days: must be greater than 1")
        previous_to = band["to"]
    if bands[0]["from"] > age_lo or bands[-1]["to"] < age_hi:
        raise SpecError("field basis.age_bands: bands do not cover the eligible age range")

    _number_between(d, "basis.safety_loading", 0.0, 1.0)
    _number_between(d, "basis.expense_ratio", 0.0, 0.60)
    _payment_modes(d)


_VALIDATORS = {"term_life": _validate_term_life, "hospital_cash": _validate_hospital_cash}


# ------------------------------------------------------------------ public
def validate_spec(raw: dict) -> Product:
    """Validate a parsed specification and wrap it in a Product."""
    if not isinstance(raw, dict):
        raise SpecError("specification must be a mapping")
    name = _get(raw, "product", str)
    ptype = _get(raw, "type", str)
    if ptype not in PRODUCT_TYPES:
        raise SpecError(f"field type: unknown product type '{ptype}' (expected one of {PRODUCT_TYPES})")
    version = _get(raw, "version", str)
    currency = _get(raw, "currency", str)
    _VALIDATORS[ptype](raw)
    return Product(name=name, type=ptype, version=version, currency=currency, spec=raw)


def load_product(path: str | Path) -> Product:
    """Read a YAML product specification from disk and validate it."""
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return validate_spec(raw)
