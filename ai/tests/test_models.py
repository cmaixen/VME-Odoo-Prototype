"""Which model each task uses, and the fallback that only some models support."""
from classifier import MODELS, fallback_options, model_for


def test_each_task_has_its_own_model(monkeypatch):
    monkeypatch.delenv("VME_AI_MODEL", raising=False)
    assert model_for("invoice") == MODELS["invoice"] == "claude-haiku-5-5"
    assert model_for("mail") == "claude-sonnet-5-5"


def test_override_for_every_task(monkeypatch):
    monkeypatch.setenv("VME_AI_MODEL", "claude-opus-5-5")
    assert {model_for(task) for task in MODELS} == {"claude-opus-5-5"}


def test_no_server_side_fallback_on_haiku():
    assert fallback_options("claude-haiku-5-5") == {}
    assert fallback_options("claude-sonnet-5-5") == {
        "betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
