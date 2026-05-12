"""
Graph-focused pipeline: конспект → планировщик (только графики) → SVG.

Убраны все diagram-типы. Планировщик ищет ТОЛЬКО возможности для:
  - function_graph (графики функций)
  - tangent_line_graph (касательные)
  - derivative_sign_chart (знаки производной)
  - number_line (числовая прямая)
  - coordinate_plane (точки на координатной плоскости)

Использование:
    python3 pipeline/run_graphs.py
    python3 pipeline/run_graphs.py conspects/task8.md
"""

import json
import os
import re
import sys
import time
import math
import html as html_mod
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from visual_planner import split_conspect_into_sections, _extract_json, TOGETHER_API_URL
from visual_planner_v2 import _call_together, _extract_json_array
from pipeline.converter import convert_plan_to_scene, _normalize_expr

API_KEY = os.environ.get("TOGETHER_API_KEY", "")
MODEL = "Qwen/Qwen2.5-7B-Instruct-Turbo"
OUTPUT_DIR = ROOT / "pipeline" / "output_graphs"
CONSPECTS = [
    ROOT / "conspects" / "task4.md",
    ROOT / "conspects" / "task6.md",
    ROOT / "conspects" / "task8.md",
    ROOT / "conspects" / "task12.md",
]

# ═══════════════════════════════════════════════════════════════
# Graph-only prompts
# ═══════════════════════════════════════════════════════════════

GRAPH_TYPES = {
    "function_graph": "График функции y=f(x) на координатной плоскости: парабола, гипербола, показательная, логарифмическая, тригонометрическая и др.",
    "tangent_line_graph": "График функции с касательной линией в точке — показывает наклон и угловой коэффициент",
    "derivative_sign_chart": "График функции f(x) вместе с графиком производной f'(x) — показывает возрастание/убывание, критические точки, экстремумы",
    "number_line": "Числовая прямая с отмеченными точками, корнями уравнений, областью допустимых значений",
    "coordinate_plane": "Координатная плоскость с несколькими функциями или точками пересечения",
}

PASS1_PROMPT = """Ты — планировщик визуалов-ГРАФИКОВ для учебных конспектов ЕГЭ по математике.

Тебе дан конспект, разбитый на пронумерованные секции. Твоя задача — найти ВСЕ места, где можно нарисовать МАТЕМАТИЧЕСКИЙ ГРАФИК.

## Доступные типы визуалов (ТОЛЬКО графики):

{visual_types}

## Правила:

1. Ищи МАКСИМУМ возможностей для графиков — это твоя главная цель.
2. ОБЯЗАТЕЛЬНО нужен график для:
   - Любой функции, упомянутой в тексте (y = x², y = 2^x, y = log₂(x), и т.д.) → function_graph
   - Описания касательной к графику, углового коэффициента → tangent_line_graph
   - Описания возрастания/убывания, экстремумов, знаков производной → derivative_sign_chart
   - Корней уравнений, ОДЗ, интервалов → number_line
   - Пересечения функций, сравнения графиков → coordinate_plane
3. Даже если функция упомянута в ПРИМЕРЕ решения — всё равно предложи график.
4. Если в секции есть формула y = ..., f(x) = ..., a^x = ... — это ВСЕГДА повод для графика.
5. НЕ нужен график только для секций без математических выражений (введение, советы).

## Формат ответа:

Верни ТОЛЬКО валидный JSON-массив (без markdown-обёртки):

[
  {"section_id": 0, "need_visual": true, "visual_type": "function_graph", "reason": "почему"},
  {"section_id": 1, "need_visual": false, "visual_type": "none", "reason": "нет функций для графика"},
  ...
]

Включи ВСЕ секции."""

