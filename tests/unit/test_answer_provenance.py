"""The service half of the model pills: which model ANSWERED, and whether it searched.

The console shows two pills at the top right: the model that answered the last request, and
``Search`` when that answer used an online search tool. Both come from response headers the kit
emits (``install_answer_provenance`` in ``api/app.py``) for whatever the model adapters NOTED as
they called. Before a request is answered the pill shows ``generator_model`` from ``/healthz``,
so that value must be the model the bound adapter calls, never one a configuration flag names
while the adapter calls another.

This service binds no model port: validation is a deterministic engine, so it notes nothing,
its responses carry neither header, and the pill keeps showing ``no-model``. The route is still
proved to carry both headers the day an adapter notes something, by standing a noting engine in
for the real one.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from hex_service_kit import provenance

from model_risk_validation import config
from model_risk_validation.api import app as app_module
from model_risk_validation.domain.validation_service import ValidationService

from tests import REPO_ROOT
from tests.unit.test_api import _ESCALATING_BODY

ANSWERED_BY = "x-answered-by"
SEARCH_USED = "x-search-used"


@pytest.fixture()
def local_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The API under ``local`` whatever the shell exported: CI runs with no profile set."""
    monkeypatch.setenv(config._PROFILE_ENV, "local")
    app_module._container.cache_clear()
    with TestClient(app_module.app, client=("127.0.0.1", 50000)) as client:
        yield client
    app_module._container.cache_clear()


def _validate(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/v1/validate", json=_ESCALATING_BODY, headers={"X-Dev-Persona": "auditor"}
    )
    assert response.status_code == 200, response.text
    return dict(response.headers)


def test_a_deterministic_answer_names_no_model(local_client: TestClient) -> None:
    """Nothing noted, nothing sent: the pill never invents a model the engine did not call."""
    headers = _validate(local_client)
    assert ANSWERED_BY not in headers
    assert SEARCH_USED not in headers


class _AnsweringService(ValidationService):
    """The real engine, plus what a model adapter that searched would note while it called."""

    def validate(self, *args: object, **kwargs: object) -> object:  # type: ignore[override]
        provenance.note_model("fake-answering-model")
        provenance.note_search()
        return super().validate(*args, **kwargs)  # type: ignore[arg-type]


def test_the_route_names_the_model_that_answered_and_that_it_searched(
    local_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "ValidationService", _AnsweringService)
    headers = _validate(local_client)
    assert headers[ANSWERED_BY] == "fake-answering-model"
    assert headers[SEARCH_USED] == "true"
    # The next request is a fresh record: an answer never leaks into a later response.
    monkeypatch.setattr(app_module, "ValidationService", ValidationService)
    assert ANSWERED_BY not in _validate(local_client)


def test_the_pill_starts_from_no_model_because_nothing_here_calls_one() -> None:
    settings = config.Settings.load(REPO_ROOT / "config" / "settings.yaml")
    assert settings.generator_model == "no-model"


def test_no_flag_swaps_in_a_model_the_adapter_never_calls() -> None:
    """The latent false banner: a flag that moved the pill but not the model that answered."""
    models = SimpleNamespace(
        reasoning="the-model-the-adapter-calls",
        hard_reasoning="a-model-nobody-calls",
        use_hard_reasoning=True,
    )
    named = config._model_from_settings(SimpleNamespace(models=models), "models.reasoning")
    assert named == "the-model-the-adapter-calls"


def test_the_hard_reasoning_flag_does_not_exist() -> None:
    settings_file = (REPO_ROOT / "config" / "settings.yaml").read_text(encoding="utf-8")
    assert "use_hard_reasoning" not in settings_file
    for source in sorted((REPO_ROOT / "src").rglob("*.py")):
        assert "use_hard_reasoning" not in source.read_text(encoding="utf-8"), source
