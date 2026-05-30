#!/bin/bash
# Run main.py simulations on Leonardo against a local vLLM server.
#
# What this script does:
#   1. Brings up vLLM inside the Singularity image, serving the HF model
#      from $HF_HOME on http://127.0.0.1:8000/v1 with tensor-parallel=4.
#   2. Waits for /v1/models to respond.
#   3. Runs python main.py — the model + endpoint come from config.yaml
#      (see utils.llm_client.resolve_endpoint / resolve_model).
#   4. Outputs land in outputs/ (rsync them back from your dev box afterwards).
#
# Prereqs (done ONCE on a Leonardo login / serial node — see LEONARDO_SIMULATION.md):
#   * Repo cloned under $SCRATCH/hackathon
#   * Pixi env with Python 3.14 created:   pixi install
#   * HF model cached:   hf download Qwen/Qwen2.5-32B-Instruct \
#                        --local-dir $SCRATCH/hf_cache/qwen2.5-32b-instruct
#   * vLLM Singularity image at $SCRATCH/containers/vllm-openai-v0.22.0-cu129.sif
#   * config.yaml: inference_base_url=http://127.0.0.1:8000/v1,
#                  model_name=qwen2.5-32b-instruct (or matching --served-model-name)
#
# Submit:  mkdir -p logs && sbatch training/leonardo_simulation.sbatch
# Watch:   squeue --me ; tail -c +0 -f logs/sim-<jobid>.out

#SBATCH --partition=boost_usr_prod
#SBATCH --account=euhpc_d30_031        # hackathon allocation
#SBATCH --reservation=s_tra_ncc        # hackathon reservation
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-task=4              # full A100 node for tensor-parallel vLLM
#SBATCH --cpus-per-task=32             # fair-share: 8 * gpus-per-task
#SBATCH --mem=480GB                    # fair-share: 120GB * gpus-per-task
#SBATCH --time=04:00:00
#SBATCH --job-name=sim-vllm
#SBATCH --output=logs/sim-%j.out

set -euo pipefail

cd "$SLURM_SUBMIT_DIR"

# ---- Knobs (override on the sbatch CLI: `sbatch --export=ALL,MODEL_DIR=... ...`)
: "${HF_HOME:=$SCRATCH/hf_cache}"
: "${MODEL_DIR:=$HF_HOME/qwen2.5-32b-instruct}"
: "${SERVED_NAME:=qwen2.5-32b-instruct}"        # must match config.yaml::model_name
: "${VLLM_SIF:=$SCRATCH/containers/vllm-openai-v0.22.0-cu129.sif}"
: "${NUM_SIMULATIONS:=20}"
: "${VLLM_PORT:=8000}"

export HF_HOME HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

mkdir -p logs outputs

echo "[$(date -Is)] node=$(hostname) gpus=$CUDA_VISIBLE_DEVICES model=$MODEL_DIR"
nvidia-smi -L

# ---- 1. Launch vLLM in the background (Singularity, A100 SXM = no FP8, use BF16)
singularity exec --nv \
    --bind "$SCRATCH:$SCRATCH" \
    --bind "$PWD:$PWD" \
    "$VLLM_SIF" \
    python3 -m vllm.entrypoints.openai.api_server \
        --model "$MODEL_DIR" \
        --served-model-name "$SERVED_NAME" \
        --tensor-parallel-size 4 \
        --dtype bfloat16 \
        --max-model-len 8192 \
        --gpu-memory-utilization 0.90 \
        --host 127.0.0.1 --port "$VLLM_PORT" \
    > "logs/vllm-${SLURM_JOB_ID}.log" 2>&1 &
VLLM_PID=$!

# Always tear down vLLM, even if main.py crashes.
cleanup() {
    echo "[$(date -Is)] stopping vLLM (pid=$VLLM_PID)"
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
}
trap cleanup EXIT

# ---- 2. Wait for /v1/models (vLLM warm-up can be several minutes for 32B)
echo "[$(date -Is)] waiting for vLLM on http://127.0.0.1:${VLLM_PORT}/v1 ..."
for i in $(seq 1 120); do
    if curl -fsS "http://127.0.0.1:${VLLM_PORT}/v1/models" >/dev/null 2>&1; then
        echo "[$(date -Is)] vLLM is up after ${i} attempts"
        break
    fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "[$(date -Is)] ERROR: vLLM process died during warm-up — see logs/vllm-${SLURM_JOB_ID}.log"
        exit 1
    fi
    sleep 10
done
curl -fsS "http://127.0.0.1:${VLLM_PORT}/v1/models" >/dev/null \
    || { echo "vLLM never became ready"; exit 1; }

# ---- 3. Run the simulations against the local vLLM
#    Endpoint + model come from config.yaml (utils.llm_client). We *unset*
#    FEATHERLESS_API_KEY / OPENAI_API_KEY so the config path actually wins.
unset FEATHERLESS_API_KEY OPENAI_API_KEY OPENAI_BASE_URL

pixi run python main.py \
    --num-simulations "$NUM_SIMULATIONS" \
    --intervention-mode llm \
    --coach-mode chat

echo "[$(date -Is)] simulations finished — outputs/ has $(ls outputs | wc -l) files"
