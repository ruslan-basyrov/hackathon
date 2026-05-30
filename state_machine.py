"""Journey state machine — pure mechanics, NO randomness.

In-scope private-doctor / "myself" / Start–Optimal path only. Step 5 (the hospital
add-on) is deliberately absent: states jump S4 -> S6.

`Action` is defined here because it is the machine's transition input; the spec's
frozen definition is reproduced verbatim. Do not change its field set without
surfacing the change first (see BUILD_SPEC §1, §3).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Literal, Optional


# ---- FROZEN: Action ---------------------------------------------------------
@dataclass
class Action:
    type: Literal[
        "continue", "back", "select", "hover", "change_field", "open_tab", "abandon"
    ]
    target: Optional[str] = None   # tariff/element/field, or branch choice
    dwell_s: float = 0.0           # seconds on the current screen BEFORE this action


# ---- States -----------------------------------------------------------------
class Step(IntEnum):
    START = 0
    S1_COVERAGE_TYPE = 1     # "doctor" vs "hospital"
    S2_FOR_WHOM = 2          # "myself" vs "others"
    S3_PERSONAL_DATA = 3     # DOB + social insurance number
    S4_INITIAL_PRICE = 4     # 4 tariffs, provisional premium   <- 66% drop
    S6_HEALTH_QS = 6         # health questions                 <- 24% drop (attributed; see §4)
    S7_FINAL_PRICE = 7       # individualized premium           <- 78% drop
    S12_CLOSING = 12         # data, payment, consents, confirm
    CONVERTED = 90           # terminal — online purchase
    ABANDONED = 91           # terminal — closed tab
    ROUTED_ADVISOR = 92      # terminal — selected an out-of-scope option


# Maps config drop-off keys ("S4"/"S6"/"S7") onto the enum.
NAME2STEP = {
    "S4": Step.S4_INITIAL_PRICE,
    "S6": Step.S6_HEALTH_QS,
    "S7": Step.S7_FINAL_PRICE,
}

# Branch targets.
IN_SCOPE_TARGETS = {"doctor", "myself", "Start", "Optimal"}
OUT_OF_SCOPE_TARGETS = {"hospital", "both", "others", "OptPlus", "Premium"}

# Linear in-scope path.
NEXT = {
    Step.START: Step.S1_COVERAGE_TYPE,
    Step.S1_COVERAGE_TYPE: Step.S2_FOR_WHOM,
    Step.S2_FOR_WHOM: Step.S3_PERSONAL_DATA,
    Step.S3_PERSONAL_DATA: Step.S4_INITIAL_PRICE,
    Step.S4_INITIAL_PRICE: Step.S6_HEALTH_QS,
    Step.S6_HEALTH_QS: Step.S7_FINAL_PRICE,
    Step.S7_FINAL_PRICE: Step.S12_CLOSING,
    Step.S12_CLOSING: Step.CONVERTED,
}
PREV = {
    Step.S2_FOR_WHOM: Step.S1_COVERAGE_TYPE,
    Step.S3_PERSONAL_DATA: Step.S2_FOR_WHOM,
    Step.S4_INITIAL_PRICE: Step.S3_PERSONAL_DATA,
    Step.S6_HEALTH_QS: Step.S4_INITIAL_PRICE,
    Step.S7_FINAL_PRICE: Step.S6_HEALTH_QS,
    Step.S12_CLOSING: Step.S7_FINAL_PRICE,
}

_TERMINALS = {Step.CONVERTED, Step.ABANDONED, Step.ROUTED_ADVISOR}


def is_terminal(state: Step) -> bool:
    return state in _TERMINALS


def step(state: Step, action: Action) -> Step:
    """(state, action) -> next state. The machine is permissive about ordering:
    the agent is responsible for selecting before continuing. `select` of an
    in-scope target is a no-op on state (the screen stays put); `select` of an
    out-of-scope target routes to the advisor immediately.
    """
    if is_terminal(state):
        return state
    t = action.type
    if t == "abandon":
        return Step.ABANDONED
    if t == "select":
        if action.target in OUT_OF_SCOPE_TARGETS:
            return Step.ROUTED_ADVISOR
        return state  # in-scope selection: no state change
    if t in ("hover", "change_field", "open_tab"):
        return state  # signal-generating, non-advancing
    if t == "back":
        return PREV.get(state, state)
    if t == "continue":
        return NEXT.get(state, state)
    return state
