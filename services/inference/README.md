# Inference service

The OpenAI-compatible model server that `coach/llm_realize.py` (Phase 4) and
later `agent_llm.py` (Phase 5) talk to.

**The swap boundary is two env vars** (BUILD_SPEC §8):

```
INFERENCE_BASE_URL=http://localhost:8000/v1
MODEL_NAME=qwen2.5-7b-instruct
```

These also live in `config.yaml` (`inference_base_url`, `model_name`). Nothing
else in the codebase knows whether you're running a local small model, the
local merged fine-tuned model, or a remote endpoint.

## Phase 4 is opt-in

The default `config.yaml` has `realize.method: template` — so the coach runs
with template wording and **no inference server is required**. Phase 4
tests use a mocked OpenAI client; they pass without any model running.

To get real LLM wording, flip `realize.method` to `llm` and start one of the
servers below.

## Option 1 — vLLM (recommended for this dev box)

The spec's recommendation for the RTX 5070 Ti (Blackwell). FP8 is Blackwell-
native and halves VRAM vs FP16 at ~99% quality.

```bash
# install (CPU-only client/server image is fine for a small model; for FP8
# you want the CUDA image)
pip install vllm

# serve a 7B in FP8 (~10GB VRAM)
vllm serve Qwen/Qwen2.5-7B-Instruct --dtype fp8 --port 8000

# or a small 1.5B for fast iteration
vllm serve Qwen/Qwen2.5-1.5B-Instruct --dtype auto --port 8000
```

Then in `config.yaml`:

```yaml
inference_base_url: "http://localhost:8000/v1"
model_name: "Qwen/Qwen2.5-7B-Instruct"     # match what vllm serves
realize:
  method: llm
```

**Blackwell sm_120 landmine** (BUILD_SPEC §8): some runtimes silently fall
back to CPU on the 5070 Ti. Always verify with `nvidia-smi` that the vLLM
process is actually on GPU.

## Option 2 — Ollama (easier, watch the Blackwell trap)

```bash
ollama pull qwen2.5:7b-instruct
ollama serve   # listens on http://localhost:11434, OpenAI-compatible at /v1
```

`config.yaml`:

```yaml
inference_base_url: "http://localhost:11434/v1"
model_name: "qwen2.5:7b-instruct"
realize:
  method: llm
```

**Verify GPU use:** `ollama ps` should show non-zero VRAM. Recent Ollama
builds on Blackwell can silently run on CPU — see BUILD_SPEC §8.

## Option 3 — a remote OpenAI-compatible endpoint

Featherless, OpenRouter, anyone with an OpenAI-compatible API. Point
`inference_base_url` at their `/v1` endpoint and put a key in
`config.yaml`'s `inference_api_key` (or via `OPENAI_API_KEY` env).

## Smoke test once the server is running

```bash
# generate sample wording for each (persona × intervention type) and print
.venv/bin/python tests/test_phase4_wording.py
```

(With LLM mode on and the mock client patched out — see the `__main__` block
in that file. To exercise the REAL endpoint, comment out the patch and run
the same loop.)

## Docker compose

The `inference` service in `docker-compose.yml` is the production shape (the
container is the swap boundary — swapping models means swapping what THIS
service runs, never touching coach code). The Dockerfile here is the
starting point; pick vLLM or Ollama based on your hardware.
