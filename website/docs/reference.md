---
title: Reference
description: The repository module map — what each file and package is responsible for.
sidebar_position: 5
---

# Reference: module map

A guide to where each responsibility lives. The split mirrors the
[frozen seams](./architecture.md#frozen-interfaces): the root modules plus
`coach/` form the **coach service**; the model lives in a separate **inference
service**.

## Core substrate (root modules)

| File | Responsibility |
|---|---|
| `state_machine.py` | The `Step` enum + transition table + `step()`. Pure mechanics, **no randomness**. |
| `signals.py` | The `Signals` dataclass and `extract(state, history) → Signals`. |
| `agent.py` | The `Agent` protocol — the `act()` contract every driver implements. |
| `agent_stub.py` | The scripted agent. **The only place stochastic drop-off (`p_dropoff`) lives.** |
| `runner.py` | The seeded episode loop, trace logging, and conversion aggregation. CLI: `--config`, `--n`. |
| `main.py` | The persona-simulation entry point (LLM-facing). See [Running locally](./running-locally.md). |
| `config.yaml` | Seeds, `p_dropoff`, surcharge dist, thresholds, `inference_base_url` + `model_name`, W&B project. |

## `coach/` — decision logic (inspectable)

The yellow boxes from the [architecture diagram](./architecture.md#the-per-episode-data-path).
All readable code — never model weights.

| File | Responsibility |
|---|---|
| `coach/__init__.py` | `coach(signals, persona, policy) → Optional[Intervention]`. |
| `coach/detection.py` | `detect()` — threshold (Phase 2) and GBM (Phase 3) behind one function. |
| `coach/features.py` | Feature assembly for the GBM detector. |
| `coach/policy.py` | The per-persona decision table: which intervention, given step + persona. |
| `coach/realize.py` | `realize()` — template wording (Phase 2/3). |
| `coach/llm_realize.py` | LLM wording (Phase 4), same signature, with graceful fallback to templates. |

## `simulation/` — the engine

The runnable simulation that ties the substrate to the personas and the coach.

| File | Responsibility |
|---|---|
| `simulation/engine.py` | `SimulationEngine` — orchestrates a persona run end-to-end. |
| `simulation/funnel.py` | The funnel steps the agent walks. |
| `simulation/coach.py` · `ai_coach.py` | Coach integration into the engine. |
| `simulation/intervention_model.py` | Intervention data model. |
| `simulation/llm_bot.py` · `llm_coach_bot.py` | LLM-driven user bot and chat-style coach bot. |
| `simulation/json_utils.py` | Robust JSON parsing for model output. |

## `bots/` — the personas

| File | Responsibility |
|---|---|
| `bots/persona.py` | The persona model. |
| `bots/persona_factory.py` | Builds personas from `tracks/insurance-uniqa/personas.json`. |

## `services/` — containers

The three-service topology (see [Architecture](./architecture.md#service-topology)).

| Path | Responsibility |
|---|---|
| `services/inference/` | OpenAI-compatible model server — **the model-swap boundary**. |
| `services/ui/` | NiceGUI viewer (Phase 3.5): `/` debug view + `/journey` on-stage demo. |
| `services/coach.Dockerfile` | Packages the root modules + `coach/` into the coach service. |
| `services/ui.Dockerfile` | Packages the NiceGUI viewer. |
| `docker-compose.yml` | Orchestrates `inference` + `coach` + `ui`. |

## `training/` — offline tooling

| Path | Responsibility |
|---|---|
| `training/train_gbm.py` | Local GBM training + W&B logging (Phase 3, no cluster). |
| `training/train_lora.py` | LoRA fine-tune on Leonardo + W&B offline (Phase 5). |
| `training/data_gen.py` · `validate_dataset.py` | Training-data generation and validation. |
| `training/distill_persona.py` | Persona distillation for the bots. |
| `training/leonardo*.sbatch` · `LEONARDO*.md` | Slurm batch scripts + Leonardo runbooks. |

## `utils/` and `tracks/`

| Path | Responsibility |
|---|---|
| `utils/llm_client.py` | Resolves the inference endpoint + model name (env → config precedence). |
| `tracks/insurance-uniqa/` | The track briefing, persona files, and `personas.json` (figures only — not architecture). |
| `tests/` | One acceptance test per phase. |

:::note[Source of truth]
The authoritative architecture spec is `BUILD_SPEC.md` at the repo root. These
docs summarize it; when they disagree, the spec wins.
:::
