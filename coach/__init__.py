"""Conversion Coach — pure decision logic.

FROZEN signature: coach(signals, persona, policy) -> Optional[Intervention].

Phase 1 (here): no-op — returns None. With no coach, the baseline must reproduce
~5.6% (the Phase 1 acceptance test).

Later phases add, behind this same entry point:
  * detection.py  (Phase 2 threshold, Phase 3 GBM)  — when to intervene
  * policy.py     (Phase 2)                          — per-persona: which intervention
  * realize.py    (Phase 2 templates, Phase 5 LLM)   — phrasing the intervention

`effectiveness` is consumed by the agent's abandonment draw. The no-op coach never
fires, so it has no effect on Phase 1 numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from signals import Signals


@dataclass
class Intervention:
    type: str                 # e.g. "price_reframe", "market_comparison", "callback"
    persona: str
    step: int
    text: str = ""            # filled by realize() (templates P2, LLM P5)
    effectiveness: float = 0.0  # assumed drop-off reduction in P1-P3 (parameter, not measured)


def coach(signals: Signals, persona: str, policy) -> Optional[Intervention]:
    """Phase 1 no-op. Replace with detection + policy in Phase 2."""
    return None
