"""
Движок визуализации задачи 18 ЕГЭ (задача с параметром).

Ключевые визуальные паттерны:
  - Графический метод: «горизонтальная прямая y=a пересекает кривую»
  - Метод областей: закрашенные регионы на плоскости (x, a) или (x, y)
  - Критические значения параметра — точки смены числа решений
  - Семейства кривых при разных значениях параметра

Новые объекты (расширяют function_plot):
  - hline / vline          — горизонтальная / вертикальная прямая на весь canvas
  - filled_between         — заливка между двумя кривыми (или кривой и осью)
  - filled_region          — произвольная область по точкам (polygon fill)
  - region_label           — текстовая метка внутри области
  - open_point             — незаполненная точка (выколотая)

Использование:
    python3 pipeline/task18_parameter.py
"""

import copy
import json
import math
import os
import re
import time
import html as html_mod
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
OUTPUT_DIR = ROOT / "pipeline" / "output_geometry"

COLORS = ["#2980b9", "#e74c3c", "#27ae60", "#8e44ad", "#e67e22", "#1abc9c"]

# ═══════════════════════════════════════════════════════════════
# Safe math evaluator
# ═══════════════════════════════════════════════════════════════

_EVAL_NS = {
    "__builtins__": {},
    "pi": math.pi, "e": math.e,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "sqrt": math.sqrt, "abs": abs, "exp": math.exp,
    "log": math.log, "asin": math.asin, "acos": math.acos,
    "atan": math.atan,
}


def _eval_y(expr: str, xval: float) -> float | None:
    try:
        ns = {**_EVAL_NS, "x": xval}
        result = eval(expr, ns)
        if isinstance(result, (int, float)) and math.isfinite(result):
            return float(result)
    except Exception:
        pass
    expr2 = re.sub(r'log\((\d+),\s*([^)]+)\)', r'log(\2)/log(\1)', expr)
    if expr2 != expr:
        try:
            ns = {**_EVAL_NS, "x": xval}
            result = eval(expr2, ns)
            if isinstance(result, (int, float)) and math.isfinite(result):
                return float(result)
        except Exception:
            pass
    return None


# ═══════════════════════════════════════════════════════════════
# SVG renderer for parameter analysis
# ═══════════════════════════════════════════════════════════════

