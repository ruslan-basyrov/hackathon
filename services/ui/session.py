"""Per-page-load simulator state for the NiceGUI viewer.

A `Session` wraps one episode of the same simulator the runtime uses:
`StubAgent` + state machine + `signals.extract` + `coach.coach`. Seeding is
identical to `runner.run` (`random.Random(f"{seed}:{episode}")`) so a given
(seed, episode) selects the same "user" in the UI as in the CLI.

Three driver modes share the same simulator core:

  * **auto mode** - `step_once()` consults the coach, lets `StubAgent` choose
    an action, and applies it. This is the timer-driven path used by the
    debug viewer (`/`), the auto-play /journey demo, and all the tests.

  * **interactive mode** - the human is the driver. The UI calls
    `consult_coach(virtual_dwell_s=...)` to ask "would the coach fire right
    now?" (the wall-clock dwell since this state is entered is added to the
    signal), and `apply_action(action)` to apply a user-built `Action`.
    `StubAgent` is not used.

  * **live mode** - `step_once()` calls the `SimulationEngine` which uses the
    `LLMBot` to drive the simulation. This shows a real-time graphical
    simulation of the LLM bot's behavior.

The split (`consult_coach` / `apply_action`) is what lets interactive mode
reuse the rest of the substrate unchanged.
"""
from __future__ import annotations

import copy
import os
import random
import time
from typing import Optional
from pathlib import Path

from agent_stub import StubAgent
from coach import coach as coach_fn, Intervention
from runner import load_config
from signals import Record, Signals, extract
from state_machine import Action, Step, is_terminal, step
from simulation.engine import SimulationEngine

# Project root, so config.yaml and other assets can be found.
_REPO_ROOT = Path(__file__).resolve().parents[2]


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
        mode: str = "auto",
    ):
        self.seed = int(seed)
        self.episode = int(episode)
        self.persona = persona
        self.mode = mode
        self.interactive = (mode == "interactive")

        # Ensure config_path is absolute
        if not os.path.isabs(config_path):
            config_path = os.path.join(_REPO_ROOT, config_path)

        self.cfg = copy.deepcopy(load_config(config_path))
        self.cfg["detection"]["method"] = method
        self.cfg["detection"]["gbm_threshold"] = float(gbm_threshold)

        self.rng = random.Random(f"{self.seed}:{self.episode}")

        if self.mode == 'live':
            # Use 'rule' or 'off' based on the method, 'threshold' is mapped to 'rule' in the engine context
            engine_method = "rule" if method == "threshold" else method
            if engine_method not in ("off", "rule", "llm", "gbm"):
                engine_method = "rule"  # fallback
            
            # The SimulationEngine now handles finding the personas.json using _REPO_ROOT
            self.engine = SimulationEngine(
                model_name="deepseek-ai/DeepSeek-V4-Flash",
                intervention_mode=engine_method,
                coach_mode='chat',
            )
            
            # Map the UI persona names to the segment names expected by personas.json
            segment_map = {
                "judith": "segment_1",
                "franz": "segment_2",
                "peter": "segment_3"
            }
            engine_segment = segment_map.get(persona, persona)

            self.engine.start_simulation(segment_id=engine_segment)
            self.state: Step = self.engine.funnel.current_state
            self.history: list[Record] = self.engine.funnel.history
        else:
            self.engine = None
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
        now = time.time()
        self.state_entry_time = now
        self.last_action_time = now
        self.shown_intervention_step: Optional[int] = None

    def is_done(self) -> bool:
        if self.mode == 'live':
            return self.engine.funnel.is_terminal()
        return is_terminal(self.state)

    def _compute_signals(self) -> Signals:
        sig = extract(self.state, self.history)
        if self.state == Step.S7_FINAL_PRICE and self.provisional is not None:
            sig.price_gap_eur = round(self.provisional * self.surcharge, 2)
        return sig

    def consult_coach(self, virtual_dwell_s: float = 0.0):
        sig = self._compute_signals()
        if virtual_dwell_s > 0:
            sig.dwell_current_s += virtual_dwell_s
            sig.dwell_total_s += virtual_dwell_s
        intervention = coach_fn(sig, self.persona, self.cfg)
        self.last_signal = sig
        return sig, intervention

    def apply_action(self, action: Action) -> dict:
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
            self.shown_intervention_step = None
        return {"from_step": int(prev_state), "to_step": int(self.state),
                "action": action}

    def wall_clock_dwell(self) -> float:
        return time.time() - self.last_action_time

    def step_once(self):
        if self.is_done():
            return None

        if self.mode == 'live':
            turn_data = self.engine.step()
            if turn_data is None:
                return None

            self.state = self.engine.funnel.current_state
            self.history = self.engine.funnel.history
            self.last_action = turn_data.get('action')

            prices = self.cfg["tariff_prices"]
            if self.last_action and self.last_action.type == "select" and self.last_action.target in prices:
                self.provisional = prices[self.last_action.target]

            intervention_data = turn_data.get('coach_intervention')
            intervention = None
            if intervention_data:
                intervention = Intervention(
                    step=int(self.engine.funnel.current_state),
                    type=intervention_data['trigger_context'],
                    mode=self.engine.coach_mode,
                    effectiveness=0.0,
                    text=intervention_data['coach_message'],
                    persona=self.persona,
                )
                # Attach chat history directly to the intervention object
                intervention.chat_history = intervention_data.get('chat_history')

            if intervention is not None:
                self.fire_count += 1
            self.last_intervention = intervention

            return {
                "from_step": turn_data['state'],
                "to_step": turn_data['next_state'],
                "action": self.last_action,
                "signals": turn_data['signals'],
                "intervention": intervention,
            }

        sig, intervention = self.consult_coach()
        action: Action = self.agent.act(self.state, sig, intervention, self.rng)
        result = self.apply_action(action)
        if intervention is not None:
            self.fire_count += 1
        self.last_intervention = intervention
        result["signals"] = sig
        result["intervention"] = intervention
        return result
