# Conversion Coach — skeleton

Phase 1 of the build in `BUILD_SPEC.md`: the simulation substrate + the no-coach
baseline. Everything above the state machine is a stub to be swapped in later phases.

## Run Phase 1 (local, no GPU)

```bash
uv sync                          # Phase 1 deps only (pyyaml)
uv run python runner.py          # prints online conversion (~5.7%) + per-step survival
uv run pytest tests/             # acceptance gate: conversion in [5.3%, 5.9%]
```

Later phases pull in more deps via extras:
`uv sync --extra phase3 --extra phase4 --extra ui --extra dev`
(or `uv sync --all-extras`).

Expected: conversion ~5.7%, survival tracking 34% / 76% / 22%, zero advisor routing.
A sample of full step traces is written to `traces.jsonl` (the demo material).

## Run via Docker

```bash
docker compose run --rm coach           # Phase 1: no GPU, no inference service
```

## Inference service (Phase 4+)

The model only enters at Phase 4. It lives in its own container — the swap boundary.

```bash
cp .env.example .env                     # set MODEL_ID / MODEL_NAME (+ HF_TOKEN if gated)
docker compose --profile inference up inference
```

⚠️ **Blackwell check.** The RTX 5070 Ti is sm_120; some runtimes silently fall back to
CPU if their CUDA kernels don't cover it. Confirm the GPU is actually used — run
`nvidia-smi` during a request and check the vLLM process appears with VRAM in use.
GPU passthrough needs `nvidia-container-toolkit` on the host (see compose comments).

## Swapping models (Phase 4+)

Change `MODEL_ID` / `MODEL_NAME` in `.env`. Local small model → local fine-tuned
(merged) model → remote endpoint, all without touching coach code.

## Where things go next

`coach/detection.py` (P2 threshold, P3 GBM), `coach/policy.py` (P2 per-persona table),
`coach/realize.py` (P2 templates, P5 LLM), `agent_llm.py` (P4 persona bots),
`training/train_gbm.py` (P3, local), `training/train_lora.py` (P4, Leonardo).
See `BUILD_SPEC.md` for the per-phase contracts and acceptance tests.