def render_parameter_svg(scene: dict) -> str:
    """Render a parameter-analysis scene to SVG.

    Supports all function_plot objects plus:
      hline, vline, filled_between, filled_region, region_label, open_point.
    """
    c = scene.get("canvas", {})
    w = c.get("width", 560)
    h = c.get("height", 440)
    xmin, xmax = c.get("x_min", -5), c.get("x_max", 5)
    ymin, ymax = c.get("y_min", -5), c.get("y_max", 5)
    x_label = c.get("x_label", "x")
    y_label = c.get("y_label", "y")
    N_SAMPLES = 400

    def sx(x):
        return (x - xmin) / (xmax - xmin) * w

    def sy(y):
        return (ymax - y) / (ymax - ymin) * h

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(w)}" height="{int(h)}" '
        f'viewBox="0 0 {int(w)} {int(h)}" style="background:white;font-family:sans-serif">',
        "  <defs>",
        '    <marker id="ah" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">',
        '      <path d="M0,0 L8,3 L0,6" fill="#555"/></marker>',
        "  </defs>",
    ]

    # ── grid ──
    for xi in range(math.ceil(xmin), math.floor(xmax) + 1):
        lines.append(
            f'  <line x1="{sx(xi):.1f}" y1="0" x2="{sx(xi):.1f}" y2="{h}" '
            f'stroke="#eee" stroke-width="0.5"/>')
    for yi in range(math.ceil(ymin), math.floor(ymax) + 1):
        lines.append(
            f'  <line x1="0" y1="{sy(yi):.1f}" x2="{w}" y2="{sy(yi):.1f}" '
            f'stroke="#eee" stroke-width="0.5"/>')

    # ── axes ──
    if ymin <= 0 <= ymax:
        lines.append(
            f'  <line x1="0" y1="{sy(0):.1f}" x2="{w}" y2="{sy(0):.1f}" '
            f'stroke="#555" stroke-width="1" marker-end="url(#ah)"/>')
    if xmin <= 0 <= xmax:
        lines.append(
            f'  <line x1="{sx(0):.1f}" y1="{h}" x2="{sx(0):.1f}" y2="0" '
            f'stroke="#555" stroke-width="1" marker-end="url(#ah)"/>')

    # ── tick labels ──
    for xi in range(math.ceil(xmin), math.floor(xmax) + 1):
        if xi == 0:
            continue
        y0 = sy(0) if ymin <= 0 <= ymax else h - 4
        lines.append(
            f'  <text x="{sx(xi):.1f}" y="{y0 + 14:.1f}" text-anchor="middle" '
            f'font-size="10" fill="#888">{xi}</text>')
    for yi in range(math.ceil(ymin), math.floor(ymax) + 1):
        if yi == 0:
            continue
        x0 = sx(0) if xmin <= 0 <= xmax else 4
        lines.append(
            f'  <text x="{x0 - 6:.1f}" y="{sy(yi) + 4:.1f}" text-anchor="end" '
            f'font-size="10" fill="#888">{yi}</text>')

    if xmin <= 0 <= xmax and ymin <= 0 <= ymax:
        lines.append(
            f'  <text x="{sx(0) - 8:.1f}" y="{sy(0) + 14:.1f}" '
            f'font-size="10" fill="#888">0</text>')

    # ── axis labels (x, y or a) ──
    lines.append(
        f'  <text x="{w - 4:.1f}" y="{sy(0) - 6:.1f}" text-anchor="end" '
        f'font-size="13" font-style="italic" fill="#555">{html_mod.escape(x_label)}</text>')
    if xmin <= 0 <= xmax:
        lines.append(
            f'  <text x="{sx(0) + 10:.1f}" y="14" font-size="13" '
            f'font-style="italic" fill="#555">{html_mod.escape(y_label)}</text>')

    # ── helper: compute polyline for expression ──
    def _curve_points(expr, cxmin=None, cxmax=None):
        cxmin = cxmin if cxmin is not None else xmin
        cxmax = cxmax if cxmax is not None else xmax
        segments = []
        seg = []
        for i in range(N_SAMPLES + 1):
            xv = cxmin + (cxmax - cxmin) * i / N_SAMPLES
            yv = _eval_y(expr, xv)
            if yv is not None and ymin - 10 <= yv <= ymax + 10:
                seg.append((xv, yv))
            else:
                if seg:
                    segments.append(seg)
                    seg = []
        if seg:
            segments.append(seg)
        return segments

    # ══════════════  RENDER OBJECTS  ══════════════

    objects = scene.get("objects", [])

    # ── 1) filled_between — must be drawn FIRST (behind curves) ──
    for obj in objects:
        if obj["type"] != "filled_between":
            continue
        expr_top = obj.get("upper", obj.get("expression", "0"))
        expr_bot = obj.get("lower", "0")
        fb_xmin = obj.get("x_min", xmin)
        fb_xmax = obj.get("x_max", xmax)
        style = obj.get("style") or {}
        fill = style.get("fill", "rgba(41,128,185,0.18)")
        stroke = style.get("stroke", "none")
        sw = style.get("stroke_width", 0)

        top_pts = []
        bot_pts = []
        for i in range(N_SAMPLES + 1):
            xv = fb_xmin + (fb_xmax - fb_xmin) * i / N_SAMPLES
            yt = _eval_y(expr_top, xv)
            yb = _eval_y(expr_bot, xv)
            if yt is not None and yb is not None:
                top_pts.append((xv, yt))
                bot_pts.append((xv, yb))

        if len(top_pts) < 2:
            continue

        path_parts = [f"M{sx(top_pts[0][0]):.1f},{sy(top_pts[0][1]):.1f}"]
        for xv, yv in top_pts[1:]:
            path_parts.append(f"L{sx(xv):.1f},{sy(yv):.1f}")
        for xv, yv in reversed(bot_pts):
            path_parts.append(f"L{sx(xv):.1f},{sy(yv):.1f}")
        path_parts.append("Z")

        lines.append(
            f'  <path d="{" ".join(path_parts)}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>')

    # ── 2) filled_region (polygon from point list) ──
    for obj in objects:
        if obj["type"] != "filled_region":
            continue
        pts = obj.get("points", [])
        if len(pts) < 3:
            continue
        style = obj.get("style") or {}
        fill = style.get("fill", "rgba(155,89,182,0.15)")
        stroke = style.get("stroke", "none")
        coords = " ".join(f"{sx(p[0]):.1f},{sy(p[1]):.1f}" for p in pts)
        lines.append(
            f'  <polygon points="{coords}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{style.get("stroke_width", 0)}"/>')

    # ── 3) hline / vline ──
    for obj in objects:
        if obj["type"] == "hline":
            yv = obj["y"]
            style = obj.get("style") or {}
            stroke = style.get("stroke", "#e74c3c")
            sw = style.get("stroke_width", 1.5)
            dash = ' stroke-dasharray="8,4"' if style.get("dash") == "dashed" else ""
            lines.append(
                f'  <line x1="0" y1="{sy(yv):.1f}" x2="{w}" y2="{sy(yv):.1f}" '
                f'stroke="{stroke}" stroke-width="{sw}"{dash}/>')
            label = obj.get("label")
            if label:
                lx = obj.get("label_x", xmax - 0.5)
                lines.append(
                    f'  <text x="{sx(lx):.1f}" y="{sy(yv) - 6:.1f}" '
                    f'text-anchor="end" font-size="12" font-style="italic" '
                    f'fill="{stroke}">{html_mod.escape(label)}</text>')

        elif obj["type"] == "vline":
            xv = obj["x"]
            style = obj.get("style") or {}
            stroke = style.get("stroke", "#8e44ad")
            sw = style.get("stroke_width", 1.5)
            dash = ' stroke-dasharray="8,4"' if style.get("dash") == "dashed" else ""
            lines.append(
                f'  <line x1="{sx(xv):.1f}" y1="0" x2="{sx(xv):.1f}" y2="{h}" '
                f'stroke="{stroke}" stroke-width="{sw}"{dash}/>')
            label = obj.get("label")
            if label:
                ly = obj.get("label_y", ymax - 0.5)
                lines.append(
                    f'  <text x="{sx(xv) + 6:.1f}" y="{sy(ly):.1f}" '
                    f'font-size="12" font-style="italic" '
                    f'fill="{stroke}">{html_mod.escape(label)}</text>')

    # ── 4) function_curve ──
    color_idx = 0
    for obj in objects:
        if obj["type"] != "function_curve":
            continue
        expr = obj["expression"]
        cxmin = obj.get("x_min", xmin)
        cxmax = obj.get("x_max", xmax)
        style = obj.get("style") or {}
        stroke = style.get("stroke", COLORS[color_idx % len(COLORS)])
        dash = ' stroke-dasharray="8,4"' if style.get("dash") == "dashed" else ""
        sw = style.get("stroke_width", 2.5)
        color_idx += 1

        for seg in _curve_points(expr, cxmin, cxmax):
            pts_str = " ".join(f"{sx(xv):.1f},{sy(yv):.1f}" for xv, yv in seg)
            lines.append(
                f'  <polyline points="{pts_str}" fill="none" '
                f'stroke="{stroke}" stroke-width="{sw}"{dash}/>')

        label = obj.get("label") or style.get("label")
        if label:
            lx_world = cxmax * 0.7
            ly_val = _eval_y(expr, lx_world)
            if ly_val is not None and ymin <= ly_val <= ymax:
                lines.append(
                    f'  <text x="{sx(lx_world) + 8:.1f}" y="{sy(ly_val) - 8:.1f}" '
                    f'font-size="12" fill="{stroke}" font-style="italic">'
                    f'{html_mod.escape(label)}</text>')

    # ── 5) point / open_point ──
    for obj in objects:
        if obj["type"] == "point":
            px, py = sx(obj["x"]), sy(obj["y"])
            style = obj.get("style") or {}
            fill = style.get("fill", "#e74c3c")
            r = style.get("radius", 4.5)
            lines.append(
                f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="{r}" '
                f'fill="{fill}" stroke="white" stroke-width="1.5"/>')
            if obj.get("label"):
                ldx = obj.get("label_dx", 8)
                ldy = obj.get("label_dy", -8)
                lines.append(
                    f'  <text x="{px + ldx:.1f}" y="{py + ldy:.1f}" '
                    f'font-size="12" fill="#333">'
                    f'{html_mod.escape(str(obj["label"]))}</text>')

        elif obj["type"] == "open_point":
            px, py = sx(obj["x"]), sy(obj["y"])
            style = obj.get("style") or {}
            stroke = style.get("stroke", "#e74c3c")
            r = style.get("radius", 4.5)
            lines.append(
                f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="{r}" '
                f'fill="white" stroke="{stroke}" stroke-width="2"/>')
            if obj.get("label"):
                ldx = obj.get("label_dx", 8)
                ldy = obj.get("label_dy", -8)
                lines.append(
                    f'  <text x="{px + ldx:.1f}" y="{py + ldy:.1f}" '
                    f'font-size="12" fill="#333">'
                    f'{html_mod.escape(str(obj["label"]))}</text>')

    # ── 6) region_label ──
    for obj in objects:
        if obj["type"] == "region_label":
            px, py = sx(obj["x"]), sy(obj["y"])
            style = obj.get("style") or {}
            color = style.get("color", "#555")
            fs = style.get("font_size", 14)
            bg = style.get("background")
            text = obj.get("text", "")
            if bg:
                tw = len(text) * fs * 0.55
                th = fs + 6
                lines.append(
                    f'  <rect x="{px - tw/2 - 4:.1f}" y="{py - th/2 - 2:.1f}" '
                    f'width="{tw + 8:.1f}" height="{th + 4:.1f}" rx="4" '
                    f'fill="{bg}" stroke="none"/>')
            lines.append(
                f'  <text x="{px:.1f}" y="{py + fs * 0.35:.1f}" text-anchor="middle" '
                f'font-size="{fs}" font-weight="600" fill="{color}">'
                f'{html_mod.escape(text)}</text>')

    # ── annotations ──
    for ann in scene.get("annotations", []):
        if ann.get("type") == "label":
            ax_px = sx(ann.get("x", 0))
            ay_px = sy(ann.get("y", 0))
            color = ann.get("color", "#2c3e50")
            fs = ann.get("font_size", 12)
            lines.append(
                f'  <text x="{ax_px:.1f}" y="{ay_px:.1f}" font-size="{fs}" '
                f'fill="{color}" font-style="italic">'
                f'{html_mod.escape(ann.get("text", ""))}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Step-by-step parameter analysis builder
# ═══════════════════════════════════════════════════════════════

class StepByStepParameter:
    """Progressive construction for task-18 style parameter problems."""

    def __init__(self, canvas, y_label="y"):
        self.base_scene = {
            "scene_type": "parameter_plot",
            "canvas": {**canvas, "y_label": y_label},
            "objects": [],
            "annotations": [],
        }
        self._obj_ids = set()
        self.steps = []

    def add(self, obj):
        if obj.get("id") and obj["id"] not in self._obj_ids:
            self.base_scene["objects"].append(obj)
            self._obj_ids.add(obj["id"])
        elif not obj.get("id"):
            self.base_scene["objects"].append(obj)
        return self

    def annotate(self, ann):
        self.base_scene["annotations"].append(ann)
        return self

    def snapshot(self, title="", description=""):
        svg = render_parameter_svg(copy.deepcopy(self.base_scene))
        self.steps.append({"title": title, "description": description, "svg": svg})
        return self


# ═══════════════════════════════════════════════════════════════
# LLM planner system prompt (for future auto-pipeline)
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = r"""Ты — модуль планирования пошаговых визуализаций для задачи 18 ЕГЭ (задача с параметром).

Тебе дают задачу с решением. Верни ОДИН JSON (без markdown-обёртки):

{
  "title": "...",
  "canvas": {"width": 560, "height": 440, "x_min": ..., "x_max": ..., "y_min": ..., "y_max": ...,
             "x_label": "x", "y_label": "y или a"},
  "steps": [...]
}

## Типы объектов (в каждом шаге — массив objects):

- function_curve: {"type":"function_curve","id":"f1","expression":"x**2 - 1","label":"y = x² − 1","style":{"stroke":"#2980b9","stroke_width":2.5}}
  Выражение — Python-синтаксис по x. Доступны: sin, cos, tan, sqrt, abs, exp, log, pi, e, asin, acos, atan.

- hline: {"type":"hline","id":"h1","y":3,"label":"a = 3","style":{"stroke":"#e74c3c","dash":"dashed"}}
  Горизонтальная прямая y=const на весь canvas. Используй для «уровня параметра a».

- vline: {"type":"vline","id":"v1","x":2,"label":"x = 2","style":{"stroke":"#8e44ad","dash":"dashed"}}
  Вертикальная прямая x=const.

- filled_between: {"type":"filled_between","id":"fb1","upper":"x**2","lower":"0","x_min":-2,"x_max":2,"style":{"fill":"rgba(41,128,185,0.18)"}}
  Закрашенная область между двумя кривыми (или кривой и осью OX при lower="0").

- filled_region: {"type":"filled_region","id":"fr1","points":[[x1,y1],[x2,y2],...],"style":{"fill":"rgba(155,89,182,0.15)"}}
  Закрашенный многоугольник по точкам.

- point: {"type":"point","id":"p1","x":1,"y":2,"label":"(1; 2)"}
  Заполненная точка с подписью.

- open_point: {"type":"open_point","id":"op1","x":1,"y":2,"label":"(1; 2)"}
  Выколотая (незаполненная) точка.

- region_label: {"type":"region_label","id":"rl1","x":0,"y":3,"text":"2 решения","style":{"color":"#2980b9","font_size":14,"background":"rgba(255,255,255,0.85)"}}
  Текстовая метка внутри области (число решений, знак неравенства и т.п.).

## Правила steps:
1. Шаг 1: условие задачи + основной график (function_curve).
2. Шаг 2: критические значения параметра — hline для каждого.
3. Следующие шаги: закрашивание областей (filled_between) + region_label для каждой.
4. Последний шаг: ответ.
5. Каждый шаг ОБЯЗАТЕЛЬНО содержит text (описание) и хотя бы 1 объект.
6. Используй LaTeX: $a=3$, $$x^2+a=0$$.
7. Используй РАЗНЫЕ цвета.
8. Всего 4-7 шагов.

## Графический метод (самый частый):
Если в задаче «при каких a уравнение f(x) = a имеет n решений» —
нарисуй y = f(x), затем горизонтальные прямые y = a для критических значений.
Число пересечений прямой y=a с графиком = число решений.

## ПОЛНЫЙ ПРИМЕР

Задача: "При каких значениях a уравнение x² - 2|x| = a имеет ровно 3 решения?"

Решение: Перепишем как y = x² − 2|x|, y = a. При x≥0: y = (x−1)²−1, мин. −1. Функция чётная.
Критические: a=−1 (касание мин.), a=0 (проходит через 0).
При a>0: 4 решения, a=0: 3 решения, −1<a<0: 4, a=−1: 2, a<−1: 0. Ответ: a=0.

{"title":"x² − 2|x| = a — ровно 3 решения","canvas":{"width":560,"height":440,"x_min":-4,"x_max":4,"y_min":-2,"y_max":5,"x_label":"x","y_label":"y"},"steps":[{"text":"Строим график $y = x^2 - 2|x|$.\nПри $x \\geq 0$: $y = (x-1)^2 - 1$. Функция чётная.","objects":[{"type":"function_curve","id":"f1","expression":"x**2 - 2*abs(x)","label":"y = x² − 2|x|","style":{"stroke":"#2980b9","stroke_width":2.5}}]},{"text":"**Критические уровни параметра:**\n$a = -1$ — касание минимумов, $a = 0$ — проходит через начало координат.","objects":[{"type":"hline","id":"h1","y":-1,"label":"a = −1","style":{"stroke":"#e74c3c","dash":"dashed"}},{"type":"hline","id":"h2","y":0,"label":"a = 0","style":{"stroke":"#8e44ad","dash":"dashed"}},{"type":"point","id":"p1","x":1,"y":-1,"label":"(1; −1)"},{"type":"point","id":"p2","x":-1,"y":-1,"label":"(−1; −1)"},{"type":"point","id":"p3","x":0,"y":0,"label":"(0; 0)"}]},{"text":"Считаем пересечения $y = a$ с графиком:\n- $a > 0$: **4 решения**\n- $a = 0$: **3 решения** ✓\n- $-1 < a < 0$: **4 решения**\n- $a = -1$: **2 решения**\n- $a < -1$: **0 решений**","objects":[{"type":"region_label","id":"rl1","x":0,"y":3.5,"text":"4 решения","style":{"color":"#27ae60","font_size":13,"background":"rgba(255,255,255,0.9)"}},{"type":"region_label","id":"rl2","x":3,"y":-0.5,"text":"a=0 → 3","style":{"color":"#e74c3c","font_size":13,"background":"rgba(255,255,255,0.9)"}},{"type":"region_label","id":"rl3","x":0,"y":-1.6,"text":"0 решений","style":{"color":"#888","font_size":13,"background":"rgba(255,255,255,0.9)"}}]},{"text":"**Ответ: $a = 0$.**","objects":[{"type":"hline","id":"h_answer","y":0,"label":"a = 0  ← ответ","style":{"stroke":"#27ae60","stroke_width":2.5}}]}]}

Верни ТОЛЬКО JSON.
"""


# ═══════════════════════════════════════════════════════════════
# LLM call with retry + JSON extraction (ported from geometry_auto)
# ═══════════════════════════════════════════════════════════════

def _call_llm(api_key: str, model: str, system: str, user: str,
              temperature: float = 0.3, max_tokens: int = 8192,
              retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            resp = requests.post(
                TOGETHER_API_URL,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"model": model,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}],
                      "temperature": temperature,
                      "max_tokens": max_tokens},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage", {})
            return {"raw": raw,
                    "tokens_in": usage.get("prompt_tokens", 0),
                    "tokens_out": usage.get("completion_tokens", 0)}
        except requests.exceptions.HTTPError:
            if attempt < retries - 1 and resp.status_code >= 500:
                wait = 2 ** (attempt + 1)
                print(f"  HTTP error, retry in {wait}s...")
                time.sleep(wait)
            else:
                try:
                    err_body = resp.json()
                except Exception:
                    err_body = resp.text[:300]
                print(f"  HTTP {resp.status_code}: {err_body}")
                raise