PASS2_PROMPT_TEMPLATE = """Ты — планировщик графических визуалов для ЕГЭ. Тебе дана секция конспекта, для которой нужен визуал типа "__VISUAL_TYPE__".

Твоя задача — извлечь КОНКРЕТНЫЕ математические данные для построения графика.

## Критически важно:
- Извлекай ТОЧНЫЕ функции, уравнения, числа из текста.
- Пиши выражения в Python-формате: x**2 вместо x², 2*x вместо 2x.
- Указывай конкретный диапазон x_range, подходящий для данной функции.
- Если есть точки пересечения, корни, экстремумы — извлекай их координаты.

## Примеры:

### function_graph:
{"need_visual": true, "visual_type": "function_graph", "description": "График параболы y = x^2 - 4x + 3", "params": {"equation": "x**2 - 4*x + 3", "x_range": [-1, 5], "highlight_points": [{"x": 2, "y": -1, "label": "вершина (2,-1)"}, {"x": 1, "y": 0, "label": "x=1"}, {"x": 3, "y": 0, "label": "x=3"}]}, "caption": "y = x^2 - 4x + 3", "placement": "after_section", "priority": "high"}

### function_graph (показательная):
{"need_visual": true, "visual_type": "function_graph", "description": "Графики 2^x и 3^x", "params": {"equations": [{"expression": "2**x", "label": "y = 2^x"}, {"expression": "3**x", "label": "y = 3^x"}], "x_range": [-3, 3], "highlight_points": [{"x": 0, "y": 1, "label": "(0,1)"}]}, "caption": "Показательные функции", "placement": "after_section", "priority": "high"}

### tangent_line_graph:
{"need_visual": true, "visual_type": "tangent_line_graph", "description": "f(x) = x^2 с касательной в точке x=1", "params": {"equation": "x**2", "tangent_point": {"x": 1, "y": 1}, "tangent_equation": "2*x - 1", "x_range": [-2, 4]}, "caption": "Касательная к y = x^2 в (1,1)", "placement": "after_section", "priority": "high"}

### derivative_sign_chart:
{"need_visual": true, "visual_type": "derivative_sign_chart", "description": "f(x) и f'(x) с критическими точками", "params": {"function": "x**3 - 3*x", "derivative": "3*x**2 - 3", "x_range": [-3, 3], "critical_points": [-1, 1], "extrema": [{"x": -1, "type": "max", "y": 2}, {"x": 1, "type": "min", "y": -2}]}, "caption": "f(x) = x^3 - 3x и f'(x)", "placement": "after_section", "priority": "high"}

### number_line:
{"need_visual": true, "visual_type": "number_line", "description": "Числовая прямая с корнями", "params": {"points": [{"value": -2, "label": "x=-2"}, {"value": 3, "label": "x=3"}]}, "caption": "Корни на числовой прямой", "placement": "after_section", "priority": "medium"}

## Формат ответа:
Верни ТОЛЬКО валидный JSON (без markdown-обёртки, без ```json```)."""""


# ═══════════════════════════════════════════════════════════════
# Graph planner
# ═══════════════════════════════════════════════════════════════

