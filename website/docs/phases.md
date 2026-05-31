---
title: Build phases
description: The staged build — one swappable component at a time, each gated by an acceptance test.
sidebar_position: 3
---

# Build phases

The project is built **one phase at a time, in order**. Each phase swaps a stub
for a real component and re-runs the same harness. A phase is "done" only when
its acceptance test passes — the test, not judgement, defines "correct."

:::info[What the early-phase numbers actually mean]
In Phases 1–4 the agent is **scripted**, so a coach intervention reduces drop-off
by a *parameter* (an assumed effectiveness factor in config). The uplift number
in Phases 1–4 therefore validates the **plumbing and the measurement**, not the
**efficacy** of the interventions. Efficacy only becomes real in **Phase 5**, when
LLM persona bots actually react to the wording. Do not claim "the coach works"
from Phase 1–4 numbers — claim "the harness measures uplift correctly."
:::

## Phase 1 — Skeleton + baseline

- **Builds:** the state machine, the signal extractor, the scripted stub agent
  (drop-off randomness lives here), a no-op coach stub, and the runner (episode
  loop + seeding + trace log + conversion aggregation).
- **Acceptance:** run the runner with the stub agent, **no coach**, `N=10000`.
- **Must pass:** conversion rate ∈ **[5.3%, 5.9%]** (the calibrated ~5.6%
  baseline); a trace log is written per episode.

A few decisions are pinned here so they are not re-litigated later:

- **The S5 gap is intentional** — the in-scope path skips the out-of-scope
  add-on step; states jump S4 → S6.
- **Baseline drop-off attribution:** `p_dropoff = {S4: 0.66, S6: 0.24, S7: 0.78}`,
  attributing the 24% intermediate drop to S6 (the only in-scope step between S4
  and S7), preserving the official ~5.6% baseline.
- **`price_gap_eur` is synthetic:** `final = provisional × (1 + surcharge)`,
  `surcharge ~ Uniform(0, 0.15)`.
- **Seeding:** every episode is seeded by its index; the *same* seed is used for
  the with-coach and without-coach runs, so the coach is the only variable.

## Phase 2 — Threshold detection + per-persona decision table

- **Builds:** `coach/detection.py` with a signal-**threshold** `detect()`;
  `coach/policy.py` with the per-persona table (below); `realize.py` with
  template strings. Per-persona `p_dropoff` and an assumed effectiveness factor
  move into config.
- **Acceptance:** run each persona with coach vs without, identical seeds; print
  uplift + annoyance rate.
- **Must pass:** for each persona, conversion *with* coach > *without* on
  identical seeds; **annoyance rate** (interventions fired with no genuine
  abandonment risk) is computed and reported.

The central technical challenge — one unified strategy fails:

| Persona | Primary drop | Interventions | Conversion counts as | Never do |
|---|---|---|---|---|
| **Judith** (Rising Hybrid) | initial price (S4) | market comparison · price reframe (€/day) · smooth advisor handoff | online purchase **or** advisor handoff | aggressive online-only push |
| **Franz** (Online Affine) | final price (S7) | justify price jump · cheaper-tariff alternative · save-progress/resume | online purchase **only** (handoff = failure) | suggest an advisor / add friction |
| **Peter** (Service Affine) | early, pre-price (S1–S3) | detect overwhelm early · proactive callback · simplify screen | qualified service contact (online is **not** the target) | push self-service / add options |

Discriminative signal signatures (guide thresholds now, the GBM next, bots in P5):

- **Peter:** high `dwell_total_s` + low `max_steps_completed`; `back_nav_count ≥ 2`;
  elevated `field_change_count`.
- **Judith:** long `dwell_current_s` on S4; high `tariff_hover_count`;
  `advisory_tariff_clicked` then `back`.
- **Franz:** low dwell on S1–S3; `external_tab_opens ≥ 1`; at S7 `price_gap_eur`
  over threshold + `hover_cancel_count ≥ 1`.

## Phase 3 — GBM detection

