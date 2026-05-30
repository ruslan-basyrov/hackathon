"""Detection layer — WHEN to intervene. Phase 2: transparent signal thresholds.

Returns (fire: bool, reason: str). Phase 3 swaps a GBM in behind this same
(signals, cfg) -> (bool, ...) shape; this threshold version stays as the ablation.

Rules are ORed, most-specific-first, each keyed to a persona signature (§5 Phase 2):
  * S7 price-gap + cancel hover  -> Franz at the final price (genuine exit risk)
  * S4 long dwell                -> Judith hesitating at the price table
  * early form re-edits          -> Peter, genuinely overwhelmed (vs a confident Peter
                                     who breezes through and self-serves)
  * repeated back-navigation     -> generic friction (mostly inert until the P4 bots)

Two deliberate non-triggers (they caused unnecessary fires — see the Phase 2 fix):
  * advisory-tariff engagement is NOT a trigger. A quick glance at Opt.Plus/Premium is
    decisive shoppers checking, not hesitation; the "this needs a call" message is a
    static tooltip, not a nudge. It remains a SIGNAL (a feature for the GBM), just not
    a threshold trigger — otherwise Franz gets coached at S4 where he's not at risk.
  * raw dwell is NOT the early-overwhelm trigger; form re-editing is. Every Peter
    dwells; only the struggling ones re-edit, and those are the ones worth routing.
"""
from __future__ import annotations

from typing import Tuple

S4 = 4
S7 = 7


def detect(signals, cfg_detection: dict) -> Tuple[bool, str]:
    s = signals
    d = cfg_detection

    # Final-price near-abandonment (Franz): the price jumped and they're hovering cancel.
    if s.step == S7 and s.price_gap_eur > d["price_gap_threshold"] and s.hover_cancel_count >= 1:
        return True, "s7_price_gap+cancel_hover"

    # Price-screen hesitation (Judith): genuinely lingering on the table.
    if s.step == S4 and s.dwell_current_s > d["dwell_threshold_s"]:
        return True, "s4_dwell"

    # Early overwhelm (Peter): repeated form re-edits with little progress.
    if s.field_change_count >= d["overwhelm_changes"] and s.steps_completed < d["early_overwhelm_max_steps"]:
        return True, "early_overwhelm"

    # Generic friction.
    if s.back_nav_count >= d["back_nav_threshold"]:
        return True, "repeated_back_nav"

    return False, ""