class GraphPlanner:
    def __init__(self, api_key: str, model: str = MODEL):
        self.api_key = api_key
        self.model = model

    def plan(self, markdown_text: str) -> dict:
        sections = split_conspect_into_sections(markdown_text)
        sections = [s for s in sections if len(s["text"].strip()) >= 30]

        total_tokens_in = 0
        total_tokens_out = 0
        total_time = 0

        # Pass 1: find all graph opportunities
        p1 = self._pass1(sections)
        total_tokens_in += p1["tokens_in"]
        total_tokens_out += p1["tokens_out"]
        total_time += p1["elapsed"]

        decisions = {}
        if p1["parsed"]:
            for item in p1["parsed"]:
                sid = item.get("section_id")
                if sid is not None:
                    decisions[sid] = item

        # Pass 2: detail for each graph
        plans = []
        for section in sections:
            sid = section["id"]
            dec = decisions.get(sid, {})
            need = dec.get("need_visual", False)
            vtype = dec.get("visual_type", "none")

            if need and vtype != "none" and vtype in GRAPH_TYPES:
                detail = self._pass2(section, vtype)
                total_tokens_in += detail["tokens_in"]
                total_tokens_out += detail["tokens_out"]
                total_time += detail["elapsed"]

                parsed = detail["parsed"]
                if parsed is None:
                    parsed = {"need_visual": True, "visual_type": vtype}

                plans.append({
                    "section_id": sid,
                    "section_title": section["title"],
                    "section_text_preview": section["text"][:200],
                    "need_visual": True,
                    "visual_type": parsed.get("visual_type", vtype),
                    "description": parsed.get("description", ""),
                    "params": parsed.get("params", {}),
                    "caption": parsed.get("caption", ""),
                    "priority": parsed.get("priority", "high"),
                })

        return {
            "model": self.model,
            "total_sections": len(sections),
            "graphs_planned": len(plans),
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_time_sec": round(total_time, 2),
            "plans": plans,
        }

    def _call_with_retry(self, system, user, max_tokens=4096, retries=3):
        for attempt in range(retries):
            try:
                return _call_together(self.api_key, self.model, system, user, 0.3, max_tokens)
            except Exception as e:
                if attempt < retries - 1:
                    wait = 5 * (attempt + 1)
                    print(f"    [retry {attempt+1}] {e}, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    def _pass1(self, sections):
        types_str = "\n".join(f"- **{k}**: {v}" for k, v in GRAPH_TYPES.items())
        system = PASS1_PROMPT.replace("{visual_types}", types_str)
        sections_text = "\n\n".join(
            f"--- Секция {s['id']}: {s['title']} ---\n{s['text'][:600]}"
            for s in sections
        )
        user = f"Конспект ЕГЭ по математике:\n\n{sections_text}\n\nНайди ВСЕ возможности для графиков. Верни JSON-массив."
        result = self._call_with_retry(system, user, 4096)
        parsed = _extract_json_array(result["raw"])
        return {"parsed": parsed, **result}

    def _pass2(self, section, vtype):
        system = PASS2_PROMPT_TEMPLATE.replace("__VISUAL_TYPE__", vtype)
        user = f'Создай детальный план графика типа "{vtype}" для этой секции.\n\n### {section["title"]}\n\n{section["text"]}\n\nИзвлеки конкретные функции, уравнения и числа из текста. Верни JSON.'
        result = self._call_with_retry(system, user, 2048)
        parsed = _extract_json(result["raw"])
        return {"parsed": parsed, **result}


# ═══════════════════════════════════════════════════════════════
# Enhanced function_plot renderer
# ═══════════════════════════════════════════════════════════════

COLORS = ["#2980b9", "#e74c3c", "#27ae60", "#8e44ad", "#e67e22", "#1abc9c"]

_EVAL_NS = {
    "__builtins__": {},
    "pi": math.pi, "e": math.e,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "sqrt": math.sqrt, "abs": abs, "exp": math.exp,
    "log": math.log,
}


def _eval_y(expr: str, xval: float) -> float | None:
    try:
        ns = {**_EVAL_NS, "x": xval}
        result = eval(expr, ns)
        if isinstance(result, (int, float)) and math.isfinite(result):
            return float(result)
    except Exception:
        pass
    # try log(base, arg) → log(arg)/log(base)
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


def render_graph_svg(scene: dict) -> str:
    """Render a function_plot scene to SVG with enhanced styling."""
    c = scene.get("canvas", {})
    w = c.get("width", 500)
    h = c.get("height", 400)
    xmin, xmax = c.get("x_min", -5), c.get("x_max", 5)
    ymin, ymax = c.get("y_min", -5), c.get("y_max", 5)

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

    # grid
    for xi in range(math.ceil(xmin), math.floor(xmax) + 1):
        lines.append(f'  <line x1="{sx(xi):.1f}" y1="0" x2="{sx(xi):.1f}" y2="{h}" stroke="#eee" stroke-width="0.5"/>')
    for yi in range(math.ceil(ymin), math.floor(ymax) + 1):
        lines.append(f'  <line x1="0" y1="{sy(yi):.1f}" x2="{w}" y2="{sy(yi):.1f}" stroke="#eee" stroke-width="0.5"/>')

    # axes
    if ymin <= 0 <= ymax:
        lines.append(f'  <line x1="0" y1="{sy(0):.1f}" x2="{w}" y2="{sy(0):.1f}" stroke="#555" stroke-width="1" marker-end="url(#ah)"/>')
    if xmin <= 0 <= xmax:
        lines.append(f'  <line x1="{sx(0):.1f}" y1="{h}" x2="{sx(0):.1f}" y2="0" stroke="#555" stroke-width="1" marker-end="url(#ah)"/>')

    # tick labels
    for xi in range(math.ceil(xmin), math.floor(xmax) + 1):
        if xi == 0:
            continue
        y0 = sy(0) if ymin <= 0 <= ymax else h - 4
        lines.append(f'  <text x="{sx(xi):.1f}" y="{y0 + 14:.1f}" text-anchor="middle" font-size="10" fill="#888">{xi}</text>')
    for yi in range(math.ceil(ymin), math.floor(ymax) + 1):
        if yi == 0:
            continue
        x0 = sx(0) if xmin <= 0 <= xmax else 4
        lines.append(f'  <text x="{x0 - 6:.1f}" y="{sy(yi) + 4:.1f}" text-anchor="end" font-size="10" fill="#888">{yi}</text>')

    if xmin <= 0 <= xmax and ymin <= 0 <= ymax:
        lines.append(f'  <text x="{sx(0) - 8:.1f}" y="{sy(0) + 14:.1f}" font-size="10" fill="#888">0</text>')

    # render objects
    color_idx = 0
    for obj in scene.get("objects", []):
        if obj["type"] == "function_curve":
            expr = obj["expression"]
            oxmin = obj.get("x_min", xmin)
            oxmax = obj.get("x_max", xmax)
            style = obj.get("style") or {}
            stroke = style.get("stroke", COLORS[color_idx % len(COLORS)])
            dash = ' stroke-dasharray="8,4"' if style.get("dash") == "dashed" else ""
            sw = style.get("stroke_width", 2.5)
            color_idx += 1

            pts = []
            prev_valid = False
            for i in range(301):
                xv = oxmin + (oxmax - oxmin) * i / 300
                yv = _eval_y(expr, xv)
                if yv is not None and ymin - 5 <= yv <= ymax + 5:
                    pts.append(f"{sx(xv):.1f},{sy(yv):.1f}")
                    prev_valid = True
                else:
                    if pts and prev_valid:
                        lines.append(f'  <polyline points="{" ".join(pts)}" fill="none" stroke="{stroke}" stroke-width="{sw}"{dash}/>')
                        pts = []
                    prev_valid = False
            if pts:
                lines.append(f'  <polyline points="{" ".join(pts)}" fill="none" stroke="{stroke}" stroke-width="{sw}"{dash}/>')

            label = obj.get("label") or style.get("label")
            if label:
                lx = sx(oxmax * 0.75)
                ly_val = _eval_y(expr, oxmax * 0.75)
                if ly_val is not None:
                    ly = sy(ly_val)
                    lines.append(f'  <text x="{lx + 6:.1f}" y="{ly - 8:.1f}" font-size="12" fill="{stroke}" font-style="italic">{html_mod.escape(label)}</text>')

        elif obj["type"] == "point":
            px, py = sx(obj["x"]), sy(obj["y"])
            lines.append(f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="#e74c3c" stroke="white" stroke-width="1.5"/>')
            if obj.get("label"):
                lines.append(f'  <text x="{px + 8:.1f}" y="{py - 8:.1f}" font-size="11" fill="#333">{html_mod.escape(str(obj["label"]))}</text>')

    # annotations
    for ann in scene.get("annotations", []):
        if ann["type"] == "label":
            anchor_obj = next((o for o in scene["objects"] if o.get("id") == ann.get("anchor")), None)
            if anchor_obj and "x" in anchor_obj:
                ax = sx(anchor_obj["x"] + ann.get("dx", 0))
                ay = sy(anchor_obj["y"] + ann.get("dy", 0))
                lines.append(f'  <text x="{ax:.1f}" y="{ay:.1f}" font-size="12" fill="#2c3e50" font-style="italic">{html_mod.escape(ann["text"])}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def convert_multi_equation(plan: dict) -> dict | None:
    """Handle plans with multiple equations on one coordinate_plane."""
    params = plan.get("params", {})
    equations = params.get("equations", [])

    if not equations:
        return convert_plan_to_scene(plan)

    x_range = params.get("x_range", [-5, 5])
    if isinstance(x_range, list) and len(x_range) >= 2:
        xmin, xmax = float(x_range[0]), float(x_range[1])
    else:
        xmin, xmax = -5.0, 5.0

    objects = []
    all_ys = []
    for i, eq in enumerate(equations):
        if isinstance(eq, dict):
            raw = eq.get("expression", eq.get("equation", ""))
            label = eq.get("label", "")
        else:
            raw = str(eq)
            label = ""
        if not raw:
            continue

        expr = _normalize_expr(raw)
        objects.append({
            "type": "function_curve", "id": f"func_{i}",
            "expression": expr, "x_min": xmin, "x_max": xmax,
            "style": {"stroke": COLORS[i % len(COLORS)], "label": label},
        })
        for j in range(21):
            xv = xmin + (xmax - xmin) * j / 20
            yv = _eval_y(expr, xv)
            if yv is not None:
                all_ys.append(yv)

    for i, pt in enumerate(params.get("highlight_points", [])):
        if isinstance(pt, dict):
            objects.append({
                "type": "point", "id": f"pt_{i}",
                "x": float(pt.get("x", 0)), "y": float(pt.get("y", 0)),
                "label": pt.get("label", ""),
            })

    if not all_ys:
        all_ys = [-5, 5]
    ymin = math.floor(min(all_ys) - 1)
    ymax = math.ceil(max(all_ys) + 1)

    return {
        "scene_type": "function_plot",
        "canvas": {"width": 500, "height": 400,
                    "x_min": xmin - 0.5, "x_max": xmax + 0.5,
                    "y_min": ymin, "y_max": ymax},
        "style": {"theme": "light", "stroke_color": "#333", "fill_color": "none",
                  "font_size": 12, "font_family": "sans-serif"},
        "objects": objects,
        "constraints": [],
        "annotations": [],
    }


# ═══════════════════════════════════════════════════════════════
# Pipeline
# ═══════════════════════════════════════════════════════════════

def run_graph_pipeline(conspect_path: Path, api_key: str, model: str) -> dict:
    print(f"\n{'=' * 60}")
    print(f"  {conspect_path.name}")
    print(f"{'=' * 60}")

    text = conspect_path.read_text(encoding="utf-8")
    planner = GraphPlanner(api_key=api_key, model=model)

    print("  Планирование графиков...")
    t0 = time.time()
    plan_result = planner.plan(text)
    plan_time = time.time() - t0
    print(f"  → {plan_result['graphs_planned']} графиков за {plan_time:.1f}s")

    task_name = conspect_path.stem
    task_dir = OUTPUT_DIR / task_name
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "plan.json").write_text(
        json.dumps(plan_result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("  Рендеринг SVG...")
    results = []
    for plan in plan_result["plans"]:
        vtype = plan["visual_type"]
        if vtype not in GRAPH_TYPES:
            continue

        params = plan.get("params", {})
        has_real_data = bool(
            params.get("equation") or params.get("function") or
            params.get("equations") or params.get("derivative") or
            params.get("tangent_equation") or params.get("points") or
            params.get("critical_points")
        )
        if not has_real_data:
            print(f"    [SKIP] S{plan['section_id']} {vtype}: no extracted data")
            continue

        if params.get("equations"):
            scene = convert_multi_equation(plan)
        else:
            scene = convert_plan_to_scene(plan)

        if scene is None or scene.get("scene_type") not in ("function_plot", "geometry"):
            continue

        scene_file = task_dir / f"scene_{plan['section_id']}_{vtype}.json"
        scene_file.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")

        svg = render_graph_svg(scene)
        svg_file = task_dir / f"graph_{plan['section_id']}_{vtype}.svg"
        svg_file.write_text(svg, encoding="utf-8")

        print(f"    [OK] S{plan['section_id']} {vtype}: {plan.get('caption', '')[:50]}")

        results.append({
            "section_id": plan["section_id"],
            "section_title": plan.get("section_title", ""),
            "visual_type": vtype,
            "caption": plan.get("caption", ""),
            "description": plan.get("description", ""),
            "priority": plan.get("priority", ""),
            "svg_file": str(svg_file),
            "params": plan.get("params", {}),
        })

    print(f"  → {len(results)} SVG отрендерено")
    return {
        "conspect": task_name,
        "plan_result": plan_result,
        "graphs": results,
    }


def generate_html_report(all_results: list[dict]):
    total_graphs = sum(len(r["graphs"]) for r in all_results)

    html = [f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>Графики: Планировщик визуалов → SVG</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f0f2f5; color: #1a1a2e; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
             padding: 40px 20px; text-align: center; color: white; }}
  .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
  .header p {{ opacity: 0.8; font-size: 15px; }}
  .stats-bar {{ display: flex; justify-content: center; gap: 30px;
                margin-top: 20px; flex-wrap: wrap; }}
  .stat {{ background: rgba(255,255,255,0.15); padding: 10px 24px;
           border-radius: 8px; text-align: center; }}
  .stat-val {{ font-size: 24px; font-weight: bold; }}
  .stat-label {{ font-size: 11px; opacity: 0.7; text-transform: uppercase; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 30px 20px; }}
  .task-section {{ margin-bottom: 40px; }}
  .task-title {{ font-size: 20px; color: #1a1a2e; margin-bottom: 16px;
                 padding-bottom: 8px; border-bottom: 2px solid #0f3460; }}
  .graph-card {{ background: white; border-radius: 12px; margin-bottom: 24px;
                 box-shadow: 0 2px 12px rgba(0,0,0,0.08); overflow: hidden; }}
  .graph-meta {{ padding: 16px 20px; border-bottom: 1px solid #f0f0f0; }}
  .graph-meta h3 {{ font-size: 15px; color: #333; margin-bottom: 4px; }}
  .graph-meta .desc {{ font-size: 13px; color: #666; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 10px;
            font-size: 11px; color: white; margin-right: 6px; }}
  .badge-fn {{ background: #2980b9; }}
  .badge-tg {{ background: #e74c3c; }}
  .badge-dsc {{ background: #27ae60; }}
  .badge-nl {{ background: #e67e22; }}
  .badge-cp {{ background: #8e44ad; }}
  .graph-body {{ padding: 20px; text-align: center; background: #fafbfc; }}
  .graph-body svg {{ max-width: 100%; height: auto; border: 1px solid #eee;
                     border-radius: 8px; }}
  .graph-caption {{ padding: 12px 20px; font-size: 13px; color: #555;
                    font-style: italic; text-align: center; background: #f8f9fa; }}
  .params {{ padding: 12px 20px; font-size: 12px; color: #777;
             background: #f8f9fa; border-top: 1px solid #eee; }}
  .params code {{ background: #e8e8e8; padding: 1px 4px; border-radius: 3px;
                  font-size: 11px; }}
</style>
</head>
<body>
<div class="header">
  <h1>Генерация графиков для конспектов ЕГЭ</h1>
  <p>Планировщик визуалов (LLM) → Конвертер → SVG Renderer</p>
  <div class="stats-bar">
    <div class="stat"><div class="stat-val">{total_graphs}</div><div class="stat-label">графиков</div></div>
    <div class="stat"><div class="stat-val">{len(all_results)}</div><div class="stat-label">конспектов</div></div>
    <div class="stat"><div class="stat-val">{MODEL.split('/')[-1]}</div><div class="stat-label">модель</div></div>
  </div>
</div>
<div class="container">
"""]

    type_badges = {
        "function_graph": ("fn", "badge-fn", "function"),
        "tangent_line_graph": ("tg", "badge-tg", "tangent"),
        "derivative_sign_chart": ("dsc", "badge-dsc", "derivative"),
        "number_line": ("nl", "badge-nl", "number line"),
        "coordinate_plane": ("cp", "badge-cp", "coord plane"),
    }

    for res in all_results:
        task = res["conspect"]
        graphs = res["graphs"]
        if not graphs:
            continue

        html.append(f'<div class="task-section">')
        html.append(f'<h2 class="task-title">{html_mod.escape(task)} — {len(graphs)} графиков</h2>')

        for g in graphs:
            vtype = g["visual_type"]
            badge_short, badge_class, badge_text = type_badges.get(vtype, ("?", "badge-fn", vtype))
            svg_file = g.get("svg_file", "")
            svg_content = ""
            if svg_file and os.path.exists(svg_file):
                svg_content = Path(svg_file).read_text(encoding="utf-8")

            params = g.get("params", {})
            eq = params.get("equation", params.get("function", ""))
            deriv = params.get("derivative", "")
            x_range = params.get("x_range", "")

            params_parts = []
            if eq:
                params_parts.append(f"f(x) = <code>{html_mod.escape(str(eq))}</code>")
            if deriv:
                params_parts.append(f"f'(x) = <code>{html_mod.escape(str(deriv))}</code>")
            if x_range:
                params_parts.append(f"x ∈ {x_range}")
            eqs = params.get("equations", [])
            for e in eqs:
                if isinstance(e, dict):
                    params_parts.append(f"<code>{html_mod.escape(e.get('expression', ''))}</code> ({html_mod.escape(e.get('label', ''))})")

            html.append(f"""
<div class="graph-card">
  <div class="graph-meta">
    <span class="badge {badge_class}">{badge_text}</span>
    <span style="font-size:12px;color:#999;">Секция {g['section_id']}: {html_mod.escape(g.get('section_title', ''))}</span>
    <h3>{html_mod.escape(g.get('description', ''))}</h3>
  </div>
  <div class="graph-body">{svg_content}</div>
""")
            if g.get("caption"):
                html.append(f'  <div class="graph-caption">{html_mod.escape(g["caption"])}</div>')
            if params_parts:
                html.append(f'  <div class="params">{" &nbsp;|&nbsp; ".join(params_parts)}</div>')
            html.append("</div>")

        html.append("</div>")

    # summary stats
    from collections import Counter
    all_types = Counter()
    for res in all_results:
        for g in res["graphs"]:
            all_types[g["visual_type"]] += 1

    type_names = {
        "function_graph": "График функции",
        "tangent_line_graph": "Касательная",
        "derivative_sign_chart": "Производная + функция",
        "number_line": "Числовая прямая",
        "coordinate_plane": "Координатная плоскость",
    }

    html.append(f"""
<div style="margin-top:40px; padding:24px; background:white; border-radius:12px;
     box-shadow:0 2px 12px rgba(0,0,0,0.08);">
  <h2 style="margin-bottom:16px; color:#1a1a2e;">Сводка по типам графиков</h2>
  <div style="display:flex; gap:12px; flex-wrap:wrap;">
""")
    for vtype, count in all_types.most_common():
        badge_short, badge_class, badge_text = type_badges.get(vtype, ("?", "badge-fn", vtype))
        name = type_names.get(vtype, vtype)
        html.append(f"""
    <div style="flex:1; min-width:140px; background:#f8f9fa; border-radius:8px;
         padding:16px; text-align:center;">
      <div style="font-size:28px; font-weight:bold; color:#0f3460;">{count}</div>
      <div><span class="badge {badge_class}">{badge_text}</span></div>
      <div style="font-size:12px; color:#666; margin-top:4px;">{name}</div>
    </div>
""")

    llm_count = sum(len(r["graphs"]) for r in all_results if "curated" not in str(r.get("conspect", "")))
    curated_count = total_graphs - llm_count

    html.append(f"""
  </div>
  <p style="margin-top:16px; font-size:13px; color:#888;">
    Всего: {total_graphs} графиков ({llm_count} сгенерировано LLM + {curated_count} курированных примеров) |
    Модель: {MODEL}
  </p>
</div>
""")

    html.append("""
</div>
</body>
</html>""")

    out_path = OUTPUT_DIR / "graphs_report.html"
    out_path.write_text("\n".join(html), encoding="utf-8")
    print(f"\n  Отчёт: {out_path}")
    return out_path


CURATED_GRAPHS = [
    {
        "conspect": "task6_curated",
        "title": "Типичные функции ЕГЭ (задание 6)",
        "plans": [
            {
                "section_id": 100,
                "section_title": "Показательные функции",
                "visual_type": "function_graph",
                "description": "Семейство показательных функций: 2^x, 3^x, (1/2)^x",
                "caption": "Показательные функции и их свойства",
                "priority": "high",
                "params": {
                    "equations": [
                        {"expression": "2**x", "label": "y = 2ˣ"},
                        {"expression": "3**x", "label": "y = 3ˣ"},
                        {"expression": "(1/2)**x", "label": "y = (1/2)ˣ"},
                    ],
                    "x_range": [-3, 3],
                    "highlight_points": [{"x": 0, "y": 1, "label": "(0, 1)"}],
                },
            },
            {
                "section_id": 101,
                "section_title": "Логарифмическая функция",
                "visual_type": "function_graph",
                "description": "Графики логарифмов с разными основаниями",
                "caption": "Логарифмические функции log₂(x) и log₃(x)",
                "priority": "high",
                "params": {
                    "equations": [
                        {"expression": "log(x)/log(2)", "label": "y = log₂(x)"},
                        {"expression": "log(x)/log(3)", "label": "y = log₃(x)"},
                    ],
                    "x_range": [0.1, 10],
                    "highlight_points": [
                        {"x": 1, "y": 0, "label": "(1, 0)"},
                        {"x": 2, "y": 1, "label": "(2, 1)"},
                    ],
                },
            },
            {
                "section_id": 102,
                "section_title": "Иррациональная функция",
                "visual_type": "function_graph",
                "description": "y = √x и решение уравнения √(x+3) = 2",
                "caption": "y = √x: ОДЗ x ≥ 0",
                "priority": "high",
                "params": {
                    "equation": "x**0.5",
                    "x_range": [0, 9],
                    "highlight_points": [
                        {"x": 1, "y": 1, "label": "(1, 1)"},
                        {"x": 4, "y": 2, "label": "(4, 2)"},
                        {"x": 9, "y": 3, "label": "(9, 3)"},
                    ],
                },
            },
            {
                "section_id": 103,
                "section_title": "Дробно-рациональная функция",
                "visual_type": "function_graph",
                "description": "y = (x+1)/(x-3) — гипербола с вертикальной асимптотой x=3",
                "caption": "y = (x+1)/(x-3): асимптота x = 3",
                "priority": "high",
                "params": {
                    "equation": "(x+1)/(x-3)",
                    "x_range": [-5, 10],
                    "highlight_points": [
                        {"x": -1, "y": 0, "label": "корень x = -1"},
                        {"x": 0, "y": -0.333, "label": "(0, -1/3)"},
                    ],
                },
            },
        ],
    },
    {
        "conspect": "task8_curated",
        "title": "Производная и касательная (задание 8)",
        "plans": [
            {
                "section_id": 200,
                "section_title": "Касательная к параболе",
                "visual_type": "tangent_line_graph",
                "description": "f(x) = x² с касательной в точке x = 1: y = 2x - 1",
                "caption": "Касательная к y = x² в точке (1, 1), наклон k = 2",
                "priority": "high",
                "params": {
                    "equation": "x**2",
                    "tangent_point": {"x": 1, "y": 1},
                    "tangent_equation": "2*x - 1",
                    "x_range": [-2, 4],
                },
            },
            {
                "section_id": 201,
                "section_title": "Касательная к кубической функции",
                "visual_type": "tangent_line_graph",
                "description": "f(x) = x³ - 3x с касательной в точке x = 2",
                "caption": "Касательная к y = x³ - 3x в точке (2, 2), k = f'(2) = 9",
                "priority": "high",
                "params": {
                    "equation": "x**3 - 3*x",
                    "tangent_point": {"x": 2, "y": 2},
                    "tangent_equation": "9*x - 16",
                    "x_range": [-3, 4],
                },
            },
        ],
    },
    {
        "conspect": "task12_curated",
        "title": "Исследование функций (задание 12)",
        "plans": [
            {
                "section_id": 300,
                "section_title": "Функция и её производная",
                "visual_type": "derivative_sign_chart",
                "description": "f(x) = x³ - 3x и f'(x) = 3x² - 3: экстремумы в x = ±1",
                "caption": "f(x) = x³ - 3x (синий) и f'(x) = 3x² - 3 (красный пунктир)",
                "priority": "high",
                "params": {
                    "function": "x**3 - 3*x",
                    "derivative": "3*x**2 - 3",
                    "x_range": [-3, 3],
                    "critical_points": [-1, 1],
                    "extrema": [
                        {"x": -1, "type": "макс", "y": 2},
                        {"x": 1, "type": "мин", "y": -2},
                    ],
                },
            },
            {
                "section_id": 301,
                "section_title": "Нахождение наибольшего значения на отрезке",
                "visual_type": "function_graph",
                "description": "f(x) = -x² + 6x - 5 на [1, 4]: максимум в вершине x = 3",
                "caption": "f(x) = -x² + 6x - 5 на [1, 4]: max = f(3) = 4",
                "priority": "high",
                "params": {
                    "equation": "-x**2 + 6*x - 5",
                    "x_range": [0, 5],
                    "highlight_points": [
                        {"x": 1, "y": 0, "label": "f(1) = 0"},
                        {"x": 3, "y": 4, "label": "max: f(3) = 4"},
                        {"x": 4, "y": 3, "label": "f(4) = 3"},
                    ],
                },
            },
            {
                "section_id": 302,
                "section_title": "Квадратичная функция",
                "visual_type": "derivative_sign_chart",
                "description": "f(x) = x² - 4x + 3 и f'(x) = 2x - 4: минимум в x = 2",
                "caption": "f(x) = x² - 4x + 3 и f'(x) = 2x - 4",
                "priority": "high",
                "params": {
                    "function": "x**2 - 4*x + 3",
                    "derivative": "2*x - 4",
                    "x_range": [-1, 5],
                    "critical_points": [2],
                    "extrema": [{"x": 2, "type": "мин", "y": -1}],
                },
            },
        ],
    },
]


def render_curated_graphs():
    """Render curated graph examples and return results."""
    all_results = []

    for group in CURATED_GRAPHS:
        task_name = group["conspect"]
        task_dir = OUTPUT_DIR / task_name
        task_dir.mkdir(parents=True, exist_ok=True)

        graphs = []
        for plan in group["plans"]:
            plan["need_visual"] = True
            params = plan.get("params", {})
            if params.get("equations"):
                scene = convert_multi_equation(plan)
            else:
                scene = convert_plan_to_scene(plan)

            if scene is None:
                continue

            svg = render_graph_svg(scene)
            svg_file = task_dir / f"graph_{plan['section_id']}_{plan['visual_type']}.svg"
            svg_file.write_text(svg, encoding="utf-8")

            graphs.append({
                "section_id": plan["section_id"],
                "section_title": plan.get("section_title", ""),
                "visual_type": plan["visual_type"],
                "caption": plan.get("caption", ""),
                "description": plan.get("description", ""),
                "priority": plan.get("priority", ""),
                "svg_file": str(svg_file),
                "params": params,
            })

        print(f"  {group['title']}: {len(graphs)} графиков")
        all_results.append({
            "conspect": group["title"],
            "plan_result": {"total_sections": 0, "graphs_planned": len(graphs),
                            "total_tokens_in": 0, "total_tokens_out": 0, "total_time_sec": 0,
                            "plans": group["plans"]},
            "graphs": graphs,
        })

    return all_results


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_results = []

    if API_KEY:
        paths = [Path(sys.argv[1])] if len(sys.argv) > 1 else [p for p in CONSPECTS if p.exists()]
        for p in paths:
            result = run_graph_pipeline(p, API_KEY, MODEL)
            all_results.append(result)
    else:
        print("TOGETHER_API_KEY not set — using cached plans only")

    print("\n  Добавление курированных примеров...")
    curated = render_curated_graphs()
    all_results.extend(curated)

    generate_html_report(all_results)

    total = sum(len(r["graphs"]) for r in all_results)
    print(f"\n{'=' * 60}")
    print(f"  ИТОГО: {total} графиков отрендерено")
    print(f"  Результаты: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
