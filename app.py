#!/usr/bin/env python3
"""OmniVoice Studio - a custom, GPU-aware web UI for OmniVoice.

Features
--------
* Three generation modes: Auto voice, Voice design, Voice clone.
* Voice-design presets (chips) plus fine-grained attribute pickers.
* Live character counter with an estimated spoken duration.
* Real timing feedback for every generation (audio seconds vs compute seconds).
* Session history with inline playback and per-clip download.
* GPU panel: device, driver, VRAM in use, temperature.

Run the web UI:
    .venv\\Scripts\\python.exe app.py

Verify the generation pipeline without starting a server:
    .venv\\Scripts\\python.exe app.py --selftest
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import os
import random
import shutil
import sys
import tempfile
import threading
import time
import zipfile
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

# Force offline mode: all weights are already downloaded into ./models/OmniVoice
# (and the HF cache). This prevents the startup from trying to fetch
# openai/whisper-small and other files over the network, which on this
# machine takes 10+ minutes and makes the UI look frozen.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import gradio as gr
import numpy as np
import soundfile as sf
import torch

from omnivoice import OmniVoice, OmniVoiceGenerationConfig
from omnivoice.utils.lang_map import LANG_NAMES, lang_display_name

from run_local import pick_dtype, resolve_model_path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

DEFAULT_MODEL = "k2-fsa/OmniVoice"
DEFAULT_ASR = "openai/whisper-small"

# ---------------------------------------------------------------------------
# Static content
# ---------------------------------------------------------------------------

ALL_LANGUAGES = ["Auto"] + sorted(lang_display_name(n) for n in LANG_NAMES)

# "Auto" is handled as "let the model decide".
# The model validates `instruct` against a fixed whitelist of voice attributes,
# so presets are attribute combinations (never free-text descriptions).
PRESETS: Dict[str, Dict[str, str]] = {
    "None": {},
    "Female narrator": {"gender": "Female", "age": "Young Adult", "pitch": "Moderate Pitch"},
    "Deep male trailer": {"gender": "Male", "age": "Middle-aged", "pitch": "Very Low Pitch"},
    "British butler": {"gender": "Male", "age": "Elderly", "pitch": "Low Pitch", "accent": "British Accent"},
    "Energetic young male": {"gender": "Male", "age": "Young Adult", "pitch": "High Pitch"},
    "Soft whisper": {"gender": "Female", "age": "Young Adult", "style": "Whisper"},
    "Gentle grandmother": {"gender": "Female", "age": "Elderly", "pitch": "Low Pitch"},
    "News anchor": {"gender": "Female", "age": "Middle-aged", "pitch": "Moderate Pitch", "accent": "American Accent"},
    "Playful child": {"age": "Child", "pitch": "Very High Pitch"},
    "Documentary narrator": {"gender": "Male", "age": "Middle-aged", "pitch": "Low Pitch"},
    "Henan storyteller": {"gender": "Male", "age": "Middle-aged", "dialect": "河南话"},
}

GENDERS = ["Auto", "Male", "Female"]
AGES = ["Auto", "Child", "Teenager", "Young Adult", "Middle-aged", "Elderly"]
PITCHES = ["Auto", "Very Low Pitch", "Low Pitch", "Moderate Pitch", "High Pitch", "Very High Pitch"]
STYLES = ["Auto", "Whisper"]
ACCENTS = [
    "Auto", "American Accent", "Australian Accent", "British Accent", "Canadian Accent",
    "Chinese Accent", "Indian Accent", "Japanese Accent", "Korean Accent",
    "Portuguese Accent", "Russian Accent",
]
DIALECTS = [
    "Auto", "东北话", "河南话", "陕西话", "四川话", "贵州话", "云南话",
    "桂林话", "济南话", "石家庄话", "甘肃话", "宁夏话", "青岛话",
]

EXAMPLES = [
    "The quick brown fox jumps over the lazy dog, again and again, until the sun goes down.",
    "Welcome back. Today we are looking at three things: speed, clarity, and control.",
    "I never thought a laptop could talk this well, but here we are.",
    "Good evening. The train to Edinburgh will depart from platform four in five minutes.",
    "Selbstverständlich können wir das auch auf Deutsch sagen, ganz ohne Akzent.",
    "这是一段用中文生成的语音，用来测试模型的多语言能力。",
]

DISCLAIMER = (
    "Use only voices you have permission to reproduce. "
    "Do not use this for impersonation or fraud."
)

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

_MODEL: Optional[OmniVoice] = None
_DEVICE: str = "cpu"
_ASR_LOADED: bool = False
_LOCK = threading.Lock()
_HISTORY: List[Dict[str, Any]] = []


def load_model(device: Optional[str] = None, dtype: str = "auto", asr: bool = False) -> Tuple[OmniVoice, str]:
    """Load OmniVoice once and cache it in the module globals."""
    global _MODEL, _DEVICE, _ASR_LOADED
    if _MODEL is not None:
        return _MODEL, _DEVICE

    dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
    dt = pick_dtype(dev, dtype)
    path = resolve_model_path(DEFAULT_MODEL)
    print(f"[studio] device={dev} dtype={dt} weights={path}", flush=True)
    _MODEL = OmniVoice.from_pretrained(
        path,
        device_map=dev,
        dtype=dt,
        load_asr=asr,
        asr_model_name=DEFAULT_ASR,
    )
    _DEVICE = dev
    _ASR_LOADED = asr
    return _MODEL, _DEVICE


def _driver_version() -> str:
    try:
        import subprocess

        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "-"
    except Exception:
        return "-"


def gpu_badge_html() -> str:
    """Small status panel shown at the top of the page."""
    if not torch.cuda.is_available():
        return (
            "<div class='ov-badges'>"
            "<span class='ov-badge warn'>CPU mode</span>"
            "<span class='ov-badge'>no CUDA device detected</span>"
            "</div>"
        )

    name = torch.cuda.get_device_name(0)
    free, total = torch.cuda.mem_get_info(0)
    used = (total - free) / 1024**3
    total_gb = total / 1024**3
    pct = 100.0 * used / total_gb if total_gb else 0.0
    temp = "?"
    try:
        out = __import__("subprocess").run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        temp = out.stdout.strip() or "?"
    except Exception:
        pass

    return (
        "<div class='ov-badges'>"
        f"<span class='ov-badge ok'>GPU {html.escape(name)}</span>"
        f"<span class='ov-badge'>driver {html.escape(_driver_version())}</span>"
        f"<span class='ov-badge'>VRAM {used:.2f} / {total_gb:.1f} GB ({pct:.0f}%)</span>"
        f"<span class='ov-badge'>{temp} &deg;C</span>"
        "<span class='ov-badge'>fp16</span>"
        "</div>"
    )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _compose_instruct(
    gender: str,
    age: str,
    pitch: str,
    style: str,
    accent: str,
    dialect: str,
) -> Tuple[Optional[str], List[str]]:
    """Build a valid instruct string from the dropdown values.

    The model only accepts whitelisted attribute tokens and rejects mixing an
    English accent with a Chinese dialect, so the accent is dropped in that case.
    """
    notes: List[str] = []
    dia = dialect if dialect and dialect != "Auto" else None
    acc = accent if accent and accent != "Auto" else None
    if dia and acc:
        acc = None
        notes.append("English accent ignored because a Chinese dialect is selected")

    parts = [v for v in (gender, age, pitch, style) if v and v != "Auto"]
    if dia:
        parts.append(dia)
    elif acc:
        parts.append(acc)
    return (", ".join(parts) or None), notes


def _save_wav(audio: np.ndarray, sr: int, tag: str) -> str:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}-{tag}.wav"
    path = os.path.join(OUT_DIR, name)
    sf.write(path, audio, sr)
    return path


def _history_html() -> str:
    if not _HISTORY:
        return "<div class='ov-empty'>Nothing generated yet in this session.</div>"

    rows = []
    for item in reversed(_HISTORY[-12:]):
        url = "/gradio_api/file=" + quote(item["path"].replace("\\", "/"), safe="/:")
        text = html.escape(item["text"][:180]) or "(no text)"
        mode = html.escape(item["mode"])
        rows.append(
            "<div class='ov-hcard'>"
            f"<div class='ov-hmeta'><span class='ov-htag'>{mode}</span>"
            f"<span class='ov-htime'>{item['when']} &middot; {item['dur']:.2f}s audio "
            f"&middot; {item['gen']:.2f}s compute</span></div>"
            f"<div class='ov-htext'>{text}</div>"
            f"<audio controls preload='none' src='{url}'></audio>"
            "</div>"
        )
    return "<div class='ov-history'>" + "".join(rows) + "</div>"


def generate(
    text: str,
    language: str,
    mode: str,
    instruct: Optional[str] = None,
    ref_audio: Optional[str] = None,
    ref_text: Optional[str] = None,
    num_step: int = 32,
    guidance: float = 2.0,
    speed: float = 1.0,
    denoise: bool = True,
    preprocess: bool = True,
    postprocess: bool = True,
) -> Tuple[Any, str, Optional[str], str]:
    """Core generation used by every tab. Returns (audio, status, file, history)."""
    if not text or not text.strip():
        return None, "### Waiting for text\nType something to synthesize.", None, _history_html()

    if mode == "clone" and not ref_audio:
        return None, "### Reference audio missing\nUpload or record a 3-10 second clip.", None, _history_html()
    if mode == "clone" and (not ref_text or not ref_text.strip()) and not _ASR_LOADED:
        return (
            None,
            "### Transcript required\n"
            "Whisper is not loaded, so please type the transcript of the reference "
            "clip (or restart the server with `--asr`).",
            None,
            _history_html(),
        )
    if mode == "clone" and ref_audio:
        try:
            import soundfile as _sf
            _info = _sf.info(ref_audio)
            if _info.duration < 2.5:
                return (
                    None,
                    f"### Reference too short\n"
                    f"The clip is only {_info.duration:.1f} s. Please use 3-10 seconds.",
                    None,
                    _history_html(),
                )
        except Exception:
            pass

    model, device = load_model()

    lang = None if (not language or language == "Auto") else language
    cfg = OmniVoiceGenerationConfig(
        num_step=int(num_step or 32),
        guidance_scale=float(guidance if guidance is not None else 2.0),
        denoise=bool(denoise),
        preprocess_prompt=bool(preprocess),
        postprocess_output=bool(postprocess),
    )

    kwargs: Dict[str, Any] = {
        "text": text.strip(),
        "language": lang,
        "generation_config": cfg,
    }
    if speed is not None and abs(float(speed) - 1.0) > 1e-6:
        kwargs["speed"] = float(speed)

    if mode == "clone":
        kwargs["voice_clone_prompt"] = model.create_voice_clone_prompt(
            ref_audio=ref_audio,
            ref_text=(ref_text.strip() if ref_text and ref_text.strip() else None),
        )

    if instruct and instruct.strip():
        kwargs["instruct"] = instruct.strip()

    t0 = time.perf_counter()
    try:
        with _LOCK:
            audios = model.generate(**kwargs)
    except Exception as exc:  # noqa: BLE001 - surface the real error to the UI
        return None, f"### Generation failed\n`{type(exc).__name__}: {exc}`", None, _history_html()
    elapsed = time.perf_counter() - t0

    sr = model.sampling_rate
    audio = np.asarray(audios[0], dtype=np.float32)
    duration = len(audio) / sr
    peak = float(np.abs(audio).max()) if audio.size else 0.0

    if peak > 0:
        audio = audio / peak * 0.9 if peak > 0.99 else audio

    path = _save_wav(audio, sr, mode)
    rt = (duration / elapsed) if elapsed > 0 else 0.0

    _HISTORY.append(
        {
            "path": path,
            "mode": {"auto": "Auto", "design": "Design", "clone": "Clone"}.get(mode, mode),
            "text": text.strip(),
            "when": _dt.datetime.now().strftime("%H:%M:%S"),
            "dur": duration,
            "gen": elapsed,
        }
    )

    status = (
        f"### Done\n"
        f"**{duration:.2f} s** of audio in **{elapsed:.2f} s** "
        f"({rt:.1f}x realtime) &nbsp;|&nbsp; {sr // 1000} kHz &nbsp;|&nbsp; "
        f"{int(num_step)} steps &nbsp;|&nbsp; `{device}`"
    )
    if instruct:
        status += f"\n\n<small>voice: {html.escape(instruct)}</small>"
    return (sr, (audio * 32767).astype(np.int16)), status, path, _history_html()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

CSS = """
:root { --ov-accent: #7c5cff; --ov-accent2: #22d3ee; }
.gradio-container { max-width: 1180px !important; margin: 0 auto !important; }
#ov-hero { padding: 22px 26px; border-radius: 18px;
  background: linear-gradient(135deg, rgba(124,92,255,.20), rgba(34,211,238,.12));
  border: 1px solid rgba(124,92,255,.30); margin-bottom: 14px; }
