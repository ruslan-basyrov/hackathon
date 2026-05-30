"""Funnel — thin wrapper around state_machine.step().

Holds:
  * current_state: Step
  * history: list[Record(step, action)]  — fed to signals.extract()
  * session_data: any persona-entered fields, kept across turns

Per-step legal Action.types and select targets are tabulated here so the LLM
bot can be told what's pickable. The actual transition is delegated to
state_machine.step(); this class does not duplicate that logic.

Two virtual action types are exposed at the funnel level and translated to the
underlying state_machine primitives in `apply()`:
  * "cancel"   -> state_machine "abandon" (lands in ABANDONED)
  * "purchase" -> state_machine "continue" at S12_CLOSING (lands in CONVERTED)
This keeps state_machine.py frozen while letting the bot emit the conversion /
cancellation as semantically named events in the simulation log.
"""
from __future__ import annotations

from typing import List

from state_machine import Action, Step, is_terminal, step as sm_step
from signals import Record


# Per-step legal action types shown to the LLM. `cancel` replaces the raw
# state_machine "abandon" name everywhere; `purchase` replaces "continue" at
# S12 only (where continue means "confirm and convert"). Other steps keep
# "continue" as the natural advance verb.
_ALLOWED_TYPES = {
    Step.START: ["continue", "cancel"],
    Step.S1_COVERAGE_TYPE: ["select", "continue", "back", "hover", "cancel"],
    Step.S2_FOR_WHOM: ["select", "continue", "back", "hover", "cancel"],
    Step.S3_PERSONAL_DATA: ["select", "continue", "back", "change_field", "hover", "cancel"],
    Step.S4_INITIAL_PRICE: ["select", "continue", "back", "hover", "open_tab", "cancel"],
    Step.S6_HEALTH_QS: ["select", "continue", "back", "change_field", "hover", "cancel"],
    Step.S7_FINAL_PRICE: ["select", "continue", "back", "hover", "cancel"],
    Step.S12_CLOSING: ["select", "purchase", "back", "change_field", "hover", "cancel"],
}

# Per-step targets that `select` recognizes. Plus the universal handoff target.
_SELECT_TARGETS = {
    Step.S1_COVERAGE_TYPE: ["doctor", "hospital"],
    Step.S2_FOR_WHOM: ["myself", "others"],
    Step.S4_INITIAL_PRICE: ["Start", "Optimal", "OptPlus", "Premium"],
}

# Free-form hover hints — used to prompt the LLM. Not enforced.
_HOVER_HINTS = {
    Step.S4_INITIAL_PRICE: ["Start", "Optimal", "OptPlus", "Premium"],
    Step.S7_FINAL_PRICE: ["cancel", "price"],
}

# Short human description per step, for the bot prompt.
STEP_DESCRIPTION = {
    Step.START: "Landing page.",
    Step.S1_COVERAGE_TYPE: "Choose coverage type: doctor visits or hospital.",
    Step.S2_FOR_WHOM: "Insure yourself or someone else.",
    Step.S3_PERSONAL_DATA: "Enter DOB and social insurance number.",
    Step.S4_INITIAL_PRICE: "Initial price table with 4 tariffs (Start, Optimal, OptPlus, Premium).",
    Step.S6_HEALTH_QS: "Answer health questions.",
    Step.S7_FINAL_PRICE: "Individualized final price.",
    Step.S12_CLOSING: (
        "Closing — data, payment, consents. Emit `purchase` to confirm and convert, "
        "or `cancel` to drop out at the final step."
    ),
}

# Virtual -> state_machine primitive translation. Anything not in this table is
# passed through unchanged.
_VIRTUAL_TO_PRIMITIVE = {
    "cancel": "abandon",
    "purchase": "continue",
}


class Funnel:
    def __init__(self):
        self.current_state: Step = Step.START
        self.history: List[Record] = []
        self.session_data: dict = {}

    # ---- introspection ------------------------------------------------------
    def get_allowed_action_types(self) -> List[str]:
        return list(_ALLOWED_TYPES.get(self.current_state, []))

    def get_select_targets(self) -> List[str]:
        base = list(_SELECT_TARGETS.get(self.current_state, []))
        # advisor_callback is a universal handoff — coach may steer the bot here later.
        return base + ["advisor_callback"]

    def get_hover_hints(self) -> List[str]:
        return list(_HOVER_HINTS.get(self.current_state, []))

    def describe(self) -> str:
        return STEP_DESCRIPTION.get(self.current_state, self.current_state.name)

    def is_terminal(self) -> bool:
        return is_terminal(self.current_state)

    # ---- transition ---------------------------------------------------------
    def apply(self, action: Action) -> Step:
        """Translates virtual action types, records the primitive Action in
        history (so signals.extract sees the canonical state_machine vocabulary),
        then advances state via state_machine.step()."""
        primitive = self._to_primitive(action)
        self.history.append(Record(step=int(self.current_state), action=primitive))
        self.current_state = sm_step(self.current_state, primitive)
        return self.current_state

    @staticmethod
    def _to_primitive(action: Action) -> Action:
        mapped = _VIRTUAL_TO_PRIMITIVE.get(action.type)
        if mapped is None:
            return action
        return Action(type=mapped, target=action.target, dwell_s=action.dwell_s)
