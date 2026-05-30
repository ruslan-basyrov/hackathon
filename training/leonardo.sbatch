#!/bin/bash
# Phase 5 LoRA fine-tune on Leonardo (BUILD_SPEC §5 Phase 5, §9).
#
# Prereqs on a Leonardo login node (done ONCE before the first sbatch):
#   1. Code under $SCRATCH (not $WORK / $FAST — slides forbid those):
#         cd $SCRATCH && git clone <repo-url> hackathon && cd hackathon
#   2. Long-running shell for env setup + 7B download (login nodes have a
#      10-min CPU limit, which would kill an HF download mid-way):
#         srun --partition=lrd_all_serial --time 04:00:00 \
#              --gres=tmpfs:100G --mem=16G --pty bash
#      then inside that srun:
#         module load python/3.11
#         python -m venv $SCRATCH/hackathon/.venv-lora
#         source $SCRATCH/hackathon/.venv-lora/bin/activate
#         pip install -U pip wheel
#         pip install -e ".[lora]"
#         export HF_HOME=$SCRATCH/hf_cache
#         huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
#             --local-dir $HF_HOME/qwen2.5-7b-instruct
#         wandb login   # paste your API key
#
# Submit:    mkdir -p logs && sbatch training/leonardo.sbatch
# Watch:     squeue --me ; tail -c +0 -f logs/qwen7b-personas-<jobid>.out
# Attach:    srun --overlap --pty --jobid=<jobid> bash
#
# After the run, on a login node:
#   wandb sync wandb/offline-run-*
#   python -m training.train_lora --eval-only \
#     --base $HF_HOME/qwen2.5-7b-instruct \
#     --out  models/qwen7b-personas-merged --no-wandb

#SBATCH --partition=boost_usr_prod
#SBATCH --reservation=s_tra_ncc       # hackathon reservation (priority slot)
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-task=1             # 1× A100 is plenty for 7B BF16 LoRA
#SBATCH --mem=120GB                   # Leonardo fair share: 120GB * gpus-per-task
#SBATCH --cpus-per-task=8             # Leonardo fair share: 8 * gpus-per-task
#SBATCH --time=02:00:00               # ~3 epochs on ~600 rows fits comfortably
#SBATCH --job-name=qwen7b-personas
#SBATCH --output=logs/%x-%j.out

set -euo pipefail

cd "$SLURM_SUBMIT_DIR"
source .venv-lora/bin/activate

# Compute nodes have no internet — pin the cache and force offline.
# The hackathon proxy exists (slides) but is flaky; we don't need it here.
export HF_HOME="$SCRATCH/hf_cache"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export WANDB_MODE=offline
export WANDB_PROJECT=conversion-coach

mkdir -p logs models

python -m training.train_lora \
  --base "$HF_HOME/qwen2.5-7b-instruct" \
  --train training/datasets/persona_sft.jsonl \
  --eval  training/datasets/persona_sft_holdout.jsonl \
  --out   models/qwen7b-personas-merged
