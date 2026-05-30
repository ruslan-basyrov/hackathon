# Conversion Coach — Build Spec

**Track:** Insurance AI (UNIQA) — AI-Guided Conversion Flow
**Audience:** the coding agent building this, and the human steering it.
**Reference docs (for numbers only, not architecture):** `tracks/insurance-uniqa/` — the funnel doc, persona files, `personas.json`, and the track spec. Consult them to look up a specific figure. Do **not** redesign the architecture from them; this document is the architecture.

---

## 0. The one idea this whole project is built on

**Decision logic lives in inspectable code. The LLM produces behavior (persona bots) and words (intervention wording) — never decisions.**

This track is explicitly *not* an LLM-wrapper case and the jury grades "traceable decision rules," "trigger precision/recall," and "annoyance rate." A coach whose when/how policy is fused into model weights has nothing inspectable to show and scores poorly. So: the state machine, the detection layer, and the decision/policy layer are all readable code. The model only drives the synthetic users and phrases an intervention *after* the policy has decided to fire it.

**Build the measurement substrate first; upgrade components into it.** The eval harness is not the finale — it is the scaffold built in Phase 1 and filled in every phase after. Every later phase is "swap a stub for a real component and re-run the same harness."

---

## 1. Operating protocol (read this before writing any code)

This is how the build stays steerable and avoids dead-ends.

1. **The interfaces in §3 are frozen.** Do not change a frozen signature or dataclass field without first surfacing the proposed change, the reason, and waiting for approval. Everything *behind* an interface is yours to implement and redo freely; nothing in front of one may trap a neighbour.
2. **Build one phase at a time, in order (§5).** At each phase boundary: (a) `git commit`, (b) run that phase's acceptance test, (c) report the result and the number it produced, (d) **stop and wait for go-ahead** before starting the next phase. Do not run multiple phases silently.
3. **A phase is "done" only when its acceptance test passes.** The acceptance test, not your judgement, defines "correct." If you believe a phase is done but the test isn't written or doesn't pass, it isn't done.
4. **When uncertain, stop and ask — do not guess.** For any modelling decision not pinned in §4 (a new signal, a drop-off attribution, a persona threshold, a metric definition), state the options, give a recommendation, and wait. The decisions already made for you are in §4 — do not re-litigate those.
5. **Commit at every checkpoint so any phase is a clean rewind.** If a phase goes wrong, we `git reset` to the previous phase's commit. The frozen interfaces make this safe.
6. **Obey the non-goals (§6) as hard prohibitions.** Over-building a phase is a way of cornering it.

---

## 2. Suggested repo layout

A starting skeleton. The module split is fixed (it mirrors the frozen seams); internal data structures inside each module are yours.

```
state_machine.py      # Step enum, transition table, step() — pure mechanics, NO randomness
signals.py            # Signals dataclass, extract(state, history) -> Signals
agent.py              # Agent protocol (the act() contract)
  agent_stub.py       #   scripted agent — randomness (p_dropoff) lives HERE
  agent_llm.py        #   LLM persona bots (Phase 4) — same Action contract
coach/
  __init__.py         # coach(signals, persona, policy) -> Intervention | None
  detection.py        # detect(signals, persona) -> bool/score — threshold (P2) and GBM (P3) behind one fn
  policy.py           # per-persona decision table: which intervention, given state+persona
  realize.py          # realize(intervention, persona) -> str — templates (P2) and LLM (P5) behind one fn
runner.py             # episode loop, seeding, trace logging, aggregation
config.yaml           # p_dropoff, effectiveness, surcharge dist, seeds, thresholds,
                      #   INFERENCE_BASE_URL + MODEL_NAME (§8), wandb project (§9)
eval/                 # metric computation + report generation (reads traces)
tests/                # one acceptance test per phase
training/
  train_gbm.py        # local GBM training + W&B logging (§9) — no cluster needed
  train_lora.py       # LoRA fine-tune on Leonardo + W&B offline (§9)
docker-compose.yml    # service topology (§7)
services/
  inference/          # OpenAI-compatible model server — the swap boundary (§8)
  coach.Dockerfile    # packages the root modules + coach/ into the coach service
  ui.Dockerfile       # NiceGUI viewer (Phase 3.5)
README.md REPORT.md LICENSE requirements.txt   # submission requirements
```

