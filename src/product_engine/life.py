"""Term life calculations (per unit of sum insured unless stated otherwise).

Notation (discrete model, annual premiums paid at the start of each year while
the policy is in force, death benefit paid at the end of the year of death):

    kpx      probability that a life aged x survives k years
    v        1 / (1 + i)
    A        actuarial present value (APV) of 1 payable at the end of the year
             of death, if death occurs within n years:  sum_k v^(k+1) * kpx * q(x+k)
    a_due    APV of 1 paid at the start of each year while alive, for n years:
             sum_k v^k * kpx

Net premium (equivalence principle):  P = S * A / a_due
Gross premium with expense loadings:

    G * a_due = S*A + alpha*S + gamma*S*a_due + beta*G*a_due
    =>  G = (S*A + alpha*S + gamma*S*a_due) / ((1 - beta) * a_due)
"""
from __future__ import annotations

from dataclasses import dataclass

from .mortality import Mortality


def survival_probabilities(mort: Mortality, age: int, n: int) -> list[float]:
    """[0px, 1px, ..., npx] as a list of length n + 1."""
    probs = [1.0]
    for k in range(n):
        probs.append(probs[-1] * (1.0 - mort.q(age + k)))
    return probs


def term_insurance_apv(mort: Mortality, i: float, age: int, n: int) -> float:
    """APV of a unit death benefit over an n-year term."""
    if n <= 0:
        return 0.0
    v = 1.0 / (1.0 + i)
    kpx = survival_probabilities(mort, age, n)
    return sum(v ** (k + 1) * kpx[k] * mort.q(age + k) for k in range(n))


def annuity_due(mort: Mortality, i: float, age: int, n: int) -> float:
    """APV of a unit premium paid annually in advance, for at most n years."""
    if n <= 0:
        return 0.0
    v = 1.0 / (1.0 + i)
    kpx = survival_probabilities(mort, age, n)
    return sum(v ** k * kpx[k] for k in range(n))


def net_premium_rate(mort: Mortality, i: float, age: int, n: int) -> float:
    """Net annual premium per unit of sum insured."""
    return term_insurance_apv(mort, i, age, n) / annuity_due(mort, i, age, n)


@dataclass(frozen=True)
class Loadings:
    alpha: float   # acquisition, share of sum insured, once
    gamma: float   # administration, share of sum insured, per premium year
    beta: float    # share of the gross premium


def gross_premium_rate(mort: Mortality, i: float, age: int, n: int, loadings: Loadings) -> float:
    """Gross annual premium per unit of sum insured."""
    A = term_insurance_apv(mort, i, age, n)
    a = annuity_due(mort, i, age, n)
    return (A + loadings.alpha + loadings.gamma * a) / ((1.0 - loadings.beta) * a)


def net_prospective_reserve(mort: Mortality, i: float, age: int, n: int, t: int) -> float:
    """Net premium reserve per unit of sum insured at integer time t, policy in force.

    tV = A(x+t, n-t) - P * a_due(x+t, n-t), with P the net premium set at inception.
    """
    if not 0 <= t <= n:
        raise ValueError("t must be between 0 and n")
    P = net_premium_rate(mort, i, age, n)
    return term_insurance_apv(mort, i, age + t, n - t) - P * annuity_due(mort, i, age + t, n - t)


def project_cashflows(mort: Mortality, i: float, age: int, n: int, sum_insured: float,
                      loadings: Loadings) -> list[dict]:
    """Expected cash flows per policy sold, year by year (annual premium mode).

    Premiums and expenses fall at the start of each year, death benefits at the
    end of it. Discounted with the technical interest rate `i`.
    """
    v = 1.0 / (1.0 + i)
    G = gross_premium_rate(mort, i, age, n, loadings) * sum_insured
    kpx = survival_probabilities(mort, age, n)
    rows = []
    for k in range(n):
        q = mort.q(age + k)
        premium = G * kpx[k]
        expenses = (loadings.gamma * sum_insured + loadings.beta * G) * kpx[k]
        if k == 0:
            expenses += loadings.alpha * sum_insured
        deaths = sum_insured * kpx[k] * q
        rows.append({
            "year": k + 1,
            "attained_age": age + k,
            "in_force_start": kpx[k],
            "premium_income": premium,
            "expenses": expenses,
            "death_benefit": deaths,
            "pv_premium_income": premium * v ** k,
            "pv_expenses": expenses * v ** k,
            "pv_death_benefit": deaths * v ** (k + 1),
        })
    return rows
