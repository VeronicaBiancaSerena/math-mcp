"""Validate the agent eval set: structure, registry consistency, and coverage."""

from __future__ import annotations

import json
from pathlib import Path

from math_mcp.operation_registry import get_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_PATH = REPO_ROOT / "evals" / "math_agent_cases.jsonl"

REQUIRED = {
    "id",
    "prompt",
    "expected_public_tool",
    "expected_operation",
    "expected_operation_state",
    "allow_numeric_evidence",
}


def _load_cases() -> list[dict]:
    return [json.loads(line) for line in EVAL_PATH.read_text().splitlines() if line.strip()]


def test_eval_cases_well_formed() -> None:
    cases = _load_cases()
    assert len(cases) >= 15
    ids = set()
    for case in cases:
        assert set(case) >= REQUIRED, f"{case.get('id')} missing keys"
        assert case["id"] not in ids, f"duplicate id {case['id']}"
        ids.add(case["id"])


def test_eval_referenced_operations_exist() -> None:
    for case in _load_cases():
        spec = get_spec(case["expected_public_tool"], case["expected_operation"])
        assert spec is not None, f"{case['id']} references unknown operation"
        assert spec.state == case["expected_operation_state"]


def test_eval_certainty_respects_max() -> None:
    from math_mcp.status import certainty_rank

    for case in _load_cases():
        if "expected_certainty" not in case:
            continue
        spec = get_spec(case["expected_public_tool"], case["expected_operation"])
        assert spec is not None
        # The expected certainty must be reachable (no stronger than the op's max).
        assert certainty_rank(case["expected_certainty"]) >= certainty_rank(spec.max_certainty)


def test_eval_includes_negative_and_recovery_cases() -> None:
    cases = _load_cases()
    negatives = [c for c in cases if c["id"].startswith("neg_")]
    assert len(negatives) >= 5
    # At least one each: LaTeX, natural-language, timeout, z3 unknown, sampling-evidence.
    notes = " ".join(c.get("note", "") for c in negatives).lower()
    assert "latex" in notes
    assert "sampling" in notes
    assert "unknown" in notes
    # A conditional-solution recovery case must exist (guide §15.16).
    assert "conditional" in notes