def _fix_latex_escapes(text: str) -> str:
    latex_cmds = (
        r'\\parallel', r'\\perp', r'\\angle', r'\\triangle', r'\\square',
        r'\\frac', r'\\cdot', r'\\times', r'\\div', r'\\pm', r'\\mp',
        r'\\leq', r'\\geq', r'\\neq', r'\\approx', r'\\sim',
        r'\\sqrt', r'\\sum', r'\\prod', r'\\int', r'\\infty',
        r'\\alpha', r'\\beta', r'\\gamma', r'\\delta', r'\\theta',
        r'\\pi', r'\\sigma', r'\\phi', r'\\psi', r'\\omega',
        r'\\quad', r'\\qquad', r'\\text', r'\\mathrm', r'\\mathbf',
        r'\\left', r'\\right', r'\\big', r'\\Big',
        r'\\overline', r'\\underline', r'\\hat', r'\\vec',
        r'\\boxed', r'\\dfrac', r'\\tfrac',
    )
    for cmd in latex_cmds:
        single = cmd[1:]
        text = text.replace(single, cmd)
    for cmd in latex_cmds:
        triple = '\\' + cmd
        text = text.replace(triple, cmd)
    return text


def _try_repair_json(text: str) -> str | None:
    text = re.sub(r',\s*"[^"]*"?\s*:?\s*"?[^"]*$', '', text)
    text = re.sub(r',\s*\{[^}]*$', '', text)
    text = re.sub(r',\s*\[[^\]]*$', '', text)
    opens = sq = 0
    for ch in text:
        if ch == '{': opens += 1
        elif ch == '}': opens -= 1
        elif ch == '[': sq += 1
        elif ch == ']': sq -= 1
    text += ']' * max(0, sq)
    text += '}' * max(0, opens)
    return text


