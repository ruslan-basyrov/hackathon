"""Per-page-load simulator state for the NiceGUI viewer.

A `Session` wraps one episode of the same simulator the runtime uses:
`StubAgent` + state machine + `signals.extract` + `coach.coach`. Seeding is
identical to `runner.run` (`random.Random(f"{seed}:{episode}")`) so a given
(seed, episode) selects the same "user" in the UI as in the CLI - critical for
the URL-driven test contract (BUILD_SPEC §Phase 3.5).

`step_once()` advances the simulator by exactly one action: it computes signals,
asks the coach, runs the agent (whose drop-off is the only stochastic bit), then
applies the action. The returned dict is what the UI binds its panels and the
popup to. No randomness lives in this file - it just choreographs the existing
modules.
"""
from __future__ import annotations

import copy
import random
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
    ):
        self.seed = int(seed)
        self.episode = int(episode)
        self.persona = persona
        # local copy so UI knob flips never bleed back into the on-disk config
        self.cfg = copy.deepcopy(load_config(config_path))
        self.cfg["detection"]["method"] = method
        self.cfg["detection"]["gbm_threshold"] = float(gbm_threshold)

        # IMPORTANT: same seeding scheme as runner.run - the UI is the same user
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

    def is_done(self) -> bool:
        return is_terminal(self.state)

    def step_once(self):
        """Advance by one action. Returns a dict describing what happened, or None
        if the episode is already terminal."""
        if self.is_done():
            return None

        prices = self.cfg["tariff_prices"]
        sig = extract(self.state, self.history)
        if self.state == Step.S7_FINAL_PRICE and self.provisional is not None:
            sig.price_gap_eur = round(self.provisional * self.surcharge, 2)

        intervention = coach_fn(sig, self.persona, self.cfg)
        action: Action = self.agent.act(self.state, sig, intervention, self.rng)

        if action.type == "select" and action.target in prices:
            self.provisional = prices[action.target]

        self.history.append(Record(int(self.state), action))
        prev_state = self.state
        self.state = step(self.state, action)
        self.step_count += 1
        if intervention is not None:
            self.fire_count += 1

        self.last_signal = sig
        self.last_intervention = intervention
        self.last_action = action
        return {
            "from_step": int(prev_state),
            "to_step": int(self.state),
            "action": action,
            "signals": sig,
            "intervention": intervention,
        }
