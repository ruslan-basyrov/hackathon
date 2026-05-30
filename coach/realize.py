"""Realization layer — phrasing an intervention once the policy has chosen it.
Phase 2: templates. Phase 5 swaps an LLM in behind this same (type, signals) -> str shape.

In Phase 2 the text is for the trace / demo only — the scripted agent reacts to the
intervention's *effectiveness/mode*, not to the words. (Wording efficacy becomes real
in Phase 4-5, when LLM persona bots actually read it.)
"""
from __future__ import annotations

_PRICES = {"Start": 38.74, "Optimal": 68.14}


def realize(itype: str, signals) -> str:
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
    return ""
