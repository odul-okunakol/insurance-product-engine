import copy
from pathlib import Path

import pytest

from product_engine import load_product, validate_spec

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def term_life():
    return load_product(ROOT / "products" / "term_life.yaml")


@pytest.fixture(scope="session")
def hospital_cash():
    return load_product(ROOT / "products" / "hospital_cash.yaml")


def modified(product, path: str, value):
    """A copy of a product with one specification value changed (path like 'basis.interest_rate')."""
    raw = copy.deepcopy(product.spec)
    cur = raw
    keys = path.split(".")
    for key in keys[:-1]:
        cur = cur[key]
    cur[keys[-1]] = value
    return validate_spec(raw)
