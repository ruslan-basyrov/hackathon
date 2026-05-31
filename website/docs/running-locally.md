---
title: Running locally
description: Set up the environment, run the seeded harness and the persona simulations, and swap models.
sidebar_position: 4
---

# Running locally

The project is **local-first**: the default run needs no GPU, no cloud provider,
and no inference server. Heavier capabilities are gated behind optional extras
and a single model-swap interface.

## Prerequisites

- **Python ≥ 3.10**
- **[uv](https://docs.astral.sh/uv/)** for environment + dependency management
  (the repo ships a `uv.lock`)
- *(optional)* **Docker + Docker Compose** for the containerized topology
- *(optional, Phase 4+)* an **NVIDIA GPU** with `nvidia-container-toolkit` for the
  local inference server

## Install

```bash
# Base environment (Phase 1–2: just pyyaml + the openai client)
uv sync

# Optional capability sets, added as needed:
uv sync --extra phase3   # GBM detection, metrics, Weights & Biases
uv sync --extra ui       # NiceGUI viewer + Playwright demo driver
uv sync --extra phase4   # OpenAI-compatible client for the inference service
# (the `lora` extra is for Leonardo only — do NOT install it into the coach env)
```

## Run the baseline harness

`runner.py` is the seeded episode loop — the measurement substrate. It runs the
**scripted** agent and needs no model.

```bash
# Phase 1 acceptance: 10k episodes, no coach → conversion ~5.6%
uv run python runner.py --config config.yaml --n 10000
```

`--n` overrides `n_episodes` in `config.yaml`. With/without-coach comparisons use
**identical seeds**, so the coach is the only variable.

## Run the persona simulations

`main.py` drives the persona-based simulations (the LLM-facing entry point).

```bash
# Defaults: LLM intervention decider + chat-style coach wording
uv run python main.py --num-simulations 5

# Deterministic, no inference server needed — rule-based decider + template wording
uv run python main.py --intervention-mode rule --coach-mode realize --realize-method template

# GBM detector (needs a trained model at models/gbm.json — see Phase 3)
uv run python main.py --intervention-mode gbm --gbm-model-path models/gbm.json --gbm-threshold 0.5

# Generate training data (forces intervention off)
uv run python main.py --generate-training-data
```

| Flag | Choices | Meaning |
|---|---|---|
| `--intervention-mode` | `off` · `rule` · `llm` · `gbm` | who decides *whether* to intervene |
| `--coach-mode` | `chat` · `realize` | wording engine: free-form chat, or `policy.lookup` + `realize` |
| `--realize-method` | `llm` · `template` | only with `--coach-mode realize` |
| `--num-simulations` | int | how many persona runs |
| `--model` | str | override `model_name`; defaults to `config.yaml` |

## The model-swap interface

One mechanism does all model swapping — **`INFERENCE_BASE_URL` + `MODEL_NAME`**.
The same code path serves a local small model now, the merged fine-tuned model
later, or a remote endpoint, with nothing downstream aware of which.

Configure it either in `config.yaml`:

```yaml
inference_base_url: "http://localhost:8003/v1"   # local docker-compose inference service
model_name: "qwen2.5-1.5b-instruct"
inference_api_key: "local"                        # most local servers ignore this
```

…or via environment variables (these take precedence — see
`utils/llm_client.py`). The endpoint is resolved in this order:

1. `FEATHERLESS_API_KEY` → Featherless
2. `OPENAI_API_KEY` (+ optional `OPENAI_BASE_URL`) → OpenAI-compatible
3. `config.yaml` → `inference_base_url` + `inference_api_key`

:::tip[Default is offline-safe]
`config.yaml` defaults the realize method to `template`, so the Phase 2/3
contract holds with **no inference server running**. Flip to `llm` (and start a
local model) only when you want generated wording. The coach degrades back to
templates if the endpoint is down — by design.
:::

## Local inference server (Phase 4+)

For generated wording and persona bots, serve an OpenAI-compatible endpoint. The
recommended local server is **vLLM with `--dtype fp8`** — Blackwell-native, and
the same stack used on Leonardo, so local and cluster behave consistently.

:::warning[Verify the GPU is actually in use]
On recent NVIDIA hardware (sm_120 / Blackwell), some runtimes whose bundled CUDA
kernels don't cover the architecture will **silently fall back to CPU** — the
model runs, slowly, with no error. Always confirm the GPU is active (`nvidia-smi`
shows the server process). Use CUDA 12.8+ builds.
:::

## Docker Compose

The full topology — `inference`, `coach`, `ui` — is orchestrated by
`docker-compose.yml`:

```bash
docker compose up            # bring up the stack
docker compose up inference  # just the model server
```

The `inference` (and LoRA) containers need GPU passthrough — install
`nvidia-container-toolkit` on the host and reserve the device in compose
(`--gpus all` or `deploy.resources.reservations.devices`). **Verify the GPU is
visible *inside* the container**, not just on the host.

## Secrets and `.env`

Docker Compose reads `.env` automatically. Copy the template and fill in your
own values:

```bash
cp .env.example .env   # then edit .env with YOUR tokens
```

`.env` holds `MODEL_ID`, `MODEL_NAME`, `INFERENCE_BASE_URL`, and — only if you
need them — `HF_TOKEN` (gated base models) and `WANDB_API_KEY` (experiment
tracking; or use `wandb login`).

:::danger[Never commit real secrets]
`.env` is git-ignored and must stay that way. **Do not put real tokens in
`.env.example`** — it is committed, and the project's own hard constraints
forbid secrets in git or history. Use placeholder values there
(e.g. `HF_TOKEN=hf_xxx`).
:::

## Experiment tracking

Two training jobs log to Weights & Biases (project `conversion-coach`):

```bash
wandb login                          # store the API key locally, NOT in the repo

# GBM (Phase 3) — local, online
uv run python training/train_gbm.py

# LoRA (Phase 5) — on Leonardo, offline; sync later from a login node
WANDB_MODE=offline python training/train_lora.py
wandb sync wandb/offline-run-*       # from a login node (compute nodes have no internet)
```
