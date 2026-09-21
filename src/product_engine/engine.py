"""Quote engine: turns a validated product specification and a customer request
into an eligibility decision and a premium breakdown.

Eligibility problems are returned as error codes (not exceptions), so a caller
such as a web front end can show a precise reason for every rejected request.
"""
from __future__ import annotations

from typing import Any

from . import health, life
from .mortality import GompertzMakeham
from .spec import INSTALMENTS_PER_YEAR, Product


def _err(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def _mortality(spec: dict) -> GompertzMakeham:
    m = spec["basis"]["mortality"]
    return GompertzMakeham(A=m["A"], B=m["B"], c=m["c"], multiplier=m["multiplier"])


def _loadings(spec: dict) -> life.Loadings:
    lo = spec["loadings"]
    return life.Loadings(
        alpha=lo["acquisition_pct_of_sum_insured"],
        gamma=lo["admin_pct_of_sum_insured_per_year"],
        beta=lo["premium_proportional"],
    )


def _missing(request: dict, keys: list[str]) -> list[dict]:
    return [_err("MISSING_INPUT", f"input '{k}' is required") for k in keys if k not in request]


def _payment_mode_error(spec: dict, mode: str) -> list[dict]:
    if mode not in spec["payment_modes"]:
        return [_err("ELIG_PAYMENT_MODE",
                     f"payment mode '{mode}' is not offered (available: {sorted(spec['payment_modes'])})")]
    return []


def _instalments(spec: dict, mode: str, annual_gross: float) -> dict:
    surcharge = spec["payment_modes"][mode]
    per_year = INSTALMENTS_PER_YEAR[mode]
    # The customer pays whole cents per instalment, so the annual total is built from the rounded instalment.
    instalment = round(annual_gross * surcharge / per_year, 2)
    return {
        "payment_mode": mode,
        "instalments_per_year": per_year,
        "instalment": instalment,
        "total_annual_payable": round(instalment * per_year, 2),
    }


# ------------------------------------------------------------------ term life
def check_term_life(spec: dict, request: dict) -> list[dict]:
    errors = _missing(request, ["age", "term_years", "sum_insured"])
    if errors:
        return errors
    el = spec["eligibility"]
    age, term, s = request["age"], request["term_years"], request["sum_insured"]
    if not el["entry_age"]["min"] <= age <= el["entry_age"]["max"]:
        errors.append(_err("ELIG_ENTRY_AGE",
                           f"entry age {age} is outside {el['entry_age']['min']}-{el['entry_age']['max']}"))
    if not el["term_years"]["min"] <= term <= el["term_years"]["max"]:
        errors.append(_err("ELIG_TERM",
                           f"term {term} years is outside {el['term_years']['min']}-{el['term_years']['max']}"))
    if age + term > el["max_age_at_expiry"]:
        errors.append(_err("ELIG_EXPIRY_AGE",
                           f"age at expiry {age + term} exceeds {el['max_age_at_expiry']}"))
    if not el["sum_insured"]["min"] <= s <= el["sum_insured"]["max"]:
        errors.append(_err("ELIG_SUM_INSURED",
                           f"sum insured {s} is outside {el['sum_insured']['min']}-{el['sum_insured']['max']}"))
    errors += _payment_mode_error(spec, request.get("payment_mode", "annual"))
    return errors


def quote_term_life(product: Product, request: dict) -> dict[str, Any]:
    spec = product.spec
    errors = check_term_life(spec, request)
    if errors:
        return {"product": product.name, "eligible": False, "errors": errors}

    age, term, s = request["age"], request["term_years"], request["sum_insured"]
    mode = request.get("payment_mode", "annual")
    mort, i = _mortality(spec), spec["basis"]["interest_rate"]
    net = life.net_premium_rate(mort, i, age, term) * s
    gross = life.gross_premium_rate(mort, i, age, term, _loadings(spec)) * s
    return {
        "product": product.name,
        "version": product.version,
        "currency": product.currency,
        "eligible": True,
        "errors": [],
        "net_annual_premium": round(net, 2),
        "gross_annual_premium": round(gross, 2),
        **_instalments(spec, mode, gross),
    }


# -------------------------------------------------------------- hospital cash
def _age_band(spec: dict, age: int) -> dict:
    for band in spec["basis"]["age_bands"]:
        if band["from"] <= age <= band["to"]:
            return band
    raise ValueError(f"no age band for age {age}")


def check_hospital_cash(spec: dict, request: dict) -> list[dict]:
    errors = _missing(request, ["age", "daily_benefit", "deductible_days", "max_days_per_stay"])
    if errors:
        return errors
    el = spec["eligibility"]
    if not el["age"]["min"] <= request["age"] <= el["age"]["max"]:
        errors.append(_err("ELIG_AGE", f"age {request['age']} is outside {el['age']['min']}-{el['age']['max']}"))
    if not el["daily_benefit"]["min"] <= request["daily_benefit"] <= el["daily_benefit"]["max"]:
        errors.append(_err("ELIG_DAILY_BENEFIT",
                           f"daily benefit {request['daily_benefit']} is outside "
                           f"{el['daily_benefit']['min']}-{el['daily_benefit']['max']}"))
    if request["deductible_days"] not in el["deductible_days_allowed"]:
        errors.append(_err("ELIG_DEDUCTIBLE",
                           f"deductible {request['deductible_days']} days not offered "
                           f"(allowed: {el['deductible_days_allowed']})"))
    if request["max_days_per_stay"] not in el["max_days_per_stay_allowed"]:
        errors.append(_err("ELIG_MAX_DAYS",
                           f"maximum {request['max_days_per_stay']} days per stay not offered "
                           f"(allowed: {el['max_days_per_stay_allowed']})"))
    errors += _payment_mode_error(spec, request.get("payment_mode", "annual"))
    return errors


def quote_hospital_cash(product: Product, request: dict) -> dict[str, Any]:
    spec = product.spec
    errors = check_hospital_cash(spec, request)
    if errors:
        return {"product": product.name, "eligible": False, "errors": errors}

    mode = request.get("payment_mode", "annual")
    band = _age_band(spec, request["age"])
    benefit = health.annual_expected_benefit(
        band["admission_rate"], band["mean_length_of_stay_days"],
        request["deductible_days"], request["max_days_per_stay"], request["daily_benefit"],
    )
    gross = health.gross_annual_premium(benefit, spec["basis"]["safety_loading"], spec["basis"]["expense_ratio"])
    return {
        "product": product.name,
        "version": product.version,
        "currency": product.currency,
        "eligible": True,
        "errors": [],
        "expected_annual_benefit": round(benefit, 2),
        "gross_annual_premium": round(gross, 2),
        **_instalments(spec, mode, gross),
    }


# ------------------------------------------------------------------- dispatch
def quote(product: Product, request: dict) -> dict[str, Any]:
    """Price a request against a product specification."""
    if product.type == "term_life":
        return quote_term_life(product, request)
    if product.type == "hospital_cash":
        return quote_hospital_cash(product, request)
    raise ValueError(f"unsupported product type: {product.type}")
