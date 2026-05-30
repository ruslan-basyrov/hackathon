"""Scripted stub agent — Phase 1 driver.

Behaviour that the acceptance test depends on:
  * Exactly ONE abandonment draw per critical step (S4/S6/S7), made the first time
    the agent is asked to act on that step. This is what makes the no-coach baseline
    deterministic at prod(survivals) = 0.34 * 0.76 * 0.22 ~= 5.68%.
  * Phase 1 always picks in-scope branches (doctor / myself / Start|Optimal), so no
    episode routes to the advisor. `p_out_of_scope_branch` is wired but defaults to 0.
  * dwell / tariff-hover / cancel-hover noise is emitted for signal variance but never
    triggers abandonment, so it does not move the baseline.

Phase 2 note: the abandonment draw already multiplies by (1 - intervention.effectiveness),
so swapping the no-op coach for a real one immediately makes interventions reduce drop-off
with no change to this file.
"""
from __future__ import annotations

import random
from typing import Optional

from state_machine import Action, NAME2STEP, Step


class StubAgent:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.p = {NAME2STEP[k]: v for k, v in cfg["p_dropoff"].items()}
        self.dwell_mean = float(cfg.get("dwell_mean_s", 12.0))
        self.tariff_hover_max = int(cfg.get("tariff_hover_max", 3))
        self.cancel_hover_prob = float(cfg.get("cancel_hover_prob", 0.3))
        self.reset()

    def reset(self) -> None:
        self._decided = set()      # critical steps where abandonment is already drawn
        self._selected = set()     # steps where the branch/tariff select is emitted
        self._s4_hovers_left = None
        self._s7_hovered = False

    def _dwell(self, rng: random.Random) -> float:
        return max(0.0, rng.gauss(self.dwell_mean, self.dwell_mean * 0.4))

    def act(self, state: Step, signals, intervention, rng: random.Random) -> Action:
        dwell = self._dwell(rng)

        if state == Step.START:
            return Action("continue", dwell_s=dwell)

        # --- one-time abandonment decision at a critical step ---
        if state in self.p and state not in self._decided:
            self._decided.add(state)
            eff = (1.0 - intervention.effectiveness) if intervention else 1.0
            if rng.random() < self.p[state] * eff:
                return Action("abandon", dwell_s=dwell)

        # --- in-scope branch selections (Phase 1 never routes out of scope) ---
        if state == Step.S1_COVERAGE_TYPE and state not in self._selected:
            self._selected.add(state)
            return Action("select", "doctor", dwell)
        if state == Step.S2_FOR_WHOM and state not in self._selected:
            self._selected.add(state)
            return Action("select", "myself", dwell)

        # --- S4 price table: optional hovers, then pick an in-scope tariff ---
        if state == Step.S4_INITIAL_PRICE:
            if self._s4_hovers_left is None:
                self._s4_hovers_left = rng.randint(0, self.tariff_hover_max)
            if self._s4_hovers_left > 0:
                self._s4_hovers_left -= 1
                return Action("hover", rng.choice(["Start", "Optimal", "OptPlus", "Premium"]), dwell)
            if state not in self._selected:
                self._selected.add(state)
                return Action("select", rng.choice(["Start", "Optimal"]), dwell)
            return Action("continue", dwell_s=dwell)

        # --- S7 final price: occasional cancel-hover (near-abandonment tell) ---
        if state == Step.S7_FINAL_PRICE and not self._s7_hovered:
            self._s7_hovered = True
            if rng.random() < self.cancel_hover_prob:
                return Action("hover", "cancel", dwell)

        return Action("continue", dwell_s=dwell)
