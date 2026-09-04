"""ObligationFeedPort: the seam to the obligations-control-mapping register graph.

model-risk-validation PROPOSES model-to-obligation edges into obligations-control-mapping (slice 6).
The edges are typed by ``obligation-register-kit`` (never copied), built in the pure domain; the
adapters carry them to the register. The local adapter buffers them, the managed adapter posts to
obligations-control-mapping over S2S, and the on-premises placeholder refuses. A feed that silently
dropped the edges would let a tiered model never reach the register, so the local adapter is a real
buffer and the managed one fails closed when obligations-control-mapping is unreachable.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from obligation_register import Edge


@runtime_checkable
class ObligationFeedPort(Protocol):
    def emit(self, edges: tuple[Edge, ...], *, actor: str) -> tuple[str, ...]:
        """Emit proposed obligation edges to the register, returning one reference per edge.

        ``actor`` is the verified principal that produced the underlying validation. The return
        tuple has one reference per edge, never empty for a non-empty input, so a caller can
        record that every tiered model reached the feed (the export-completeness guarantee).
        """
        ...
