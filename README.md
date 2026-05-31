# Conversion Coach — UNIQA Insurance AI

An **AI-guided Conversion Coach** for UNIQA's online health-insurance calculator.
It detects, in real time, when a user is about to abandon the funnel and intervenes
with a persona-appropriate nudge — then *proves* the effect by running synthetic
personas through a seeded journey simulator, with and without the Coach, on
identical seeds.

> **Track:** Insurance AI (UNIQA) — AI-Guided Conversion Flow.
> Built to the staged contract in [BUILD_SPEC.md](BUILD_SPEC.md). Full write-up in
> [REPORT.md](REPORT.md); validated logics in [extras/hypotheses.md](extras/hypotheses.md).

---

## The one idea

**The decision logic lives in inspectable code; the LLM only produces behaviour
(persona bots) and words (intervention wording) — never decisions.** This is
deliberately *not* an LLM-wrapper: the state machine, the detection layer, and the
per-persona policy are all readable code you can audit. The model is reached behind
a single swap boundary (`INFERENCE_BASE_URL` + `MODEL_NAME`) and is never on the
critical path for a decision.

```
Signals  →  coach()  →  Action  →  state_machine.step()
   ▲          │ detection.detect()   (threshold | GBM)
   │          │ policy.lookup()      (per-persona table)
   └──────────┘ realize.realize()    (template | LLM, graceful fallback)
```

---

## What's in the box

The repo is two layers over one shared substrate (`state_machine.py`,
`signals.py`, `coach/`):

| Layer | Driver | Decision logic | Wording | Entry point |
|---|---|---|---|---|
| **Deterministic harness** (validated artifact) | `agent_stub.py` (scripted; the only place drop-off randomness lives) | `coach/` threshold **or** GBM | templates, or LLM with graceful fallback | [`runner.py`](runner.py) |
| **LLM persona-bot simulation** (experimental) | `simulation/llm_bot.py` (Judith/Franz/Peter as LLM bots that read & react to the nudge) | `simulation/intervention_model.py` (rule / LLM / GBM) | `simulation/engine.py` |

The harness is what produces the reproducible numbers (it needs no GPU and no API
key). The LLM layer is where intervention *efficacy* becomes emergent rather than
parameterised — see [REPORT.md](REPORT.md).

### Key files

```
state_machine.py    in-scope funnel (S0→S1→S2→S3→S4→S6→S7→S12); no S5 (out of scope)
signals.py          Signals dataclass + deterministic extract(state, history)
agent_stub.py       scripted persona behaviour; per-episode confident/struggling sub-profiles
coach/
  __init__.py       coach(signals, persona, cfg) -> Intervention | None   (detect→policy→realize)
  detection.py      WHEN: threshold rules (Phase 2) | xgboost GBM (Phase 3)
  policy.py         WHICH: explicit per-persona × step intervention table
  realize.py        HOW (wording): templates | LLM, with graceful fallback
  llm_realize.py    the only Phase-4 caller of the inference endpoint
  features.py       Signals → fixed-order vector for the GBM
runner.py           episode loop, paired control-vs-coach compare(), conversion accounting
config.yaml         per-persona p_dropoff, thresholds, surcharge, effectiveness, model knobs
training/
  data_gen.py       (Signals → abandoned?) pairs from the SAME simulator
  train_gbm.py      local xgboost training + W&B + feature importances (the GBM's exhibit)
  train_lora.py     Leonardo-only LoRA SFT for persona bots
services/ui/        NiceGUI demo: / (debug) and /journey (on-stage, branded "HealthCover")
simulation/         LLM persona-bot engine + funnel wrapper + intervention models
tests/              one acceptance test per phase (1 baseline, 2 uplift, 3 ablation, 4 wording)
```

---

## Setup

Python ≥ 3.10. Either use `uv` (recommended — exact pins from `uv.lock`):

```bash
uv sync                       # core harness
uv sync --all-extras          # + GBM, UI, LoRA, dev
```

