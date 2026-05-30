"""Assemble the Phase 5 SFT corpus: seeds + distilled labels, holdout split.

Pipeline:
  1. Generate a snapshot pool from `distill_persona.generate_snapshots()` —
     same scripted simulator, so train-time signals match runtime signals.
  2. Label each snapshot via `labeler.label(persona, step, signals, itype)` —
     Claude's persona judgment encoded as a documented decision tree.
  3. Concatenate with the hand-authored seeds from `build_seeds.py`.
  4. Validate every row against `validate_dataset.validate_row`.
  5. 10% stratified-by-step holdout, frozen via seed=0.

Run from repo root:
    python -m training.seed_data.assemble

Outputs (paths match those expected by `train_lora.py`):
  * training/datasets/persona_sft.jsonl          — training set
  * training/datasets/persona_sft_holdout.jsonl  — eval set
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import yaml

from signals import Signals
from training.distill_persona import generate_snapshots, to_sft_row
from training.seed_data import build_seeds, labeler
from training.validate_dataset import validate_row


PERSONAS = ("judith", "franz", "peter")
SEED_DIR = Path(__file__).parent
OUT_DIR = Path("training/datasets")


def _seed_rows_from_build_seeds() -> List[dict]:
    """Trigger build_seeds to (re-)write its JSONL output, then load it."""
    build_seeds.main()
    rows = []
    for p in PERSONAS:
        path = SEED_DIR / f"{p}.jsonl"
        with path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def _label_snapshots(snapshots: List[dict], seed: int) -> List[dict]:
    """Fill in `completion` for each snapshot by running it through the
    labeler. `seed` controls the labeler's RNG so the corpus is reproducible."""
    rng = random.Random(seed)
    labeled = []
    for row in snapshots:
        sig_dict = {k: v for k, v in row.items() if k in Signals.__dataclass_fields__}
        # The snapshot generator put signals into the user prompt as text;
        # we need the original Signals object to call labeler.label(). The
        # snapshot rows don't carry it directly, so re-derive from the row.
        # (Cheaper than re-running the simulator: every field we need is
        # already on the row via the `to_sft_row` builder — but we stored
        # only the rendered prompt. So we attach signals upstream.)
        sig = row.get("_signals")
        if sig is None:
            # Fallback: reconstruct a minimal Signals from `step`.
            sig = Signals(
                step=row["step"], max_steps_completed=0, dwell_current_s=0.0,
                dwell_total_s=0.0, time_since_last_action_s=0.0,
                back_nav_count=0, back_from_step=None, field_change_count=0,
                tariff_hover_count=0, advisory_tariff_clicked=False,
                tariff_selected=None, external_tab_opens=0,
                price_gap_eur=0.0, hover_cancel_count=0,
            )
        completion = labeler.label(
            row["persona"], row["step"], sig, row.get("last_intervention_type"), rng
        )
        row = dict(row)
        row["completion"] = completion
        row.pop("_signals", None)
        labeled.append(row)
    return labeled


def _generate_labeled_distill(cfg: dict, n_per_persona: int, seed: int) -> List[dict]:
    """Snapshot generator emits rendered prompts but loses the structured
    Signals object on the way out — we need the object to call the labeler.
    Re-run the simulator here in a thin loop that keeps the Signals around."""
    from agent_stub import StubAgent
    from coach import policy
    from coach.realize import _template_realize
    from signals import Record, extract
    from state_machine import Step, is_terminal, step as advance

    prices = cfg["tariff_prices"]
    sc = cfg["surcharge"]
    rows: List[dict] = []
    coach_fraction = 0.4

    for persona in PERSONAS:
        n_coach = int(round(n_per_persona * coach_fraction))
        for ep in range(n_per_persona):
            with_coach = ep < n_coach
            ep_seed = f"distill:{seed}:{persona}:{ep}"
            rng = random.Random(ep_seed)
            agent = StubAgent(cfg, persona)
            agent.reset(rng)
            state = Step.START
            history: List[Record] = []
            surcharge = rng.uniform(sc["low"], sc["high"])
            provisional = None
            last_itype = None
            last_itext = None

            while not is_terminal(state):
                sig = extract(state, history)
                if state == Step.S7_FINAL_PRICE and provisional is not None:
                    sig.price_gap_eur = round(provisional * surcharge, 2)

                itype_now = None
                itext_now = None
                if with_coach:
                    itype_now, _ = policy.lookup(persona, int(state))
                    if itype_now:
                        itext_now = _template_realize(itype_now, sig)

                row = to_sft_row(
                    persona=persona,
                    step_int=int(state),
                    sig=sig,
                    last_intervention_type=itype_now or last_itype,
                    last_intervention_text=itext_now or last_itext,
                    completion="",
                )
                # Attach the Signals object for the labeler; stripped before dump.
                row["_signals"] = sig
                rows.append(row)

                if itype_now:
                    last_itype, last_itext = itype_now, itext_now

                action = agent.act(state, sig, None, rng)
                if action.type == "select" and action.target in prices:
                    provisional = prices[action.target]
                history.append(Record(int(state), action))
                state = advance(state, action)

    return rows


