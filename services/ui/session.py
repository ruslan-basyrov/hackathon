"""Per-page-load simulator state for the NiceGUI viewer.

A `Session` wraps one episode of the same simulator the runtime uses:
`StubAgent` + state machine + `signals.extract` + `coach.coach`. Seeding is
identical to `runner.run` (`random.Random(f"{seed}:{episode}")`) so a given
(seed, episode) selects the same "user" in the UI as in the CLI.

Two driver modes share the same simulator core:

  * **auto mode** - `step_once()` consults the coach, lets `StubAgent` choose
    an action, and applies it. This is the timer-driven path used by the
    debug viewer (`/`), the auto-play /journey demo, and all the tests.

  * **interactive mode** - the human is the driver. The UI calls
    `consult_coach(virtual_dwell_s=...)` to ask "would the coach fire right
    now?" (the wall-clock dwell since this state was entered is added to the
    signal), and `apply_action(action)` to apply a user-built `Action`.
    `StubAgent` is not used.

The split (`consult_coach` / `apply_action`) is what lets interactive mode
reuse the rest of the substrate unchanged.
"""
from __future__ import annotations

import copy
import random
import time
from typing import Optional

from agent_stub import StubAgent
from coach import coach as coach_fn
from runner import load_config
from signals import Record, Signals, extract
from state_machine import Action, Step, is_terminal, step


class Session:
    def __init__(
        self,
        *,
        seed: int,
        episode: int,
        persona: str,
        method: str,
        gbm_threshold: float = 0.85,
        config_path: str = "config.yaml",
        interactive: bool = False,
    ):
        self.seed = int(seed)
        self.episode = int(episode)
        self.persona = persona
        self.interactive = interactive
        self.cfg = copy.deepcopy(load_config(config_path))
        self.cfg["detection"]["method"] = method
        self.cfg["detection"]["gbm_threshold"] = float(gbm_threshold)

        # same seeding as runner.run - same (seed, ep) is the same user
        self.rng = random.Random(f"{self.seed}:{self.episode}")
        self.agent = StubAgent(self.cfg, persona)
        self.agent.reset(self.rng)
        self.state: Step = Step.START
        self.history: list[Record] = []
        self.surcharge = self.rng.uniform(
            self.cfg["surcharge"]["low"], self.cfg["surcharge"]["high"]
        )
        self.provisional: Optional[float] = None
        self.last_signal: Optional[Signals] = None
        self.last_intervention = None
        self.last_action: Optional[Action] = None
        self.step_count = 0
        self.fire_count = 0
        # wall-clock anchor used by interactive mode: time of the most recent
        # action OR of state entry, whichever is later. Each user click's
        # `dwell_s` is `time.time() - last_action_time`. The watchdog adds the
        # same delta to current/total dwell so dwell-based detection sees real
        # time on the page.
        now = time.time()
        self.state_entry_time = now
        self.last_action_time = now
        # the step at which the last shown popup fired - prevents the watchdog
        # from re-firing the same intervention every tick.
        self.shown_intervention_step: Optional[int] = None

    def is_done(self) -> bool:
        return is_terminal(self.state)

    # ---- shared simulator primitives ---------------------------------------
    def _compute_signals(self) -> Signals:
        sig = extract(self.state, self.history)
        if self.state == Step.S7_FINAL_PRICE and self.provisional is not None:
            sig.price_gap_eur = round(self.provisional * self.surcharge, 2)
        return sig

    def consult_coach(self, virtual_dwell_s: float = 0.0):
        """Compute signals (optionally adding `virtual_dwell_s` to the current
        and total dwell - used by the interactive-mode watchdog so dwell-based
        detection sees the human's wall-clock time on the page) and ask the
        coach. Does NOT apply any action."""
        sig = self._compute_signals()
        if virtual_dwell_s > 0:
            sig.dwell_current_s += virtual_dwell_s
            sig.dwell_total_s += virtual_dwell_s
        intervention = coach_fn(sig, self.persona, self.cfg)
        self.last_signal = sig
        return sig, intervention

    def apply_action(self, action: Action) -> dict:
        """Apply an externally-built `Action` (interactive mode) or one
        produced by the agent (auto mode). Updates history, advances state,
        binds provisional price on tariff selection, and resets the wall-clock
        dwell anchor if the state changed."""
        if self.is_done():
            return {"from_step": int(self.state), "to_step": int(self.state),
                    "action": action}
        prices = self.cfg["tariff_prices"]
        if action.type == "select" and action.target in prices:
            self.provisional = prices[action.target]
        self.history.append(Record(int(self.state), action))
        prev_state = self.state
        self.state = step(self.state, action)
        self.step_count += 1
        self.last_action = action
        now = time.time()
        self.last_action_time = now
        if self.state != prev_state:
            self.state_entry_time = now
            self.shown_intervention_step = None  # new step, new intervention possible
        return {"from_step": int(prev_state), "to_step": int(self.state),
                "action": action}

    def wall_clock_dwell(self) -> float:
        """Seconds since the most recent action (or state entry if none yet).
        Used for both the next user action's `dwell_s` AND the watchdog's
        `virtual_dwell_s` in `consult_coach`."""
        return time.time() - self.last_action_time

    # ---- auto driver (StubAgent + coach + apply) ---------------------------
    def step_once(self):
        """Auto-mode tick: consult coach, let agent act, apply. Returns the
        same dict shape as `apply_action` plus `signals` and `intervention`."""
        if self.is_done():
            return None
        sig, intervention = self.consult_coach()
        action: Action = self.agent.act(self.state, sig, intervention, self.rng)
        result = self.apply_action(action)
        if intervention is not None:
            self.fire_count += 1
        self.last_intervention = intervention
        result["signals"] = sig
        result["intervention"] = intervention
        return result
