"""Monotonic wall-clock timing helpers."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager


class Stopwatch:
    """Accumulates elapsed wall-clock milliseconds between start and stop."""

    def __init__(self) -> None:
        self._start = time.monotonic()
        self._elapsed_ms: int | None = None

    def stop(self) -> int:
        if self._elapsed_ms is None:
            self._elapsed_ms = int((time.monotonic() - self._start) * 1000)
        return self._elapsed_ms

    @property
    def elapsed_ms(self) -> int:
        if self._elapsed_ms is not None:
            return self._elapsed_ms
        return int((time.monotonic() - self._start) * 1000)


@contextmanager
def measure() -> Iterator[Stopwatch]:
    """Context manager yielding a :class:`Stopwatch`; stops on exit."""
    watch = Stopwatch()
    try:
        yield watch
    finally:
        watch.stop()
