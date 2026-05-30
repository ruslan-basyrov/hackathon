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

### Quickstart via this project's docker-compose

```bash
docker compose --profile inference up -d inference
# defaults: Qwen2.5-1.5B-Instruct on host port 8003, FP8, 55% GPU util
```

Then in `config.yaml`:

```yaml
inference_base_url: "http://localhost:8003/v1"
model_name: "qwen2.5-1.5b-instruct"        # matches --served-model-name
realize:
  method: llm
```

(or set `MODEL_ID`, `MODEL_NAME`, `VLLM_HOST_PORT`, `VLLM_GPU_UTIL` in `.env`
to override — see `docker-compose.yml`.)

### Bare-metal vLLM

```bash
pip install vllm
vllm serve Qwen/Qwen2.5-1.5B-Instruct --dtype fp8 --port 8003 \
  --attention-backend TRITON_ATTN          # see Blackwell trap below
```

### ⚠️ Blackwell sm_120 trap (BUILD_SPEC §8)

The RTX 5070 Ti is compute capability **12.0**. FlashInfer (vLLM's default
attention backend) has a bundled CUDA-arch check that was compiled before
sm_120 existed:

```
RuntimeError: FlashInfer requires GPUs with sm75 or higher
```

…even though sm_120 IS higher than sm75. vLLM crashes on the first chat
completion. **Fix: force the Triton backend.** Either:

* env var: `VLLM_ATTENTION_BACKEND=TRITON_ATTN` (already set in our
  `docker-compose.yml`'s `inference` service)
* CLI flag: `--attention-backend TRITON_ATTN`

The other Blackwell trap is silent CPU fallback — some bundled CUDA kernels
don't cover sm_120 and the runtime keeps going on CPU. Always verify GPU
is actually in use: `nvidia-smi` should show the vLLM process with non-zero
VRAM during a request.

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
