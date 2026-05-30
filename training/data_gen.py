"""Generate (Signals -> abandoned?) training pairs from the scripted simulator.

This shares signal-generation logic with the runtime (`extract`, `agent_stub`),
so train-time and detect-time see the same feature distribution (BUILD_SPEC §5
Phase 3). Coach is OFF: we want the unmodified per-step abandonment behaviour.

For each baseline (no-coach) episode we capture `Signals` at every non-terminal
state visit, then label every captured row with the episode's final outcome
(1 = ABANDONED, else 0). One episode therefore contributes multiple rows -
this is intentional: the GBM learns risk at each step of the journey, mirroring
how the runtime calls `detect` once per state visit.
"""
from __future__ import annotations

import random
from typing import Iterable, List, Tuple

import numpy as np

from agent_stub import StubAgent
from coach.features import FEATURE_NAMES, signals_to_vec
from signals import Record, Signals, extract
from state_machine import Action, Step, is_terminal, step


# (signals, label, persona, step_int) - the unit row of generated data.
Row = Tuple[Signals, int, str, int]


def generate(cfg: dict, persona: str, n: int, seed: int = 0) -> List[Row]:
    """Run `n` baseline episodes for `persona` with no coach; yield one row per
    non-terminal state visit, labelled with the episode's terminal outcome.

    Seeding mirrors the runner exactly so a (seed, episode) maps to the same user.
    """
    prices = cfg["tariff_prices"]
    sc = cfg["surcharge"]
    agent = StubAgent(cfg, persona)

    rows: List[Row] = []
    for ep in range(n):
        rng = random.Random(f"{seed}:{ep}")
        agent.reset(rng)
        state = Step.START
        history: List[Record] = []
        surcharge = rng.uniform(sc["low"], sc["high"])
        provisional = None
        captured: List[Tuple[int, Signals]] = []

        while not is_terminal(state):
            sig = extract(state, history)
            if state == Step.S7_FINAL_PRICE and provisional is not None:
                sig.price_gap_eur = round(provisional * surcharge, 2)
            captured.append((int(state), sig))

            action: Action = agent.act(state, sig, None, rng)
            if action.type == "select" and action.target in prices:
                provisional = prices[action.target]
            history.append(Record(int(state), action))
            state = step(state, action)

        label = 1 if state == Step.ABANDONED else 0
        for st_int, sig in captured:
            rows.append((sig, label, persona, st_int))
    return rows


def to_matrix(rows: Iterable[Row]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Materialise rows into (X, y, persona_col, step_col) arrays for xgboost."""
    rows = list(rows)
    X = np.vstack([signals_to_vec(r[0]) for r in rows]).astype(np.float32) if rows else \
        np.zeros((0, len(FEATURE_NAMES)), dtype=np.float32)
    y = np.array([r[1] for r in rows], dtype=np.int32)
    persona_col = np.array([r[2] for r in rows])
    step_col = np.array([r[3] for r in rows], dtype=np.int32)
    return X, y, persona_col, step_col
