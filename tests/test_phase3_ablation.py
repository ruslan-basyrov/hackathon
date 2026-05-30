"""Phase 3 acceptance - GBM vs threshold detection on held-out simulator runs.

Gate (BUILD_SPEC §5 Phase 3):
  * GBM and threshold both report precision/recall on the SAME held-out test set.
  * Comparison is honest (no cherry-picking; identical labels, identical samples).
  * GBM need NOT win - the acceptance is that the comparison exists and reports
    real numbers.

What we measure (per-state):
  * positive = the episode this state belongs to ended in ABANDONED
  * fired    = the detector returned True at that state
  * precision = P(abandoned | fired);  recall = P(fired | abandoned)

The GBM is trained on seed 0 and evaluated on seed 1 - genuinely held-out under
the same simulator. Training is small (1500/persona) so the test stays quick;
the canonical training command is `python -m training.train_gbm` which produces
the artefact for the runtime to load. W&B is disabled in the test.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from coach.detection import detect, _load_model  # noqa: E402
from runner import load_config  # noqa: E402
from training.data_gen import generate, to_matrix  # noqa: E402
from training.train_gbm import PERSONAS, train  # noqa: E402

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")


def _eval(method_cfg, test_signals, labels):
    """Apply detect() to each test sample; return precision/recall/fired/positive."""
    preds = np.array(
        [1 if detect(s, method_cfg)[0] else 0 for s in test_signals], dtype=np.int32
    )
    labels = labels.astype(np.int32)
    tp = int(((preds == 1) & (labels == 1)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    fired = tp + fp
    pos = tp + fn
    precision = tp / fired if fired else 0.0
    recall = tp / pos if pos else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0,
        "fired": fired,
        "positives": pos,
        "n": len(preds),
    }


def _build_test_set(cfg, n_per_persona, seed):
    rows = []
    for p in PERSONAS:
        rows.extend(generate(cfg, p, n_per_persona, seed=seed))
    sigs = [r[0] for r in rows]
    _, y, persona_col, _ = to_matrix(rows)
    return sigs, y, persona_col


def _ablation(cfg, model_path, n_test=1000, gbm_threshold=0.5):
    test_signals, y, persona_col = _build_test_set(cfg, n_test, seed=1)

    threshold_cfg = {**cfg["detection"], "method": "threshold"}
    gbm_cfg = {
        **cfg["detection"],
        "method": "gbm",
        "gbm_model_path": model_path,
        "gbm_threshold": gbm_threshold,
    }

    rows = []
    for label, det_cfg in [("threshold", threshold_cfg), ("gbm", gbm_cfg)]:
        overall = _eval(det_cfg, test_signals, y)
        per_persona = {}
        for p in PERSONAS:
            mask = persona_col == p
            sigs_p = [s for s, m in zip(test_signals, mask) if m]
            per_persona[p] = _eval(det_cfg, sigs_p, y[mask])
        rows.append((label, overall, per_persona))
    return rows


def _print_table(rows):
    print(f"\n{'method':10s} {'scope':8s} {'precision':>10s} {'recall':>8s} "
          f"{'f1':>6s} {'fired':>7s} {'positives':>9s} {'n':>7s}")
    for label, overall, per_persona in rows:
        for scope, m in [("overall", overall), *per_persona.items()]:
            print(f"{label:10s} {scope:8s} "
                  f"{m['precision']:10.3f} {m['recall']:8.3f} {m['f1']:6.3f} "
                  f"{m['fired']:7d} {m['positives']:9d} {m['n']:7d}")


def test_phase3_ablation():
    cfg = load_config(CONFIG)
    with tempfile.TemporaryDirectory() as tmp:
        model_path = os.path.join(tmp, "gbm.json")
        train(
            cfg_path=CONFIG,
            n_per_persona_train=1500,
            n_per_persona_test=300,
            out_path=model_path,
            use_wandb=False,
        )
        _load_model.cache_clear()    # force the freshly-trained artefact

        rows = _ablation(cfg, model_path, n_test=800)
        _print_table(rows)

    by_label = {label: (overall, _) for label, overall, _ in rows}
    th_overall, _ = by_label["threshold"]
    gbm_overall, _ = by_label["gbm"]

    # Honest comparison: both methods must report well-defined precision and recall
    # (i.e. each method actually fires somewhere on the held-out set and there ARE
    # positives in the set). The acceptance is that the table exists - GBM need
    # not beat threshold.
    assert th_overall["fired"] > 0, "threshold detector never fires on the test set"
    assert gbm_overall["fired"] > 0, "GBM detector never fires on the test set"
    assert th_overall["positives"] > 0, "no abandonments in the test set (data bug)"
    assert gbm_overall["positives"] == th_overall["positives"], "test sets diverged"
    for m in (th_overall, gbm_overall):
        assert 0.0 <= m["precision"] <= 1.0
        assert 0.0 <= m["recall"] <= 1.0


if __name__ == "__main__":
    test_phase3_ablation()
    print("\nPASS")