- **Builds:** a gradient-boosting `detect()` (same signature as the threshold one,
  selectable via config), trained on `(Signals → abandoned?)` pairs generated from
  the **same simulator**, so train and eval share signal-generation logic.
- **Tracks:** `training/train_gbm.py` logs to Weights & Biases (local, online — no
  cluster) — hyperparameters, per-persona precision/recall/AUC, confusion matrix,
  and **feature importances** (which double as the GBM's inspectability exhibit).
- **Acceptance:** ablation — GBM vs threshold on held-out simulated runs; print
  precision/recall for both.
- **Must pass:** GBM precision/recall reported and compared against the threshold
  baseline (the GBM need not win, but the comparison must exist and be honest).

## Phase 3.5 — Visualization

A **checkpoint phase, not a substrate change** — a thin viewer over the existing
`coach()`, built *before* the LLM work so the integration is developed against a
runnable demo. Framework: **NiceGUI** (its Playwright-backed test harness lets the
same test code run headless in CI and headed for the on-stage demo).

Two routes share one session, URL contract, and persona/method switchers:

- **`/` — debug viewer:** renders the funnel with the current step highlighted,
  shows the live `Signals`, supports step-through, and opens a dialog with the
  `Intervention` text + detection reason when `coach()` fires.
- **`/journey` — customer-facing journey** (the on-stage demo route): a stylized
  "HealthCover" signup with one branded page per step; the intervention popup is
  overlaid on the real product page as "A nudge from HealthCover."

The demo path writes a screenshot + video per persona scenario to `demo_videos/`
on every run — the stage-day fallback. **One command on stage**, rehearsed.

## Phase 4 — LLM intervention wording

Stands up the inference plumbing with the lowest-risk integration: one LLM call
per fired intervention, replacing template strings. **Bots stay scripted**, so
uplift numbers are unchanged — what is validated here is the swap boundary
(`INFERENCE_BASE_URL` + `MODEL_NAME`) and graceful degradation.

- **Acceptance:** generate wording per intervention type per persona; then re-run
  the harness with the endpoint **mocked to fail**.
- **Must pass:** wording reads naturally per persona register; **with the endpoint
  down, decisions are unchanged and the system degrades to templates** — proving
  decisions never depended on the endpoint.

## Phase 5 — LLM persona bots

With inference plumbing proven and wording in place, the bots layer on top of the
same path. **This is where intervention efficacy first becomes real** — Judith /
Franz / Peter actually read the Phase 4 wording and respond to it, so uplift is no
longer a parameter, it is an emergent measurement.

- **Builds:** `agent_llm.py` — personas as bots that emit the **same `Action`
  schema** (not chat). The LoRA fine-tune (on Leonardo) is the upgrade for bot
  *quality*, swapped in by changing only `INFERENCE_BASE_URL` + `MODEL_NAME`.
- **Acceptance:** validate every emitted action against the `Action` schema;
  re-run GBM precision/recall on bot-driven runs; report uplift *with* LLM wording
  vs templates only.
- **Must pass:** bots emit only valid `Action`s; GBM metrics on bot runs reported
  (drift vs simulated-data numbers flagged); uplift with LLM wording reported as
  the first **measured** efficacy number.

## Phase 6 — Results consolidation

- **Builds:** `eval/` consolidation — with/without coach, identical seeds,
  per-persona, per-step survival, annoyance rate, GBM precision/recall — assembled
  into `REPORT.md`.
- **Must pass:** every required result is present and sourced from the harness;
  per-persona conversion definitions correctly applied in the scorer.

## Experiment tracking

Two **training** jobs get tracked in Weights & Biases (inference and simulation do
not need it):

- **GBM (Phase 3) — local, online.** Logs hyperparameters, per-persona
  precision/recall/AUC, confusion matrix, and the feature-importance plot.
- **LoRA (Phase 5) — on Leonardo, offline.** The cluster compute nodes have no
  internet, so W&B runs in `WANDB_MODE=offline` and is `wandb sync`'d from a login
  node. Logs loss curves, learning rate, and eval metrics.

The W&B API key goes via `wandb login` / env var — **never in the repo.**
