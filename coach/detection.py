"""Detection layer — WHEN to intervene. Phase 2: transparent signal thresholds.

Returns (fire: bool, reason: str). The reason string is for the trace/logs and the
"traceable decision rules" the rubric wants. Phase 3 swaps in a GBM behind this same
(signals, cfg) -> (bool, ...) shape, selectable via config; this threshold version is
kept as the ablation baseline.

Rules are ORed and ordered most-specific-first. Each maps to a persona signature
(BUILD_SPEC §5 Phase 2):
  * S7 price-gap + cancel hover     -> Franz at the final price
  * S4 long dwell / advisory click  -> Judith at the price screen
  * early high-dwell + low progress -> Peter, overwhelmed before the price
  * repeated back-navigation        -> generic friction (mostly inert in Phase 2;
                                        real back-nav arrives with the LLM bots in P4)
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

    # Price-screen hesitation (Judith): long dwell on the table, or engaging an
    # advisory-only tariff (the "wall").
    if s.step == S4 and (s.dwell_current_s > d["dwell_threshold_s"] or s.advisory_tariff_clicked):
        return True, "s4_dwell_or_advisory"

    # Early overwhelm (Peter): a lot of time on an early step with little progress.
    if s.dwell_current_s > d["early_overwhelm_dwell_s"] and s.steps_completed < d["early_overwhelm_max_steps"]:
        return True, "early_overwhelm"

    # Generic friction.
    if s.back_nav_count >= d["back_nav_threshold"]:
        return True, "repeated_back_nav"

    return False, ""
