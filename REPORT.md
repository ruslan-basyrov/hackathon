# {Team Name} — Insurance AI (UNIQA)

## Team

- **{Name}** — {role, e.g. simulation / coach logic}
- **{Name}** — {role, e.g. LLM / persona bots}
- **{Name}** — {role, e.g. UI / demo}

**Track:** Insurance AI (UNIQA) — AI-Guided Conversion Flow

---

## TL;DR

We built a **Conversion Coach** for UNIQA's online health-insurance calculator: a
detection-and-decision layer that watches behavioural signals, decides *when* and
*how* to nudge a hesitating user, and routes out-of-scope users cleanly to an
advisor. All of the when/how logic is **inspectable code** (a state machine, a
detector, and an explicit per-persona policy table); the LLM only drives the
synthetic users and phrases the nudges. On a seeded journey simulator the harness
measures per-persona uplift on identical with/without-coach populations, and a GBM
detector lifts abandonment recall from 0.25 to 0.99 over hand-written thresholds.

---

## Problem

Out of 1,000 people who start UNIQA's 15-step calculator, only ~56 complete an
online purchase (**5.6%**). The drop-off cliffs are known but un-reacted-to: **66%**
abandon at the initial price screen (S4) and **78%** at the personalised final
price (S7); everyone gets the same static funnel regardless of whether they are
hesitating, comparing, or sticker-shocked.

We solved the **in-scope online-purchasable path only**: private-doctor tariffs,
"insure myself", Start (€38.74) / Optimal (€68.14). **Conversion = online purchase
completion.** Hospital, "other persons", and the advisory-required Opt.Plus /
Premium tariffs are explicitly *not* coached — they are routed to an advisor as a
clean exit (a valid outcome, but not a conversion win for this track).

We treat all three segments as first-class, because a single unified nudge strategy
fails — each abandons for a different reason, at a different step:

- **Judith** (Segment 1, Rising Hybrid, 30%) — hesitates at the **initial price (S4)**.
- **Franz** (Segment 2, Online Affine, 50%) — bolts at the **final price (S7)**; must never be pushed to a human.
- **Peter** (Segment 3, Service Affine, 20%) — overwhelmed **early (S1–S3)**, before price; wants a person.

---

## Approach

- **Decision logic in code, never in weights.** A pure state machine
  (`state_machine.py`, no randomness), a deterministic feature extractor
  (`signals.py`), and a three-stage coach: `detect` (when) → `policy.lookup` (which)
  → `realize` (how/wording). This directly serves the rubric's "traceable decision
  rules / trigger precision-recall / annoyance rate".
- **Two interchangeable detectors behind one frozen `detect(signals, cfg)`**:
  hand-written **thresholds** (Phase 2, the ablation baseline) and an **xgboost
  GBM** (Phase 3) trained on `(Signals → abandoned?)` pairs from the *same*
  simulator, so train- and detect-time see one feature distribution.
