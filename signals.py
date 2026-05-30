"""Signal extraction. `extract` is deterministic over the action history.

`price_gap_eur` is the one field NOT computed here: it derives from a per-episode
synthetic surcharge, so the runner sets it directly after calling extract (keeps this
function pure and the frozen `extract(state, history)` signature intact). See §3, §4.

Phase 2: `advisory_tariff_clicked` now also counts a *hover* on Opt.Plus/Premium —
engaging the advisory-only tariffs (the "wall") is the signal, whether clicked or
hovered. This keeps the state machine simple (a hover never routes).
"""
from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from typing import List, Optional

from state_machine import Step

Record = namedtuple("Record", ["step", "action"])


# ---- FROZEN: Signals --------------------------------------------------------
@dataclass
class Signals:
    # progress / time
    step: int
    steps_completed: int
    dwell_current_s: float
    dwell_total_s: float
    time_since_last_action_s: float
    # navigation / friction
    back_nav_count: int
    back_from_step: Optional[int]
    field_change_count: int
    # S4-specific (price table)
    tariff_hover_count: int
    advisory_tariff_clicked: bool
    tariff_selected: Optional[str]
    external_tab_opens: int
    # S7-specific (final price)
    price_gap_eur: float
    hover_cancel_count: int


def extract(state: Step, history: List[Record]) -> Signals:
    step_int = int(state)
    s4 = int(Step.S4_INITIAL_PRICE)
    s7 = int(Step.S7_FINAL_PRICE)

    continues = sum(1 for r in history if r.action.type == "continue")
    dwell_total = sum(r.action.dwell_s for r in history)
    dwell_current = sum(r.action.dwell_s for r in history if r.step == step_int)
    last_dwell = history[-1].action.dwell_s if history else 0.0

    backs = [r for r in history if r.action.type == "back"]
    field_changes = sum(1 for r in history if r.action.type == "change_field")

    tariff_hovers = sum(1 for r in history if r.action.type == "hover" and r.step == s4)
    # advisory interest: a select OR hover of an advisory-only tariff.
    advisory = any(
        r.action.type in ("select", "hover") and r.action.target in ("OptPlus", "Premium")
        for r in history
    )
    tariff_sels = [
        r.action.target
        for r in history
        if r.action.type == "select"
        and r.step == s4
        and r.action.target in ("Start", "Optimal")
    ]
    tab_opens = sum(1 for r in history if r.action.type == "open_tab")
    cancel_hovers = sum(
        1
        for r in history
        if r.action.type == "hover" and r.action.target == "cancel" and r.step == s7
    )

    return Signals(
        step=step_int,
        steps_completed=continues,
        dwell_current_s=round(dwell_current, 2),
        dwell_total_s=round(dwell_total, 2),
        time_since_last_action_s=round(last_dwell, 2),
        back_nav_count=len(backs),
        back_from_step=backs[-1].step if backs else None,
        field_change_count=field_changes,
        tariff_hover_count=tariff_hovers,
        advisory_tariff_clicked=advisory,
        tariff_selected=tariff_sels[-1] if tariff_sels else None,
        external_tab_opens=tab_opens,
        price_gap_eur=0.0,  # injected by the runner at S7
        hover_cancel_count=cancel_hovers,
    )