…or a plain venv with `requirements.txt`:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Nothing above needs a GPU or an API key. The LLM-backed paths are opt-in (see
[Inference](#optional-real-llm-wording-and-bots)).

---

## How to run it

All commands assume the venv interpreter (`.venv/bin/python`, or just `python`
inside `uv run`).

### 1. Baseline + per-persona uplift (no GPU, no API key)

```bash
python runner.py                 # default n=10000 from config.yaml
python runner.py --n 50000       # larger sample
```

Prints the Phase-1 global baseline (~5.7% online conversion) and the Phase-2
per-persona control-vs-coach comparison on **identical seeds**, with
`fired / wasted / saved` accounting. A sample of full step traces is written to
`traces.jsonl` (demo material).

### 2. Acceptance tests (the gates)

```bash
pytest tests/                    # phase 1–4
```

- **Phase 1** — baseline conversion ∈ [5.3%, 5.9%], zero advisor routing.
- **Phase 2** — per-persona uplift > 0 on identical seeds; wasted-rate reported; Franz wasted-rate < 0.40.
- **Phase 3** — trains a temp GBM, prints the GBM-vs-threshold ablation table (honest comparison, GBM need not win).
- **Phase 4** — LLM wording per intervention type with the client **mocked**; proves graceful degradation (endpoint down → templates → decisions byte-for-byte unchanged). No server required.

### 3. Train the GBM detector

```bash
python -m training.train_gbm --no-wandb         # writes models/gbm.json
```

Prints overall + per-persona precision/recall/AUC and **feature importances**
(the GBM's traceable-rules exhibit). Drop `--no-wandb` and run `wandb login` to log
the run. To use the GBM at runtime, set `detection.method: gbm` in `config.yaml`.

### 4. The visual demo (NiceGUI)

```bash
python -m services.ui.app        # serves on http://localhost:8080
```

- `/` — debug viewer: the in-scope funnel, live `Signals`, and a dialog whenever the Coach fires.
- `/journey` — the on-stage "HealthCover" signup; auto-plays a persona through the funnel and overlays the nudge as a product feature. URL contract: `?seed=N&episode=N&persona=judith|franz|peter&method=threshold|gbm|llm&mode=auto|interactive|live`.

Headless gate + headed rehearsal (needs the `ui` extra and `playwright install chromium`):

```bash
pytest services/ui/tests/test_ui.py services/ui/tests/test_journey.py
pytest services/ui/tests/test_demo.py --headed --slowmo=400 --video=on   # writes demo_videos/
```

Fixed `(seed, episode)` demo scenarios live in `services/ui/tests/scenarios.py`
(Judith S4 dwell, Franz S7 gap+cancel, Peter early form re-edits).

### Optional: real LLM wording and bots

Both LLM paths are opt-in and degrade gracefully when no endpoint is reachable
(the harness falls back to templates; decisions never change). Point them at any
OpenAI-compatible server:

```bash
cp .env.example .env             # set MODEL_ID / MODEL_NAME (+ HF_TOKEN if gated)
docker compose --profile inference up -d inference   # local vLLM (FP8), host port 8003
```

The two model-swap knobs are `inference_base_url` + `model_name` in `config.yaml`
(or env). See [services/inference/README.md](services/inference/README.md) for vLLM /
Ollama / remote options and the **Blackwell sm_120** attention-backend trap.

To get LLM **wording** in the harness, set `realize.method: llm` in `config.yaml`.
The LLM client (`utils/llm_client.py`) also reads `FEATHERLESS_API_KEY` or
`OPENAI_API_KEY` from the environment for a remote endpoint; with no key it runs in
a mock mode.

> **Known issue:** the LLM persona-bot CLI `main.py` currently fails on import
> (`resolve_model` is imported from `utils.llm_client` but not defined there, and
> its result is unused). Drive the LLM simulation through
> `simulation.engine.SimulationEngine` (as `services/ui/session.py` does in
> `mode=live`) until that import is removed. See REPORT "A note on honesty".

### Persona-bot fine-tune (Leonardo only)

```bash
pip install -e .[lora]                                   # GPU env, do NOT install locally
python -m training.train_lora --base Qwen/Qwen2.5-7B-Instruct   # W&B offline; sync from a login node
```

`training/leonardo.sbatch` / `leonardo_simulation.sbatch` are the SLURM wrappers.

---

## Scope (what the Coach does and doesn't touch)

In scope: the **private-doctor**, **"myself"**, **online-purchasable** path
(Start €38.74 / Optimal €68.14). **Conversion = online purchase completion.**
Out of scope and cleanly routed to an advisor (no coaching): the hospital path,
the "other persons" branch, and the Opt.Plus / Premium tariffs. The funnel keeps
**S5 deliberately absent** (the hospital add-on step), so states jump S4 → S6; the
24% intermediate drop is attributed to S6 to preserve the ~5.6% baseline (see
[REPORT.md](REPORT.md) and `config.yaml`).

Data lives in [tracks/insurance-uniqa/](tracks/insurance-uniqa/) (personas, funnel
doc, product reference, `personas.json` with segments `segment_1/2/3`).

---

## Results at a glance

| | baseline | with Coach | uplift |
|---|---|---|---|
| Global (online conversion) | ~5.7% | — | — |
| Judith (S1, Rising Hybrid) | 15.4% | 39.8% | +24.4 pp |
| Franz (S2, Online Affine) | 13.0% | 28.7% | +15.8 pp |
| Peter (S3, Service Affine) | 39.2% | 91.9% | +52.7 pp |

GBM detection lifts recall from **0.25** (thresholds) to **0.99** at comparable
overall precision (~0.80 → ~0.78). **Important:** in the scripted harness, uplift is
*parameter-driven* — it validates the measurement plumbing, not coaching efficacy.
Read [REPORT.md](REPORT.md) for the full numbers, caveats, and per-persona
conversion definitions.

---

## License

MIT — see [LICENSE](LICENSE).

---

<sub>**Note on placement:** these submission files were drafted into `sub/`. For the
actual submission they belong at the repo root — `README.md`, `REPORT.md`,
`requirements.txt` at the top level and `hypotheses.md` at `extras/hypotheses.md`.
The relative links above assume that final (repo-root) placement.</sub>
