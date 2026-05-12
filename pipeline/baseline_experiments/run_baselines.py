"""Run two baselines for the trapezoid task (task16) used as the running example:

  (A) Direct SVG generation: ask a large language model to produce an SVG
      file directly from the problem text.
  (B) Text-to-image generation: ask a t2i model to draw the diagram.

Outputs are written to ``pipeline/baseline_experiments/outputs/``.

Usage:
    python run_baselines.py --api-key tgp_v1_...

The Together AI API is used for both calls. The script is intentionally
small and self-contained because it is not part of the production pipeline:
it documents the qualitative failure of both naive baselines that motivates
the two-step architecture.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import sys
import time
from typing import Any

import requests


PROBLEM_RU = (
    "В трапеции ABCD основания BC = 4 и AD = 9, "
    "диагонали AC = 12 и BD = 5. "
    "а) Докажите, что диагонали трапеции перпендикулярны. "
    "б) Найдите высоту трапеции."
)

PROBLEM_EN = (
    "Trapezoid ABCD with parallel bases BC = 4 and AD = 9. "
    "Diagonals AC = 12 and BD = 5 are drawn inside. "
    "a) Prove the diagonals are perpendicular. "
    "b) Find the trapezoid height."
)

DIRECT_SVG_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
T2I_MODEL = "black-forest-labs/FLUX.1-schnell"

DIRECT_SVG_SYSTEM_PROMPT = (
    "Ты эксперт по SVG. По формулировке задачи ниже сгенерируй полный "
    "корректный SVG-код, изображающий геометрический чертёж задачи. "
    "В чертеже должны быть подписаны вершины буквами и указаны числовые "
    "длины сторон и диагоналей. Используй разумные размеры (например, "
    "width=600, height=400, viewBox=\"0 0 600 400\"). "
    "Выведи ТОЛЬКО SVG-код, без markdown-обёрток и без пояснений."
)

T2I_PROMPT = (
    "A clean black-on-white geometric textbook diagram of a trapezoid "
    "ABCD with parallel bases BC and AD where BC is shorter. "
    "Vertices labeled with letters A, B, C, D in capital letters. "
    "Both diagonals AC and BD are drawn inside and intersect. "
    "Side lengths are labeled: BC = 4, AD = 9, AC = 12, BD = 5. "
    "Plain white background, thin black lines, no shading, no color."
)


def call_chat_completion(api_key: str, model: str, system: str, user: str) -> str:
    url = "https://api.together.xyz/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.post(url, json=payload, headers=headers, timeout=180)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def call_image_generation(api_key: str, model: str, prompt: str) -> bytes:
    url = "https://api.together.xyz/v1/images/generations"
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "width": 1024,
        "height": 768,
        "steps": 4,
        "n": 1,
        "response_format": "b64_json",
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.post(url, json=payload, headers=headers, timeout=180)
    response.raise_for_status()
    data = response.json()
    b64 = data["data"][0]["b64_json"]
    return base64.b64decode(b64)


def strip_markdown_svg(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        # remove ``` fence
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=os.environ.get("TOGETHER_API_KEY"))
    parser.add_argument("--skip-svg", action="store_true")
    parser.add_argument("--skip-t2i", action="store_true")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: --api-key required (or set TOGETHER_API_KEY)", file=sys.stderr)
        return 2

    out_dir = pathlib.Path(__file__).parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    log: dict[str, Any] = {
        "problem_ru": PROBLEM_RU,
        "problem_en": PROBLEM_EN,
        "direct_svg": {"model": DIRECT_SVG_MODEL, "system_prompt": DIRECT_SVG_SYSTEM_PROMPT},
        "t2i": {"model": T2I_MODEL, "prompt": T2I_PROMPT},
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if not args.skip_svg:
        print("[A] direct SVG via", DIRECT_SVG_MODEL, "...", flush=True)
        t0 = time.time()
        try:
            raw = call_chat_completion(
                args.api_key, DIRECT_SVG_MODEL, DIRECT_SVG_SYSTEM_PROMPT, PROBLEM_RU
            )
            elapsed = time.time() - t0
            svg = strip_markdown_svg(raw)
            (out_dir / "baseline_direct_svg_raw.txt").write_text(raw, encoding="utf-8")
            (out_dir / "baseline_direct_svg.svg").write_text(svg, encoding="utf-8")
            log["direct_svg"]["elapsed_s"] = round(elapsed, 2)
            log["direct_svg"]["raw_length_chars"] = len(raw)
            log["direct_svg"]["svg_length_chars"] = len(svg)
            print(f"  done in {elapsed:.1f}s, svg = {len(svg)} chars")
        except Exception as e:  # noqa: BLE001
            log["direct_svg"]["error"] = repr(e)
            print("  FAILED:", e)

    if not args.skip_t2i:
        print("[B] text-to-image via", T2I_MODEL, "...", flush=True)
        t0 = time.time()
        try:
            png_bytes = call_image_generation(args.api_key, T2I_MODEL, T2I_PROMPT)
            elapsed = time.time() - t0
            (out_dir / "baseline_t2i.png").write_bytes(png_bytes)
            log["t2i"]["elapsed_s"] = round(elapsed, 2)
            log["t2i"]["png_size_bytes"] = len(png_bytes)
            print(f"  done in {elapsed:.1f}s, png = {len(png_bytes)} bytes")
        except Exception as e:  # noqa: BLE001
            log["t2i"]["error"] = repr(e)
            print("  FAILED:", e)

    (out_dir / "baselines_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("log saved to", out_dir / "baselines_log.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
