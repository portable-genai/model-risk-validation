"""Managed ObligationFeedPort: post proposed edges to the Rgc7 register over S2S.

Serialises each edge with the kit's canonical JSON and posts it to the Rgc7 feed endpoint,
authenticated as a trusted service caller. The register base URL comes from ``obligations_url``
in ``config/settings.yaml``; the S2S credentials come from google-auth, imported LAZILY so the
offline profiles construct with no cloud SDK. With nothing reachable it refuses (ImportError from
the lazy import, or RuntimeError when unconfigured), never a silent success: a dropped proposal
is a model that never reached the register.
"""

from __future__ import annotations

from obligation_register import Edge

from ...config import Settings

_SERVICE_ACTOR = "model-risk-validation"


class CloudObligationFeed:
    """Post proposed obligation edges to Rgc7 through an authenticated S2S session."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def emit(self, edges: tuple[Edge, ...], *, actor: str) -> tuple[str, ...]:
        base_url = self._settings.obligations_url.strip()
        if not base_url:
            raise RuntimeError(
                "obligations_url is not configured, so the Rgc7 feed cannot be honoured. Set "
                "RGC7_OBLIGATIONS_URL (config/settings.yaml obligations_url) to the register."
            )
        # Lazy import: google-auth is absent in the offline profiles and in the SDK-free gate.
        from google.auth.transport.requests import AuthorizedSession  # noqa: PLC0415
        from google.oauth2 import id_token  # noqa: PLC0415
        from obligation_register import to_jsonable  # noqa: PLC0415

        session = AuthorizedSession(id_token.fetch_id_token_credentials(base_url))
        refs: list[str] = []
        for edge in edges:
            response = session.post(
                f"{base_url}/v1/service/edges",
                json={"edge": to_jsonable(edge), "actor": actor, "producer": _SERVICE_ACTOR},
                timeout=30,
            )
            response.raise_for_status()
            refs.append(str(response.json().get("edge_id", edge.id)))
        return tuple(refs)