def _fix_json_fractions(text: str) -> str:
    """Replace bare fractions like -9/4 with decimal equivalents in JSON values."""
    def _eval_frac(m):
        try:
            val = eval(m.group(0))
            return str(round(val, 6))
        except Exception:
            return m.group(0)
    return re.sub(r'(?<=[:,\s])-?\d+(?:\.\d+)?/\d+(?:\.\d+)?', _eval_frac, text)


def _extract_json(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    text = _fix_json_fractions(text)
    for t in [text, _fix_latex_escapes(text)]:
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            pass
        m = re.search(r'\{[\s\S]*\}', t)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    for t in [text, _fix_latex_escapes(text)]:
        m = re.search(r'\{[\s\S]*', t)
        if m:
            candidate = _try_repair_json(m.group())
            if candidate:
                try:
                    r = json.loads(candidate)
                    if isinstance(r, dict):
                        return r
                except json.JSONDecodeError:
                    pass
    return None


# ═══════════════════════════════════════════════════════════════
# Planner: problem text → LLM → JSON plan
# ═══════════════════════════════════════════════════════════════

def plan_task18(problem_text: str, api_key: str = None,
                model: str = DEFAULT_MODEL) -> dict:
    api_key = api_key or os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        raise RuntimeError("TOGETHER_API_KEY not set")

    user_msg = (
        "Вот задача 18 ЕГЭ (с параметром) с решением. "
        "Сгенерируй полный JSON-план пошаговой визуализации.\n\n"
        f"{problem_text}\n\n"
        "ПОДСКАЗКИ:\n"
        "- Если в задаче «при каких a уравнение f(x)=a имеет n решений» — "
        "используй графический метод: y=f(x), затем hline для критических a.\n"
        "- expression — Python-синтаксис: x**2 (не x^2), abs(x), sqrt(x).\n"
        "- canvas: подбери x_min, x_max, y_min, y_max так чтобы все ключевые "
        "точки и области были видны, с запасом ±1.\n"
        "- Каждый шаг: text + objects. Объекты из предыдущих шагов НЕ повторяются.\n"
        "- id уникальны: f1, f2, h1, h2, p1, p2, rl1, rl2, fb1, ...\n\n"
        "Верни ТОЛЬКО JSON."
    )

    print(f"[task18] Planning ({model})...")
    t0 = time.time()
    result = _call_llm(api_key, model, SYSTEM_PROMPT, user_msg, temperature=0.2)
    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s ({result['tokens_in']}+{result['tokens_out']} tok)")

    raw = result["raw"]
    plan = _extract_json(raw)
    if not plan or "steps" not in plan:
        debug_path = OUTPUT_DIR / "task18_debug_raw.txt"
        debug_path.write_text(raw, encoding="utf-8")
        print(f"  Raw saved: {debug_path}")
        raise ValueError("LLM returned invalid plan (no steps)")

    plan.setdefault("title", "Задача 18 — параметр")
    plan.setdefault("canvas", {"width": 560, "height": 440,
                                "x_min": -5, "x_max": 5,
                                "y_min": -5, "y_max": 5})
    _postprocess_plan(plan)
    return plan


def _postprocess_plan(plan: dict):
    """Fix common LLM mistakes."""
    for step in plan.get("steps", []):
        step.setdefault("objects", [])
        step.setdefault("text", "")

        for obj in step["objects"]:
            if obj.get("type") == "function_curve":
                expr = obj.get("expression", "")
                expr = expr.replace("^", "**")
                expr = re.sub(r'(?<![a-z])ln\(', 'log(', expr)
                for var in ("t", "n", "u", "s"):
                    expr = re.sub(rf'\b{var}\b', 'x', expr)
                obj["expression"] = expr

            if obj.get("type") == "filled_between":
                for key in ("upper", "lower"):
                    v = obj.get(key, "0")
                    if isinstance(v, (int, float)):
                        obj[key] = str(v)
                    elif isinstance(v, str):
                        v = v.replace("^", "**")
                        v = re.sub(r'(?<![a-z])ln\(', 'log(', v)
                        for var in ("t", "n", "u", "s"):
                            v = re.sub(rf'\b{var}\b', 'x', v)
                        obj[key] = v

    # Remove text-only steps (no objects) by merging with the next step
    merged = []
    pending = ""
    for step in plan["steps"]:
        if step.get("objects"):
            if pending:
                step["text"] = pending + "\n\n" + step.get("text", "")
                pending = ""
            merged.append(step)
        else:
            pending += ("\n\n" if pending else "") + step.get("text", "")
    if pending and merged:
        merged[-1]["text"] += "\n\n" + pending
    elif pending and not merged:
        merged.append({"text": pending, "objects": []})
    plan["steps"] = merged


# ═══════════════════════════════════════════════════════════════
# Executor: JSON plan → StepByStepParameter → blocks
# ═══════════════════════════════════════════════════════════════

def execute_task18_plan(plan: dict) -> list[dict]:
    canvas = plan.get("canvas", {"width": 560, "height": 440,
                                  "x_min": -5, "x_max": 5,
                                  "y_min": -5, "y_max": 5})
    y_label = canvas.get("y_label", "y")

    sp = StepByStepParameter(canvas, y_label=y_label)
    blocks = []

    for step in plan["steps"]:
        text = step.get("text", "")
        if text.strip():
            blocks.append({"type": "text", "content": text})

        if not step.get("objects"):
            continue

        for obj in step["objects"]:
            sp.add(obj)

        sp.snapshot()
        blocks.append({
            "type": "visual",
            "svg": sp.steps[-1]["svg"],
            "caption": step.get("caption", ""),
        })

    return blocks


# ═══════════════════════════════════════════════════════════════
# Full auto pipeline: text → LLM → plan → SVG → HTML
# ═══════════════════════════════════════════════════════════════

def run_auto(problem_text: str, output_name: str = "auto_task18",
             title: str = "Задача 18 — параметр",
             api_key: str = None, model: str = DEFAULT_MODEL,
             save_plan: bool = True) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    plan = plan_task18(problem_text, api_key=api_key, model=model)

    if save_plan:
        plan_path = OUTPUT_DIR / f"{output_name}_plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"[task18] Plan saved: {plan_path}")

    blocks = execute_task18_plan(plan)
    html = generate_html(blocks, title=plan.get("title", title))

    out_path = OUTPUT_DIR / f"{output_name}.html"
    out_path.write_text(html, encoding="utf-8")

    n_text = sum(1 for b in blocks if b["type"] == "text")
    n_vis = sum(1 for b in blocks if b["type"] == "visual")
    print(f"[task18] Report: {out_path}")
    print(f"[task18] {n_text} text blocks, {n_vis} visuals")
    return out_path


def run_from_plan(plan_path: str, output_name: str = "auto_task18",
                  title: str = "Задача 18 — параметр") -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    _postprocess_plan(plan)

    blocks = execute_task18_plan(plan)
    html = generate_html(blocks, title=plan.get("title", title))

    out_path = OUTPUT_DIR / f"{output_name}.html"
    out_path.write_text(html, encoding="utf-8")
    n_vis = sum(1 for b in blocks if b["type"] == "visual")
    print(f"[task18] Report from plan: {out_path} ({n_vis} visuals)")
    return out_path


# ═══════════════════════════════════════════════════════════════
# Built-in test problems
# ═══════════════════════════════════════════════════════════════

TASK18_PROBLEM_1 = """Задание 18 Профильного ЕГЭ по математике.

При каких значениях параметра a уравнение x⁴ − 5x² + 4 = a имеет ровно 6 решений?

Решение:
Пусть t = x², t ≥ 0. Тогда t² − 5t + 4 = a, то есть y = t² − 5t + 4.
Обозначим f(t) = t² − 5t + 4 = (t − 5/2)² − 9/4.
Вершина параболы: t = 5/2, f(5/2) = −9/4.
f(0) = 4, нули: t = 1 и t = 4.

Число решений исходного уравнения зависит от числа корней t² − 5t + 4 = a при t ≥ 0:
- Каждый корень t > 0 даёт 2 корня x = ±√t.
- Корень t = 0 даёт 1 корень x = 0.

Чтобы получить 6 решений по x, нужно 3 корня t > 0 (каждый → 2 решения).
Это возможно, когда прямая y = a пересекает параболу в 3 точках при t > 0.

Но парабола — квадратичная по t, поэтому больше 2 пересечений быть не может.
Значит: 2 корня t > 0 (дают 4 решения) + корень t = 0 (даёт ещё 1) = 5. Не подходит.

Альтернативно: нарисуем y = x⁴ − 5x² + 4 напрямую по x.
f(x) = x⁴ − 5x² + 4. f'(x) = 4x³ − 10x = 2x(2x² − 5).
Критические точки: x = 0, x = ±√(5/2).
f(0) = 4, f(±√(5/2)) = 25/4 − 25/2 + 4 = −9/4.
f(±1) = 0, f(±2) = 0.

График: локальный максимум f(0) = 4, два локальных минимума f(±√(5/2)) = −9/4.

Для 6 решений: прямая y = a должна пересечь график в 6 точках.
Это возможно при −9/4 < a < 0: прямая проходит ниже локального максимума,
выше минимумов, и пересекает все 4 ветви параболы + ещё 2 через область около 0.

Но при 0 < a < 4: 4 пересечения. При a = 0: 4 пересечения (x = ±1, ±2).
При −9/4 < a < 0: 6 пересечений.
При a = −9/4: 4 пересечения (2 касания + 2).

Ответ: −9/4 < a < 0.
"""

TASK18_PROBLEM_2 = """Задание 18 Профильного ЕГЭ по математике.

Найдите все значения параметра a, при каждом из которых уравнение
|x² − 4x + 3| = a имеет ровно 3 решения.

Решение:
Раскроем: x² − 4x + 3 = (x − 1)(x − 3). Нули: x = 1 и x = 3. Вершина: x = 2, y = −1.
График y = |x² − 4x + 3|: парабола, отражённая вверх ниже оси OX.
Минимумы (нули): y = 0 при x = 1 и x = 3.
Локальный максимум «отражённой» части: y = 1 при x = 2.

Горизонтальная прямая y = a:
- a < 0: 0 решений
- a = 0: 2 решения (x = 1, 3)
- 0 < a < 1: 4 решения
- a = 1: 3 решения (x = 2 — касание, плюс 2 внешних)
- a > 1: 2 решения

Ответ: a = 1.
"""


# ═══════════════════════════════════════════════════════════════
# HTML generation
# ═══════════════════════════════════════════════════════════════

def render_md(text):
    result = []
    for line in text.strip().split("\n"):
        s = line.strip()
        if s.startswith("$$") and s.endswith("$$"):
            result.append(f'<div class="formula">{s}</div>')
        elif s.startswith("- "):
            result.append(f'<div style="padding-left:16px;">• {s[2:]}</div>')
        elif s == "":
            result.append("<br/>")
        else:
            s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
            result.append(f'<p>{s}</p>')
    return "\n".join(result)


def generate_html(blocks, title="Задача 18 — параметр"):
    esc = html_mod.escape
    n_vis = sum(1 for b in blocks if b["type"] == "visual")
    parts = [f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"/>
<title>{esc(title)}</title>
<script>
MathJax = {{ tex: {{ inlineMath: [['$','$']], displayMath: [['$$','$$']] }}, svg: {{ fontCache: 'global' }} }};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Georgia','PT Serif',serif; background:#faf9f6; color:#2c2c2c; line-height:1.85; }}
  .page-header {{ background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
                  padding:36px 20px; text-align:center; color:white; }}
  .page-header h1 {{ font-size:24px; margin-bottom:6px; font-family:sans-serif; }}
  .page-header p {{ opacity:0.8; font-size:13px; font-family:sans-serif; }}
  .conspect {{ max-width:780px; margin:0 auto; padding:32px 28px 60px; }}
  .text-block {{ margin:14px 0; font-size:16.5px; }}
  .text-block p {{ margin:5px 0; }}
  .formula {{ background:#f7f9fc; padding:14px 20px; border-radius:8px; margin:12px 0;
              text-align:center; border-left:3px solid #2980b9; }}
  .visual-block {{ margin:22px 0; text-align:center; }}
  .visual-frame {{ display:inline-block; background:white; border:1px solid #e0e0e0;
                   border-radius:10px; padding:14px 18px;
                   box-shadow:0 2px 10px rgba(0,0,0,0.06); }}
  .visual-frame svg {{ max-width:100%; height:auto; }}
  .visual-caption {{ font-family:-apple-system,sans-serif; font-size:13px; color:#777;
                     margin-top:8px; font-style:italic; }}
  .footer {{ text-align:center; padding:30px 20px; color:#aaa; font-size:11px;
             font-family:sans-serif; border-top:1px solid #eee; }}
</style></head><body>
<div class="page-header">
  <h1>{esc(title)}</h1>
  <p>Пошаговое решение с графическим методом</p>
</div><div class="conspect">
"""]
    for b in blocks:
        if b["type"] == "text":
            parts.append(f'<div class="text-block">{render_md(b["content"])}</div>')
        elif b["type"] == "visual":
            parts.append(f"""<div class="visual-block">
  <div class="visual-frame">{b['svg']}</div>
  <div class="visual-caption">{esc(b.get('caption', ''))}</div>
</div>""")
    parts.append(f"""</div>
<div class="footer">task18_parameter.py · {n_vis} визуализаций</div>
</body></html>""")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# DEMO: hand-crafted examples of typical Task 18 problems
# ═══════════════════════════════════════════════════════════════

def demo_horizontal_line_method():
    """При каких a уравнение x² − 2|x| = a имеет ровно 3 решения?"""
    canvas = {"width": 560, "height": 440,
              "x_min": -4, "x_max": 4, "y_min": -2, "y_max": 5,
              "x_label": "x", "y_label": "y"}

    sp = StepByStepParameter(canvas, y_label="y")
    blocks = []

    blocks.append({"type": "text", "content":
        "**Задача.** При каких значениях параметра $a$ уравнение $x^2 - 2|x| = a$ имеет ровно 3 решения?"})

    # Step 1: draw the curve y = x² - 2|x|
    sp.add({"type": "function_curve", "id": "f1", "expression": "x**2 - 2*abs(x)",
            "label": "y = x² − 2|x|",
            "style": {"stroke": "#2980b9", "stroke_width": 2.5}})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "Перепишем уравнение: $y = x^2 - 2|x|$. Построим график этой функции.\n\n"
        "При $x \\geq 0$: $y = x^2 - 2x = (x-1)^2 - 1$, минимум $-1$ при $x=1$.\n"
        "Функция чётная, поэтому график симметричен."})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"], "caption": "График y = x² − 2|x|"})

    # Step 2: critical parameter values
    sp.add({"type": "hline", "id": "h_minus1", "y": -1,
            "label": "a = −1", "style": {"stroke": "#e74c3c", "dash": "dashed"}})
    sp.add({"type": "hline", "id": "h_0", "y": 0,
            "label": "a = 0", "style": {"stroke": "#8e44ad", "dash": "dashed"}})
    sp.add({"type": "point", "id": "min1", "x": 1, "y": -1, "label": "(1; −1)"})
    sp.add({"type": "point", "id": "min2", "x": -1, "y": -1, "label": "(−1; −1)"})
    sp.add({"type": "point", "id": "origin", "x": 0, "y": 0, "label": "(0; 0)"})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "**Критические значения параметра:**\n"
        "- $a = -1$: прямая $y = a$ касается минимумов (2 точки касания)\n"
        "- $a = 0$: прямая проходит через начало координат"})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"],
                   "caption": "Критические уровни a = −1 и a = 0"})

    # Step 3: analysis of regions
    sp.add({"type": "region_label", "id": "rl1", "x": 0, "y": 4,
            "text": "4 решения", "style": {"color": "#27ae60", "font_size": 13, "background": "rgba(255,255,255,0.9)"}})
    sp.add({"type": "region_label", "id": "rl2", "x": 0, "y": -0.5,
            "text": "3 решения", "style": {"color": "#e74c3c", "font_size": 14, "background": "rgba(255,255,255,0.9)"}})
    sp.add({"type": "region_label", "id": "rl3", "x": 0, "y": -1.5,
            "text": "0 решений", "style": {"color": "#888", "font_size": 13, "background": "rgba(255,255,255,0.9)"}})
    sp.add({"type": "filled_between", "id": "fb_answer",
            "upper": "0", "lower": "-1",
            "x_min": -4, "x_max": 4,
            "style": {"fill": "rgba(231,76,60,0.08)"}})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "Считаем число пересечений прямой $y = a$ с графиком:\n"
        "- $a > 0$: 4 пересечения → **4 решения**\n"
        "- $a = 0$: 3 пересечения (в т.ч. $x=0$) → **3 решения** ✓\n"
        "- $-1 < a < 0$: 4 пересечения → **4 решения**\n"
        "- $a = -1$: 2 пересечения (касание) → **2 решения**\n"
        "- $a < -1$: 0 пересечений → **0 решений**\n\n"
        "**Ответ: $a = 0$.**"})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"],
                   "caption": "Число решений в каждой области"})

    return blocks, "Задача 18: x² − 2|x| = a — ровно 3 решения"


def demo_range_method():
    """При каких a система x²+y²=1, y=ax+1 имеет решения? (касательная к окружности)"""
    canvas = {"width": 560, "height": 500,
              "x_min": -3, "x_max": 3, "y_min": -2.5, "y_max": 3.5,
              "x_label": "x", "y_label": "y"}

    sp = StepByStepParameter(canvas)
    blocks = []

    blocks.append({"type": "text", "content":
        "**Задача.** При каких значениях параметра $a$ прямая $y = ax + 1$ "
        "является касательной к окружности $x^2 + y^2 = 1$?"})

    # Step 1: draw circle via upper/lower halves
    sp.add({"type": "function_curve", "id": "circ_top", "expression": "sqrt(1 - x**2)",
            "x_min": -1, "x_max": 1,
            "style": {"stroke": "#2980b9", "stroke_width": 2.5}})
    sp.add({"type": "function_curve", "id": "circ_bot", "expression": "-sqrt(1 - x**2)",
            "x_min": -1, "x_max": 1,
            "style": {"stroke": "#2980b9", "stroke_width": 2.5}})
    sp.add({"type": "point", "id": "center", "x": 0, "y": 0, "label": "O",
            "label_dx": -12, "label_dy": 10,
            "style": {"fill": "#2980b9"}})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "Рисуем единичную окружность $x^2 + y^2 = 1$ с центром в начале координат."})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"], "caption": "Окружность x² + y² = 1"})

    # Step 2: family of lines passing through (0, 1) with different slopes
    sp.add({"type": "point", "id": "fixed", "x": 0, "y": 1, "label": "(0; 1)",
            "style": {"fill": "#e74c3c"}})
    for i, a_val in enumerate([0, 1, -1]):
        dash = ""
        sp.add({"type": "function_curve", "id": f"line_{i}",
                "expression": f"{a_val}*x + 1",
                "label": f"a = {a_val}" if a_val != 0 else "a = 0",
                "style": {"stroke": "#aaa", "stroke_width": 1.2, "dash": "dashed"}})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "Все прямые $y = ax + 1$ проходят через точку $(0; 1)$ — это пучок прямых.\n\n"
        "Показаны прямые при $a = -1, 0, 1$ (штриховые)."})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"],
                   "caption": "Пучок прямых через (0; 1)"})

    # Step 3: tangent lines
    sp.add({"type": "function_curve", "id": "tangent_pos",
            "expression": "0*x + 1",
            "style": {"stroke": "#e74c3c", "stroke_width": 2.2}})
    sp.add({"type": "point", "id": "tang_pt", "x": 0, "y": 1, "label": "",
            "style": {"fill": "#e74c3c"}})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "**Условие касания:** расстояние от центра $(0;0)$ до прямой $ax - y + 1 = 0$ равно $r = 1$:\n\n"
        "$$\\frac{|0 \\cdot a - 0 + 1|}{\\sqrt{a^2 + 1}} = 1$$\n\n"
        "$$1 = \\sqrt{a^2 + 1}$$\n$$1 = a^2 + 1$$\n$$a^2 = 0$$\n$$a = 0$$\n\n"
        "**Ответ: $a = 0$.** Прямая $y = 1$ — единственная касательная из пучка."})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"],
                   "caption": "Касательная y = 1 при a = 0"})

    return blocks, "Задача 18: касательная к окружности из пучка прямых"


def demo_number_of_solutions():
    """При каких a уравнение |x² - 4| = a имеет ровно 2 решения?"""
    canvas = {"width": 560, "height": 440,
              "x_min": -4, "x_max": 4, "y_min": -1, "y_max": 6,
              "x_label": "x", "y_label": "y"}

    sp = StepByStepParameter(canvas)
    blocks = []

    blocks.append({"type": "text", "content":
        "**Задача.** При каких значениях параметра $a$ уравнение $|x^2 - 4| = a$ имеет ровно 2 решения?"})

    # Step 1: graph of |x² - 4|
    sp.add({"type": "function_curve", "id": "f1", "expression": "abs(x**2 - 4)",
            "label": "y = |x² − 4|",
            "style": {"stroke": "#2980b9", "stroke_width": 2.5}})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "Строим график $y = |x^2 - 4|$.\n\n"
        "Это парабола $x^2 - 4$, «отражённая вверх» ниже оси $OX$.\n"
        "Нули: $x = \\pm 2$. Вершина исходной параболы: $(0; -4) \\to (0; 4)$ после отражения."})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"], "caption": "y = |x² − 4|"})

    # Step 2: critical values
    sp.add({"type": "hline", "id": "h_4", "y": 4, "label": "a = 4",
            "style": {"stroke": "#e74c3c", "dash": "dashed"}})
    sp.add({"type": "hline", "id": "h_0", "y": 0, "label": "a = 0",
            "style": {"stroke": "#8e44ad", "dash": "dashed"}})
    sp.add({"type": "point", "id": "top", "x": 0, "y": 4, "label": "(0; 4)"})
    sp.add({"type": "point", "id": "z1", "x": 2, "y": 0, "label": "(2; 0)"})
    sp.add({"type": "point", "id": "z2", "x": -2, "y": 0, "label": "(−2; 0)"})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "**Критические значения:**\n"
        "- $a = 4$: максимум функции (прямая касается вершины)\n"
        "- $a = 0$: прямая проходит через нули"})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"],
                   "caption": "Критические уровни a = 0 и a = 4"})

    # Step 3: count solutions
    sp.add({"type": "region_label", "id": "rl_above", "x": 0, "y": 5.2,
            "text": "2 решения",
            "style": {"color": "#27ae60", "font_size": 13, "background": "rgba(255,255,255,0.9)"}})
    sp.add({"type": "region_label", "id": "rl_mid", "x": 0, "y": 2,
            "text": "4 решения",
            "style": {"color": "#2980b9", "font_size": 13, "background": "rgba(255,255,255,0.9)"}})
    sp.add({"type": "region_label", "id": "rl_zero", "x": 0, "y": -0.6,
            "text": "0 решений",
            "style": {"color": "#888", "font_size": 13, "background": "rgba(255,255,255,0.9)"}})
    sp.add({"type": "filled_between", "id": "fb_ans",
            "upper": "6", "lower": "4", "x_min": -4, "x_max": 4,
            "style": {"fill": "rgba(39,174,96,0.08)"}})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "Число пересечений горизонтальной прямой $y = a$ с графиком:\n"
        "- $a > 4$: **2 решения** ✓\n"
        "- $a = 4$: **3 решения** (2 + касание)\n"
        "- $0 < a < 4$: **4 решения**\n"
        "- $a = 0$: **2 решения** ✓ (только $x = \\pm 2$)\n"
        "- $a < 0$: **0 решений** (правая часть отрицательна)\n\n"
        "**Ответ: $a > 4$ или $a = 0$.**"})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"],
                   "caption": "Ответ: a > 4 или a = 0"})

    return blocks, "Задача 18: |x² − 4| = a — ровно 2 решения"


def demo_inequality_parameter():
    """При каких a неравенство x² − 2ax + a ≤ 0 имеет решения?"""
    canvas = {"width": 560, "height": 440,
              "x_min": -1, "x_max": 5, "y_min": -1, "y_max": 5,
              "x_label": "x", "y_label": "a"}

    sp = StepByStepParameter(canvas, y_label="a")
    blocks = []

    blocks.append({"type": "text", "content":
        "**Задача.** При каких значениях параметра $a$ неравенство $x^2 - 2ax + a \\leq 0$ "
        "имеет хотя бы одно решение?"})

    blocks.append({"type": "text", "content":
        "Перепишем: $x^2 \\leq 2ax - a$, то есть $x^2 \\leq a(2x - 1)$.\n\n"
        "При $2x - 1 > 0$ (т.е. $x > 1/2$): $a \\geq \\frac{x^2}{2x-1}$.\n\n"
        "Рассмотрим кривую $a = \\frac{x^2}{2x-1}$ на плоскости $(x, a)$."})

    # Step 1: boundary curve a = x²/(2x-1)
    sp.add({"type": "function_curve", "id": "boundary",
            "expression": "x**2 / (2*x - 1)",
            "x_min": 0.55, "x_max": 5,
            "label": "a = x²/(2x−1)",
            "style": {"stroke": "#2980b9", "stroke_width": 2.5}})
    sp.add({"type": "vline", "id": "asympt", "x": 0.5,
            "style": {"stroke": "#ccc", "dash": "dashed", "stroke_width": 1}})
    sp.snapshot()
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"],
                   "caption": "Граничная кривая a = x²/(2x−1)"})

    # Step 2: find minimum of boundary curve
    # a' = (2x(2x-1) - x²·2) / (2x-1)² = (2x²-2x) / (2x-1)² = 0 => x=0 or x=1
    # at x=1: a = 1/(2-1) = 1, minimum on x>0.5
    sp.add({"type": "point", "id": "min_pt", "x": 1, "y": 1, "label": "(1; 1)",
            "style": {"fill": "#e74c3c"}})
    sp.add({"type": "hline", "id": "h_1", "y": 1, "label": "a = 1",
            "style": {"stroke": "#e74c3c", "dash": "dashed"}})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "Находим минимум $a(x) = \\frac{x^2}{2x-1}$ при $x > 1/2$:\n\n"
        "$$a'(x) = \\frac{2x(2x-1) - 2x^2}{(2x-1)^2} = \\frac{2x^2 - 2x}{(2x-1)^2} = 0$$\n\n"
        "$x(x-1) = 0$, при $x > 1/2$: $x = 1$. Тогда $a(1) = \\frac{1}{1} = 1$."})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"],
                   "caption": "Минимум граничной кривой при x = 1, a = 1"})

    # Step 3: shade the region + answer
    sp.add({"type": "filled_between", "id": "fb_sol",
            "upper": "5", "lower": "x**2 / (2*x - 1)",
            "x_min": 0.55, "x_max": 5,
            "style": {"fill": "rgba(39,174,96,0.12)"}})
    sp.add({"type": "region_label", "id": "rl_yes", "x": 2.5, "y": 3.5,
            "text": "есть решения",
            "style": {"color": "#27ae60", "font_size": 14, "background": "rgba(255,255,255,0.9)"}})
    sp.add({"type": "region_label", "id": "rl_no", "x": 3.5, "y": 0.5,
            "text": "нет решений",
            "style": {"color": "#888", "font_size": 13, "background": "rgba(255,255,255,0.9)"}})
    sp.snapshot()
    blocks.append({"type": "text", "content":
        "Неравенство имеет решение, когда прямая $y = a$ проходит через закрашенную область "
        "(выше граничной кривой).\n\n"
        "Минимум кривой $= 1$, значит при $a \\geq 1$ неравенство имеет решения.\n\n"
        "Отдельно: при $a \\leq 0$ также есть решения (при $x \\leq 0$: $x^2 + a \\leq 0$).\n\n"
        "**Ответ: $a \\leq 0$ или $a \\geq 1$.**"})
    blocks.append({"type": "visual", "svg": sp.steps[-1]["svg"],
                   "caption": "Ответ: a ≤ 0 или a ≥ 1"})

    return blocks, "Задача 18: x² − 2ax + a ≤ 0 — метод областей"


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    demos = [
        demo_horizontal_line_method,
        demo_number_of_solutions,
        demo_range_method,
        demo_inequality_parameter,
    ]

    all_cards = []
    for demo_fn in demos:
        blocks, title = demo_fn()
        html = generate_html(blocks, title=title)
        name = demo_fn.__name__.replace("demo_", "")
        path = OUTPUT_DIR / f"task18_{name}.html"
        path.write_text(html, encoding="utf-8")
        print(f"  ✓ {title}")
        print(f"    → {path}")
        all_cards.append((title, blocks))

    # Combined gallery
    esc = html_mod.escape
    parts = [f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"/>
<title>Задача 18 ЕГЭ — движок визуализации</title>
<script>
MathJax = {{ tex: {{ inlineMath: [['$','$']], displayMath: [['$$','$$']] }}, svg: {{ fontCache: 'global' }} }};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#f5f5f7; color:#1d1d1f; }}
  .header {{ background:linear-gradient(135deg,#0f3460,#16213e,#1a1a2e); padding:44px 20px; text-align:center; color:white; }}
  .header h1 {{ font-size:30px; margin-bottom:8px; }}
  .header p {{ opacity:0.75; font-size:14px; max-width:600px; margin:0 auto; }}
  .content {{ max-width:860px; margin:0 auto; padding:24px 20px 60px; }}
  .task-card {{ background:white; border-radius:14px; margin:28px 0; overflow:hidden;
                box-shadow:0 2px 16px rgba(0,0,0,0.06); }}
  .task-title {{ padding:18px 24px; font-size:17px; font-weight:700; color:#2c3e50;
                 border-bottom:1px solid #eee; background:#fafbfc; }}
  .task-body {{ padding:20px 24px; }}
  .task-body .text-block {{ font-size:15px; line-height:1.7; margin:10px 0; font-family:'Georgia',serif; }}
  .task-body .text-block p {{ margin:4px 0; }}
  .task-body .formula {{ background:#f7f9fc; padding:12px 18px; border-radius:8px; margin:10px 0;
                         text-align:center; border-left:3px solid #2980b9; font-size:15px; }}
  .task-body .visual-block {{ margin:18px 0; text-align:center; }}
  .task-body .visual-frame {{ display:inline-block; background:white; border:1px solid #eee;
                              border-radius:10px; padding:12px 14px; }}
  .task-body .visual-frame svg {{ max-width:100%; height:auto; }}
  .task-body .visual-caption {{ font-size:12px; color:#999; margin-top:6px; font-style:italic; }}
  .footer {{ text-align:center; padding:30px 20px; color:#aaa; font-size:11px; border-top:1px solid #eee; }}
</style></head><body>
<div class="header">
  <h1>Задача 18 ЕГЭ — с параметром</h1>
  <p>Графический метод · метод областей · анализ числа решений<br/>
  Движок: function_curve · hline · filled_between · region_label · open_point</p>
</div>
<div class="content">
"""]

    for title, blocks in all_cards:
        parts.append(f'<div class="task-card"><div class="task-title">{esc(title)}</div><div class="task-body">')
        for b in blocks:
            if b["type"] == "text":
                parts.append(f'<div class="text-block">{render_md(b["content"])}</div>')
            elif b["type"] == "visual":
                parts.append(f'<div class="visual-block"><div class="visual-frame">{b["svg"]}</div>'
                             f'<div class="visual-caption">{esc(b.get("caption", ""))}</div></div>')
        parts.append('</div></div>')

    parts.append(f"""</div>
<div class="footer">{len(all_cards)} задач · task18_parameter.py</div>
</body></html>""")

    gallery_path = OUTPUT_DIR / "task18_gallery.html"
    gallery_path.write_text("\n".join(parts), encoding="utf-8")
    print(f"\n  Gallery: {gallery_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Task 18 (parameter) visualizer")
    parser.add_argument("--auto", action="store_true",
                        help="Run LLM auto-pipeline on built-in test problems")
    parser.add_argument("--problem-file", type=str, default=None,
                        help="Path to .txt with problem+solution (auto mode)")
    parser.add_argument("--plan-file", type=str, default=None,
                        help="Path to saved plan JSON (skip LLM)")
    parser.add_argument("--output", type=str, default="auto_task18")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--demo", action="store_true",
                        help="Run hand-crafted demos (no LLM needed)")
    args = parser.parse_args()

    if args.api_key:
        os.environ["TOGETHER_API_KEY"] = args.api_key

    if args.plan_file:
        run_from_plan(plan_path=args.plan_file, output_name=args.output)
    elif args.auto or args.problem_file:
        if args.problem_file:
            text = Path(args.problem_file).read_text(encoding="utf-8")
            run_auto(problem_text=text, output_name=args.output,
                     model=args.model)
        else:
            for i, problem in enumerate([TASK18_PROBLEM_1, TASK18_PROBLEM_2], 1):
                run_auto(problem_text=problem,
                         output_name=f"auto_task18_p{i}",
                         model=args.model)
    else:
        main()
