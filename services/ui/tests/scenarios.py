"""Fixed (seed, episode) pairs that produce one popup per persona at its
documented detection step. These were located once by walking the simulator
under the threshold detector (see git history for the discovery script).

The headless gate and the on-stage demo both iterate this list - one source of
truth for the test contract.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Scenario:
    name: str
    persona: str
    method: str
    seed: int
    episode: int
    expected_fire_step: int    # the step where the coach is expected to fire
    expected_intervention_type: str
    narration: str             # on-screen line for the demo path


SCENARIOS = [
    Scenario(
        name="judith_s4",
        persona="judith",
        method="threshold",
        seed=0, episode=0,
        expected_fire_step=4,
        expected_intervention_type="price_reframe",
        narration=(
            "Judith lingers on the price table — the coach reframes "
            "Optimal as roughly €2.27 a day."
        ),
    ),
    Scenario(
        name="franz_s7",
        persona="franz",
        method="threshold",
        seed=0, episode=16,
        expected_fire_step=7,
        expected_intervention_type="justify_price",
        narration=(
            "Franz sees the final price jump and hovers cancel — "
            "the coach justifies the surcharge and keeps him online."
        ),
    ),
    Scenario(
        name="peter_early",
        persona="peter",
        method="threshold",
        seed=0, episode=0,
        expected_fire_step=2,
        expected_intervention_type="callback",
        narration=(
            "Peter re-edits the form early — the coach offers "
            "a callback before he gives up."
        ),
    ),
]