The root modules (`state_machine.py` … `runner.py`) plus `coach/` are the **coach service**; the LLM lives in a separate **inference service** (§7–§8). Submission hygiene from day one: MIT `LICENSE`, pinned `requirements.txt` (or Pixi manifest), no secrets in git (proxy creds, `HF_TOKEN`, **W&B API key**), runs from clean checkout.

---

## 3. Frozen interfaces

> **FROZEN.** Do not alter these signatures or field sets without surfacing the change first.

### Action — the universal driver output

Every agent (scripted stub now, LLM bots later) emits this. This is the seam that lets you swap drivers without touching anything downstream.
```python
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class Action:
    type: Literal["continue", "back", "select", "hover", "change_field", "open_tab", "abandon"]
    target: Optional[str] = None   # tariff/element/field, or branch choice:
                                   #   "doctor"|"hospital"|"both" (S1), "myself"|"others" (S2),
                                   #   "Start"|"Optimal"|"OptPlus"|"Premium" (S4), "cancel" (S7 hover)
    dwell_s: float = 0.0           # seconds spent on the current screen BEFORE this action
```

`dwell_s` riding on every action is how dwell/inactivity signals are computed without a separate clock. `back`/`hover`/`change_field`/`open_tab` do not advance the step — they are signal-generating.

### Signals — the feature vector

Recomputed from action history after each step. Consumed by `detect()` (threshold and GBM) and by `policy.py`. **Adding a signal is a §4 "ask first" decision.**

```python
@dataclass
class Signals:
    # progress / time
    step: int
    steps_completed: int
    dwell_current_s: float
    dwell_total_s: float
    time_since_last_action_s: float
    # navigation / friction
    back_nav_count: int
    back_from_step: Optional[int]
    field_change_count: int
    # S4-specific (price table)
    tariff_hover_count: int
    advisory_tariff_clicked: bool      # clicked Opt.Plus/Premium — the "advisory-only wall"
    tariff_selected: Optional[str]
    external_tab_opens: int            # comparison-tab behaviour
    # S7-specific (final price)
    price_gap_eur: float               # final - provisional (synthetic; see §4)
    hover_cancel_count: int
```

### Coach and Agent contracts

```python
# coach/__init__.py
def coach(signals: Signals, persona: str, policy) -> Optional["Intervention"]:
    """Decide whether to intervene and, if so, with what. Pure decision logic.
       Phase 1: stub (fixed step or no-op). Phase 2: threshold + policy. Phase 3: GBM + policy."""

# agent.py
class Agent(Protocol):
    def act(self, state, signals: Signals, intervention, rng) -> Action:
        """Produce the next action. The ONLY place stochastic drop-off lives.
           An intervention may lower this step's drop-off probability or swap a branch choice."""
```

`Intervention` carries at least `{type, persona, step, text}`. `text` is empty until `realize()` fills it (templates in P2, LLM in P5).

---

## 4. Decisions already made (do not re-litigate)

These resolve the known ambiguities. They are parametrised so a mentor can override, but the defaults are set.

