"""Seeded-random operations are reproducible and never claim a proof."""

from __future__ import annotations

import pytest
from conftest import call

from math_mcp.operation_registry import all_operations

SEEDED = [
    s for s in all_operations() if s.determinism == "seeded_random" and s.state == "implemented"
]


@pytest.mark.parametrize("spec", SEEDED, ids=lambda s: f"{s.public_tool}:{s.operation}")
def test_same_seed_same_result(spec) -> None:  # type: ignore[no-untyped-def]
    limits = {"seed": 4242}
    r1 = call(spec.public_tool, spec.operation, spec.example_payload, limits=limits)
    r2 = call(spec.public_tool, spec.operation, spec.example_payload, limits=limits)
    assert r1.ok and r2.ok
    assert r1.result == r2.result
    assert r1.status == r2.status


def test_seed_is_recorded_when_not_provided() -> None:
    # search_counterexample is seeded_random; without a seed it must surface one.
    result = call(
        "verification_compute",
        "check_inequality_sampled",
        {"left": "x**2 + 1", "relation": ">", "right": "0", "variables": ["x"], "samples": 50},
    )
    assert result.ok
    assert result.metadata.get("seed") is not None


def test_seeded_random_never_proves() -> None:
    for spec in SEEDED:
        assert "symbolic" not in spec.proof_modes
        assert spec.max_certainty in ("disproved", "evidence")
