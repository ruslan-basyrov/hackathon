"""LLM-backed `realize()` (Phase 4, BUILD_SPEC §5).

At Phase 4 this is THE ONLY component that calls the inference endpoint —
that property is what makes the graceful-degradation test in §Phase 4
decisive: with the endpoint down, decisions are unchanged (the simulator
keeps running) and the system falls back to the template wording.

The endpoint is OpenAI-compatible (works with vLLM, Ollama, llama.cpp, a
remote endpoint, or our pytest mocks); the only knobs that vary between
backends are `INFERENCE_BASE_URL` + `MODEL_NAME`. See `services/inference/`
for how to start a local server.

Persona briefings are intentionally short and one-paragraph each: the
prompt needs to be cheap to evaluate (this fires once per intervention).
The intervention briefs encode the policy intent (what we WANT the wording
to do) without prescribing the words — that's the LLM's job.
"""
from __future__ import annotations

from typing import Optional


# ---- persona briefings (used in the prompt) --------------------------------
PERSONA_BRIEFINGS = {
    "judith": (
        "Judith, late 40s. Considering private health insurance for the first "
        "time. Compares prices carefully; wants reassurance the price is fair. "
        "Will NOT tolerate aggressive selling. Tone: respectful, plain, value-"
        "anchored. Open to handing off to an advisor when overwhelmed."
    ),
    "franz": (
        "Franz, 30s. Confident online buyer. Wants to finish online quickly. "
        "Hostile to anything that requires a phone call or advisor. Skeptical "
        "of upsells. Tone: direct, no nonsense, no hand-holding. Never push "
        "him toward a human."
    ),
    "peter": (
        "Peter, 60s. Service-affine. Easily overwhelmed by online forms; "
        "prefers talking to a person. Tone: warm, slower pace, plain language. "
        "Offer help proactively; do NOT push him toward self-service."
    ),
    "global": (
        "A general prospect on the signup flow. Tone: neutral and helpful, no "
        "assumptions about register."
    ),
}

# ---- intervention briefs (the policy intent, NOT the words) ----------------
INTERVENTION_BRIEFS = {
    "price_reframe": (
        "Reframe the monthly premium as a small daily amount. Anchor it to an "
        "everyday cost (e.g. a coffee). Keep it short, no hard sell."
    ),
    "explain_price": (
        "Transparently explain that the final price reflects the user's "
        "personal health profile. Reassure that completing online is still "
        "possible right now."
    ),
    "explain_advisory_alt": (
        "Clarify that Opt.Plus and Premium tariffs require an advisory call, "
        "while Optimal can be completed fully online. Gently steer toward the "
        "online option without putting down the advisory ones."
    ),
    "justify_price": (
        "Acknowledge the final price is above the estimate, give the reason "
        "(health profile), and reaffirm the user can still finish online now."
    ),
    "callback": (
        "Offer a callback or a human advisor, gently. Acknowledge that this "
        "can be a lot to weigh up. Do NOT push self-service."
    ),
    "back_nav_help": (
        "The user seems lost (multiple back navigations). Offer help in a "
        "friendly, non-pushy way."
    ),
}


def build_messages(itype: str, signals, persona: Optional[str]) -> list[dict]:
    """Build OpenAI-compatible chat messages for the given (intervention,
    signals, persona) tuple. Pure function — easy to snapshot in tests."""
    persona_brief = PERSONA_BRIEFINGS.get(persona or "global", PERSONA_BRIEFINGS["global"])
    intervention_brief = INTERVENTION_BRIEFS.get(itype, "Be helpful. One or two sentences.")

    # only the signals the wording could plausibly reference
    user_msg = (
        f"PERSONA\n{persona_brief}\n\n"
        f"CURRENT STEP: S{signals.step}\n"
        f"SIGNALS:\n"
        f"  - dwell on current screen: {signals.dwell_current_s:.0f}s\n"
        f"  - tariff selected: {signals.tariff_selected}\n"
        f"  - price gap (final vs estimate): €{signals.price_gap_eur:.2f}\n"
        f"  - back navigations: {signals.back_nav_count}\n"
        f"  - form re-edits: {signals.field_change_count}\n"
        f"\n"
        f"INTERVENTION TYPE: {itype}\n"
        f"GUIDANCE: {intervention_brief}\n"
        f"\n"
        f"Reply with ONLY the nudge text in the persona's register. "
        f"1-2 sentences max. No greetings, no closings, no quotes, no preface."
    )

    system_msg = (
        "You are a conversion coach inside an insurance signup flow. You write "
        "short, helpful nudges to users at moments of hesitation. Match the "
        "user's register exactly. Never sell aggressively. Never invent prices "
        "or coverage details — only use the figures in the brief."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def get_client(cfg: dict):
    """Build an OpenAI-compatible client from cfg. Indirected through a
    function so tests can monkeypatch it (return a mock instead of a real
    client). Imports are lazy so the openai dep is only loaded when LLM mode
    is actually used.

    `max_retries=0` is deliberate: with retries enabled, an unreachable
    endpoint would block for ~15s (3 attempts × ~5s timeout each) and a
    UI click would feel frozen / drop the WebSocket. We'd rather fail fast
    and hit the template fallback. The UI also wraps this call in
    `run.io_bound` so the event loop stays responsive even if the network
    attempt does take a couple of seconds.
    """
    from openai import OpenAI

    realize_cfg = cfg.get("realize", {}) or {}
    timeout_s = float(realize_cfg.get("timeout_s", 3.0))
    return OpenAI(
        base_url=cfg.get("inference_base_url", "http://localhost:8000/v1"),
        api_key=cfg.get("inference_api_key", "local"),
        max_retries=0,
        timeout=timeout_s,
    )


def llm_realize(itype: str, signals, persona: Optional[str], cfg: dict) -> str:
    """Single LLM call. Raises on any failure (network, timeout, empty
    response). The dispatcher in `coach/realize.py` decides whether to fall
    back to the template — keeping the error policy in one place."""
    client = get_client(cfg)
    messages = build_messages(itype, signals, persona)
    realize_cfg = cfg.get("realize", {}) or {}

    resp = client.chat.completions.create(
        model=cfg.get("model_name", "qwen2.5-7b-instruct"),
        messages=messages,
        max_tokens=int(realize_cfg.get("max_tokens", 120)),
        temperature=float(realize_cfg.get("temperature", 0.7)),
        timeout=float(realize_cfg.get("timeout_s", 8.0)),
    )
    text = (resp.choices[0].message.content or "").strip().strip('"').strip("'")
    if not text:
        raise ValueError("empty LLM response")
    return text