- **The S5 gap is intentional.** The in-scope private-doctor path skips Step 5 (the add-on/hospital step, out of coaching scope). States jump S4 → S6.
- **Baseline drop-off attribution.** Official math is `0.34 × 0.76 × 0.22 ≈ 5.6%` across three drops, but the middle drop (24%) is the out-of-scope Step 5. Resolution: **attribute the 24% intermediate drop to S6 (health questions)** — the only in-scope step between S4 and S7 — preserving the 5.6% baseline. So `p_dropoff = {S4: 0.66, S6: 0.24, S7: 0.78}`. Make it config so the two-drop variant (`0.34 × 0.22 ≈ 7.5%`) is runnable. **Note this choice in REPORT.md** (the README asks for known-gap flagging).
- **`price_gap_eur` is synthetic** (the real distribution is a documented unknown). Draw `final = provisional × (1 + surcharge)`, `surcharge ~ Uniform(0, 0.15)` (config-tunable). Calibration anchors from the persona docs: Optimal €68.14 → ~€72 (+~6%) to ~€74.82 (+~10%). Document the assumption.
- **One global `p_dropoff` until Phase 2.** Per-persona drop-off and policy arrive in Phase 2; Phase 1 uses a single global profile.
- **Seeding:** every episode is seeded by its index; the *same* seed is used for the with-coach and without-coach runs so the coach is the only variable.
- **Conversion is computed in-code over seeded episodes — never by browser automation.** (See non-goals.)
- **Model access is via `INFERENCE_BASE_URL` + `MODEL_NAME` only** (§8). The default is a local small model; no cloud provider is a hard dependency. Swapping to the fine-tuned model or a remote endpoint changes only these two values.
- **Experiment tracking is Weights & Biases** (§9): online locally for the GBM, offline-then-synced on Leonardo for the LoRA.

### ⚠️ What each phase actually validates (prevents a subtle dead-end)

In Phases 1–3 the agent is **scripted**, so a coach intervention reduces drop-off by a **parameter** (an *assumed* effectiveness factor in config). Therefore the uplift number in Phases 1–3 validates the **plumbing and the measurement**, not the **efficacy** of the interventions. Efficacy only becomes real in Phase 4–5, when LLM persona bots *react to the actual intervention wording*. Do not claim "the coach works" from Phase 1–3 numbers — claim "the harness measures uplift correctly." State this distinction in REPORT.md.

---

## 5. The phases

Each phase lists: **Builds**, **Replaces** (which stub), **Acceptance command**, **Must print/pass**, **Checkpoint**. Stop at every checkpoint.

### Phase 1 — Skeleton + baseline
- **Builds:** `state_machine.py` (states + transition table below), `signals.py` (extractor), `agent_stub.py` (scripted; drop-off randomness lives here), `coach` as a no-op/fixed-step stub, `runner.py` (episode loop + seeding + trace log + conversion aggregation).
- **Replaces:** nothing — this is the substrate.
- **Acceptance command:** run the runner with the stub agent, **no coach**, `N=10000`.
- **Must pass:** conversion rate ∈ **[5.3%, 5.9%]** (the calibrated ~5.6% baseline). Trace log written per episode.
- **Checkpoint:** commit, report the conversion number, wait.

States and transitions (FROZEN structure; the `Step` values are fixed):

```python
class Step(Enum):
    START=0; S1_COVERAGE_TYPE=1; S2_FOR_WHOM=2; S3_PERSONAL_DATA=3
    S4_INITIAL_PRICE=4; S6_HEALTH_QS=6; S7_FINAL_PRICE=7; S12_CLOSING=12
    CONVERTED=90; ABANDONED=91; ROUTED_ADVISOR=92
# (no S5 — out of scope, deliberate)
```

```
S1: select "doctor" + continue -> S2 ;  "hospital"|"both" -> ROUTED_ADVISOR
S2: select "myself" + continue -> S3 ;  "others"          -> ROUTED_ADVISOR
S3: continue -> S4
S4: select "Start"|"Optimal" + continue -> S6 ;  "OptPlus"|"Premium" -> ROUTED_ADVISOR  (coach may redirect, P2+)
S6: continue -> S7
S7: continue -> S12
S12: continue -> CONVERTED
any non-terminal: abandon -> ABANDONED ; back -> previous in-scope step
```

