#!/usr/bin/env python3
"""CPU-friendly launcher for OmniVoice on Windows.

Why this file exists:
  The upstream CLIs (`omnivoice-demo`, `omnivoice-infer`) hard-code
  ``dtype=torch.float16``, which is a GPU dtype. On a machine without a CUDA
  GPU, float16 is either extremely slow or unsupported for some ops, so this
  launcher picks a sensible dtype for the detected device (float32 on CPU).

Usage:
  # Web UI (Gradio) on http://127.0.0.1:8001
  python run_local.py demo

  # Single generation, voice design (no reference audio needed)
  python run_local.py infer --text "Hello from OmniVoice." --instruct "female, british accent"

  # Single generation, auto voice
  python run_local.py infer --text "Hello world." --output hello.wav

  # Voice cloning (ref_audio only; ref_text is optional but recommended)
  python run_local.py infer --text "Hello again." --ref_audio ref.wav --ref_text "Hello, this is my voice." --output clone.wav
"""

import argparse
import logging
import os

import torch


def pick_dtype(device: str, requested: str) -> torch.dtype:
    if requested != "auto":
        return getattr(torch, requested)
    if device.startswith(("cuda", "xpu")):
        return torch.float16
    # CPU: float32 is the only well-supported, day-to-day fast dtype.
    # MPS also works with float32 (float16 is fine there too).
    return torch.float32


LOCAL_WEIGHTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "OmniVoice")


def resolve_model_path(requested: str) -> str:
    """Prefer locally downloaded weights over the Hugging Face cache.

    The HF download client stalls on some networks, so the weights are fetched
    with curl into ./models/OmniVoice. If that folder is complete, use it.
    """
    if os.path.isdir(requested):
        return requested
    main = os.path.join(LOCAL_WEIGHTS, "model.safetensors")
    tok = os.path.join(LOCAL_WEIGHTS, "audio_tokenizer", "model.safetensors")
    if os.path.isfile(main) and os.path.isfile(tok):
        return LOCAL_WEIGHTS
    return requested


def load_model(args):
    from omnivoice import OmniVoice

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = pick_dtype(device, args.dtype)
    model_path = resolve_model_path(args.model)

    logging.info("Device: %s | dtype: %s", device, dtype)
    logging.info("Weights: %s", model_path)
    model = OmniVoice.from_pretrained(
        model_path,
        device_map=device,
        dtype=dtype,
        load_asr=not args.no_asr,
        asr_model_name=args.asr_model,
    )
    return model, device


def cmd_infer(args):
    import soundfile as sf

    model, _ = load_model(args)
    logging.info("Model loaded. Generating ...")

    gen_kwargs = dict(
        text=args.text,
        language=args.language,
        ref_audio=args.ref_audio,
        ref_text=args.ref_text,
        instruct=args.instruct,
        num_step=args.num_step,
        speed=args.speed,
        duration=args.duration,
    )

    audios = model.generate(**gen_kwargs)
    sf.write(args.output, audios[0], model.sampling_rate)
    logging.info("Saved %s (%.1fs of audio)", args.output, len(audios[0]) / model.sampling_rate)


def cmd_demo(args):
    from omnivoice.cli.demo import build_demo

    model, _ = load_model(args)
    print("Model loaded.")
    demo = build_demo(model, args.model)
    demo.queue().launch(
        server_name=args.ip,
        server_port=args.port,
        share=args.share,
        inbrowser=args.inbrowser,
    )


def build_parser():
    parser = argparse.ArgumentParser(description="OmniVoice launcher (CPU/GPU friendly)")
    parser.add_argument("mode", choices=["demo", "infer"], help="What to run.")
    parser.add_argument("--model", default="k2-fsa/OmniVoice")
    parser.add_argument("--device", default=None, help="cuda / cpu (auto-detected).")
    parser.add_argument(
        "--dtype",
        default="auto",
        choices=["auto", "float32", "float16", "bfloat16"],
        help="'auto' = float16 on GPU, float32 on CPU.",
    )
    parser.add_argument(
        "--no-asr",
        action="store_true",
        default=True,
        help="Do not load Whisper for auto-transcribing reference audio "
        "(default on, saves several GB of RAM).",
    )
    parser.add_argument(
        "--asr",
        dest="no_asr",
        action="store_false",
        help="Load Whisper so ref_text can be omitted.",
    )
    parser.add_argument(
        "--asr-model",
        default="openai/whisper-small",
        help="Whisper model used when --asr is given.",
    )

    # demo
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--share", action="store_true", default=False)
    parser.add_argument("--inbrowser", action="store_true", default=True)

    # infer
    parser.add_argument("--text", default=None)
    parser.add_argument("--output", default="output.wav")
    parser.add_argument("--ref_audio", default=None)
    parser.add_argument("--ref_text", default=None)
    parser.add_argument("--instruct", default=None)
    parser.add_argument("--language", default=None)
    parser.add_argument("--num_step", type=int, default=32)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--duration", type=float, default=None)
    return parser


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args()

    # Use physical cores; more threads than that slows PyTorch down.
    threads = os.cpu_count() or 4
    torch.set_num_threads(max(1, threads // 2 if threads > 8 else threads))

    if args.mode == "demo":
        cmd_demo(args)
    else:
        if not args.text:
            parser.error("--text is required for 'infer' mode")
        cmd_infer(args)


if __name__ == "__main__":
    main()