- **An explicit per-persona × step policy table** (`coach/policy.py`) — Judith gets
  a €/day price reframe at S4 and a transparency nudge at S7; Franz gets an
  advisory-alternative explainer at S4 and a price-justification at S7 (and *never*
  a handoff — that's failure for him); Peter gets an early **callback** handoff.
  Per-persona **conversion definitions** are applied in the scorer (`runner.py`):
  handoff counts as success for Judith/Peter, as failure for Franz.
- **The model is one swap boundary** (`INFERENCE_BASE_URL` + `MODEL_NAME`), used by
  both the wording layer (`coach/llm_realize.py`) and the persona bots
  (`simulation/`). With the endpoint down the system **degrades to templates and
  decisions are byte-for-byte unchanged** — proving decisions never depend on the LLM.
- **Where it runs:** the whole harness, GBM training, and the NiceGUI demo run
  locally, CPU-only, no API key. The persona-bot LoRA fine-tune
  (`training/train_lora.py`, Qwen2.5-7B) is the one Leonardo job (W&B offline,
  synced from a login node).

A second layer (`simulation/engine.py`) drives the personas as **actual LLM bots**
that read the coach's wording and react — this is where intervention *efficacy*
stops being a parameter and becomes an emergent measurement.

---

## How to run it

See [README.md](README.md) for the full guide. The essentials (CPU-only, no key):

```bash
python -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
python runner.py                       # baseline + per-persona uplift table
pytest tests/                          # phase 1–4 acceptance gates
python -m training.train_gbm --no-wandb   # train models/gbm.json + feature importances
python -m services.ui.app              # NiceGUI demo on http://localhost:8080  (/ and /journey)
```

LLM wording/bots are opt-in: start any OpenAI-compatible server, set
`realize.method: llm` and the `inference_base_url` / `model_name` knobs in
`config.yaml` (see README → *Optional: real LLM wording and bots*).

---

## Results

Numbers below are from this repo at the documented commit. The harness is fully
seeded, so they reproduce exactly.

### Baseline (Phase 1)

Scripted agent, **no coach**, global profile: **~5.7% online conversion**
(`n=10000`; the Phase-1 gate holds the calibrated ~5.68% at `n=100000` inside
[5.3%, 5.9%]), with **zero advisor routing** on the in-scope path. Per-step survival
reproduces the official funnel math (`0.34 × 0.76 × 0.22 ≈ 5.6%`), with the 24%
intermediate drop attributed to S6 (see *honesty* below).

### Per-persona uplift (Phase 2, paired control vs coach on identical seeds, `n=10000`)

| Persona | without | with Coach | uplift | fired | wasted | saved |
|---|---|---|---|---|---|---|
| Judith | 15.4% | 39.8% | **+24.4 pp** | 100.0% | 15.4% | 24.4% |
| Franz | 13.0% | 28.7% | **+15.8 pp** | 63.8% | 14.2% | 24.8% |
| Peter | 39.2% | 91.9% | **+52.7 pp** | 66.2% | 20.4% | 79.6% |

- *fired* = % of users shown an intervention; *wasted* = of those, the share who'd
  have succeeded anyway (the annoyance / over-route cost); *saved* = of those, the
  share the intervention actually rescued.
- The **Franz fix** holds: his interventions are no longer dominated by unnecessary
  S4 nudges (wasted-rate 14.2%, well under the 40% gate) — advisory-tariff
  engagement is treated as a *signal*, not a trigger.

> **Read this before quoting the uplift.** In the scripted harness (Phases 1–4) a
> coach intervention reduces drop-off by an **assumed effectiveness parameter**
> (`intervention_effectiveness.default = 0.45` in `config.yaml`). So these uplift
> numbers validate that the **measurement plumbing is correct** (paired seeds,
> per-persona conversion definitions, fired/wasted/saved accounting) — **not** that
> the wording is persuasive. Efficacy becomes a *measured* quantity only when the
> LLM persona bots (`simulation/`) actually read and react to the wording.

### Detection ablation (Phase 3, GBM vs threshold, held-out seed, `n_test=800/persona`)

| Method | scope | precision | recall | F1 |
|---|---|---|---|---|
| threshold | overall | 0.798 | 0.252 | 0.383 |
| threshold | judith | 0.809 | 0.277 | 0.413 |
| threshold | franz | 0.820 | 0.121 | 0.210 |
| threshold | peter | 0.779 | 0.438 | 0.560 |
| **GBM** | overall | 0.784 | **0.990** | **0.875** |
| GBM | judith | 0.849 | 0.979 | 0.910 |
| GBM | franz | 0.844 | 1.000 | 0.915 |
| GBM | peter | 0.636 | 0.991 | 0.775 |

The GBM trades a sliver of overall precision (0.80 → 0.78) for an enormous recall
gain (0.25 → 0.99): the thresholds miss most abandoners (especially Franz, recall
0.12), while the GBM catches nearly all of them. Honest caveat: the GBM is trained
and evaluated on the *same* synthetic generator (seed 0 train / seed 1 test), so it
partly learns the generator — the real test of detection is on bot-driven,
non-scripted behaviour (next steps). Feature importances (logged to W&B) double as
the GBM's traceable-rules exhibit.

### Graceful degradation (Phase 4)

With `realize.method: llm` and the endpoint mocked to fail on every call, the
per-persona `success_with` and `fired_rate` are **identical** to the template
baseline — decisions never touched the network. Verified by
`tests/test_phase4_wording.py::test_decisions_unchanged_when_endpoint_down`.

Raw numbers reproduce via `python runner.py` and `pytest tests/`; the validated
logics are written up in [extras/hypotheses.md](extras/hypotheses.md).

---

## What worked

- **The "decision logic in code, LLM for words" split.** It made every claim
  auditable: you can read exactly why the coach fired and what it chose, and the
  Phase-4 test proves the LLM is never load-bearing for a decision.
- **The paired-seed counterfactual harness.** Because episode *i* is the same
  simulated user with and without the coach, uplift, wasted-rate and saved-rate fall
  out cleanly — and the same `compare()` code path feeds the CLI table, the tests,
  and the UI aggregate panel (no duplicated metric code).
- **The GBM recall jump and the per-persona policy.** Modelling each segment's drop
  step separately (and refusing to push Franz to a human) is what makes the numbers
  defensible rather than a single blunt nudge — and the GBM closes the recall gap
  the thresholds leave open.

---

## What didn't work

- **Real, at-scale efficacy from the LLM bots.** The plumbing for LLM-driven
  personas exists (`simulation/engine.py`, `llm_bot.py`, `llm_coach_bot.py`) and
  works through `SimulationEngine`, but we did not get a large, seeded
  bot-vs-bot uplift run consolidated into a number — so the headline uplift remains
  parameter-driven, not measured. This is the honest gap.
- **`main.py` (the LLM-sim CLI) is currently broken on import** — it imports
  `resolve_model` from `utils.llm_client`, which doesn't exist there (and its result
  is unused). The engine works when driven directly (the UI's `mode=live` does), but
  the CLI wrapper needs that one line removed.
- **Two `simulation/` modules are dead code.** `simulation/coach.py` and
  `simulation/ai_coach.py` are imported nowhere — leftovers from an earlier merge
  that should be deleted.

---

## What you'd do with another 36 hours

- Remove the `main.py` import bug and delete the dead `simulation/coach.py` /
  `ai_coach.py`, then run **N≥2,000 seeded bot-driven episodes per persona** to
  produce the first *measured* (not parameter-driven) uplift, with the LLM wording
  on vs templates only.
- Re-run the Phase-3 ablation **on bot-driven signals** (not the scripted generator)
  and report the precision/recall drift — the real test of whether detection
  generalises beyond the data it was trained on.
- Fit `intervention_effectiveness` from the bot reactions instead of assuming 0.45,
  and calibrate the synthetic S7 price-gap surcharge against any real distribution
  UNIQA can share.
- Sweep intervention *timing* and thresholds as a third axis, and surface drop-off
  patterns not visible in UNIQA's current step-level data.

---

## Track-specific deliverables (Insurance AI / UNIQA)

- [x] Working Conversion Coach prototype runs (`python runner.py`, `pytest tests/`).
- [x] Simulation across at least three personas (Judith / Franz / Peter, per-persona policy + conversion definitions).
- [x] Hypotheses document with 2–3 validated logics — [extras/hypotheses.md](extras/hypotheses.md).
- [x] Demo handles one persona from each segment — `services/ui/` `/journey` route + `services/ui/tests/scenarios.py` (Judith S4, Franz S7, Peter early).

---

## Credits & dependencies

- **Open-source libraries:** Python ≥3.10, `pyyaml`, `numpy`, `xgboost`,
  `scikit-learn`, `openai` (client only), `nicegui` + `playwright` (demo/tests),
  `wandb` (tracking). LoRA env (Leonardo only): `torch`, `transformers`, `peft`,
  `trl`, `accelerate`, `datasets`. Versions in `requirements.txt` / `pyproject.toml`
  / `uv.lock`.
- **Pre-trained models:** Qwen2.5 instruct (1.5B for fast iteration, 7B as the
  fine-tune base) served via vLLM (FP8) — local-first; any OpenAI-compatible
  endpoint works.
- **External APIs:** none required to reproduce results. Optional OpenAI-compatible
  endpoints (local vLLM / Ollama, or remote Featherless / OpenAI) for LLM wording
  and bots.
- **Datasets:** UNIQA-provided persona briefings, funnel documentation, product
  reference, and `personas.json` (segmentation research, n=4,004) in
  `tracks/insurance-uniqa/` — cleared for hackathon use, no real-customer PII.
- **AI coding assistants used:** {Claude Code / Cursor / Copilot / … — fill in}.

---

## A note on honesty

We want the gaps on the table:

1. **Uplift in Phases 1–4 is parameter-driven**, not measured. The scripted agent
   reduces drop-off by `intervention_effectiveness=0.45` — so the uplift numbers
   prove the *harness measures correctly*, not that the nudges persuade. Real
   efficacy requires the LLM bots, which we wired but did not run at scale.
2. **The S7 price gap is synthetic.** `final = provisional × (1 + Uniform(0, 0.15))`
   (config-tunable); the real distribution is a documented unknown.
3. **The 24% intermediate drop is attributed to S6**, because the official 24% sits
   at the out-of-scope S5 (which we deliberately omit). This is a config choice that
   preserves the ~5.6% baseline; the two-drop variant is runnable.
4. **The GBM is trained and tested on the same synthetic generator**, so its 0.99
   recall partly reflects learning the generator, not real users.
5. **`main.py` does not run as-is** (the `resolve_model` import), and
   `simulation/coach.py` / `ai_coach.py` are dead code. The validated artifact is
   the deterministic harness + GBM + UI, all of which run from a clean checkout.

---

*Submitted by team {Team Name} for Zero One Hack_01, 2026.*
