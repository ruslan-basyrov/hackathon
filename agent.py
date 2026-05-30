"""The driver contract. FROZEN: do not change `act`'s signature without surfacing
the change first (BUILD_SPEC §1, §3).

Phase 1: agent_stub.StubAgent (scripted; the only place stochastic drop-off lives).
Phase 4: agent_llm.* — Judith/Franz/Peter, emitting the SAME Action schema, reached
over INFERENCE_BASE_URL + MODEL_NAME.
"""
from __future__ import annotations

from typing import Optional, Protocol

from signals import Signals
from state_machine import Action, Step


class Agent(Protocol):
    def reset(self, rng=None) -> None:
        """Clear per-episode state. `rng` (optional) lets the agent draw a per-episode
        sub-profile, e.g. a persona's sub-segments. Called by the runner each episode."""
        ...

    def act(self, state: Step, signals: Signals, intervention, rng) -> Action:
        """Produce the next action. An intervention (Phase 2+) may lower this step's
        drop-off probability or swap a branch choice. In Phase 1 there is no coach,
        so `intervention` is always None."""
        ...