The scripted agent draws `abandon` with probability `p_dropoff[step]` at critical steps, else `continue`, with small noise on dwell/back-nav/hover so signals have variance.

### Phase 2 — Threshold detection + per-persona decision table
- **Builds:** `coach/detection.py` with a **signal-threshold** `detect()` (e.g. fire if `dwell_current_s > X` and `back_nav_count ≥ 2`); `coach/policy.py` with the **per-persona table** (§ below); `realize.py` with template strings. Per-persona `p_dropoff` and an assumed per-(persona, intervention) effectiveness factor in config.
- **Replaces:** the no-op coach stub.
- **Acceptance command:** run each persona with coach vs without, identical seeds; print uplift + annoyance rate.
- **Must pass:** for each persona, conversion *with* coach > *without* on identical seeds; **annoyance rate** (interventions fired with no genuine abandonment risk) is computed and reported; per-persona conversion *definitions* applied (below).
- **Checkpoint:** commit, report per-persona uplift + annoyance, wait.

Per-persona decision table (the central technical challenge — one unified strategy fails):

| Persona | Primary drop | Interventions | Conversion counts as | Never do |
|---|---|---|---|---|
| **Judith** (S1, Rising Hybrid) | initial price (S4) | market comparison · price reframe (€/day) · smooth advisor handoff | online purchase **OR** advisor handoff | aggressive online-only push |
| **Franz** (S2, Online Affine) | final price (S7) | justify price jump · cheaper-tariff alternative · save-progress/resume | online purchase **only** (handoff = failure) | suggest an advisor / add friction |
| **Peter** (S3, Service Affine) | early, pre-price (S1–S3) | detect overwhelm early · proactive callback · simplify screen | qualified service contact (online **not** the target) | push self-service / add options to screen |

Discriminative signal signatures (guide thresholds now, GBM next, bots in P4):
- **Peter:** high `dwell_total_s` + low `steps_completed`; `back_nav_count ≥ 2`; elevated `field_change_count`.
- **Judith:** long `dwell_current_s` on S4; high `tariff_hover_count`; `advisory_tariff_clicked` then `back`.
- **Franz:** low dwell on S1–S3; `external_tab_opens ≥ 1`; at S7 `price_gap_eur` over threshold + `hover_cancel_count ≥ 1`.

### Phase 3 — GBM detection
- **Builds:** gradient-boosting `detect()` (same function/signature as the threshold one, selectable via config), trained on `(Signals → abandoned?)` pairs generated from the **same simulator** (scripted agent), so train and eval share signal-generation logic.
- **Tracks:** `training/train_gbm.py` logs to W&B (local, online — no cluster) — hyperparameters, per-persona precision/recall/AUC, confusion matrix, and **feature importances**, which double as the GBM's traceable-rules inspectability exhibit (§9).
- **Replaces:** the threshold `detect()` (kept as a baseline for ablation).
- **Acceptance command:** ablation — GBM vs threshold on held-out simulated runs; print precision/recall for both.
- **Must pass:** GBM precision/recall reported and compared against the threshold baseline (GBM need not win, but the comparison must exist and be honest). The W&B run holds the ablation comparison and the feature-importance plot.
- **Checkpoint:** commit, report the ablation table, wait.

### Phase 3.5 — Visualization (a window pops up when the coach fires)

