"""Specification-driven quote engine for term life and hospital daily cash products.

Illustrative project: all assumptions are invented and no real insurer, tariff or mortality table is used.
"""
from .engine import quote
from .spec import Product, SpecError, load_product, validate_spec

__all__ = ["quote", "Product", "SpecError", "load_product", "validate_spec"]
