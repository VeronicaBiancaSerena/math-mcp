"""NumPy-backed numeric helpers: Markov chain analysis and Monte Carlo simulation."""

from __future__ import annotations

from typing import Any

import numpy as np


def markov_analyze(matrix: list[list[float]], query: str, steps: int) -> dict[str, Any]:
    """Analyze a row-stochastic transition matrix (stationary or n-step)."""
    arr = np.array(matrix, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError("transition matrix must be square")
    if not np.allclose(arr.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("transition matrix rows must each sum to 1")
    if query == "n_step":
        powered = np.linalg.matrix_power(arr, max(1, steps))
        return {"n_step_matrix": powered.tolist(), "steps": steps}
    # Stationary distribution: left eigenvector for eigenvalue 1.
    values, vectors = np.linalg.eig(arr.T)
    idx = int(np.argmin(np.abs(values - 1.0)))
    vec = np.real(vectors[:, idx])
    vec = vec / vec.sum()
    return {"stationary_distribution": vec.tolist()}


def simulate(
    experiment: str, trials: int, *, p: float, sides: int, target: float, seed: int
) -> dict[str, Any]:
    """Run a seeded Monte Carlo experiment; returns an estimated probability (evidence)."""
    rng = np.random.default_rng(seed)
    if experiment == "coin":
        draws: Any = rng.integers(0, 2, size=trials)
        hits = int(np.count_nonzero(draws == int(target)))
    elif experiment == "dice":
        draws = rng.integers(1, sides + 1, size=trials)
        hits = int(np.count_nonzero(draws == int(target)))
    elif experiment == "bernoulli":
        draws = rng.random(size=trials)
        hits = int(np.count_nonzero(draws < p))
    else:
        raise ValueError(f"unknown experiment '{experiment}'")
    return {"estimate": hits / trials, "hits": hits, "trials": trials, "seed": seed}
