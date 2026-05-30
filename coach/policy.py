"""Policy layer — WHICH intervention, given persona + step. The central technical
challenge of the track: one unified strategy fails, so this is an explicit per-persona
table (BUILD_SPEC §5 Phase 2).

Each entry is (intervention_type, mode):
  * mode "stay"    -> a nudge that lowers drop-off at this step (Judith, Franz)
  * mode "handoff" -> route to a person; lands in SERVICE_CONTACT (Peter, Judith-optional)

Per-persona conversion definitions (applied in the scorer, runner.py):
  * Judith : online purchase OR service contact both count
  * Franz  : online purchase ONLY (a handoff is a failure) -> NO handoff entries here
  * Peter  : qualified service contact is the target (online also fine)

`lookup` returns (None, None) when there is no entry, so the coach emits nothing —
detection gating plus an empty policy cell both mean "don't intervene."
"""
from __future__ import annotations

from typing import Optional, Tuple

# step int -> (intervention_type, mode)
TABLE = {
    "judith": {
        4: ("price_reframe", "stay"),     # market comparison / €-per-day reframe
        7: ("explain_price", "stay"),     # transparency on the final price
    },
    "franz": {
        4: ("explain_advisory_alt", "stay"),  # "Opt.Plus needs a call; Optimal is fully online"
        7: ("justify_price", "stay"),         # justify the jump / cheaper alt / save-progress
        # NO handoff entries: pushing Franz to an advisor is a failure for his goal.
    },
    "peter": {
        1: ("callback", "handoff"),       # route to a person early and gracefully
        2: ("callback", "handoff"),
        3: ("callback", "handoff"),
        4: ("callback", "handoff"),
    },
    # "global" has no policy: in Phase 1 the coach is off; if run with a coach,
    # an empty table means no interventions.
}


def lookup(persona: str, step: int) -> Tuple[Optional[str], Optional[str]]:
    entry = TABLE.get(persona, {}).get(int(step))
    if entry is None:
        return None, None
    return entry