This is a **checkpoint phase, not a substrate change.** No new decision logic, no new signals — it is a thin viewer over the existing `coach()`. Built **before** Phase 4 so the LLM persona bots are developed against a runnable demo, not a CLI table. The former "Optional / stretch" visualization is promoted into this phase, and the **framework choice is NiceGUI, not Streamlit**. Rationale: NiceGUI elements carry stable named IDs and ship with a Playwright-backed test harness (`nicegui.testing`), so the **same test code runs headless in CI and headed for the on-stage demo by flipping `--headed --slowmo=...`** — the presentation deliverable and the regression suite are one artefact, not two. (Streamlit's auto-generated DOM and AppTest-vs-Playwright split would force two parallel test surfaces.)

- **Builds:** a NiceGUI app at `services/ui/app.py` (the container slot reserved in §7) registering **two routes that share the same `Session`, URL contract, and persona/method switchers**:

  **`/` — debug viewer** (`services/ui/debug_view.py`)
  - renders the in-scope funnel (S0 → S1 → S2 → S3 → S4 → S6 → S7 → S12) with the agent's current step highlighted;
  - shows the live `Signals` for the current state (dwell, back-navs, hovers, field changes, tariff selection, S7 price gap) — read straight from `signals.extract()`, no duplicated logic;
  - step-through (one action per click) + optional auto-play (off in tests);
  - opens a `ui.dialog` with the `Intervention` text, type and detection reason whenever `coach()` fires for the current step.

  **`/journey` — customer-facing journey** (`services/ui/journey_view.py`) — **this is the on-stage demo route**
  - renders a stylized "HealthCover" insurance signup with one branded page per simulator step (welcome, coverage type, for-whom, personal data, tariff cards, health questions, personalised price, confirm) — page transitions only (no cursor/typing animation, per the Phase 3.5 design choice);
  - auto-play is ON by default at a watchable cadence (`autoplay_ms` URL param, defaults to 900ms); a popup pauses auto-play, dismissing it resumes;
  - the intervention popup is overlaid on the actual product page with brand-consistent styling (the "A nudge from HealthCover" card), so the audience sees the coach as a product feature, not a debug overlay;
  - terminal states (Converted / Abandoned / Routed-to-advisor / Service-contact) get their own branded end-pages.

  Both routes share:
  - URL contract **`?seed=N&episode=N&persona=X&method=X&gbm_threshold=F&narration=…`** read into session state on first load;
  - persona switcher (Judith / Franz / Peter / global) + detection-method switcher (`threshold` ↔ `gbm`) that flip `cfg["detection"]["method"]` at runtime;
  - stable named element ids (`step-button`, `intervention-modal`, `intervention-type`, `intervention-text`, `funnel-current-step`, `narration` on `/`; `journey-page`, `journey-popup`, `journey-popup-type`, `journey-popup-text`, `journey-popup-close`, `journey-step-label`, `journey-narration` on `/journey`) — these names are the contract tests bind to; renaming one is a spec change.

  Optional later: a small **aggregate panel** that calls `runner.compare(cfg, persona, n=…)` and renders the same `without / with / uplift / fired / wasted / saved` columns the CLI already prints (no duplicated metric code).
- **Demo path (presentation deliverable):** `services/ui/tests/test_demo.py` drives the **`/journey` route** (not `/`) — the audience sees the branded HealthCover signup with the popup overlaid on the product page, not a debug funnel. The same test code that gates regression in headless mode runs headed for the stage via `uv run pytest services/ui/tests/test_demo.py --headed --slowmo=400 --video=on`. It walks one scenario per persona using fixed `(seed, episode)` pairs from `services/ui/tests/scenarios.py`, lets auto-play advance the journey, pauses on each popup for audience read time, and writes a screenshot + video per scenario to `demo_videos/` on every run as the fallback for stage-day network/USB issues. **One command on stage**, rehearsed in advance.
- **Replaces:** the former "Optional / stretch — Streamlit visualization" section, removed below; supersedes that section's framework choice.
- **Acceptance command:**
  - headless gate (both routes): `uv run pytest services/ui/tests/test_ui.py services/ui/tests/test_journey.py`
  - demo rehearsal (on-stage path, `/journey`): `uv run pytest services/ui/tests/test_demo.py --headed --slowmo=400 --video=on`
- **Must pass:**
  - headless suite green: every persona × detection-method combination renders the in-scope path end-to-end without unhandled exceptions;
  - each persona surfaces **≥1 intervention popup** in its seeded scenario at its documented step (Judith S4 dwell, Franz S7 gap+cancel, Peter S1–S3 form re-edits);
  - flipping the detection method changes popup behaviour visibly (e.g. `gbm` fires more often than `threshold` at default settings, consistent with the Phase 3 ablation);
  - the aggregate panel numbers match `python runner.py --n N` for the same seed (it is the same code path);
  - the headed demo writes a screenshot **and** a video per persona scenario to `demo_videos/`, and the on-screen popup text matches `realize()` output for that intervention type.
- **Checkpoint:** commit, attach the screenshots from `demo_videos/` per persona, wait.

**Non-goals for this phase (do NOT cross into other phases' territory):**
- No new logic in `coach/`, `signals.py`, `agent_stub.py`, or `state_machine.py`. The UI consumes `coach()` and `extract()` unchanged.
- The UI is **read-only over the simulator**: it never owns conversion accounting or intervention effectiveness — those stay in `runner.py` and `agent_stub.py`.
- If the GBM model file is missing the UI surfaces the same `gbm_model_missing` no-fire that `detection.py` already returns — it does not retrain or recompute.
- Two new optional dependencies, both in `[project.optional-dependencies].ui` (replacing the previous `streamlit` entry): `nicegui[testing]` (the in-process `User` fixture for any pure-Python assertions we want later) and `playwright`. The on-stage demo and the headless gate are **both driven by Playwright directly** against the running NiceGUI app — NiceGUI 3.x's `Screen` fixture is Selenium-based and requires a system Chrome/Chromedriver, which we deliberately avoid. Playwright bundles its own chromium (`playwright install chromium`) so no sudo / system browser is needed.
- No `time.sleep` or wall-clock waits anywhere in the test code path — pacing in the demo run comes from Playwright's `--slowmo` flag, nothing else.

### Phase 4 — LLM persona bots
- **Builds:** `agent_llm.py` — Judith/Franz/Peter as bots that emit the **same `Action` schema** (not chat). Start with a **local small model** reached via `INFERENCE_BASE_URL` + `MODEL_NAME` (§8) using the full persona briefings; the LoRA fine-tune (on Leonardo — this is the cluster training job) is the upgrade, swapped in by changing only those two values. `training/train_lora.py` logs to W&B in **offline** mode, synced from a login node (§9).
- **Replaces:** `agent_stub.py` as the driver.
- **Acceptance command:** run bot-driven episodes; validate every emitted action against the `Action` schema; re-run the GBM precision/recall on bot-driven runs.
- **Must pass:** bots emit only valid `Action`s; GBM precision/recall on bot runs is reported (and drift vs simulated-data numbers flagged — this is the first real test of detection against non-scripted behaviour).
- **Checkpoint:** commit, report schema-validity + bot-run GBM metrics, wait.

### Phase 5 — LLM intervention wording
- **Builds:** LLM `realize()` (same signature as the template one) producing register-appropriate intervention text. **This is the only component that calls the inference endpoint.**
- **Replaces:** the template `realize()`.
- **Acceptance command:** generate wording for each intervention type per persona; then run with the endpoint **mocked to fail**.
- **Must pass:** wording is produced per intervention type; **with the endpoint down, decisions are unchanged and the system degrades to templates** (graceful degradation — proves decisions never depended on the endpoint).
- **Checkpoint:** commit, report wording samples + degradation behaviour, wait.

### Phase 6 — Results consolidation (REPORT.md numbers)
- **Builds:** `eval/` consolidation — with/without coach, identical seeds, **per-persona**, per-step survival, annoyance rate, GBM precision/recall. Assemble into REPORT.md.
- **Replaces:** nothing — these numbers have been produced by the harness since Phase 2; this consolidates them.
- **Acceptance command:** generate the full results bundle.
- **Must pass:** every required REPORT.md result is present and sourced from the harness; per-persona conversion definitions correctly applied in the scorer.
- **Checkpoint:** commit, report the bundle, wait.

### Stretch beyond Phase 6
Anything additive that consumes the finished harness: before/after side-by-side dashboards, per-step survival sankeys, exporting wandb runs into REPORT.md plots. A pretty UI on weak logic scores lower than logs on strong logic — so stretches stay additive, never the critical path. The core viewer (the popup-on-detection demo) is no longer stretch territory; it is Phase 3.5.

---

## 6. Hard constraints and non-goals (prohibitions)

**Must remain true regardless:**
- Detection and decision logic stay in **inspectable code**, not in model weights.
- The model sits behind **one swappable interface** (`INFERENCE_BASE_URL` + `MODEL_NAME`); swapping models — local-small → local-fine-tuned → remote — touches only those values and the inference container, never coach code.
- **Services are containerized** (§7) along the frozen seams; the inference server is the swap boundary. Do **not** over-decompose into microservices — the GBM stays in-process inside the coach service; do not containerize a phase before it earns it.
- **Local-first**: default to a local small model on the dev box; no cloud provider is a hard dependency.
- Conversion is **computed in-code over seeded episodes**. No browser automation (Selenium/Playwright against the live UNIQA site) for measuring conversion — that is the spec's high-risk option and is out of bounds for measurement.
- Identical seeds for with/without-coach comparisons.
- No secrets in git or history (proxy credentials, `HF_TOKEN`, **W&B API key**). MIT `LICENSE`, pinned deps, clean-checkout runnable.
- Only the in-scope path is coached (private-doctor / "myself" / Start & Optimal). Hospital, "other persons", and Opt.Plus/Premium route to `ROUTED_ADVISOR` — no coaching.

**Do NOT, in Phase 1:** use an LLM, a trained model, or a UI. Those are stub slots filled in later phases. Over-building Phase 1 is how it gets cornered.

**Do NOT, ever:** fold the when/how decision into the model; claim intervention *efficacy* from Phase 1–3 (parameter-driven) numbers; remove or skip any calculator data-collection step (the coach may support completion, not simplify data gathering — except as an explicit Peter intervention on an overwhelmed screen, which is a *coaching* action, not a removal of required fields).

---

## 7. Service topology & containers (modular design)

Decompose along the frozen seams, not finer. **Three services, orchestrated by `docker-compose.yml`:**

1. **`inference`** — an OpenAI-compatible model server. **This container is the swap boundary** (§8): swapping models means swapping what this service runs, not editing any other code.
2. **`coach`** — the simulation engine: state machine, signals, detection, policy, realize, runner (the root modules + `coach/`). Talks to `inference` over HTTP.
3. **`ui`** — NiceGUI viewer (Phase 3.5). Opens a `ui.dialog` whenever `coach()` fires for the current step; consumes the coach service over the same in-process imports (no extra HTTP seam introduced for the UI). The framework's built-in `nicegui.testing` (Playwright-backed) is the single test surface for both the headless regression suite and the headed on-stage demo.

Rules that keep this from becoming a time-sink:
- **The coach reaches the model only over HTTP**, using `INFERENCE_BASE_URL` + `MODEL_NAME` from env. So model swaps touch env + the inference image — never coach code.
- **Do not over-decompose.** The GBM is a loaded object *inside* the coach service, not its own service. The state machine is a library, not a service. Microservices here buy nothing and cost integration time.
- **Define the compose topology early, fill services as phases land.** Phase 1 can run in a single container (or in-process); the `inference` service only becomes load-bearing at Phase 4. The topology existing early is what lets each phase slot in without re-architecting.
- **GPU passthrough is the one setup gotcha on Arch.** The `inference` (and `train_lora`) containers need `nvidia-container-toolkit` installed on the host and a device reservation in compose (`deploy.resources.reservations.devices` with `capabilities: [gpu]`, or `--gpus all`). Verify the GPU is actually visible *inside* the container, not just on the host — see the §8 verification step.

---

## 8. Local-first inference & model-swap strategy

**One mechanism does all the swapping:** `INFERENCE_BASE_URL` + `MODEL_NAME` (env/config), consumed by **both** `agent_llm.py` (Phase 4) and `realize.py` (Phase 5), both speaking OpenAI-compatible chat-completions. The same code path serves: a local small model now → the local merged fine-tuned model later → a remote endpoint (Featherless / Leonardo tunnel) if ever. Nothing downstream knows which.

**Local-first ladder on the dev box (Arch · RTX 5070 Ti 16 GB · 9950X3D · 64 GB):**
- **Fast iteration:** a small instruct model (1.5–3B) — near-instant, for wiring up the Phase 4/5 plumbing before the bots need to be good.
- **Persona-bot realism:** the 7B fine-tune base (e.g. `Qwen2.5-7B-Instruct`) at **FP8** or Q4 — fits comfortably in 16 GB with context headroom.
- **Later:** the merged fine-tuned 7B, served identically — only `MODEL_NAME` changes.

**Hardware reality (verified):**
- 16 GB VRAM is the binding constraint: 7B at FP8/8-bit is comfortable; 13–14B needs 8-bit; ~24B only with 4-bit + offload. **Don't run unquantized 14B+.** For this project a 7B is plenty.
- **FP8 is Blackwell-native** (halves VRAM vs FP16 at ~99% quality) — the recommended local precision.
- ⚠️ **Blackwell silent-CPU-fallback landmine.** The 5070 Ti is compute capability 12.0 (sm_120), new enough that some runtimes whose bundled CUDA kernels don't cover sm_120 will **silently fall back to CPU** — the model runs, slowly, with `size_vram=0` and no error (documented for recent Ollama builds). **Always verify the GPU is actually in use** (`nvidia-smi` shows the server process; for Ollama, `ollama ps` shows non-zero VRAM). Use CUDA 12.8+ builds and current tool versions. Arch's recent drivers help, but tool-bundled runtimes can still lag the driver.
- **Recommended local server: vLLM with `--dtype fp8`.** It's Blackwell-native, OpenAI-compatible, and is the *same* vLLM stack used on Leonardo (per the onboarding slides) — so local and cluster behave consistently. Ollama is fine for quick iteration **only if** you've confirmed it's GPU-accelerated, per the check above.

---

## 9. Experiment tracking (Weights & Biases)

Two **training** jobs get tracked. Inference and simulation do not need W&B.

**GBM — Phase 3, LOCAL (no cluster).** Gradient boosting on simulated tabular data is trivial for the 9950X3D / 64 GB; the cluster is not needed, as you noted. `train_gbm.py` runs in **online** mode (dev box has internet) and logs: hyperparameters, per-persona train/val precision/recall/AUC, confusion matrix, and **feature importances**. The feature-importance plot is not just hygiene — it *is* the GBM's inspectability exhibit, directly serving the rubric's "traceable decision rules." Also log the ablation-vs-threshold comparison as a run/table. xgboost/lightgbm both ship W&B callbacks; manual logging is fine too.

**LoRA — Phase 4, on Leonardo.** Set `report_to="wandb"` in the TRL/transformers `Trainer` → loss curves, learning rate, eval metrics, satisfying REPORT.md's "training logs, loss curves" deliverable.
- ⚠️ **Leonardo GPU compute nodes have no internet** (onboarding slides). Run W&B in **offline** mode (`WANDB_MODE=offline`) and `wandb sync` the run directory later **from a login node**. Do **not** route telemetry through the flaky proxy.

**Secret handling:** the W&B API key goes via `wandb login` / env var — never in the repo (§6).

---

## 10. How to start

Begin Phase 1. Build `state_machine.py`, `signals.py`, `agent_stub.py`, the no-op `coach`, and `runner.py`. Write the Phase 1 acceptance test in `tests/`. Run it with `N=10000`, no coach. Then **stop, report the conversion number, and wait.**