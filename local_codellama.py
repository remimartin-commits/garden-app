#!/usr/bin/env python3
"""
Local Code Llama CLI (Hugging Face Transformers).

Loads a Code Llama–family model from disk/cache and answers coding prompts.

-------------------------------------------------------------------------------
OFFLINE / AIR-GAPPED USE
-------------------------------------------------------------------------------

1) One-time download (needs internet and usually a Hugging Face account token
   for gated models like Code Llama):

   pip install torch transformers accelerate safetensors python-dotenv

   huggingface-cli login
   # or set HF_TOKEN in .env

   huggingface-cli download codellama/CodeLlama-7b-Instruct-hf \\
     --local-dir ./models/CodeLlama-7b-Instruct-hf

2) Point the script at the local folder (no network at runtime):

   HF_CODELLAMA_MODEL=./models/CodeLlama-7b-Instruct-hf
   HF_OFFLINE=1

   export HF_HUB_OFFLINE=1
   export TRANSFORMERS_OFFLINE=1

   python local_codellama.py

3) Cache layout: models are stored under HF_HOME (default ~/.cache/huggingface).
   Copy that directory to an offline machine and set HF_HOME to that path.

4) VRAM: 7B Instruct ~14 GB in fp16/bf16; use a smaller checkpoint or CPU
   (slow) / LOAD_IN_8BIT=1 on CUDA with bitsandbytes installed.

-------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import os
import sys

import torch
from dotenv import load_dotenv
from transformers import AutoModelForCausalLM, AutoTokenizer


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _build_prompt(instruction: str, system: str | None) -> str:
    """Code Llama Instruct single-turn format (HF convention)."""
    if system and system.strip():
        return (
            "<s>[INST] <<SYS>>\n"
            f"{system.strip()}\n"
            "<</SYS>>\n\n"
            f"{instruction.strip()} [/INST]"
        )
    return f"<s>[INST] {instruction.strip()} [/INST]"


def load_model_and_tokenizer():
    load_dotenv()

    model_id = os.getenv("HF_CODELLAMA_MODEL", "codellama/CodeLlama-7b-Instruct-hf").strip()
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
    device_pref = os.getenv("HF_DEVICE", "auto").strip().lower()

    load_in_8bit = _env_bool("LOAD_IN_8BIT", False)
    has_cuda = torch.cuda.is_available()
    if device_pref != "cpu" and not has_cuda:
        sys.stderr.write(
            "Note: PyTorch built without CUDA (torch.cuda.is_available() is False). "
            "You get CPU inference — slow on a 7B model. "
            "Install a CUDA build from https://pytorch.org/get-started/locally/ "
            "(pick Windows + Pip + your CUDA version).\n"
        )
        sys.stderr.write(
            f"      torch={torch.__version__} cuda_compiled={getattr(torch.version, 'cuda', None)}\n"
        )

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        token=token,
        local_files_only=_env_bool("HF_OFFLINE", False),
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    common_kw: dict = {
        "pretrained_model_name_or_path": model_id,
        "token": token,
        "local_files_only": _env_bool("HF_OFFLINE", False),
        "low_cpu_mem_usage": True,
    }

    if load_in_8bit and has_cuda:
        try:
            model = AutoModelForCausalLM.from_pretrained(
                **common_kw,
                device_map="auto",
                load_in_8bit=True,
            )
        except Exception as e:
            raise RuntimeError(
                "LOAD_IN_8BIT requires CUDA, bitsandbytes, and compatible GPU. "
                f"Original error: {e}"
            ) from e
        return model, tokenizer

    if device_pref == "cpu" or not has_cuda:
        dtype = torch.float32
        model = AutoModelForCausalLM.from_pretrained(
            **common_kw,
            dtype=dtype,
            device_map=None,
        )
        model = model.to("cpu")
        return model, tokenizer

    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model = AutoModelForCausalLM.from_pretrained(
        **common_kw,
        dtype=dtype,
        device_map="auto",
    )
    return model, tokenizer


@torch.inference_mode()
def generate_code(
    model,
    tokenizer,
    prompt: str,
    *,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
) -> str:
    device = next(model.parameters()).device
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    input_len = inputs["input_ids"].shape[-1]
    do_sample = temperature > 0
    gen_kw: dict = {
        "max_new_tokens": max_new_tokens,
        "do_sample": do_sample,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }
    if do_sample:
        gen_kw["temperature"] = max(0.01, temperature)
        gen_kw["top_p"] = top_p
    out_ids = model.generate(**inputs, **gen_kw)
    new_tokens = out_ids[0][input_len:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Local Code Llama coding assistant (Transformers).",
    )
    parser.add_argument(
        "-p",
        "--prompt",
        help="Single coding request; if omitted, interactive REPL.",
    )
    parser.add_argument(
        "--system",
        default=os.getenv("SYSTEM_PROMPT", "").strip() or None,
        help="Optional system preamble for instruction-tuned models.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=int(os.getenv("MAX_NEW_TOKENS", "512")),
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=float(os.getenv("TEMPERATURE", "0.2")),
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=float(os.getenv("TOP_P", "0.95")),
    )
    args = parser.parse_args()

    sys.stderr.write("Loading model (first run downloads weights)…\n")
    sys.stderr.flush()
    model, tokenizer = load_model_and_tokenizer()
    sys.stderr.write(f"Ready on device: {next(model.parameters()).device}\n")

    def run_one(user_text: str) -> str:
        prompt = _build_prompt(user_text, args.system)
        return generate_code(
            model,
            tokenizer,
            prompt,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
        ).strip()

    if args.prompt:
        print(run_one(args.prompt))
        return

    print("Enter coding requests. Empty line exits.", file=sys.stderr)
    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            break
        print(run_one(line))
        print()


if __name__ == "__main__":
    main()
