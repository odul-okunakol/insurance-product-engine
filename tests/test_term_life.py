import math

import pytest

from conftest import modified
from product_engine import life, quote
from product_engine.engine import _loadings, _mortality
from product_engine.mortality import ConstantMortality


def codes(result):
    return {e["code"] for e in result["errors"]}


def base_request(**overrides):
    request = {"age": 35, "term_years": 20, "sum_insured": 100_000}
    request.update(overrides)
    return request


# ---------------------------------------------------------------- REQ-TL-01
def test_valid_request_is_accepted(term_life):
    """REQ-TL-01: a request inside all limits is accepted."""
    result = quote(term_life, base_request())
    assert result["eligible"] and result["errors"] == []


@pytest.mark.parametrize("overrides, expected_code", [
    ({"age": 17, "term_years": 10}, "ELIG_ENTRY_AGE"),
    ({"age": 66, "term_years": 5}, "ELIG_ENTRY_AGE"),
    ({"term_years": 4}, "ELIG_TERM"),
    ({"term_years": 41}, "ELIG_TERM"),
    ({"age": 60, "term_years": 20}, "ELIG_EXPIRY_AGE"),
    ({"sum_insured": 9_999}, "ELIG_SUM_INSURED"),
    ({"sum_insured": 1_000_001}, "ELIG_SUM_INSURED"),
    ({"payment_mode": "weekly"}, "ELIG_PAYMENT_MODE"),
])
def test_eligibility_violations_have_specific_codes(term_life, overrides, expected_code):
    """REQ-TL-01: each violation is reported with its own error code."""
    result = quote(term_life, base_request(**overrides))
    assert not result["eligible"]
    assert expected_code in codes(result)


def test_boundary_values_are_accepted(term_life):
    """REQ-TL-01: the limits themselves are inside the allowed range."""
    assert quote(term_life, {"age": 18, "term_years": 5, "sum_insured": 10_000})["eligible"]
    assert quote(term_life, {"age": 35, "term_years": 40, "sum_insured": 1_000_000})["eligible"]
    assert quote(term_life, {"age": 65, "term_years": 10, "sum_insured": 50_000})["eligible"]


def test_missing_inputs_are_reported(term_life):
    """REQ-TL-01: missing inputs are reported with MISSING_INPUT."""
    result = quote(term_life, {"age": 35})
    assert codes(result) == {"MISSING_INPUT"}
    assert len(result["errors"]) == 2


# ---------------------------------------------------------------- REQ-TL-02
def test_net_premium_satisfies_equivalence_principle(term_life):
    """REQ-TL-02: PV(net premiums) == PV(death benefits) at inception.

    The present values are computed here with an independent loop over the policy years.
    """
    mort, i = _mortality(term_life.spec), term_life.spec["basis"]["interest_rate"]
    age, n = 35, 20
    net_rate = life.net_premium_rate(mort, i, age, n)

    alive, pv_premiums, pv_benefits = 1.0, 0.0, 0.0
    for k in range(n):
        q = mort.q(age + k)
        pv_premiums += net_rate * alive / (1 + i) ** k
        pv_benefits += alive * q / (1 + i) ** (k + 1)
        alive *= 1 - q
    assert pv_premiums == pytest.approx(pv_benefits, rel=1e-12)


# ---------------------------------------------------------------- REQ-TL-03
@pytest.mark.parametrize("q, n", [(0.01, 2), (0.01, 10), (0.003, 25), (0.05, 7)])
def test_zero_interest_constant_mortality_gives_premium_equal_to_q(q, n):
    """REQ-TL-03: with i = 0 and constant q, the net annual premium rate is q."""
    assert life.net_premium_rate(ConstantMortality(q), 0.0, 40, n) == pytest.approx(q, rel=1e-12)


def test_two_year_hand_calculation():
    """REQ-TL-03: q = 0.01, i = 0, n = 2: A = 0.01 + 0.99*0.01 = 0.0199, a = 1 + 0.99 = 1.99."""
    mort = ConstantMortality(0.01)
    assert life.term_insurance_apv(mort, 0.0, 40, 2) == pytest.approx(0.0199)
    assert life.annuity_due(mort, 0.0, 40, 2) == pytest.approx(1.99)


