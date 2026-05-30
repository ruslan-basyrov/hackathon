"""Scripted stub agent — Phases 1-2 driver.

Per critical step the agent runs three phases across successive act() calls:
  1. SIGNATURE  — emit non-state-changing actions (hovers / form re-edits / tab opens)
                  that surface this persona's signals, so detection can fire BEFORE the
                  abandonment decision. (No real back-navigation — that changes state
                  mid-step; it arrives with the LLM bots in Phase 4.)
  2. DECISION   — draw abandonment ONCE. A stay-intervention multiplies p by
                  (1 - effectiveness); a handoff-intervention (handled at the top of
                  act(), any step) diverts to a service contact instead.
  3. PROGRESS   — select (S1/S2/S4) then continue.

Per-episode sub-profiles: a persona with `confident_prob` is heterogeneous. Each episode
reset() draws confident vs struggling and swaps the drop-off / dwell / signature maps:
  * struggling -> high dwell + form re-edits -> detection fires -> routed
  * confident  -> base dwell, no re-edits    -> detection stays quiet -> self-serves
This is what makes routing SELECTIVE rather than "route everyone" (the Phase 2 fix).

Invariants:
  * Exactly one abandonment draw per critical step -> the no-coach `global` baseline
    sits at prod(survivals) ~= 5.68% regardless of signature noise preceding it.
  * `self.fires` records each acted-on intervention as (mode, would_abandon_base) for
    any downstream metric that wants the step-level counterfactual.
"""
from __future__ import annotations

import random

from state_machine import Action, NAME2STEP, Step


class StubAgent:
    def __init__(self, cfg: dict, persona: str = "global"):
        self.cfg = cfg
        self.persona = persona
        self.profile = cfg["personas"][persona]
        # These flags are profile-level (the personas that use confident_prob have none
        # of them, so confident-mode never emits advisory/external/cancel actions).
        self.advisory = bool(self.profile.get("advisory_interest", False))
        self.external_tab = bool(self.profile.get("external_tab", False))
        self.s7_cancel = bool(self.profile.get("s7_cancel", False))
        self.dwell_mean = float(cfg.get("dwell_mean_s", 12.0))
        self.accept_prob = float(cfg.get("handoff_accept_prob", {}).get(persona, 0.0))
        self.reset()

    def _maps(self, confident: bool):
        prof = self.profile
        if confident:
            pd = prof.get("confident_p_dropoff", prof.get("p_dropoff", {}))
            return ({NAME2STEP[k]: v for k, v in pd.items()}, {}, {}, {})
        return (
            {NAME2STEP[k]: v for k, v in prof.get("p_dropoff", {}).items()},
            {NAME2STEP[k]: v for k, v in prof.get("dwell_mult", {}).items()},
            {NAME2STEP[k]: v for k, v in prof.get("sig_hovers", {}).items()},
            {NAME2STEP[k]: v for k, v in prof.get("sig_changes", {}).items()},
        )

    def reset(self, rng=None) -> None:
        self._decided = set()
        self._selected = set()
        self._sig = {}
        self._diverted = False
        self.fires = []
        confident = False
        if rng is not None and "confident_prob" in self.profile:
            confident = rng.random() < float(self.profile["confident_prob"])
        self._confident = confident
        self.p, self.dwell_mult, self.sig_hovers, self.sig_changes = self._maps(confident)

    def _dwell(self, state: Step, rng: random.Random) -> float:
        base = max(0.0, rng.gauss(self.dwell_mean, self.dwell_mean * 0.4))
        return base * self.dwell_mult.get(state, 1.0)

    def _init_sig(self, state: Step) -> None:
        if state in self._sig:
            return
        self._sig[state] = {
            "hover": self.sig_hovers.get(state, 0),
            "change": self.sig_changes.get(state, 0),
            "tab": 1 if (self.external_tab and state == Step.S4_INITIAL_PRICE) else 0,
            "cancel": 1 if (self.s7_cancel and state == Step.S7_FINAL_PRICE) else 0,
        }

    def act(self, state: Step, signals, intervention, rng: random.Random) -> Action:
        dwell = self._dwell(state, rng)

        if state == Step.START:
            return Action("continue", dwell_s=dwell)

        # --- handoff diversion (any step the coach offers one) ---
        if intervention and getattr(intervention, "mode", "stay") == "handoff" and not self._diverted:
            if rng.random() < self.accept_prob:
                self._diverted = True
                self.fires.append(("handoff", None))
                return Action("select", "advisor_callback", dwell)
            # not accepted this turn: fall through

        # --- signature phase: surface signals before deciding ---
        self._init_sig(state)
        b = self._sig[state]
        if b["hover"] > 0:
            b["hover"] -= 1
            if self.advisory and b["hover"] == 0:
                return Action("hover", rng.choice(["OptPlus", "Premium"]), dwell)
            return Action("hover", rng.choice(["Start", "Optimal"]), dwell)
        if b["cancel"] > 0:
            b["cancel"] -= 1
            return Action("hover", "cancel", dwell)
        if b["tab"] > 0:
            b["tab"] -= 1
            return Action("open_tab", "comparison", dwell)
        if b["change"] > 0:
            b["change"] -= 1
            return Action("change_field", "form", dwell)

        # --- decision phase (once per critical step) ---
        if state in self.p and state not in self._decided:
            self._decided.add(state)
            u = rng.random()
            p_base = self.p[state]
            would_abandon = u < p_base
            eff = 0.0
            if intervention and getattr(intervention, "mode", "stay") == "stay":
                self.fires.append(("stay", would_abandon))
                eff = intervention.effectiveness
            if u < p_base * (1.0 - eff):
                return Action("abandon", dwell_s=dwell)

        # --- progress phase ---
        if state == Step.S1_COVERAGE_TYPE and state not in self._selected:
            self._selected.add(state)
            return Action("select", "doctor", dwell)
        if state == Step.S2_FOR_WHOM and state not in self._selected:
            self._selected.add(state)
            return Action("select", "myself", dwell)
        if state == Step.S4_INITIAL_PRICE and state not in self._selected:
            self._selected.add(state)
            return Action("select", rng.choice(["Start", "Optimal"]), dwell)
        return Action("continue", dwell_s=dwell)
