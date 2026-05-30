"""Episode runner + aggregation.

Per-episode RNG is seeded by (master_seed, episode_index) only — never by whether a
coach is present — so with-coach and without-coach runs simulate the SAME users
(the coach is the only variable). See BUILD_SPEC §4.

Phase 1 entry point: run with coach_fn=None and reproduce the ~5.6% baseline.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

import yaml

from agent_stub import StubAgent
from coach import coach as default_coach
from signals import Record, extract
from state_machine import Action, Step, is_terminal, step


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run(
    cfg: dict,
    coach_fn: Optional[Callable] = None,
    n: Optional[int] = None,
    seed: Optional[int] = None,
    write_traces: bool = False,
) -> dict:
    """Run n episodes. coach_fn=None means no coach (Phase 1 baseline).
    Returns aggregate metrics. Optionally writes a small sample of full step traces.
    """
    n = int(n if n is not None else cfg["n_episodes"])
    seed = int(seed if seed is not None else cfg["seed"])
    prices = cfg["tariff_prices"]
    sc = cfg["surcharge"]
    agent = StubAgent(cfg)

    outcomes: Counter = Counter()
    reach = Counter()      # episodes that reached a given critical step
    survive = Counter()    # ... and reached the step after it
    trace_sample = int(cfg.get("trace_sample", 0)) if write_traces else 0
    trace_lines = []

    critical = [Step.S4_INITIAL_PRICE, Step.S6_HEALTH_QS, Step.S7_FINAL_PRICE]

    for ep in range(n):
        rng = random.Random(f"{seed}:{ep}")  # coach-independent per-episode seed
        agent.reset()
        state = Step.START
        history: list[Record] = []
        surcharge = rng.uniform(sc["low"], sc["high"])  # drawn first: coach-independent
        provisional = None
        reached = set()

        while not is_terminal(state):
            reached.add(state)
            signals = extract(state, history)
            if state == Step.S7_FINAL_PRICE and provisional is not None:
                signals.price_gap_eur = round(provisional * surcharge, 2)

            intervention = coach_fn(signals, "global", None) if coach_fn else None
            action: Action = agent.act(state, signals, intervention, rng)

            if action.type == "select" and action.target in prices:
                provisional = prices[action.target]

            if ep < trace_sample:
                trace_lines.append(json.dumps({
                    "episode": ep, "step": int(state), "action": action.type,
                    "target": action.target, "dwell_s": round(action.dwell_s, 2),
                    "intervened": intervention is not None,
                }))

            history.append(Record(int(state), action))
            state = step(state, action)

        outcomes[state.name] += 1
        for c in critical:
            if c in reached:
                reach[c] += 1
                nxt = {Step.S4_INITIAL_PRICE: Step.S6_HEALTH_QS,
                       Step.S6_HEALTH_QS: Step.S7_FINAL_PRICE,
                       Step.S7_FINAL_PRICE: Step.S12_CLOSING}[c]
                if nxt in reached:
                    survive[c] += 1

    conversion = outcomes["CONVERTED"] / n
    result = {
        "n": n,
        "conversion": conversion,
        "outcomes": dict(outcomes),
        "survival": {
            c.name: (survive[c] / reach[c] if reach[c] else None) for c in critical
        },
    }

    if write_traces and trace_lines:
        Path("traces.jsonl").write_text("\n".join(trace_lines) + "\n")

    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--n", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    res = run(cfg, coach_fn=None, n=args.n, write_traces=True)  # Phase 1: no coach

    print(f"episodes:          {res['n']}")
    print(f"online conversion: {res['conversion'] * 100:.2f}%")
    print(f"outcomes:          {res['outcomes']}")
    print("per-step survival (should track 0.34 / 0.76 / 0.22):")
    for k, v in res["survival"].items():
        print(f"  {k:18s} {v * 100:.1f}%" if v is not None else f"  {k:18s} n/a")


if __name__ == "__main__":
    main()
