"""Shared feature contract for the GBM detector.

A `Signals` dataclass is the runtime input; xgboost needs a fixed-order numeric
vector. This module pins:
  * FEATURE_NAMES   - the canonical column order (used by training and inference)
  * signals_to_vec  - the Signals -> np.float32[D] conversion

`tariff_selected` is the one categorical: integer-encoded since xgboost handles
ordinal features well enough at this scale and one-hot would inflate the table.
Order: None=0, Start=1, Optimal=2, OptPlus=3, Premium=4 (cheapest -> most premium).
"""
from __future__ import annotations

from typing import List

import numpy as np


FEATURE_NAMES: List[str] = [
    "step",
    "max_steps_completed",
    "dwell_current_s",
    "dwell_total_s",
    "time_since_last_action_s",
    "back_nav_count",
    "back_from_step",
    "field_change_count",
    "tariff_hover_count",
    "advisory_tariff_clicked",
    "tariff_selected",
    "external_tab_opens",
    "price_gap_eur",
    "hover_cancel_count",
]

_TARIFF_ENC = {None: 0, "Start": 1, "Optimal": 2, "OptPlus": 3, "Premium": 4}


def signals_to_vec(s) -> np.ndarray:
    return np.array(
        [
            float(s.step),
            float(s.max_steps_completed),
            float(s.dwell_current_s),
            float(s.dwell_total_s),
            float(s.time_since_last_action_s),
            float(s.back_nav_count),
            float(s.back_from_step if s.back_from_step is not None else -1),
            float(s.field_change_count),
            float(s.tariff_hover_count),
            float(bool(s.advisory_tariff_clicked)),
            float(_TARIFF_ENC.get(s.tariff_selected, 0)),
            float(s.external_tab_opens),
            float(s.price_gap_eur),
            float(s.hover_cancel_count),
        ],
        dtype=np.float32,
    )