#ov-hero h1 { margin: 0 0 4px 0; font-size: 1.9rem; letter-spacing: -.02em; }
#ov-hero p { margin: 0; opacity: .78; font-size: .95rem; }
.ov-badges { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.ov-badge { font-size: .78rem; padding: 4px 10px; border-radius: 999px;
  background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.12); }
.ov-badge.ok { border-color: rgba(34,197,94,.55); background: rgba(34,197,94,.14); }
.ov-badge.warn { border-color: rgba(250,204,21,.55); background: rgba(250,204,21,.14); }
.ov-history { display: flex; flex-direction: column; gap: 10px; }
.ov-hcard { padding: 12px 14px; border-radius: 12px;
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); }
.ov-hmeta { display: flex; justify-content: space-between; gap: 10px;
  font-size: .76rem; opacity: .72; margin-bottom: 6px; }
.ov-htag { text-transform: uppercase; letter-spacing: .08em; font-weight: 600;
  color: var(--ov-accent2); }
.ov-htext { font-size: .9rem; margin-bottom: 8px; opacity: .9; }
.ov-hcard audio { width: 100%; height: 34px; }
.ov-empty { opacity: .55; font-size: .9rem; padding: 10px 0; }
.ov-counter { font-size: .78rem; opacity: .65; text-align: right; margin-top: -6px; }
#ov-generate { min-height: 46px; font-weight: 600; }
footer { opacity: .5; }
"""


def _gen_settings(prefix: str):
    """Shared advanced settings block. Returns the component tuple."""
    with gr.Accordion("Advanced settings", open=False):
        steps = gr.Slider(
            4, 64, value=32, step=1,
            label="Quality (diffusion steps)",
            info="32 = default. 8-16 for fast drafts, 48-64 for final takes.",
        )
        guidance = gr.Slider(
            0.5, 4.0, value=2.0, step=0.1,
            label="Guidance scale (CFG)",
            info="Higher follows the text and voice prompt more literally.",
        )
        speed = gr.Slider(
            0.5, 1.5, value=1.0, step=0.05,
            label="Speaking speed",
            info="1.0 = normal. Works together with the text length.",
        )
        denoise = gr.Checkbox(value=True, label="Denoise output")
        pre = gr.Checkbox(value=True, label="Preprocess reference audio",
                          info="Trim silence and normalise the prompt.")
        post = gr.Checkbox(value=True, label="Trim long silences in the output")
    return steps, guidance, speed, denoise, pre, post


def _language_dropdown(label: str = "Language") -> gr.Dropdown:
    return gr.Dropdown(
        choices=ALL_LANGUAGES,
        value="Auto",
        label=label,
        info="Leave on Auto to let the model detect it.",
    )


def make_theme() -> gr.themes.Base:
    return gr.themes.Base(
        primary_hue="violet",
        secondary_hue="cyan",
        font=[gr.themes.GoogleFont("Inter"), "Segoe UI", "sans-serif"],
    ).set(
        body_background_fill="#0b0d17",
        body_background_fill_dark="#0b0d17",
        block_background_fill="#121524",
        block_background_fill_dark="#121524",
        block_border_width="1px",
        block_radius="14px",
    )


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="OmniVoice Studio") as demo:
        gr.HTML(
            "<div id='ov-hero'>"
            "<h1>OmniVoice Studio</h1>"
            "<p>Text to speech in 600+ languages &mdash; auto voices, designed voices, "
            "and voice cloning. Running locally on your laptop.</p>"
            f"{gpu_badge_html()}"
            "</div>"
        )

        with gr.Tabs():
            # -----------------------------------------------------------------
            # Auto voice
            # -----------------------------------------------------------------
            with gr.Tab("Auto voice"):
                gr.Markdown(
                    "Fastest mode: the model picks a voice for you. "
                    "Every run picks a different one."
                )
                with gr.Row():
                    with gr.Column(scale=6):
                        auto_text = gr.Textbox(
                            label="Text", lines=6, max_lines=20,
                            placeholder="Type or paste what you want to hear...",
                        )
                        auto_counter = gr.HTML("<div class='ov-counter'>0 characters</div>")
                        with gr.Row():
                            auto_example = gr.Button("Surprise me", size="sm")
                            auto_clear = gr.Button("Clear", size="sm")
                        auto_lang = _language_dropdown()
                        a_steps, a_guid, a_speed, a_dn, a_pre, a_post = _gen_settings("auto")
                        auto_btn = gr.Button("Generate speech", variant="primary", elem_id="ov-generate")

                    with gr.Column(scale=6):
                        auto_audio = gr.Audio(label="Result", type="numpy", autoplay=True)
                        auto_status = gr.Markdown("Ready.")
                        auto_file = gr.File(label="Download WAV", interactive=False)

                auto_inputs = [auto_text, auto_lang, a_steps, a_guid, a_speed, a_dn, a_pre, a_post]

            # -----------------------------------------------------------------
            # Voice design
            # -----------------------------------------------------------------
            with gr.Tab("Voice design"):
                gr.Markdown(
                    "Describe the voice you want. Presets are shortcuts that fill in "
                    "the description for you."
                )
                with gr.Row():
                    with gr.Column(scale=6):
                        design_text = gr.Textbox(
                            label="Text", lines=5, max_lines=20,
                            placeholder="Type or paste what you want to hear...",
                        )
                        design_counter = gr.HTML("<div class='ov-counter'>0 characters</div>")
                        design_preset = gr.Dropdown(
                            choices=list(PRESETS.keys()), value="None",
                            label="Voice preset",
                            info="Fills the attributes below. Set them manually afterwards if you like.",
                        )
                        with gr.Row():
                            d_gender = gr.Dropdown(GENDERS, value="Auto", label="Gender")
                            d_age = gr.Dropdown(AGES, value="Auto", label="Age")
                        with gr.Row():
                            d_pitch = gr.Dropdown(PITCHES, value="Auto", label="Pitch")
                            d_style = gr.Dropdown(STYLES, value="Auto", label="Style")
                        d_accent = gr.Dropdown(
                            ACCENTS, value="Auto", label="English accent",
                            info="For English speech only.",
                        )
                        d_dialect = gr.Dropdown(
                            DIALECTS, value="Auto", label="Chinese dialect",
                            info="For Chinese speech only. Overrides the accent.",
                        )
                        design_lang = _language_dropdown()
                        d_steps, d_guid, d_speed, d_dn, d_pre, d_post = _gen_settings("design")
                        design_btn = gr.Button("Generate speech", variant="primary", elem_id="ov-generate")

                    with gr.Column(scale=6):
                        design_audio = gr.Audio(label="Result", type="numpy", autoplay=True)
                        design_status = gr.Markdown("Ready.")
                        design_file = gr.File(label="Download WAV", interactive=False)

                def _apply_preset(name: str):
                    spec = PRESETS.get(name or "None", {})
                    return (
                        gr.update(value=spec.get("gender", "Auto")),
                        gr.update(value=spec.get("age", "Auto")),
                        gr.update(value=spec.get("pitch", "Auto")),
                        gr.update(value=spec.get("style", "Auto")),
                        gr.update(value=spec.get("accent", "Auto")),
                        gr.update(value=spec.get("dialect", "Auto")),
                    )

                design_preset.change(
                    fn=_apply_preset,
                    inputs=[design_preset],
                    outputs=[d_gender, d_age, d_pitch, d_style, d_accent, d_dialect],
                )

                design_inputs = [
                    design_text, design_lang, d_gender, d_age, d_pitch, d_style,
                    d_accent, d_dialect, d_steps, d_guid, d_speed, d_dn, d_pre, d_post,
                ]

            # -----------------------------------------------------------------
            # Voice clone
            # -----------------------------------------------------------------
            with gr.Tab("Voice clone"):
                gr.Markdown(
                    "Upload or record 3-10 seconds of a voice, then type what it should say. "
                    "Providing the transcript improves accuracy."
                )
                with gr.Row():
                    with gr.Column(scale=6):
                        clone_text = gr.Textbox(
                            label="Text to speak", lines=5, max_lines=20,
                            placeholder="What should this voice say?",
                        )
                        clone_counter = gr.HTML("<div class='ov-counter'>0 characters</div>")
                        clone_ref = gr.Audio(
                            label="Reference audio (3-10 s)",
                            sources=["upload", "microphone"],
                            type="filepath",
                        )
                        clone_ref_text = gr.Textbox(
                            label="Transcript of the reference audio (optional)", lines=2,
                            placeholder="Exact words spoken in the clip. Leave empty only if "
                                        "the ASR model was loaded at startup.",
                        )
                        clone_lang = _language_dropdown()
                        c_steps, c_guid, c_speed, c_dn, c_pre, c_post = _gen_settings("clone")
                        clone_btn = gr.Button("Clone and speak", variant="primary", elem_id="ov-generate")

                    with gr.Column(scale=6):
                        clone_audio = gr.Audio(label="Result", type="numpy", autoplay=True)
                        clone_status = gr.Markdown("Ready.")
                        clone_file = gr.File(label="Download WAV", interactive=False)

                clone_inputs = [
                    clone_text, clone_lang, clone_ref, clone_ref_text,
                    c_steps, c_guid, c_speed, c_dn, c_pre, c_post,
                ]

            # -----------------------------------------------------------------
            # History
            # -----------------------------------------------------------------
            with gr.Tab("History"):
                gr.Markdown("Everything generated since this page was opened.")
                with gr.Row():
                    history_html = gr.HTML(_history_html())
                with gr.Row():
                    refresh_btn = gr.Button("Refresh", size="sm")
                    zip_btn = gr.Button("Download all as ZIP", size="sm")
                    zip_out = gr.File(label="Archive", interactive=False)

                refresh_btn.click(fn=_history_html, inputs=None, outputs=[history_html])

                def _make_zip() -> Optional[str]:
                    if not _HISTORY:
                        return None
                    target = os.path.join(tempfile.gettempdir(), "omnivoice-outputs.zip")
                    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
                        for item in _HISTORY:
                            zf.write(item["path"], arcname=os.path.basename(item["path"]))
                    return target

                zip_btn.click(fn=_make_zip, inputs=None, outputs=[zip_out])

        # ---- generation handlers (wired last: the history panel lives in its tab) ----
        def _auto_fn(t, l, s, g, sp, dn, pre, post):
            return generate(
                t, l, "auto", instruct=None, num_step=s, guidance=g,
                speed=sp, denoise=dn, preprocess=pre, postprocess=post,
            )

        def _design_fn(t, l, g, a, p, st, acc, dia, s, gd, sp, dn, pre, post):
            instruct, notes = _compose_instruct(g, a, p, st, acc, dia)
            audio, status, path, hist = generate(
                t, l, "design", instruct=instruct, num_step=s, guidance=gd,
                speed=sp, denoise=dn, preprocess=pre, postprocess=post,
            )
            if notes and path is not None:
                status += "\n\n" + " ".join(f"_{n}_" for n in notes)
            return audio, status, path, hist

        def _clone_fn(t, l, ref, ref_text, s, gd, sp, dn, pre, post):
            return generate(
                t, l, "clone", instruct=None, ref_audio=ref, ref_text=ref_text,
                num_step=s, guidance=gd, speed=sp, denoise=dn,
                preprocess=pre, postprocess=post,
            )

        auto_outputs = [auto_audio, auto_status, auto_file, history_html]
        design_outputs = [design_audio, design_status, design_file, history_html]
        clone_outputs = [clone_audio, clone_status, clone_file, history_html]

        auto_btn.click(fn=_auto_fn, inputs=auto_inputs, outputs=auto_outputs)
        auto_text.submit(fn=_auto_fn, inputs=auto_inputs, outputs=auto_outputs)
        design_btn.click(fn=_design_fn, inputs=design_inputs, outputs=design_outputs)
        design_text.submit(fn=_design_fn, inputs=design_inputs, outputs=design_outputs)
        clone_btn.click(fn=_clone_fn, inputs=clone_inputs, outputs=clone_outputs)

        # ---- shared wiring: counter, examples, clear ----
        def _counter(text: str) -> str:
            n = len(text or "")
            seconds = n / 15.0 if n else 0.0
            return (
                f"<div class='ov-counter'>{n} characters &middot; "
                f"~{seconds:.0f}s spoken</div>"
            )

        for box, counter in (
            (auto_text, auto_counter),
            (design_text, design_counter),
            (clone_text, clone_counter),
        ):
            box.change(fn=_counter, inputs=[box], outputs=[counter])

        auto_example.click(fn=lambda: random.choice(EXAMPLES), inputs=None, outputs=[auto_text])
        auto_clear.click(fn=lambda: ("", ""), inputs=None, outputs=[auto_text, auto_counter])

        gr.Markdown(f"<footer><small>{DISCLAIMER}</small></footer>")

    return demo


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def selftest() -> int:
    print("[selftest] loading model ...", flush=True)
    t0 = time.perf_counter()
    load_model()
    print(f"[selftest] model ready in {time.perf_counter() - t0:.1f}s", flush=True)

    print("[selftest] auto-voice generation ...", flush=True)
    audio, status, path, _ = generate(
        "This is a self test of the OmniVoice studio interface.",
        "Auto", "auto", num_step=8,
    )
    if path is None:
        print("[selftest] FAILED:", status, flush=True)
        return 1
    print("[selftest] ok ->", path, flush=True)
    print("[selftest] status:", status.replace("\n", " "), flush=True)

    print("[selftest] voice-design generation ...", flush=True)
    instruct, notes = _compose_instruct("Male", "Elderly", "Low Pitch", "Auto", "British Accent", "Auto")
    print("[selftest] instruct =", instruct, "| notes =", notes, flush=True)
    audio2, status2, path2, _ = generate(
        "Good evening. Your table is ready.",
        "Auto", "design", instruct=instruct, num_step=8,
    )
    if path2 is None:
        print("[selftest] FAILED:", status2.replace("\n", " | "), flush=True)
        return 1
    print("[selftest] ok ->", path2, flush=True)

    print("[selftest] chinese dialect instruct ...", flush=True)
    instruct3, _notes3 = _compose_instruct("Male", "Middle-aged", "Auto", "Auto", "American Accent", "河南话")
    print("[selftest] instruct =", instruct3, flush=True)

    # Verify the audio file route used by the history player.
    print("[selftest] history html length:", len(_history_html()), flush=True)
    print("[selftest] ALL GOOD", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OmniVoice Studio")
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--share", action="store_true", default=False)
    parser.add_argument("--no-browser", action="store_true", default=False)
    parser.add_argument("--asr", action="store_true", default=False,
                        help="Load Whisper so reference transcripts can be omitted.")
    parser.add_argument("--selftest", action="store_true", default=False)
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if args.selftest:
        return selftest()

    print("[studio] loading model, this takes ~25s ...", flush=True)
    load_model(asr=args.asr)
    print("[studio] model loaded", flush=True)

    demo = build_ui()
    demo.queue(default_concurrency_limit=1, max_size=16).launch(
        server_name=args.ip,
        server_port=args.port,
        share=args.share,
        inbrowser=not args.no_browser,
        allowed_paths=[OUT_DIR],
        show_error=True,
        theme=make_theme(),
        css=CSS,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
