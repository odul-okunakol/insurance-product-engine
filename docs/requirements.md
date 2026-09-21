# Requirements and test traceability

The requirements below were written before the code, as a product owner would hand them to a developer.
Each requirement has an ID. Every test that checks it carries the ID in its docstring, and
`tests/test_traceability.py` fails if a requirement here has no test.

All parameters in the product specifications are illustrative assumptions.

## Term life (`products/term_life.yaml`)

| ID | Requirement | Verified in |
|---|---|---|
| REQ-TL-01 | A request is accepted only if entry age, term, age at expiry and sum insured are inside the limits of the specification and the payment mode is offered. Each violation is reported with its own error code (`ELIG_ENTRY_AGE`, `ELIG_TERM`, `ELIG_EXPIRY_AGE`, `ELIG_SUM_INSURED`, `ELIG_PAYMENT_MODE`), and missing inputs with `MISSING_INPUT`. | `tests/test_term_life.py` |
| REQ-TL-02 | The net premium follows the equivalence principle: at inception, the present value of net premiums equals the present value of death benefits. | `tests/test_term_life.py` |
| REQ-TL-03 | Hand-checkable benchmark: with constant mortality q and a zero interest rate, the net annual premium equals sum insured x q, for any term. | `tests/test_term_life.py` |
| REQ-TL-04 | The gross premium is `G = (S*A + alpha*S + gamma*S*a) / ((1 - beta) * a)`, and it is proportional to the sum insured. | `tests/test_term_life.py` |
| REQ-TL-05 | For a fixed term, the premium increases with entry age. | `tests/test_term_life.py` |
| REQ-TL-06 | Payment modes: the instalment equals the annual gross premium x mode surcharge / number of instalments. | `tests/test_term_life.py` |
| REQ-TL-07 | The net prospective reserve is zero at inception and at expiry, and never negative in between. | `tests/test_term_life.py` |
| REQ-TL-08 | The expected cash-flow projection is consistent with the premium: the present value of premiums minus expenses minus death benefits is zero, and the discounted death benefits equal S x A. | `tests/test_term_life.py` |

## Hospital daily cash (`products/hospital_cash.yaml`)

| ID | Requirement | Verified in |
|---|---|---|
| REQ-HC-01 | A request is accepted only if age, daily benefit, deductible days and maximum days per stay are offered by the specification and the payment mode is offered. Violations are reported with error codes (`ELIG_AGE`, `ELIG_DAILY_BENEFIT`, `ELIG_DEDUCTIBLE`, `ELIG_MAX_DAYS`, `ELIG_PAYMENT_MODE`). | `tests/test_hospital_cash.py` |
| REQ-HC-02 | Expected paid days per stay use a closed form that matches an independent brute-force sum over the length-of-stay distribution, and tends to the mean length of stay when there is no deductible and no cap. | `tests/test_hospital_cash.py` |
| REQ-HC-03 | A higher deductible lowers the premium, a higher maximum number of days raises it, and the premium is proportional to the daily benefit. | `tests/test_hospital_cash.py` |
| REQ-HC-04 | The premium is admission rate x expected paid days x daily benefit x (1 + safety loading) / (1 - expense ratio); a fixed example is checked against a hand calculation. | `tests/test_hospital_cash.py` |
| REQ-HC-05 | The premium increases with the age band. | `tests/test_hospital_cash.py` |

## Specification handling

| ID | Requirement | Verified in |
|---|---|---|
| REQ-SP-01 | An invalid specification (missing field, out-of-range value, unknown product type, non-contiguous age bands) is rejected with an error message that names the field. | `tests/test_spec.py` |
| REQ-SP-02 | A change of a parameter in the specification changes the premium accordingly, with no change to the code. | `tests/test_spec.py` |
| REQ-SP-03 | The shipped specifications load and validate, and the command line tool reports valid and invalid specifications with the right exit code. | `tests/test_spec.py` |
