"""Every requirement in docs/requirements.md must be referenced by at least one test."""
import re

from conftest import ROOT

ID_PATTERN = re.compile(r"REQ-[A-Z]{2}-\d{2}")


def test_every_requirement_has_a_test():
    requirement_ids = set(ID_PATTERN.findall((ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")))
    assert requirement_ids, "no requirement IDs found"

    tested = set()
    for path in (ROOT / "tests").glob("test_*.py"):
        if path.name == "test_traceability.py":
            continue
        tested |= set(ID_PATTERN.findall(path.read_text(encoding="utf-8")))

    untested = sorted(requirement_ids - tested)
    assert not untested, f"requirements without a test: {untested}"


def test_tests_only_reference_existing_requirements():
    requirement_ids = set(ID_PATTERN.findall((ROOT / "docs" / "requirements.md").read_text(encoding="utf-8")))
    for path in (ROOT / "tests").glob("test_*.py"):
        if path.name == "test_traceability.py":
            continue
        unknown = set(ID_PATTERN.findall(path.read_text(encoding="utf-8"))) - requirement_ids
        assert not unknown, f"{path.name} references unknown requirements: {sorted(unknown)}"
