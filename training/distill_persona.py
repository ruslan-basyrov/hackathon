"""Snapshot generator + SFT row builder for Phase 5 LoRA (BUILD_SPEC §5 Phase 5).

Two stages, kept in one file so the chat-message schema lives next to the
snapshot enumeration that produces it:

  1. `generate_snapshots()` replays the scripted simulator across personas and
     seeds, emitting one (persona, step, signals, last_intervention?) row per
     non-terminal state visit. Reuses `training.data_gen.generate`'s episode
     loop so train-time and detect-time share signal generation (the same
     property Phase 3 relies on).

  2. `to_sft_row()` wraps a snapshot in the chat-message format the LoRA will
     be trained on. Mirrors `coach.llm_realize.build_messages` so the bot and
     wording prompts share conventions; only the assistant target differs (an
     Action JSON, not nudge text).

The labeling step itself (filling the empty `completion` field) is done in
Claude conversation, not here. This script writes rows with `completion=""`;
a later pass writes them back with the in-character JSON.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Iterable, List, Optional

import yaml

from agent_stub import StubAgent
from coach import policy
from coach.realize import _template_realize
from coach.llm_realize import PERSONA_BRIEFINGS
from signals import Record, Signals, extract
from state_machine import (
    PREV,
    Step,
    is_terminal,
    step as advance,
)


PERSONAS = ("judith", "franz", "peter")

# Step int -> human-readable label (only the in-scope, non-terminal ones a bot
# will be prompted for).
STEP_LABEL = {
    int(Step.START): "START (welcome screen)",
    int(Step.S1_COVERAGE_TYPE): "S1 (choose coverage type: doctor vs hospital)",
    int(Step.S2_FOR_WHOM): "S2 (for whom: myself vs others)",
    int(Step.S3_PERSONAL_DATA): "S3 (personal data: DOB + social insurance number)",
    int(Step.S4_INITIAL_PRICE): "S4 (initial price screen — 4 tariffs)",
    int(Step.S6_HEALTH_QS): "S6 (health questions)",
    int(Step.S7_FINAL_PRICE): "S7 (final, personalised price)",
    int(Step.S12_CLOSING): "S12 (closing: payment + consents)",
}

SYSTEM_MSG = (
    "You are a synthetic user interacting with an insurance signup flow. "
    "Stay strictly in character for the persona supplied. Emit exactly one "
    "JSON object matching the Action schema — no prose, no markdown fence, "
    "no commentary. Schema: "
    '{"type": "continue"|"back"|"select"|"hover"|"change_field"|"open_tab"|"abandon", '
    '"target": <string or null>, "dwell_s": <float seconds>}.'
)


def _valid_actions_for_step(step_int: int) -> List[str]:
    """Enumerate the legal Action shapes at a given step. Surfaced verbatim in
    the prompt so the model learns the per-step constraint set instead of
    having to memorise it from examples alone."""
    parts: List[str] = []
    if step_int in PREV.values() or step_int == int(Step.START):
        parts.append('continue (target=null)')
    if step_int in PREV:
        parts.append('back (target=null)')
    if step_int == int(Step.S1_COVERAGE_TYPE):
        parts.append('select target ∈ {"doctor","hospital","both"}')
    elif step_int == int(Step.S2_FOR_WHOM):
        parts.append('select target ∈ {"myself","others"}')
    elif step_int == int(Step.S4_INITIAL_PRICE):
        parts.append('select target ∈ {"Start","Optimal","OptPlus","Premium","advisor_callback"}')
    # signals are always legal
    parts.append('hover target ∈ {tariff name, "cancel", field name}')
    parts.append('change_field target="form"')
    parts.append('open_tab target="comparison"')
    parts.append('abandon (target=null)')
    return parts


def _signals_block(sig: Signals) -> str:
    """Render the Signals dataclass into the same structured block the wording
    prompt uses. Keep the field order stable across the dataset so the model
    sees a consistent layout."""
    return (
        f"  - dwell on current screen: {sig.dwell_current_s:.0f}s\n"
        f"  - dwell cumulative: {sig.dwell_total_s:.0f}s\n"
        f"  - time since last action: {sig.time_since_last_action_s:.0f}s\n"
        f"  - steps completed: {sig.max_steps_completed}\n"
        f"  - back navigations: {sig.back_nav_count}\n"
        f"  - form re-edits: {sig.field_change_count}\n"
        f"  - tariff hovers: {sig.tariff_hover_count}\n"
        f"  - tariff selected: {sig.tariff_selected}\n"
        f"  - advisory tariff engaged: {sig.advisory_tariff_clicked}\n"
        f"  - external tab opens: {sig.external_tab_opens}\n"
        f"  - hover-cancel count: {sig.hover_cancel_count}\n"
        f"  - price gap (final vs estimate): €{sig.price_gap_eur:.2f}"
    )


def build_user_msg(
    persona: str,
    step_int: int,
    sig: Signals,
    last_intervention_type: Optional[str],
    last_intervention_text: Optional[str],
) -> str:
    brief = PERSONA_BRIEFINGS.get(persona, PERSONA_BRIEFINGS["global"])
    step_label = STEP_LABEL.get(step_int, f"S{step_int}")
    valid = "\n  - ".join(_valid_actions_for_step(step_int))
    msg = (
        f"PERSONA\n{brief}\n\n"
        f"CURRENT STEP: {step_label}\n"
        f"VALID NEXT ACTIONS:\n  - {valid}\n\n"
        f"SIGNALS:\n{_signals_block(sig)}\n"
    )
    if last_intervention_type:
        text = last_intervention_text or "(no text)"
        msg += f'\nLAST INTERVENTION: "{text}"  — type={last_intervention_type}\n'
    else:
        msg += "\nLAST INTERVENTION: none\n"
    return msg


def to_sft_row(
    persona: str,
    step_int: int,
    sig: Signals,
    last_intervention_type: Optional[str] = None,
    last_intervention_text: Optional[str] = None,
    completion: str = "",
) -> dict:
    """One SFT-ready row. `completion` is the assistant target; left blank for
    snapshot-only output, filled later during labeling."""
    return {
        "persona": persona,
        "step": step_int,
        "last_intervention_type": last_intervention_type,
        "messages": [
            {"role": "system", "content": SYSTEM_MSG},
            {
                "role": "user",
                "content": build_user_msg(
                    persona, step_int, sig, last_intervention_type, last_intervention_text
                ),
            },
        ],
        "completion": completion,
    }


def _episode_snapshots(
    cfg: dict, persona: str, ep_seed: str, with_coach: bool
) -> Iterable[dict]:
    """Run one scripted episode and yield SFT rows at each non-terminal visit.

    `with_coach=True` consults `coach.policy` and `coach.realize` so the
    snapshot captures `last_intervention_*` for steps where the policy fires —
    this gives us with-vs-without-intervention pairs in the corpus."""
    prices = cfg["tariff_prices"]
    sc = cfg["surcharge"]
    rng = random.Random(ep_seed)
    agent = StubAgent(cfg, persona)
    agent.reset(rng)

    state = Step.START
    history: List[Record] = []
    surcharge = rng.uniform(sc["low"], sc["high"])
    provisional = None
    last_itype: Optional[str] = None
    last_itext: Optional[str] = None

    while not is_terminal(state):
        sig = extract(state, history)
        if state == Step.S7_FINAL_PRICE and provisional is not None:
            sig.price_gap_eur = round(provisional * surcharge, 2)

        itype_now: Optional[str] = None
        itext_now: Optional[str] = None
        if with_coach:
            itype_now, _mode = policy.lookup(persona, int(state))
            if itype_now:
                itext_now = _template_realize(itype_now, sig)

        yield to_sft_row(
            persona,
            int(state),
            sig,
            last_intervention_type=itype_now or last_itype,
            last_intervention_text=itext_now or last_itext,
        )

        if itype_now:
            last_itype, last_itext = itype_now, itext_now

        # advance using the scripted agent (intervention=None — we only want
        # the snapshot, not its mitigated behaviour).
        action = agent.act(state, sig, None, rng)
        if action.type == "select" and action.target in prices:
            provisional = prices[action.target]
        history.append(Record(int(state), action))
        state = advance(state, action)


def generate_snapshots(
    cfg: dict,
    personas: Iterable[str],
    n_per_persona: int,
    seed: int,
    coach_fraction: float = 0.4,
) -> List[dict]:
    """Run `n_per_persona` episodes per persona; `coach_fraction` of them with
    the coach policy on so the corpus contains both with- and without-
    intervention snapshots. Returns an in-memory list (the volumes are small —
    tens of thousands of rows max)."""
    rows: List[dict] = []
    for persona in personas:
        n_coach = int(round(n_per_persona * coach_fraction))
        for ep in range(n_per_persona):
            with_coach = ep < n_coach
            ep_seed = f"{seed}:{persona}:{ep}"
            rows.extend(_episode_snapshots(cfg, persona, ep_seed, with_coach=with_coach))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Emit unlabeled SFT snapshots for Phase 5 LoRA.")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default="training/datasets/persona_snapshots.jsonl")
    ap.add_argument("--n-per-persona", type=int, default=80,
                    help="episodes per persona; total rows ≈ 8x this (one per state visit)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--coach-fraction", type=float, default=0.4,
                    help="fraction of episodes run with coach on (to capture with-intervention rows)")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    rows = generate_snapshots(
        cfg,
        PERSONAS,
        n_per_persona=args.n_per_persona,
        seed=args.seed,
        coach_fraction=args.coach_fraction,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} unlabeled rows -> {out}")
    by_persona = {p: sum(1 for r in rows if r["persona"] == p) for p in PERSONAS}
    by_step = {}
    for r in rows:
        by_step[r["step"]] = by_step.get(r["step"], 0) + 1
    print(f"  by persona: {by_persona}")
    print(f"  by step:    {dict(sorted(by_step.items()))}")
    print(f"  with intervention: {sum(1 for r in rows if r['last_intervention_type'])}")


if __name__ == "__main__":
    main()
