"""LoRA SFT for Phase 5 persona bots (BUILD_SPEC §5 Phase 5, §9).

Trains Qwen2.5-7B-Instruct to emit one valid `Action` JSON per call, conditioned
on (persona, step, signals, last_intervention?). Loss is masked on the prompt
tokens (system + user) so only the assistant JSON contributes — the standard
`DataCollatorForCompletionOnlyLM` approach. Custom eval metric is per-persona
JSON-validity rate, which doubles as the Phase 5 acceptance gate (BUILD_SPEC
§5 Phase 5: "bots emit only valid Actions").

Runs on Leonardo (BUILD_SPEC §9). Compute nodes have no internet, so:
  * datasets are local JSONL paths (no HF Hub downloads at train time),
  * the base model is pre-fetched on a login node and pointed at via --base,
  * W&B is offline; sync from a login node afterwards.

The merged checkpoint at `--out` is what the inference container serves — see
docker-compose.yml. Adapter-only artifacts also kept under `--out/adapter/` so a
LoRA-aware vLLM build could load them directly without merging.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

from datasets import Dataset
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DataCollatorForCompletionOnlyLM, SFTConfig, SFTTrainer

# Reuse the validator from the same package so train-time JSON-validity
# matches the gate we apply to the dataset before training.
from training.validate_dataset import validate_action


# The two Qwen2.5 chat-template tokens we anchor on. `<|im_start|>assistant\n`
# marks the start of the response; the collator masks everything before it.
RESPONSE_TEMPLATE = "<|im_start|>assistant\n"


def load_jsonl(path: str) -> List[dict]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def to_chat_format(row: dict) -> dict:
    """Convert a {messages, completion} row to a full chat-format dict with an
    assistant turn appended. TRL's SFTTrainer auto-templates `messages` via the
    tokenizer's chat template, so we don't materialise the text ourselves."""
    return {
        "persona": row["persona"],
        "step": row["step"],
        "messages": row["messages"] + [
            {"role": "assistant", "content": row["completion"]}
        ],
    }


def build_datasets(train_path: str, eval_path: str) -> Tuple[Dataset, Dataset, List[dict]]:
    train_rows = [to_chat_format(r) for r in load_jsonl(train_path)]
    eval_rows_raw = load_jsonl(eval_path)
    eval_rows = [to_chat_format(r) for r in eval_rows_raw]
    return (
        Dataset.from_list(train_rows),
        Dataset.from_list(eval_rows),
        eval_rows_raw,  # raw rows with persona/step for the custom metric
    )


def json_validity_metric(model, tokenizer, eval_rows_raw: List[dict]) -> Dict[str, float]:
    """Generate completions for the holdout and score per-persona JSON-validity.

    This is the Phase 5 acceptance gate. We sample with temperature=0 so the
    metric is reproducible across epochs."""
    model.eval()
    results = {p: {"ok": 0, "total": 0} for p in ("judith", "franz", "peter", "global")}

    for row in eval_rows_raw:
        prompt = tokenizer.apply_chat_template(
            row["messages"], tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with __import__("torch").no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=80,
                do_sample=False,
                temperature=0.0,
                pad_token_id=tokenizer.eos_token_id,
            )
        gen = tokenizer.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

        persona = row["persona"]
        results[persona]["total"] += 1
        try:
            act = json.loads(gen)
            if validate_action(act, row["step"]) is None:
                results[persona]["ok"] += 1
        except json.JSONDecodeError:
            pass

    metrics = {}
    overall_ok = sum(r["ok"] for r in results.values())
    overall_total = sum(r["total"] for r in results.values())
    metrics["eval/json_validity"] = overall_ok / max(overall_total, 1)
    for persona, r in results.items():
        if r["total"]:
            metrics[f"eval/json_validity_{persona}"] = r["ok"] / r["total"]
    return metrics


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--train", default="training/datasets/persona_sft.jsonl")
    ap.add_argument("--eval", default="training/datasets/persona_sft_holdout.jsonl")
    ap.add_argument("--out", default="models/qwen7b-personas-merged")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--max-seq-len", type=int, default=2048)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--eval-only", action="store_true",
                    help="skip training; just evaluate the (possibly merged) model at --out")
    ap.add_argument("--no-wandb", action="store_true")
    args = ap.parse_args()

    # W&B offline (Leonardo compute nodes have no internet; sync from login).
    os.environ.setdefault("WANDB_MODE", "offline")
    os.environ.setdefault("WANDB_PROJECT", "conversion-coach")

    import torch

    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    train_ds, eval_ds, eval_rows_raw = build_datasets(args.train, args.eval)
    print(f"train: {len(train_ds)} rows · eval: {len(eval_ds)} rows")

    if args.eval_only:
        # Load the merged model from --out and report metrics only.
        model = AutoModelForCausalLM.from_pretrained(
            args.out, torch_dtype=torch.bfloat16, device_map="auto"
        )
        metrics = json_validity_metric(model, tokenizer, eval_rows_raw)
        print(json.dumps(metrics, indent=2))
        return

    model = AutoModelForCausalLM.from_pretrained(
        args.base, torch_dtype=torch.bfloat16, device_map="auto"
    )
    model.config.use_cache = False

    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    collator = DataCollatorForCompletionOnlyLM(
        response_template=RESPONSE_TEMPLATE, tokenizer=tokenizer
    )

    sft_cfg = SFTConfig(
        output_dir=str(Path(args.out).with_name(Path(args.out).name + "-runs")),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        weight_decay=0.0,
        max_seq_length=args.max_seq_len,
        bf16=True,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        report_to=("none" if args.no_wandb else "wandb"),
        packing=False,
        dataset_text_field=None,  # we use the `messages` column via the chat template
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_cfg,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collator,
        tokenizer=tokenizer,
    )
    trainer.train()

    # Custom JSON-validity gate — log once at the end of training. The
    # epoch-level eval loss above is fine for checkpoint selection; this
    # number is what the Phase 5 acceptance test reads.
    validity = json_validity_metric(trainer.model, tokenizer, eval_rows_raw)
    print("\n[final eval]")
    print(json.dumps(validity, indent=2))
    if not args.no_wandb:
        import wandb
        if wandb.run is not None:
            wandb.log(validity)
            wandb.summary.update(validity)

    # Save the adapter (small, useful for LoRA-aware vLLM) and the merged
    # full-precision model (what the FP8 inference container ingests).
    adapter_dir = Path(args.out) / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    print(f"saved adapter -> {adapter_dir}")

    print("merging adapter into base weights ...")
    merged = trainer.model.merge_and_unload()
    merged.save_pretrained(args.out, safe_serialization=True)
    tokenizer.save_pretrained(args.out)
    print(f"saved merged model -> {args.out}")


if __name__ == "__main__":
    main()
