"""LLM Conversion Coach (chat).

Adapted for the state_machine + Signals contract:
  * `funnel_step` is a Step name (e.g. "S4_INITIAL_PRICE"), not the old loose
    "PRODUCT_TARIFF_SELECTION" strings.
  * `turn_data` carries a structured Action and a Signals dict; the user prompt
    surfaces both directly instead of dumping a free-form blob.
  * `trigger_reason` can be a detector code (rule-based or GBM) or an LLM-authored
    strategy string. A small decoder maps known codes to plain-English hints so
    the chat model has something concrete to work with.

The bot stays LLM-driven and keeps its rolling chat history per session. The
canonical intervention types from coach.policy/realize are listed in the system
prompt as a vocabulary the model is encouraged to phrase from — it doesn't
replace coach/realize.py templates, just anchors the LLM's wording.
"""
from __future__ import annotations

import json
from typing import Optional

from utils.llm_client import LLMClient

from simulation.json_utils import loads_lenient


# Detector reason -> short hint for the chat LLM.
_TRIGGER_HINTS = {
    "s4_dwell": "Long dwell at the price table. Likely comparing or hesitating on tariffs.",
    "s7_price_gap+cancel_hover": "Final price is above the estimate AND the user is hovering cancel. About to drop off.",
    "early_overwhelm": "Many field edits early in the funnel. The user looks overwhelmed.",
    "repeated_back_nav": "Back-and-forth navigation. Friction, possibly lost.",
    "gbm_model_missing": "Detector model missing — fall back to a gentle, generic nudge.",
}

# Canonical intervention vocabulary (mirrors coach/policy.py + coach/realize.py).
_INTERVENTION_TYPES = (
    "price_reframe",          # €/day framing, market comparison
    "explain_price",          # transparency on the final price
    "explain_advisory_alt",   # Opt.Plus needs a call; Optimal is fully online
    "justify_price",          # justify the jump vs. cheaper alt; save-progress option
    "callback",               # offer a human handoff
    "back_nav_help",          # generic "need a hand?" nudge
)


def _decode_trigger(reason: str) -> str:
    """Detector codes -> hint. Unknown / free-form reasons are returned verbatim."""
    if not reason:
        return "Unspecified — judge from the signals."
    if reason in _TRIGGER_HINTS:
        return _TRIGGER_HINTS[reason]
    if reason.startswith("gbm:"):
        return f"GBM detector fired ({reason}). Treat as elevated drop-off risk; pick the intervention type that best fits the step."
    # LLM intervention model produces a free-form strategy description.
    return reason


class LLMCoachBot:
    """Chat-style Conversion Coach. One instance per simulation run."""

    SYSTEM_PROMPT = (
        "You are the UNIQA Conversion Coach. You appear in-page to help a user navigating an online "
        "health insurance funnel (steps S1..S12 of the journey state machine).\n\n"
        "Speak in one short, plain-language message. Match the user's apparent style: 'Online Affine' "
        "users want fast, transparent facts; 'Service Affine' users want reassurance and an easy offer of "
        "human help; 'Hybrids' want a clear comparison.\n\n"
        "When useful, anchor your wording on one of the canonical intervention types: "
        + ", ".join(_INTERVENTION_TYPES) + ".\n"
        "  - price_reframe: €/day framing or market comparison (typically at S4_INITIAL_PRICE).\n"
        "  - explain_price: transparency about the final, individualized price (typically at S7_FINAL_PRICE).\n"
        "  - explain_advisory_alt: contrast advisory-only tariffs with fully-online ones (S4).\n"
        "  - justify_price: explain a higher-than-expected final price + offer to save progress (S7).\n"
        "  - callback: gracefully offer a human callback (early steps for service-affine users).\n"
        "  - back_nav_help: generic 'need a hand?' nudge when the user is bouncing back and forth.\n\n"
        "Your response MUST be a single JSON object:\n"
        " - 'coach_message': (string) the exact message shown to the user.\n"
        " - 'intervention_type': (string, optional) one of the canonical types above, or null if none fits.\n"
    )

    def __init__(self, model_name: str):
        self.llm_client = LLMClient(model=model_name)
        self.history = []
        self.system_prompt = self.SYSTEM_PROMPT

    def get_intervention(
        self,
        funnel_step: str,
        turn_data: dict,
        trigger_reason: str,
        persona_hint: Optional[str] = None,
    ) -> str:
        action = turn_data.get("action") or {}
        signals = turn_data.get("signals") or {}
        session_data = turn_data.get("session_data_so_far") or {}
        reasoning = turn_data.get("reasoning")

        trigger_hint = _decode_trigger(trigger_reason)

        # Surface only the signal fields that matter for messaging. Keeping the prompt
        # compact also keeps the chat model focused.
        signal_view = {
            "step": signals.get("step"),
            "dwell_current_s": signals.get("dwell_current_s"),
            "dwell_total_s": signals.get("dwell_total_s"),
            "back_nav_count": signals.get("back_nav_count"),
            "field_change_count": signals.get("field_change_count"),
            "tariff_hover_count": signals.get("tariff_hover_count"),
            "tariff_selected": signals.get("tariff_selected"),
            "advisory_tariff_clicked": signals.get("advisory_tariff_clicked"),
            "external_tab_opens": signals.get("external_tab_opens"),
            "price_gap_eur": signals.get("price_gap_eur"),
            "hover_cancel_count": signals.get("hover_cancel_count"),
        }

        persona_line = f"Persona hint: {persona_hint}\n" if persona_hint else ""

        user_prompt = (
            f"Current step: {funnel_step}\n"
            f"{persona_line}"
            f"User's last action: {json.dumps(action)}\n"
            f"User's reasoning (if any): {reasoning}\n"
            f"Live signals: {json.dumps(signal_view)}\n"
            f"Data collected so far: {json.dumps(session_data)}\n"
            f"Trigger reason: {trigger_reason!r}\n"
            f"What this means: {trigger_hint}\n\n"
            "Write one short, in-character coach message that matches the step and signals. "
            "Respond with JSON."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
            {"role": "user", "content": user_prompt},
        ]

        raw_response = self.llm_client.chat_completion(messages)

        parsed = loads_lenient(raw_response)
        if parsed is None:
            print(f"ERROR: Failed to decode Coach LLM response into JSON: {raw_response}")
            return "It seems you might need some help. You can easily reach our customer service if you have questions."

        message = parsed.get(
            "coach_message",
            "It seems you might need some help. You can easily reach our customer service if you have questions.",
        )
        self.history.append({"role": "user", "content": user_prompt})
        self.history.append({"role": "assistant", "content": raw_response})
        return message
