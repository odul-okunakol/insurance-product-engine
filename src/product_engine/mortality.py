"""Mortality bases.

The Gompertz-Makeham model is used only to have a smooth, reproducible
mortality assumption for an illustration. It is NOT a real mortality table.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


class Mortality(Protocol):
    def q(self, age: int) -> float:
        """Probability that a life aged `age` dies within one year."""


@dataclass(frozen=True)
class GompertzMakeham:
    """Force of mortality mu(x) = A + B * c**x, constant within each year of age.

    With mu integrated over [x, x+1]:
        q(x) = 1 - exp(-(A + B * c**x * (c - 1) / ln(c)))
    A `multiplier` scales q(x) (prudence margin), capped at 1.
    """
    A: float
    B: float
    c: float
    multiplier: float = 1.0

    def q(self, age: int) -> float:
        integral = self.A + self.B * self.c ** age * (self.c - 1.0) / math.log(self.c)
        return min(1.0, (1.0 - math.exp(-integral)) * self.multiplier)


@dataclass(frozen=True)
class ConstantMortality:
    """The same q at every age. Used for hand-checkable test cases."""
    q_value: float

    def q(self, age: int) -> float:
        return self.q_value
