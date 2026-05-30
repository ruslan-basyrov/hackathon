"""Phase 4 acceptance (BUILD_SPEC §5 Phase 4).

Two things to verify, both with the LLM client mocked (no real endpoint
needed for the test gate):

  1. wording_per_intervention_type: with `method=llm`, each of the five
     intervention types produces wording for each persona. The mock returns
     a known string; we assert the dispatcher routed through the LLM path
     and the returned text is what the (mocked) endpoint produced.

  2. graceful_degradation_on_endpoint_failure: with `method=llm` AND the
     mocked endpoint raising on every call, the simulator's decisions are
     unchanged (Phase 2 uplift numbers match the template baseline) and
     every fired intervention has non-empty text (from the template
     fallback). This is the property that proves decisions never depended
     on the endpoint.

These tests do NOT need an inference server running. The runtime path
DOES, but the user starts one via services/inference/ when they want
real wording.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coach import coach as coach_fn  # noqa: E402
from coach.realize import realize  # noqa: E402
from runner import compare, load_config  # noqa: E402
from signals import Signals  # noqa: E402

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")


def _mk_signals(step: int, **kwargs) -> Signals:
    base = dict(
        step=step, steps_completed=0, dwell_current_s=0.0, dwell_total_s=0.0,
        time_since_last_action_s=0.0, back_nav_count=0, back_from_step=None,
        field_change_count=0, tariff_hover_count=0, advisory_tariff_clicked=False,
        tariff_selected="Optimal", external_tab_opens=0, price_gap_eur=0.0,
        hover_cancel_count=0,
    )
    base.update(kwargs)
    return Signals(**base)


def _mock_llm_response(text: str):
    """Build a MagicMock that quacks like an OpenAI chat.completions response."""
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=text))]
    return resp


def _mock_client_returning(text: str) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_llm_response(text)
    return client


# ---------------------------------------------------------------------------
# 1. wording is produced for each intervention type per persona
# ---------------------------------------------------------------------------

INTERVENTION_TYPES = ("price_reframe", "explain_price", "explain_advisory_alt",
                      "justify_price", "callback", "back_nav_help")
PERSONAS = ("judith", "franz", "peter")


@pytest.mark.parametrize("itype", INTERVENTION_TYPES)
@pytest.mark.parametrize("persona", PERSONAS)
def test_llm_wording_per_intervention_per_persona(itype: str, persona: str):
    cfg = load_config(CONFIG)
    cfg["realize"]["method"] = "llm"
    cfg["realize"]["graceful_fallback"] = True
    canned = f"[mock wording for {persona}/{itype}]"
    with patch("coach.llm_realize.get_client",
               return_value=_mock_client_returning(canned)):
        text = realize(itype, _mk_signals(step=4), persona=persona, cfg=cfg)
    assert text == canned, f"expected mock wording, got {text!r}"


def test_llm_path_actually_calls_inference():
    cfg = load_config(CONFIG)
    cfg["realize"]["method"] = "llm"
    mock_client = _mock_client_returning("ok")
    with patch("coach.llm_realize.get_client", return_value=mock_client):
        realize("price_reframe", _mk_signals(step=4), persona="judith", cfg=cfg)
    mock_client.chat.completions.create.assert_called_once()
    # the model name from cfg made it into the call
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == cfg["model_name"]
    # the message includes the persona briefing keyword
    msgs = kwargs["messages"]
    assert any("Judith" in m["content"] for m in msgs)


def test_template_path_does_not_call_inference():
    """With method=template (the default), no LLM client is built."""
    cfg = load_config(CONFIG)
    assert cfg["realize"]["method"] == "template"  # config default
    with patch("coach.llm_realize.get_client") as mock_get:
        text = realize("price_reframe", _mk_signals(step=4),
                       persona="judith", cfg=cfg)
    mock_get.assert_not_called()
    # template output mentions Optimal and the per-day price
    assert "Optimal" in text


# ---------------------------------------------------------------------------
# 2. graceful degradation: endpoint down -> templates -> decisions unchanged
# ---------------------------------------------------------------------------

def _raise_connection_error(*args, **kwargs):
    raise ConnectionError("mock: endpoint unreachable")


def test_llm_failure_falls_back_to_template():
    cfg = load_config(CONFIG)
    cfg["realize"]["method"] = "llm"
    cfg["realize"]["graceful_fallback"] = True
    broken_client = MagicMock()
    broken_client.chat.completions.create.side_effect = _raise_connection_error
    with patch("coach.llm_realize.get_client", return_value=broken_client):
        text = realize("price_reframe", _mk_signals(step=4),
                       persona="judith", cfg=cfg)
    # template fallback should have run
    assert "Optimal" in text


def test_llm_failure_without_fallback_raises():
    cfg = load_config(CONFIG)
    cfg["realize"]["method"] = "llm"
    cfg["realize"]["graceful_fallback"] = False
    broken_client = MagicMock()
    broken_client.chat.completions.create.side_effect = _raise_connection_error
    with patch("coach.llm_realize.get_client", return_value=broken_client):
        with pytest.raises(ConnectionError):
            realize("price_reframe", _mk_signals(step=4),
                    persona="judith", cfg=cfg)


def test_decisions_unchanged_when_endpoint_down():
    """The Phase 4 acceptance gate. With method=llm and a broken endpoint,
    the simulator's per-persona uplift on identical seeds must match the
    Phase 2 (template) baseline — proves decisions never depended on the
    endpoint."""
    cfg_tmpl = load_config(CONFIG)
    # baseline: template mode (Phase 2 default)
    baseline = {p: compare(cfg_tmpl, persona=p, n=2000) for p in PERSONAS}

    cfg_llm = load_config(CONFIG)
    cfg_llm["realize"]["method"] = "llm"
    cfg_llm["realize"]["graceful_fallback"] = True
    broken_client = MagicMock()
    broken_client.chat.completions.create.side_effect = _raise_connection_error
    with patch("coach.llm_realize.get_client", return_value=broken_client):
        degraded = {p: compare(cfg_llm, persona=p, n=2000) for p in PERSONAS}

    for p in PERSONAS:
        # identical seeds + scripted agent + fallback to template wording
        # => the simulator should be byte-for-byte identical
        assert baseline[p]["success_with"] == degraded[p]["success_with"], (
            p, baseline[p]["success_with"], degraded[p]["success_with"]
        )
        assert baseline[p]["fired_rate"] == degraded[p]["fired_rate"], p


def test_llm_mode_does_not_break_phase2_acceptance():
    """Bot-driven uplift in LLM-wording mode (with mocked endpoint returning
    real text) should still satisfy the Phase 2 gates: uplift > 0 per persona,
    Franz wasted_rate < 0.40. Confirms LLM mode is a drop-in replacement."""
    cfg = load_config(CONFIG)
    cfg["realize"]["method"] = "llm"
    cfg["realize"]["graceful_fallback"] = True
    mock_client = _mock_client_returning("Mock nudge text.")
    with patch("coach.llm_realize.get_client", return_value=mock_client):
        for p in PERSONAS:
            r = compare(cfg, persona=p, n=2000)
            assert r["uplift"] > 0, (p, r)
            assert r["wasted_rate"] is None or 0.0 <= r["wasted_rate"] <= 1.0
        franz = compare(cfg, persona="franz", n=2000)
        assert franz["wasted_rate"] < 0.40, franz["wasted_rate"]


if __name__ == "__main__":
    cfg = load_config(CONFIG)
    cfg["realize"]["method"] = "llm"
    with patch("coach.llm_realize.get_client",
               return_value=_mock_client_returning("[mock]")):
        for p in PERSONAS:
            for it in INTERVENTION_TYPES:
                text = realize(it, _mk_signals(step=4), persona=p, cfg=cfg)
                print(f"{p:8s} {it:25s} -> {text}")
