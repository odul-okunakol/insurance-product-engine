import copy

import pytest
import yaml

from conftest import ROOT, modified
from product_engine import SpecError, load_product, quote, validate_spec
from product_engine.cli import main


def raw(product):
    return copy.deepcopy(product.spec)


# ---------------------------------------------------------------- REQ-SP-01
def test_missing_field_is_rejected_and_named(term_life):
    """REQ-SP-01"""
    spec = raw(term_life)
    del spec["basis"]["interest_rate"]
    with pytest.raises(SpecError, match="basis.interest_rate"):
        validate_spec(spec)


def test_out_of_range_value_is_rejected_and_named(term_life):
    """REQ-SP-01"""
    spec = raw(term_life)
    spec["basis"]["interest_rate"] = -0.02
    with pytest.raises(SpecError, match="basis.interest_rate"):
        validate_spec(spec)


def test_wrong_type_is_rejected_and_named(term_life):
    """REQ-SP-01"""
    spec = raw(term_life)
    spec["loadings"]["premium_proportional"] = "five percent"
    with pytest.raises(SpecError, match="loadings.premium_proportional"):
        validate_spec(spec)


def test_unknown_product_type_is_rejected(term_life):
    """REQ-SP-01"""
    spec = raw(term_life)
    spec["type"] = "whole_life"
    with pytest.raises(SpecError, match="type"):
        validate_spec(spec)


def test_unknown_payment_mode_is_rejected(term_life):
    """REQ-SP-01"""
    spec = raw(term_life)
    spec["payment_modes"]["weekly"] = 1.10
    with pytest.raises(SpecError, match="payment_modes"):
        validate_spec(spec)


def test_non_contiguous_age_bands_are_rejected(hospital_cash):
    """REQ-SP-01"""
    spec = raw(hospital_cash)
    spec["basis"]["age_bands"][1]["from"] = 32
    with pytest.raises(SpecError, match=r"age_bands\[1\]"):
        validate_spec(spec)


def test_age_bands_must_cover_eligible_ages(hospital_cash):
    """REQ-SP-01"""
    spec = raw(hospital_cash)
    spec["basis"]["age_bands"].pop()
    with pytest.raises(SpecError, match="age_bands"):
        validate_spec(spec)


def test_inverted_range_is_rejected(term_life):
    """REQ-SP-01"""
    spec = raw(term_life)
    spec["eligibility"]["entry_age"] = {"min": 65, "max": 18}
    with pytest.raises(SpecError, match="eligibility.entry_age"):
        validate_spec(spec)


# ---------------------------------------------------------------- REQ-SP-02
def test_lower_interest_rate_raises_premium_without_code_change(term_life):
    """REQ-SP-02"""
    request = {"age": 35, "term_years": 20, "sum_insured": 100_000}
    base = quote(term_life, request)["gross_annual_premium"]
    lower = quote(modified(term_life, "basis.interest_rate", 0.0), request)["gross_annual_premium"]
    assert lower > base


def test_higher_mortality_multiplier_raises_premium(term_life):
    """REQ-SP-02"""
    request = {"age": 35, "term_years": 20, "sum_insured": 100_000}
    base = quote(term_life, request)["net_annual_premium"]
    higher = quote(modified(term_life, "basis.mortality.multiplier", 1.30), request)["net_annual_premium"]
    assert higher == pytest.approx(base * 1.30 / 1.10, rel=0.02)


def test_changed_eligibility_limit_changes_the_decision(term_life):
    """REQ-SP-02"""
    request = {"age": 60, "term_years": 20, "sum_insured": 100_000}
    assert not quote(term_life, request)["eligible"]
    relaxed = modified(term_life, "eligibility.max_age_at_expiry", 80)
    assert quote(relaxed, request)["eligible"]


def test_higher_expense_ratio_raises_health_premium(hospital_cash):
    """REQ-SP-02"""
    request = {"age": 45, "daily_benefit": 50, "deductible_days": 3, "max_days_per_stay": 60}
    base = quote(hospital_cash, request)["gross_annual_premium"]
    higher = quote(modified(hospital_cash, "basis.expense_ratio", 0.40), request)["gross_annual_premium"]
    assert higher == pytest.approx(base * 0.75 / 0.60, abs=0.01)


# ---------------------------------------------------------------- REQ-SP-03
@pytest.mark.parametrize("name", ["term_life.yaml", "hospital_cash.yaml"])
def test_shipped_specifications_load(name):
    """REQ-SP-03"""
    product = load_product(ROOT / "products" / name)
    assert product.version and product.currency == "EUR"


def test_cli_validate_reports_valid_spec(capsys):
    """REQ-SP-03"""
    assert main(["validate", str(ROOT / "products" / "term_life.yaml")]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_validate_reports_invalid_spec(tmp_path, term_life, capsys):
    """REQ-SP-03"""
    spec = raw(term_life)
    del spec["eligibility"]
    path = tmp_path / "broken.yaml"
    path.write_text(yaml.safe_dump(spec))
    assert main(["validate", str(path)]) == 2
    assert "eligibility" in capsys.readouterr().err


def test_cli_quote_exit_codes(capsys):
    """REQ-SP-03: exit code 0 for an accepted request, 1 for a rejected one."""
    spec = str(ROOT / "products" / "term_life.yaml")
    assert main(["quote", spec, "--age", "35", "--term", "20", "--sum-insured", "100000"]) == 0
    assert main(["quote", spec, "--age", "70", "--term", "20", "--sum-insured", "100000"]) == 1
    capsys.readouterr()
