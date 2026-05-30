"""Episode runner + aggregation.

Per-episode RNG is seeded by (master_seed, episode_index) only — never by whether a
coach is present — so with-coach and without-coach runs simulate the SAME users (the
coach is the only variable). This is what makes the paired counterfactual in compare()
valid: episode i is the same person in both runs. See BUILD_SPEC §4.

run()      -> aggregate metrics for one persona, plus a per-episode log for pairing.
compare()  -> control vs treatment on the same population, giving uplift AND the cost
              of intervening (wasted_rate: fired on someone who'd have succeeded anyway).
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
    success_set = SUCCESS.get(persona, {"CONVERTED"})
    agent = StubAgent(cfg, persona)

    outcomes: Counter = Counter()
    episodes = []          # per-episode (success, fired_stay, fired_handoff) for pairing
    trace_sample = int(cfg.get("trace_sample", 0)) if write_traces else 0
    trace_lines = []

    for ep in range(n):
        rng = random.Random(f"{seed}:{ep}")   # coach-independent per-episode seed
        agent.reset(rng)
        state = Step.START
        history: list[Record] = []
        surcharge = rng.uniform(sc["low"], sc["high"])
        provisional = None

        while not is_terminal(state):
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
        episodes.append((
            1 if state.name in success_set else 0,
            1 if any(m == "stay" for m, _ in agent.fires) else 0,
            1 if any(m == "handoff" for m, _ in agent.fires) else 0,
        ))

    success = sum(e[0] for e in episodes) / n
    result = {
        "persona": persona,
        "n": n,
        "success": success,
        "conversion": outcomes["CONVERTED"] / n,
        "outcomes": dict(outcomes),
        "episodes": episodes,
    }
    if write_traces and trace_lines:
        Path("traces.jsonl").write_text("\n".join(trace_lines) + "\n")
    return result


def compare(cfg: dict, persona: str, n: Optional[int] = None, seed: Optional[int] = None) -> dict:
    """Paired control (no coach) vs treatment (coach) on the SAME seeded population.

    For each episode where the coach fired, classify against the control outcome:
      * wasted      — control already succeeded; the intervention was unnecessary
      * saved       — control failed, treatment succeeded; the intervention worked
      * still_failed— control failed and treatment still failed
    Works identically for stay-nudges and handoffs (the Phase 2 metric fix).
    """
    ctrl = run(cfg, coach_fn=None, persona=persona, n=n, seed=seed)
    trt = run(cfg, coach_fn=default_coach, persona=persona, n=n, seed=seed)

    fired = wasted = saved = still_failed = 0
    for (cs, _, _), (ts, t_stay, t_hand) in zip(ctrl["episodes"], trt["episodes"]):
        if t_stay or t_hand:
            fired += 1
            if cs:
                wasted += 1
            elif ts:
                saved += 1
            else:
                still_failed += 1

    return {
        "persona": persona,
        "n": ctrl["n"],
        "success_without": ctrl["success"],
        "success_with": trt["success"],
        "uplift": trt["success"] - ctrl["success"],
        "fired_rate": fired / ctrl["n"],
        "wasted_rate": (wasted / fired) if fired else None,
        "saved_rate": (saved / fired) if fired else None,
        "still_failed_rate": (still_failed / fired) if fired else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--n", type=int, default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)

    base_global = run(cfg, coach_fn=None, persona="global", n=args.n, write_traces=True)
    print(f"[Phase 1] global baseline, no coach: {base_global['conversion'] * 100:.2f}% "
          f"online conversion (n={base_global['n']})\n")

    print("[Phase 2] per-persona, control vs coached on identical seeds:")
    print(f"  {'persona':8s} {'without':>8s} {'with':>8s} {'uplift':>8s}   "
          f"{'fired':>6s} {'wasted':>7s} {'saved':>6s}")
    for persona in ("judith", "franz", "peter"):
        r = compare(cfg, persona, n=args.n)
        pct = lambda x: f"{x * 100:.1f}%" if x is not None else "n/a"
        print(f"  {persona:8s} {pct(r['success_without']):>8s} {pct(r['success_with']):>8s} "
              f"{r['uplift'] * 100:+7.1f}pp   {pct(r['fired_rate']):>6s} "
              f"{pct(r['wasted_rate']):>7s} {pct(r['saved_rate']):>6s}")
    print("\n  fired  = % of users shown an intervention")
    print("  wasted = % of those who'd have succeeded anyway (the annoyance/over-route cost)")
    print("  saved  = % of those the intervention actually rescued")


if __name__ == "__main__":
    main()
