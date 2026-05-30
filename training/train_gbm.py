"""Local GBM training + W&B logging (BUILD_SPEC §5 Phase 3, §9).

Trains a single xgboost classifier on (Signals -> abandoned?) pairs drawn from
the scripted-agent simulator across all in-scope personas (judith / franz /
peter). One global model, evaluated overall AND per-persona - keeps `detect()`'s
frozen (signals, cfg) signature while still surfacing where the model helps or
hurts on a given persona.

Train/test split is by simulator seed (not row shuffling): train on seed 0,
evaluate on seed 1. That gives a genuinely held-out set under the SAME data
generator, which is what the Phase 3 acceptance asks for.

W&B online mode (local dev box has internet). The feature-importance plot
doubles as the GBM's inspectability exhibit (the rubric's "traceable decision
rules"). W&B is opt-out via --no-wandb; if the API key is missing or the
service is unreachable, training continues without telemetry.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import xgboost as xgb
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)

from coach.features import FEATURE_NAMES
from runner import load_config
from training.data_gen import generate, to_matrix


PERSONAS = ("judith", "franz", "peter")


def build_dataset(cfg: dict, personas, n_per_persona: int, seed: int):
    rows = []
    for p in personas:
        rows.extend(generate(cfg, p, n_per_persona, seed=seed))
    return to_matrix(rows)


def _metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> Dict[str, float]:
    y_pred = (y_prob >= threshold).astype(int)
    pr, rc, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    out = {"precision": float(pr), "recall": float(rc), "f1": float(f1)}
    if len(set(y_true.tolist())) > 1:
        out["auc"] = float(roc_auc_score(y_true, y_prob))
        out["ap"] = float(average_precision_score(y_true, y_prob))
    else:
        out["auc"] = float("nan")
        out["ap"] = float("nan")
    out["fired_rate"] = float(y_pred.mean())
    out["positive_rate"] = float(y_true.mean())
    return out


def train(
    cfg_path: str = "config.yaml",
    n_per_persona_train: int = 4000,
    n_per_persona_test: int = 1000,
    out_path: str = "models/gbm.json",
    use_wandb: bool = True,
    decision_threshold: float = 0.5,
    seed_train: int = 0,
    seed_test: int = 1,
) -> Dict[str, object]:
    cfg = load_config(cfg_path)

    X_tr, y_tr, _, _ = build_dataset(cfg, PERSONAS, n_per_persona_train, seed_train)
    X_te, y_te, p_te, s_te = build_dataset(cfg, PERSONAS, n_per_persona_test, seed_test)

    params = dict(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        eval_metric="auc",
        objective="binary:logistic",
        tree_method="hist",
        random_state=42,
    )

    run = None
    if use_wandb:
        try:
            import wandb

            run = wandb.init(
                project=cfg.get("wandb_project", "conversion-coach"),
                config={
                    **params,
                    "n_per_persona_train": n_per_persona_train,
                    "n_per_persona_test": n_per_persona_test,
                    "decision_threshold": decision_threshold,
                },
                reinit=True,
            )
        except Exception as e:  # API key missing, offline, etc.
            print(f"[wandb] disabled: {e}")
            run = None

    model = xgb.XGBClassifier(**params)
    model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)

    y_prob = model.predict_proba(X_te)[:, 1]
    overall = _metrics(y_te, y_prob, decision_threshold)
    print(
        f"\n[overall]  AUC={overall['auc']:.3f}  AP={overall['ap']:.3f}  "
        f"P={overall['precision']:.3f}  R={overall['recall']:.3f}  "
        f"F1={overall['f1']:.3f}  fired={overall['fired_rate']:.3f}  "
        f"pos_rate={overall['positive_rate']:.3f}"
    )
    cm = confusion_matrix(y_te, (y_prob >= decision_threshold).astype(int)).tolist()
    print(f"  confusion (tn,fp;fn,tp): {cm}")

    per_persona = {}
    for persona in PERSONAS:
        mask = p_te == persona
        if mask.sum() == 0:
            continue
        m = _metrics(y_te[mask], y_prob[mask], decision_threshold)
        per_persona[persona] = m
        print(
            f"[{persona:8s}] AUC={m['auc']:.3f}  P={m['precision']:.3f}  "
            f"R={m['recall']:.3f}  F1={m['f1']:.3f}  "
            f"fired={m['fired_rate']:.3f}  pos_rate={m['positive_rate']:.3f}"
        )

    importances = dict(zip(FEATURE_NAMES, model.feature_importances_.tolist()))
    print("\n[feature importances]")
    for k, v in sorted(importances.items(), key=lambda kv: -kv[1]):
        print(f"  {k:30s} {v:.3f}")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    model.save_model(out_path)
    print(f"\nsaved model -> {out_path}")

    if run is not None:
        import wandb

        wandb.log({f"overall/{k}": v for k, v in overall.items()})
        wandb.log({f"confusion/tn": cm[0][0], f"confusion/fp": cm[0][1],
                   f"confusion/fn": cm[1][0], f"confusion/tp": cm[1][1]})
        for persona, m in per_persona.items():
            wandb.log({f"{persona}/{k}": v for k, v in m.items()})
        wandb.log({"feature_importance": wandb.Table(
            data=[[k, v] for k, v in importances.items()],
            columns=["feature", "importance"],
        )})
        wandb.summary["overall"] = overall
        wandb.summary["per_persona"] = per_persona
        wandb.finish()

    return {
        "overall": overall,
        "per_persona": per_persona,
        "feature_importance": importances,
        "confusion_matrix": cm,
        "model_path": out_path,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--n-train", type=int, default=4000, help="episodes per persona for training")
    ap.add_argument("--n-test", type=int, default=1000, help="episodes per persona for held-out eval")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out", default="models/gbm.json")
    ap.add_argument("--no-wandb", action="store_true")
    args = ap.parse_args()
    summary = train(
        cfg_path=args.config,
        n_per_persona_train=args.n_train,
        n_per_persona_test=args.n_test,
        out_path=args.out,
        use_wandb=not args.no_wandb,
        decision_threshold=args.threshold,
    )
    print("\n[summary]")
    print(json.dumps({k: v for k, v in summary.items() if k != "feature_importance"}, indent=2))


if __name__ == "__main__":
    main()
