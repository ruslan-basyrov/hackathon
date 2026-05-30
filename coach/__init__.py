"""Conversion Coach — pure decision logic. FROZEN signature:
coach(signals, persona, policy) -> Optional[Intervention].

Phase 2: composes detection -> policy -> realize. `policy` is the config dict
(carries the detection thresholds and intervention-effectiveness settings).

With no coach (coach_fn=None in the runner), Phase 1's ~5.6% baseline is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from signals import Signals

from .detection import detect
from .policy import lookup
from .realize import realize


@dataclass
class Intervention:
    type: str                   # e.g. "price_reframe", "justify_price", "callback"
    persona: str
    step: int
    text: str = ""              # filled by realize() (templates P2, LLM P5)
    effectiveness: float = 0.0  # stay-mode drop-off reduction (parameter in P1-P3, not measured)
    mode: str = "stay"          # "stay" (reduce drop-off) | "handoff" (route to a person)


def coach(signals: Signals, persona: str, policy) -> Optional[Intervention]:
    """policy == the config dict. Detection gates; the per-persona table decides what.

    Narrow fallback: if detection fires for `repeated_back_nav` but the persona
    policy has no entry for the current step (e.g. Judith pressing back at S1
    isn't in the policy table), emit a generic `back_nav_help` intervention.
    This keeps the back-nav friction signal responsive at any step, regardless
    of persona / step coverage in policy.py. The fallback is intentionally
    narrow - we only do it for back-nav, not for every detection rule, to
    avoid silently expanding the persona-policy contract.
    """
    fire, reason = detect(signals, policy["detection"])
    if not fire:
        return None

    itype, mode = lookup(persona, signals.step)
    if itype is None:
        if reason == "repeated_back_nav":
            itype, mode = "back_nav_help", "stay"
        else:
            return None

    eff = policy["intervention_effectiveness"]["default"] if mode == "stay" else 0.0
    return Intervention(
        type=itype,
        persona=persona,
        step=int(signals.step),
        text=realize(itype, signals, persona=persona, cfg=policy),
        effectiveness=eff,
        mode=mode,
    )
