"""On-prem ObligationFeedPort: fail-fast portability placeholder (the sovereign-exit proof).

The client runs its own obligation register, so this binding refuses at call time rather than
dropping the proposed edges. Refusing is the correct failure: a feed that silently returned would
let a tiered model never reach the register while every gate stayed green.
"""

from __future__ import annotations

from obligation_register import Edge

from ...config import Settings


class OnPremObligationFeed:
    """Satisfies ObligationFeedPort but refuses: the client wires its own register feed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def emit(self, edges: tuple[Edge, ...], *, actor: str) -> tuple[str, ...]:
        raise NotImplementedError(
            "on-prem obligation feed is a portability placeholder: bind the client's own "
            "register feed (see docs/onprem-migration.md). Every tiered model must still reach "
            "the obligation register."
        )
