"""Detection layer - WHEN to intervene.

Two backends behind one frozen (signals, cfg_detection) -> (bool, str) interface,
selectable via cfg_detection['method']:

  * 'threshold' - explicit signal thresholds (Phase 2, kept as the ablation baseline)
  * 'gbm'       - xgboost classifier trained on simulator data (Phase 3 default
                  when a model file is present)

The GBM is loaded once and cached by path (model artefacts are small json, so a
per-process LRU is enough). If the model file is missing we degrade silently
to "no fire" rather than crashing the coach - the runner can still execute,
just without GBM-driven detection. Phase 3 acceptance trains the model first,
so this path is only hit if someone runs the coach before train_gbm.py.

Threshold rules below are the Phase 2 set, unchanged:
  * S7 price-gap + cancel hover  -> Franz near abandonment at the final price
  * S4 long dwell                -> Judith hesitating at the price table
  * early form re-edits          -> Peter genuinely overwhelmed (confident Peter
                                     breezes through and self-serves)
  * repeated back-nav            -> generic friction

Two deliberate non-triggers (the Phase 2 fix - see git log f7c216e):
  * advisory-tariff engagement is a SIGNAL only, not a trigger.
  * raw dwell is NOT Peter's early-overwhelm trigger; field_change_count is.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Tuple

from coach.features import signals_to_vec


S4 = 4
S7 = 7


def detect(signals, cfg_detection: dict) -> Tuple[bool, str]:
    method = cfg_detection.get("method", "threshold")
    if method == "gbm":
        return _detect_gbm(signals, cfg_detection)
    return _detect_threshold(signals, cfg_detection)


# ---- threshold backend ------------------------------------------------------
def _detect_threshold(signals, d: dict) -> Tuple[bool, str]:
    s = signals
    if (
        s.step == S7
        and s.price_gap_eur > d["price_gap_threshold"]
        and s.hover_cancel_count >= 1
    ):
        return True, "s7_price_gap+cancel_hover"
    if s.step == S4 and s.dwell_current_s > d["dwell_threshold_s"]:
        return True, "s4_dwell"
    if (
        s.field_change_count >= d["overwhelm_changes"]
        and s.steps_completed < d["early_overwhelm_max_steps"]
    ):
        return True, "early_overwhelm"
    if s.back_nav_count >= d["back_nav_threshold"]:
        return True, "repeated_back_nav"
    return False, ""


# ---- GBM backend ------------------------------------------------------------
@lru_cache(maxsize=4)
def _load_model(path: str):
    import xgboost as xgb  # lazy: keep xgboost out of the import path when only threshold is used

    model = xgb.XGBClassifier()
    model.load_model(path)
    return model


def _detect_gbm(signals, d: dict) -> Tuple[bool, str]:
    path = d.get("gbm_model_path", "models/gbm.json")
    threshold = float(d.get("gbm_threshold", 0.5))
    if not os.path.exists(path):
        return False, "gbm_model_missing"
    model = _load_model(path)
    x = signals_to_vec(signals).reshape(1, -1)
    p = float(model.predict_proba(x)[0, 1])
    if p >= threshold:
        return True, f"gbm:p={p:.2f}"
    return False, ""
