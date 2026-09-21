import pytest

from product_engine import health, quote


def codes(result):
    return {e["code"] for e in result["errors"]}


def base_request(**overrides):
    request = {"age": 45, "daily_benefit": 50, "deductible_days": 3, "max_days_per_stay": 60}
    request.update(overrides)
    return request


# ---------------------------------------------------------------- REQ-HC-01
def test_valid_request_is_accepted(hospital_cash):
    """REQ-HC-01: a request inside all limits is accepted."""
    assert quote(hospital_cash, base_request())["eligible"]


@pytest.mark.parametrize("overrides, expected_code", [
    ({"age": 17}, "ELIG_AGE"),
    ({"age": 65}, "ELIG_AGE"),
    ({"daily_benefit": 5}, "ELIG_DAILY_BENEFIT"),
    ({"daily_benefit": 250}, "ELIG_DAILY_BENEFIT"),
    ({"deductible_days": 5}, "ELIG_DEDUCTIBLE"),
    ({"max_days_per_stay": 45}, "ELIG_MAX_DAYS"),
    ({"payment_mode": "weekly"}, "ELIG_PAYMENT_MODE"),
])
def test_eligibility_violations_have_specific_codes(hospital_cash, overrides, expected_code):
    """REQ-HC-01: each violation is reported with its own error code."""
    result = quote(hospital_cash, base_request(**overrides))
    assert not result["eligible"]
    assert expected_code in codes(result)


def test_missing_inputs_are_reported(hospital_cash):
    """REQ-HC-01: missing inputs are reported with MISSING_INPUT."""
    result = quote(hospital_cash, {"age": 45})
    assert codes(result) == {"MISSING_INPUT"}


# ---------------------------------------------------------------- REQ-HC-02
@pytest.mark.parametrize("mean, deductible, cap", [
    (4.5, 0, 30), (6.0, 3, 60), (8.0, 7, 90), (5.0, 3, 30), (6.0, 0, 90), (7.0, 7, 30),
])
def test_closed_form_matches_bruteforce(mean, deductible, cap):
    """REQ-HC-02: closed form == independent sum over the length-of-stay distribution."""
    assert health.expected_paid_days(mean, deductible, cap) == pytest.approx(
        health.expected_paid_days_bruteforce(mean, deductible, cap), rel=1e-9)


@pytest.mark.parametrize("mean", [2.0, 4.5, 8.0])
def test_no_deductible_and_no_cap_gives_mean_length_of_stay(mean):
    """REQ-HC-02: without deductible and cap, the expected paid days per stay are the mean stay."""
    assert health.expected_paid_days(mean, 0, 100_000) == pytest.approx(mean, rel=1e-9)


def test_cap_not_above_deductible_pays_nothing():
    """REQ-HC-02: if the cap is not above the deductible, no day is ever paid."""
    assert health.expected_paid_days(6.0, 7, 7) == 0.0


def test_invalid_mean_length_of_stay_is_rejected():
    """REQ-HC-02: a mean stay of one day or less is not a valid geometric model."""
    with pytest.raises(ValueError):
        health.expected_paid_days(1.0, 0, 30)


# ---------------------------------------------------------------- REQ-HC-03
def test_higher_deductible_lowers_premium(hospital_cash):
    """REQ-HC-03"""
    premiums = [quote(hospital_cash, base_request(deductible_days=d))["gross_annual_premium"] for d in (0, 3, 7)]
    assert premiums[0] > premiums[1] > premiums[2]


def test_higher_maximum_days_raises_premium(hospital_cash):
    """REQ-HC-03: checked at age 62 (mean stay 8 days), where the difference between the caps is above one cent."""
    premiums = [quote(hospital_cash, base_request(age=62, max_days_per_stay=c))["gross_annual_premium"]
                for c in (30, 60, 90)]
    assert premiums[0] < premiums[1] < premiums[2]


def test_higher_maximum_days_never_lowers_premium_at_any_age(hospital_cash):
    """REQ-HC-03: at every age the premium does not fall when the maximum number of days rises."""
    for age in range(18, 65):
        premiums = [quote(hospital_cash, base_request(age=age, max_days_per_stay=c))["gross_annual_premium"]
                    for c in (30, 60, 90)]
        assert premiums[0] <= premiums[1] <= premiums[2]


def test_premium_is_proportional_to_daily_benefit(hospital_cash):
    """REQ-HC-03"""
    p50 = quote(hospital_cash, base_request(daily_benefit=50))["gross_annual_premium"]
    p100 = quote(hospital_cash, base_request(daily_benefit=100))["gross_annual_premium"]
    assert p100 == pytest.approx(2 * p50, abs=0.01)


# ---------------------------------------------------------------- REQ-HC-04
def test_fixed_example_matches_hand_calculation(hospital_cash):
    """REQ-HC-04: age 45 (rate 0.085, mean stay 6 days), 3 deductible days, 60-day cap, 50 EUR per day.

    r = 5/6.  E[paid days] = 6 * ((5/6)^3 - (5/6)^60) = 3.4721...
    Expected benefit = 0.085 * 3.4721 * 50 = 14.756...
    Premium = 14.756 * 1.10 / 0.75 = 21.64 (safety loading 10 %, expense ratio 25 %).
    """
    result = quote(hospital_cash, base_request())
    assert result["expected_annual_benefit"] == pytest.approx(14.76, abs=0.01)
    assert result["gross_annual_premium"] == pytest.approx(21.64, abs=0.01)


# ---------------------------------------------------------------- REQ-HC-05
def test_premium_increases_with_age_band(hospital_cash):
    """REQ-HC-05: one age in each of the five bands, premiums strictly increasing."""
    premiums = [quote(hospital_cash, base_request(age=a))["gross_annual_premium"] for a in (25, 35, 45, 55, 62)]
    assert all(later > earlier for earlier, later in zip(premiums, premiums[1:]))


def test_premium_is_constant_within_an_age_band(hospital_cash):
    """REQ-HC-05: ages 40 and 49 are in the same band and get the same premium."""
    p40 = quote(hospital_cash, base_request(age=40))["gross_annual_premium"]
    p49 = quote(hospital_cash, base_request(age=49))["gross_annual_premium"]
    assert p40 == p49
