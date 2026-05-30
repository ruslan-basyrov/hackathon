"""Realization layer - phrasing an intervention once the policy has chosen it.

Phase 2: hand-written templates (this file's `_template_realize`).
Phase 4: LLM via `coach.llm_realize.llm_realize`, dispatched by `cfg.realize.method`.
Phase 5: same interface, just driven by LLM persona bots that actually READ the
         wording the LLM produces here.

The frozen signature is `realize(itype, signals, persona=None, cfg=None) -> str`.
`persona` and `cfg` are optional keyword extensions added in Phase 4 - callers
from Phase 2-3 (templates only) still work with the original 2-arg call.

Error policy lives here, not in `llm_realize`: if the LLM call raises and
`cfg.realize.graceful_fallback` is true (default), we return the template
wording instead. That's the property that makes the Phase 4 acceptance test
decisive - the simulator never breaks just because the endpoint is down.
"""
from __future__ import annotations

from typing import Optional

_PRICES = {"Start": 38.74, "Optimal": 68.14}


def realize(itype: str, signals, persona: Optional[str] = None,
            cfg: Optional[dict] = None) -> str:
    """Dispatch on `cfg.realize.method`. Falls back to templates if cfg is
    missing OR if LLM mode is enabled but the call fails (and fallback is on)."""
    method = "template"
    fallback = True
    if cfg is not None:
        rc = cfg.get("realize", {}) or {}
        method = rc.get("method", "template")
        fallback = bool(rc.get("graceful_fallback", True))

    if method == "llm":
        try:
            from coach.llm_realize import llm_realize
            return llm_realize(itype, signals, persona, cfg)
        except Exception:
            if not fallback:
                raise
            # fall through to template
    return _template_realize(itype, signals)


def _template_realize(itype: str, signals) -> str:
    tariff = signals.tariff_selected or "Optimal"
    per_day = round(_PRICES.get(tariff, 68.14) / 30.0, 2)
    gap = signals.price_gap_eur

    if itype == "price_reframe":
        return (f"{tariff} is about €{per_day}/day — less than a coffee — and covers "
                f"therapies, medications and medical aids.")
    if itype == "explain_price":
        return ("Your final price reflects your personal health profile. You can still "
                "complete the purchase fully online right now.")
    if itype == "explain_advisory_alt":
        return ("Opt. Plus needs a short advisory call. Optimal you can complete fully "
                "online at any time — here's how the two compare.")
    if itype == "justify_price":
        return (f"Your final price is €{gap:.2f} above the estimate, based on your health "
                f"profile. You can still finish online now.")
    if itype == "callback":
        return ("This can be a lot to weigh up. Would it be easier if someone called you "
                "to walk through it?")
    if itype == "back_nav_help":
        return ("Looks like you're going back and forth a few times. "
                "Need a hand? Tap 'Need help?' at the top or call 0800 123 456.")
    return ""