def _stratified_holdout(rows: List[dict], frac: float, seed: int) -> tuple[List[dict], List[dict]]:
    """Split off `frac` of rows, stratified by (persona, step)."""
    rng = random.Random(seed)
    buckets: Dict[tuple, List[dict]] = defaultdict(list)
    for r in rows:
        buckets[(r["persona"], r["step"])].append(r)
    train, holdout = [], []
    for (_, _), bucket in buckets.items():
        rng.shuffle(bucket)
        n_hold = max(1, int(round(len(bucket) * frac))) if len(bucket) >= 2 else 0
        holdout.extend(bucket[:n_hold])
        train.extend(bucket[n_hold:])
    rng.shuffle(train)
    rng.shuffle(holdout)
    return train, holdout


def main() -> None:
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)

    print("[1/5] writing hand-crafted seeds ...")
    seed_rows = _seed_rows_from_build_seeds()
    print(f"      {len(seed_rows)} seed rows")

    print("[2/5] generating + labeling distilled snapshots ...")
    distill_snapshots = _generate_labeled_distill(cfg, n_per_persona=16, seed=0)
    distilled = _label_snapshots(distill_snapshots, seed=0)
    print(f"      {len(distilled)} labeled distillation rows")

    all_rows = seed_rows + distilled
    print(f"[3/5] combined corpus: {len(all_rows)} rows")

    print("[4/5] validating ...")
    bad = []
    for i, r in enumerate(all_rows):
        err = validate_row(r)
        if err:
            bad.append((i, err))
    if bad:
        print(f"      {len(bad)} invalid rows — printing first 10:")
        for i, err in bad[:10]:
            print(f"        row {i}: {err}  persona={all_rows[i].get('persona')} step={all_rows[i].get('step')}")
        sys.exit(1)
    print(f"      all {len(all_rows)} rows valid")

    print("[5/5] holdout split (10% stratified by persona/step) ...")
    train, holdout = _stratified_holdout(all_rows, frac=0.10, seed=0)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    train_path = OUT_DIR / "persona_sft.jsonl"
    holdout_path = OUT_DIR / "persona_sft_holdout.jsonl"
    with train_path.open("w") as f:
        for r in train:
            f.write(json.dumps(r) + "\n")
    with holdout_path.open("w") as f:
        for r in holdout:
            f.write(json.dumps(r) + "\n")
    print(f"      train:   {len(train):4d} -> {train_path}")
    print(f"      holdout: {len(holdout):4d} -> {holdout_path}")

    # Coverage report.
    by_pstep = defaultdict(lambda: [0, 0])
    for r in train:
        by_pstep[(r["persona"], r["step"])][0] += 1
    for r in holdout:
        by_pstep[(r["persona"], r["step"])][1] += 1
    print("\n[coverage] (persona, step) -> (train, holdout)")
    for (p, st), (tr, ho) in sorted(by_pstep.items()):
        print(f"  {p:7s} step={st:>2d}: train={tr:3d}  holdout={ho:2d}")


if __name__ == "__main__":
    main()
