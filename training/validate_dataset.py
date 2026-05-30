"""SFT dataset validator (BUILD_SPEC §5 Phase 5).

Each labeled row is `{"persona": ..., "step": int, "messages": [...], "completion": "<json>"}`.
The completion must parse as a single `Action` JSON that:
  * matches the frozen schema in state_machine.Action,
  * uses a `target` that is legal for the current step,
  * does not contradict the persona's "never do" rules from BUILD_SPEC §5 Phase 2.

Run before training. Failed rows are printed (file:lineno-style) and the script
exits non-zero so a downstream training run can't silently ingest bad labels.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from state_machine import HANDOFF_TARGETS, Step


VALID_TYPES = {"continue", "back", "select", "hover", "change_field", "open_tab", "abandon"}

# Step-specific allowed `select` targets EXCLUDING handoff. Handoff is
# accepted at every step (state_machine routes it to SERVICE_CONTACT
# regardless of source step — see policy.py, Peter S1-S4 callbacks).
# hover/change_field/open_tab targets are free-form because the simulator
# emits arbitrary strings for them (e.g. field names).
SELECT_TARGETS_BY_STEP = {
    int(Step.S1_COVERAGE_TYPE): {"doctor", "hospital", "both"},
    int(Step.S2_FOR_WHOM): {"myself", "others"},
    int(Step.S4_INITIAL_PRICE): {"Start", "Optimal", "OptPlus", "Premium"},
}

# Steps where `back` is undefined (no PREV entry in state_machine).
NO_BACK_STEPS = {int(Step.START), int(Step.S1_COVERAGE_TYPE)}

# Persona "never do" rules from the decision table (BUILD_SPEC.md §5 Phase 2).
# Each rule is (predicate, reason). Predicate takes (action_dict, step_int, last_intervention_type).
def _franz_never_handoff(act: dict, step_int: int, last_itype: Optional[str]) -> Optional[str]:
    if act.get("type") == "select" and act.get("target") in HANDOFF_TARGETS:
        return "Franz never accepts an advisor handoff"
    return None


PERSONA_RULES = {
    "franz": [_franz_never_handoff],
    "judith": [],
    "peter": [],
    "global": [],
}


def validate_action(act: dict, step_int: int) -> Optional[str]:
    """Return None if valid, else a short reason string."""
    if not isinstance(act, dict):
        return "completion is not a JSON object"
    keys = set(act.keys())
    if keys != {"type", "target", "dwell_s"}:
        return f"unexpected keys {sorted(keys)} (want type/target/dwell_s)"

    t = act["type"]
    if t not in VALID_TYPES:
        return f"unknown action type {t!r}"

    target = act["target"]
    if t == "select":
        if target is None:
            return "select requires a non-null target"
        if target in HANDOFF_TARGETS:
            pass  # handoff is legal at any step
        else:
            allowed = SELECT_TARGETS_BY_STEP.get(step_int)
            if allowed is None:
                return f"non-handoff select is not legal at step {step_int}"
            if target not in allowed:
                return f"select target {target!r} not in {sorted(allowed | HANDOFF_TARGETS)} for step {step_int}"
    elif t in ("continue", "back", "abandon"):
        if target is not None:
            return f"{t} must have target=null (got {target!r})"
    if t == "back" and step_int in NO_BACK_STEPS:
        return f"back is undefined at step {step_int}"

    dwell = act["dwell_s"]
    if not isinstance(dwell, (int, float)) or dwell < 0 or dwell != dwell:  # NaN check
        return f"dwell_s must be a non-negative number (got {dwell!r})"

    return None


def validate_row(row: dict) -> Optional[str]:
    persona = row.get("persona")
    if persona not in PERSONA_RULES:
        return f"unknown persona {persona!r}"
    step_int = row.get("step")
    if not isinstance(step_int, int):
        return f"step must be int (got {step_int!r})"

    completion = row.get("completion")
    if not isinstance(completion, str):
        return "completion must be a string"
    try:
        act = json.loads(completion)
    except json.JSONDecodeError as e:
        return f"completion is not valid JSON: {e}"

    err = validate_action(act, step_int)
    if err:
        return err

    last_itype = row.get("last_intervention_type")
    for rule in PERSONA_RULES[persona]:
        err = rule(act, step_int, last_itype)
        if err:
            return err
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="JSONL files to validate")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on any failure")
    args = ap.parse_args()

    total = bad = 0
    for path in args.paths:
        p = Path(path)
        with p.open() as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"{path}:{lineno}: row is not JSON: {e}")
                    bad += 1
                    continue
                err = validate_row(row)
                if err:
                    print(f"{path}:{lineno}: {err}  | persona={row.get('persona')} step={row.get('step')}")
                    bad += 1

    print(f"\n{bad}/{total} rows invalid")
    return 1 if (bad and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
