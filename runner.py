"""Episode runner + aggregation.

Per-episode RNG is seeded by (master_seed, episode_index) only — never by whether a
coach is present — so with-coach and without-coach runs simulate the SAME users (the
coach is the only variable). See BUILD_SPEC §4.

run() handles one persona. Phase 1 acceptance: persona="global", coach_fn=None -> ~5.6%.
Phase 2 acceptance: per persona, success(with) > success(without); annoyance reported.
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

# Per-persona conversion definitions (BUILD_SPEC §5 Phase 2).
SUCCESS = {
    "global": {"CONVERTED"},
    "judith": {"CONVERTED", "SERVICE_CONTACT"},   # online OR handoff both count
    "franz": {"CONVERTED"},                        # online only; handoff = failure
    "peter": {"SERVICE_CONTACT", "CONVERTED"},     # service contact is the target
}


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run(
    cfg: dict,
    coach_fn: Optional[Callable] = None,
    persona: str = "global",
    n: Optional[int] = None,
    seed: Optional[int] = None,
    write_traces: bool = False,
) -> dict:
    n = int(n if n is not None else cfg["n_episodes"])
    seed = int(seed if seed is not None else cfg["seed"])
    prices = cfg["tariff_prices"]
    sc = cfg["surcharge"]
    agent = StubAgent(cfg, persona)

    outcomes: Counter = Counter()
    reach, survive = Counter(), Counter()
    stay_fires = stay_annoying = handoff_fires = 0
    trace_sample = int(cfg.get("trace_sample", 0)) if write_traces else 0
    trace_lines = []
    critical = [Step.S4_INITIAL_PRICE, Step.S6_HEALTH_QS, Step.S7_FINAL_PRICE]
    nxt = {Step.S4_INITIAL_PRICE: Step.S6_HEALTH_QS,
           Step.S6_HEALTH_QS: Step.S7_FINAL_PRICE,
           Step.S7_FINAL_PRICE: Step.S12_CLOSING}

    for ep in range(n):
        rng = random.Random(f"{seed}:{ep}")   # coach-independent per-episode seed
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

            intervention = coach_fn(signals, persona, cfg) if coach_fn else None
            action: Action = agent.act(state, signals, intervention, rng)

            if action.type == "select" and action.target in prices:
                provisional = prices[action.target]

            if ep < trace_sample:
                trace_lines.append(json.dumps({
                    "episode": ep, "persona": persona, "step": int(state),
                    "action": action.type, "target": action.target,
                    "dwell_s": round(action.dwell_s, 2),
                    "intervention": getattr(intervention, "type", None),
                }))

            history.append(Record(int(state), action))
            state = step(state, action)

        outcomes[state.name] += 1
        for mode, would in agent.fires:
            if mode == "stay":
                stay_fires += 1
                if not would:
                    stay_annoying += 1
            elif mode == "handoff":
                handoff_fires += 1
        for c in critical:
            if c in reached:
                reach[c] += 1
                if nxt[c] in reached:
                    survive[c] += 1

    success = sum(outcomes[o] for o in SUCCESS.get(persona, {"CONVERTED"})) / n
    result = {
        "persona": persona,
        "n": n,
        "success": success,
        "conversion": outcomes["CONVERTED"] / n,
        "annoyance_rate": (stay_annoying / stay_fires) if stay_fires else None,
        "stay_fires": stay_fires,
        "handoff_fires": handoff_fires,
        "outcomes": dict(outcomes),
        "survival": {c.name: (survive[c] / reach[c] if reach[c] else None) for c in critical},
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

    # Phase 1 baseline (global, no coach).
    base_global = run(cfg, coach_fn=None, persona="global", n=args.n, write_traces=True)
    print(f"[Phase 1] global baseline, no coach: {base_global['conversion'] * 100:.2f}% "
          f"online conversion (n={base_global['n']})")

    # Phase 2 per-persona: with vs without coach, identical seeds.
    print("\n[Phase 2] per-persona success (by conversion definition), without -> with coach:")
    print(f"  {'persona':8s} {'without':>8s} {'with':>8s} {'uplift':>8s}   "
          f"{'annoyance':>9s}  fires(stay/handoff)")
    for persona in ("judith", "franz", "peter"):
        b = run(cfg, coach_fn=None, persona=persona, n=args.n)
        c = run(cfg, coach_fn=default_coach, persona=persona, n=args.n)
        ann = f"{c['annoyance_rate'] * 100:.1f}%" if c["annoyance_rate"] is not None else "  n/a"
        print(f"  {persona:8s} {b['success'] * 100:7.1f}% {c['success'] * 100:7.1f}% "
              f"{(c['success'] - b['success']) * 100:+7.1f}pp   {ann:>9s}  "
              f"{c['stay_fires']}/{c['handoff_fires']}")


if __name__ == "__main__":
    main()
