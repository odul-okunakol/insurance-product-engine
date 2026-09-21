"""Command line interface.

    python -m product_engine validate products/term_life.yaml
    python -m product_engine quote products/term_life.yaml --age 35 --term 20 --sum-insured 100000
    python -m product_engine quote products/hospital_cash.yaml --age 45 --daily-benefit 50 \
        --deductible-days 3 --max-days 60 --mode monthly
    python -m product_engine cashflows products/term_life.yaml --age 35 --term 20 --sum-insured 100000
"""
from __future__ import annotations

import argparse
import json
import sys

from . import life
from .engine import _loadings, _mortality, quote
from .spec import SpecError, load_product


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="product_engine", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="check a product specification")
    p.add_argument("spec")

    for name, help_text in (("quote", "price a request"), ("cashflows", "project expected cash flows (term life)")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("spec")
        p.add_argument("--age", type=int, required=True)
        p.add_argument("--term", type=int, dest="term_years", help="term life: policy term in years")
        p.add_argument("--sum-insured", type=float, dest="sum_insured", help="term life: sum insured")
        p.add_argument("--daily-benefit", type=float, dest="daily_benefit", help="hospital cash: daily benefit")
        p.add_argument("--deductible-days", type=int, dest="deductible_days", help="hospital cash")
        p.add_argument("--max-days", type=int, dest="max_days_per_stay", help="hospital cash: max days per stay")
        p.add_argument("--mode", dest="payment_mode", default="annual",
                       choices=sorted({"annual", "semiannual", "monthly"}))
    return parser


def _request_from_args(args: argparse.Namespace) -> dict:
    keys = ("age", "term_years", "sum_insured", "daily_benefit", "deductible_days",
            "max_days_per_stay", "payment_mode")
    return {k: getattr(args, k) for k in keys if getattr(args, k, None) is not None}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        product = load_product(args.spec)
    except (SpecError, OSError) as exc:
        print(f"Invalid specification: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate":
        print(f"OK: {product.name} v{product.version} ({product.type})")
        return 0

    request = _request_from_args(args)
    if args.command == "quote":
        result = quote(product, request)
        print(json.dumps(result, indent=2))
        return 0 if result["eligible"] else 1

    # cashflows
    if product.type != "term_life":
        print("cashflows is only available for term life products", file=sys.stderr)
        return 2
    result = quote(product, request)
    if not result["eligible"]:
        print(json.dumps(result, indent=2))
        return 1
    rows = life.project_cashflows(
        _mortality(product.spec), product.spec["basis"]["interest_rate"],
        request["age"], request["term_years"], request["sum_insured"], _loadings(product.spec),
    )
    print(f"{'year':>4} {'age':>4} {'in force':>9} {'premium':>10} {'expenses':>9} {'death ben.':>11}")
    for r in rows:
        print(f"{r['year']:>4} {r['attained_age']:>4} {r['in_force_start']:>9.4f} "
              f"{r['premium_income']:>10.2f} {r['expenses']:>9.2f} {r['death_benefit']:>11.2f}")
    pv_prem = sum(r["pv_premium_income"] for r in rows)
    pv_exp = sum(r["pv_expenses"] for r in rows)
    pv_ben = sum(r["pv_death_benefit"] for r in rows)
    print(f"\nPV premiums {pv_prem:.2f} | PV expenses {pv_exp:.2f} | PV death benefits {pv_ben:.2f} "
          f"| residual {pv_prem - pv_exp - pv_ben:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
