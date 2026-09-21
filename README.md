# Insurance Product Engine: from product specification to tested premium calculation

A small Python project that turns a **written product specification** into a **working, tested premium calculation** for two products: **Term Life** and **Hospital Daily Cash** (health). The products are defined in YAML files, the engine reads them, and every rule is covered by a test that points back to a numbered requirement.

> **All parameters in this repository are illustrative assumptions.** No real insurer, tariff, mortality table or claims statistics is used. The mortality basis is a smooth Gompertz-Makeham curve, not a real table. Premium levels say nothing about real market prices.

## Why this project exists

Digital insurance products usually start as a specification: eligibility rules, a calculation basis, loadings, payment options. Someone has to turn that into a model, configure it, test it and document it. This project practises that whole path on a small scale:

| Step | In this repository |
|---|---|
| 1. Analyse the calculation requirements | [`docs/requirements.md`](docs/requirements.md): numbered requirements (REQ-TL-01, ...) |
| 2. Turn the specification into a product model | [`products/*.yaml`](products): the product definition, with no parameters hidden in the code |
| 3. Configure and validate | [`src/product_engine/spec.py`](src/product_engine/spec.py): a specification is checked before use, and errors name the field |
| 4. Calculate | [`life.py`](src/product_engine/life.py), [`health.py`](src/product_engine/health.py), [`engine.py`](src/product_engine/engine.py) |
| 5. Test | [`tests/`](tests): 73 tests; each carries the ID of the requirement it checks |
| 6. Document | this README, the requirements table, docstrings with the formulas |

## The two products

**Term Life** (level sum insured, level annual premium, death benefit at the end of the year of death)

- Net premium by the equivalence principle: `P = S * A / a`, where `A` is the actuarial present value of the death benefit and `a` the premium annuity-due.
- Gross premium with three loadings (acquisition `alpha`, administration `gamma`, proportional `beta`):
  `G = (S*A + alpha*S + gamma*S*a) / ((1 - beta) * a)`.
- Net prospective reserve, and a year-by-year expected cash-flow projection whose present value balances to zero.
- Payment modes (annual, semi-annual, monthly) with a surcharge.

**Hospital Daily Cash** (fixed benefit per hospital day after a deductible, up to a maximum number of days per stay)

- Admission rate and mean length of stay by age band; length of stay is geometric.
- Expected paid days per stay have a closed form, which is cross-checked against a brute-force sum in the tests.
- Premium = expected benefit x (1 + safety loading) / (1 - expense ratio).

## Quick start

```bash
pip install -r requirements.txt
python -m pytest -q                       # 73 tests

export PYTHONPATH=src                     # or: pip install -e .
python -m product_engine validate products/term_life.yaml
python -m product_engine quote products/term_life.yaml --age 35 --term 20 --sum-insured 100000 --mode monthly
python -m product_engine quote products/hospital_cash.yaml --age 45 --daily-benefit 50 --deductible-days 3 --max-days 60
python -m product_engine cashflows products/term_life.yaml --age 35 --term 20 --sum-insured 100000
```

Example output (Term Life, 35 years, 20-year term, 100,000 EUR, monthly payments):

```json
{
  "product": "TERM_LIFE_V1",
  "eligible": true,
  "net_annual_premium": 247.5,
  "gross_annual_premium": 337.67,
  "payment_mode": "monthly",
  "instalments_per_year": 12,
  "instalment": 29.55,
  "total_annual_payable": 354.6
}
```

A request outside the specification is rejected with a code for each reason, so a front end could show the exact cause:

```
$ python -m product_engine quote products/term_life.yaml --age 62 --term 20 --sum-insured 5000
{ "eligible": false, "errors": [
    {"code": "ELIG_EXPIRY_AGE",   "message": "age at expiry 82 exceeds 75"},
    {"code": "ELIG_SUM_INSURED",  "message": "sum insured 5000.0 is outside 10000-1000000"} ] }
```

The cash-flow projection ends with a balance check (present value of premiums, expenses and death benefits):

```
PV premiums 6336.71 | PV expenses 1692.15 | PV death benefits 4644.56 | residual 0.000000
```

## How the tests work

- **Traceability.** Every requirement in `docs/requirements.md` is referenced by at least one test, and `tests/test_traceability.py` fails if one is not.
- **Independent checks.** The equivalence principle, the gross-premium formula and the hospital closed form are each verified with a separate calculation written in the test, not by calling the same function twice.
- **Hand-checkable cases.** With constant mortality `q` and zero interest, the net premium rate must equal `q`; a fixed hospital example is checked against a manual calculation.
- **Properties.** Premiums rise with age, with the sum insured (proportionally) and with the coverage limits; the net reserve starts and ends at zero.
- **Configuration.** Changing a value in a YAML file changes the premium as expected, and broken specifications are rejected with the field name.
- During development, deliberately injected mistakes (wrong discounting of the death benefit, a missing loading term, an off-by-one in the deductible) were caught by the tests.

## Limitations

- Illustrative assumptions only; the mortality curve, interest rate, hospital statistics and loadings are invented.
- Annual premium timing: the payment-mode surcharge is a flat factor, not a model of monthly cash flows. There are no lapses, no surrender values and no riders.
- Gross premium reserves and profit testing are not implemented; only the net reserve is.
- The geometric length-of-stay model has a thin tail. For younger age bands the premium difference between a 60-day and a 90-day cap is below one cent.
- Only two product types are supported; a new type needs a validator in `spec.py` and a calculation module.

## Project structure

```
products/                  product specifications (YAML)
src/product_engine/
    spec.py                loading and validation of specifications
    mortality.py           Gompertz-Makeham and constant mortality
    life.py                term life: APVs, premiums, reserve, cash flows
    health.py              hospital cash: expected paid days, premium
    engine.py              eligibility checks and quotes
    cli.py                 command line interface
docs/requirements.md       numbered requirements and where they are tested
tests/                     pytest suite
.github/workflows/         runs the tests on every push
```
