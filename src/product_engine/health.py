"""Hospital daily cash calculations.

Model
-----
* Hospital admissions occur at an annual rate `lam` (per age band).
* Length of stay L (days) is geometric on {1, 2, 3, ...} with mean m:
      P(L = l) = (1 - r) * r**(l - 1),   r = 1 - 1/m,   so   P(L >= k) = r**(k - 1)
* The product pays the daily benefit D for every day in hospital after the first
  `d` days (deductible days), for at most `cap` days per stay.

Paid days per admission:  max(min(L, cap) - d, 0)
Its expectation has a closed form (sum of P(L >= k) for k = d+1 .. cap):

      E[paid days] = (r**d - r**cap) / (1 - r)          for cap > d, else 0

Expected annual benefit = lam * E[paid days] * D
Gross premium = expected benefit * (1 + safety_loading) / (1 - expense_ratio)
"""
from __future__ import annotations


def expected_paid_days(mean_length_of_stay: float, deductible_days: int, max_days_per_stay: int) -> float:
    """Expected number of paid days per hospital stay (closed form)."""
    if mean_length_of_stay <= 1:
        raise ValueError("mean length of stay must be greater than 1 day")
    if deductible_days < 0 or max_days_per_stay < 0:
        raise ValueError("deductible and maximum days must not be negative")
    if max_days_per_stay <= deductible_days:
        return 0.0
    r = 1.0 - 1.0 / mean_length_of_stay
    return (r ** deductible_days - r ** max_days_per_stay) / (1.0 - r)


def expected_paid_days_bruteforce(mean_length_of_stay: float, deductible_days: int,
                                  max_days_per_stay: int, horizon: int = 5000) -> float:
    """Same quantity by summing over the length-of-stay distribution.

    Independent of the closed form; used to cross-check it in the tests.
    """
    r = 1.0 - 1.0 / mean_length_of_stay
    total = 0.0
    for stay in range(1, horizon + 1):
        prob = (1.0 - r) * r ** (stay - 1)
        total += prob * max(min(stay, max_days_per_stay) - deductible_days, 0)
    return total


def annual_expected_benefit(admission_rate: float, mean_length_of_stay: float,
                            deductible_days: int, max_days_per_stay: int, daily_benefit: float) -> float:
    return admission_rate * expected_paid_days(mean_length_of_stay, deductible_days, max_days_per_stay) * daily_benefit


def gross_annual_premium(expected_benefit: float, safety_loading: float, expense_ratio: float) -> float:
    return expected_benefit * (1.0 + safety_loading) / (1.0 - expense_ratio)
