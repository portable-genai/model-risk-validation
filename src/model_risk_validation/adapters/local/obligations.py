"""Local ObligationFeedPort: buffer proposed edges in memory (no live Rgc7).

Exercises the slice-6 feed path offline. Each edge is buffered with a producer-owned reference
so the gate, the tests and the demo can assert every tiered model reached the feed, without a
running register. The buffer is deliberately not a no-op: a silent feed would let a model never
reach Rgc7 with a green gate.
"""

from __future__ import annotations

from obligation_register import Edge

from ...config import Settings


class LocalObligationFeed:
    """Record proposed obligation edges in an in-memory buffer for the ``local`` profile."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._buffer: list[Edge] = []

    def emit(self, edges: tuple[Edge, ...], *, actor: str) -> tuple[str, ...]:
        refs: list[str] = []
        for edge in edges:
            self._buffer.append(edge)
            # The buffer reference, not a register id: nothing has been posted yet, and saying so
            # is the point. A live adapter returns the register's own edge id.
            refs.append(f"buffer:{len(self._buffer)}:{edge.id}")
        return tuple(refs)

    @property
    def buffer(self) -> tuple[Edge, ...]:
        """Expose the buffered edges for inspection in tests, the eval and the demo."""
        return tuple(self._buffer)