# ---------------------------------------------------------------- REQ-TL-04
def test_gross_premium_matches_formula(term_life):
    """REQ-TL-04: the quoted gross premium equals the closed formula, computed independently."""
    spec = term_life.spec
    mort, i = _mortality(spec), spec["basis"]["interest_rate"]
    alpha = spec["loadings"]["acquisition_pct_of_sum_insured"]
    gamma = spec["loadings"]["admin_pct_of_sum_insured_per_year"]
    beta = spec["loadings"]["premium_proportional"]
    age, n, s = 35, 20, 100_000

    v = 1 / (1 + i)
    A = a = 0.0
    alive = 1.0
    for k in range(n):
        q = mort.q(age + k)
        A += v ** (k + 1) * alive * q
        a += v ** k * alive
        alive *= 1 - q
    expected = s * (A + alpha + gamma * a) / ((1 - beta) * a)

    result = quote(term_life, base_request(age=age, term_years=n, sum_insured=s))
    assert result["gross_annual_premium"] == pytest.approx(expected, abs=0.005)


def test_premium_is_proportional_to_sum_insured(term_life):
    """REQ-TL-04: doubling the sum insured doubles the premium."""
    p1 = quote(term_life, base_request(sum_insured=100_000))["gross_annual_premium"]
    p2 = quote(term_life, base_request(sum_insured=200_000))["gross_annual_premium"]
    assert p2 == pytest.approx(2 * p1, abs=0.01)


def test_gross_premium_exceeds_net_premium(term_life):
    """REQ-TL-04: loadings are positive, so gross > net."""
    result = quote(term_life, base_request())
    assert result["gross_annual_premium"] > result["net_annual_premium"] > 0


# ---------------------------------------------------------------- REQ-TL-05
def test_premium_increases_with_entry_age(term_life):
    """REQ-TL-05: for a 10-year term, the premium rises with every year of entry age."""
    premiums = [quote(term_life, {"age": a, "term_years": 10, "sum_insured": 100_000})["gross_annual_premium"]
                for a in range(18, 66)]
    assert all(later > earlier for earlier, later in zip(premiums, premiums[1:]))


# ---------------------------------------------------------------- REQ-TL-06
@pytest.mark.parametrize("mode, per_year, surcharge", [("annual", 1, 1.00), ("semiannual", 2, 1.02), ("monthly", 12, 1.05)])
def test_payment_mode_instalments(term_life, mode, per_year, surcharge):
    """REQ-TL-06: instalment = annual gross premium x surcharge / instalments per year."""
    result = quote(term_life, base_request(payment_mode=mode))
    assert result["instalments_per_year"] == per_year
    assert result["instalment"] == pytest.approx(result["gross_annual_premium"] * surcharge / per_year, abs=0.01)
    assert result["total_annual_payable"] == pytest.approx(result["instalment"] * per_year)


# ---------------------------------------------------------------- REQ-TL-07
def test_net_reserve_is_zero_at_start_and_end_and_not_negative(term_life):
    """REQ-TL-07: the net prospective reserve starts and ends at zero and stays non-negative."""
    mort, i = _mortality(term_life.spec), term_life.spec["basis"]["interest_rate"]
    age, n = 35, 25
    reserves = [life.net_prospective_reserve(mort, i, age, n, t) for t in range(n + 1)]
    assert reserves[0] == pytest.approx(0.0, abs=1e-12)
    assert reserves[-1] == pytest.approx(0.0, abs=1e-12)
    assert min(reserves) >= -1e-12
    assert max(reserves) > 0


def test_reserve_rejects_invalid_time(term_life):
    """REQ-TL-07: a time outside the policy term is an error, not a silent value."""
    mort, i = _mortality(term_life.spec), term_life.spec["basis"]["interest_rate"]
    with pytest.raises(ValueError):
        life.net_prospective_reserve(mort, i, 35, 20, 21)


# ---------------------------------------------------------------- REQ-TL-08
def test_cashflow_projection_is_consistent_with_gross_premium(term_life):
    """REQ-TL-08: PV(premiums) - PV(expenses) - PV(death benefits) = 0, and PV(death benefits) = S x A."""
    spec = term_life.spec
    mort, i = _mortality(spec), spec["basis"]["interest_rate"]
    age, n, s = 40, 20, 250_000
    rows = life.project_cashflows(mort, i, age, n, s, _loadings(spec))

    pv_premiums = sum(r["pv_premium_income"] for r in rows)
    pv_expenses = sum(r["pv_expenses"] for r in rows)
    pv_benefits = sum(r["pv_death_benefit"] for r in rows)
    assert pv_premiums - pv_expenses - pv_benefits == pytest.approx(0.0, abs=1e-6)
    assert pv_benefits == pytest.approx(s * life.term_insurance_apv(mort, i, age, n), rel=1e-12)
    assert len(rows) == n and rows[0]["in_force_start"] == 1.0
    assert all(math.isfinite(r["premium_income"]) for r in rows)
