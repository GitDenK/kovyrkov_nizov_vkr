"""
Единый пайплайн: конспект → планировщик визуалов → конвертер → SVG-рендерер.

Использование:
    python pipeline/run_pipeline.py                          # все конспекты
    python pipeline/run_pipeline.py conspects/task4.md       # один конспект
"""

import json
import os
import sys
import time
import html as html_mod
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SVG_SERVICE = ROOT / "svg-generator" / "SVG_generator" / "service"
sys.path.insert(0, str(SVG_SERVICE))

from visual_planner import split_conspect_into_sections, TOGETHER_API_URL
from visual_planner_v2 import VisualPlannerV2
from pipeline.converter import convert_plan_to_scene, SCENE_TYPE_MAP

API_KEY = os.environ.get("TOGETHER_API_KEY", "")
MODEL = "Qwen/Qwen2.5-7B-Instruct-Turbo"
CONSPECTS = [
    ROOT / "conspects" / "task4.md",
    ROOT / "conspects" / "task6.md",
    ROOT / "conspects" / "task8.md",
    ROOT / "conspects" / "task12.md",
]

OUTPUT_DIR = ROOT / "pipeline" / "output"


def render_scene_svg(scene_dict: dict) -> dict:
    """Call SVG generator's render_scene. Returns {svg, warnings}."""
    try:
        from app.orchestrator.orchestrator import render_scene
        result = render_scene(scene_dict)
        return {"svg": result.svg, "warnings": result.warnings}
    except Exception as e:
        return {"svg": None, "warnings": [f"render_scene error: {e}"]}


def render_scene_svg_fallback(scene_dict: dict) -> dict:
    """Lightweight fallback when SVG generator deps are unavailable."""
    scene_type = scene_dict.get("scene_type", "diagram")

    if scene_type == "function_plot":
        return _render_function_plot_fallback(scene_dict)
    elif scene_type == "geometry":
        return _render_geometry_fallback(scene_dict)
    else:
        return _render_diagram_fallback(scene_dict)


def _render_function_plot_fallback(scene: dict) -> dict:
    """Standalone function_plot renderer (no external deps)."""
    import math as m

    c = scene.get("canvas", {})
    w = c.get("width", 400)
    h = c.get("height", 400)
    xmin = c.get("x_min", -5)
    xmax = c.get("x_max", 5)
    ymin = c.get("y_min", -5)
    ymax = c.get("y_max", 5)

    def sx(x):
        return (x - xmin) / (xmax - xmin) * w

    def sy(y):
        return (ymax - y) / (ymax - ymin) * h

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(w)}" height="{int(h)}" overflow="hidden">',
        "  <defs>",
        '    <marker id="arrow_axis" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto">',
        '      <path d="M0,0 L8,4 L0,8 Z" fill="#888"/>',
        "    </marker>",
        "  </defs>",
        f'  <rect width="{int(w)}" height="{int(h)}" fill="white"/>',
    ]

    for xi in range(m.ceil(xmin), m.floor(xmax) + 1):
        lines.append(f'  <line x1="{sx(xi):.1f}" y1="0" x2="{sx(xi):.1f}" y2="{h}" stroke="#e0e0e0" stroke-width="0.5"/>')
    for yi in range(m.ceil(ymin), m.floor(ymax) + 1):
        lines.append(f'  <line x1="0" y1="{sy(yi):.1f}" x2="{w}" y2="{sy(yi):.1f}" stroke="#e0e0e0" stroke-width="0.5"/>')

    if ymin <= 0 <= ymax:
        lines.append(f'  <line x1="0" y1="{sy(0):.1f}" x2="{w}" y2="{sy(0):.1f}" stroke="#888" stroke-width="1" marker-end="url(#arrow_axis)"/>')
    if xmin <= 0 <= xmax:
        lines.append(f'  <line x1="{sx(0):.1f}" y1="{h}" x2="{sx(0):.1f}" y2="0" stroke="#888" stroke-width="1" marker-end="url(#arrow_axis)"/>')

    for xi in range(m.ceil(xmin), m.floor(xmax) + 1):
        if xi == 0:
            continue
        lines.append(f'  <text x="{sx(xi):.1f}" y="{sy(0) + 14:.1f}" text-anchor="middle" font-size="10" fill="#666">{xi}</text>')
    for yi in range(m.ceil(ymin), m.floor(ymax) + 1):
        if yi == 0:
            continue
        lines.append(f'  <text x="{sx(0) - 8:.1f}" y="{sy(yi) + 4:.1f}" text-anchor="end" font-size="10" fill="#666">{yi}</text>')

    colors = ["#2980b9", "#e74c3c", "#27ae60", "#8e44ad"]
    color_idx = 0

    for obj in scene.get("objects", []):
        if obj["type"] == "function_curve":
            expr = obj["expression"]
            oxmin = obj.get("x_min", xmin)
            oxmax = obj.get("x_max", xmax)
            style = obj.get("style", {}) or {}
            stroke = style.get("stroke", colors[color_idx % len(colors)])
            dash = 'stroke-dasharray="6,4"' if style.get("dash") == "dashed" else ""
            color_idx += 1
            pts = []
            for i in range(201):
                xv = oxmin + (oxmax - oxmin) * i / 200
                try:
                    yv = eval(expr, {"__builtins__": {}}, {
                        "x": xv, "pi": m.pi, "e": m.e,
                        "sin": m.sin, "cos": m.cos, "tan": m.tan,
                        "sqrt": m.sqrt, "abs": abs, "log": m.log, "exp": m.exp,
                    })
                    if isinstance(yv, (int, float)) and m.isfinite(yv):
                        pts.append(f"{sx(xv):.1f},{sy(yv):.1f}")
                except Exception:
                    pass
            if pts:
                lines.append(f'  <polyline points="{" ".join(pts)}" fill="none" stroke="{stroke}" stroke-width="2" {dash}/>')

        elif obj["type"] == "point":
            px, py = sx(obj["x"]), sy(obj["y"])
            lines.append(f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#e74c3c" stroke="#333" stroke-width="1"/>')
            if obj.get("label"):
                lines.append(f'  <text x="{px + 8:.1f}" y="{py - 6:.1f}" font-size="11" fill="#333">{html_mod.escape(str(obj["label"]))}</text>')

    for ann in scene.get("annotations", []):
        if ann["type"] == "label":
            anchor_id = ann.get("anchor")
            anchor_obj = next((o for o in scene.get("objects", []) if o.get("id") == anchor_id), None)
            if anchor_obj and "x" in anchor_obj:
                ax = sx(anchor_obj["x"] + ann.get("dx", 0))
                ay = sy(anchor_obj["y"] + ann.get("dy", 0))
                lines.append(f'  <text x="{ax:.1f}" y="{ay:.1f}" font-size="12" fill="#333">{html_mod.escape(ann["text"])}</text>')

    lines.append("</svg>")
    return {"svg": "\n".join(lines), "warnings": []}


def _render_geometry_fallback(scene: dict) -> dict:
    """Standalone geometry renderer."""
    c = scene.get("canvas", {})
    w, h = c.get("width", 400), c.get("height", 400)
    xmin, xmax = c.get("x_min", -1), c.get("x_max", 7)
    ymin, ymax = c.get("y_min", -1), c.get("y_max", 7)

    def sx(x):
        return (x - xmin) / (xmax - xmin) * w

    def sy(y):
        return (ymax - y) / (ymax - ymin) * h

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(w)}" height="{int(h)}">',
        f'  <rect width="{int(w)}" height="{int(h)}" fill="white"/>',
    ]

    pts = {}
    for obj in scene.get("objects", []):
        if obj["type"] == "point":
            pts[obj["id"]] = (obj["x"], obj["y"])
            px, py = sx(obj["x"]), sy(obj["y"])
            lines.append(f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#2980b9"/>')
            if obj.get("label"):
                lines.append(f'  <text x="{px + 8:.1f}" y="{py - 6:.1f}" font-size="12">{html_mod.escape(str(obj["label"]))}</text>')
        elif obj["type"] == "circle":
            center = pts.get(obj.get("center"), (3, 3))
            r = obj.get("radius", 2)
            cx_px, cy_px = sx(center[0]), sy(center[1])
            r_px = r / (xmax - xmin) * w
            fill = (obj.get("style") or {}).get("fill", "rgba(100,150,200,0.15)")
            lines.append(f'  <circle cx="{cx_px:.1f}" cy="{cy_px:.1f}" r="{r_px:.1f}" fill="{fill}" stroke="#333" stroke-width="1.5"/>')

    lines.append("</svg>")
    return {"svg": "\n".join(lines), "warnings": []}


def _render_diagram_fallback(scene: dict) -> dict:
    """Standalone diagram renderer using basic SVG layout."""
    objects = scene.get("objects", [])
    style = scene.get("style", {})

    title_obj = None
    boxes = []
    formula_blocks = []
    arrows = []
    texts = []

    for obj in objects:
        t = obj["type"]
        if t == "title":
            title_obj = obj
        elif t == "box":
            boxes.append(obj)
        elif t == "formula_block":
            formula_blocks.append(obj)
        elif t == "arrow":
            arrows.append(obj)
        elif t == "text":
            texts.append(obj)

    nodes = boxes + formula_blocks
    node_map = {}

    BOX_W = 260
    BOX_H = 52
    GAP_Y = 70
    PADDING = 30
    FONT = 13

    y_cursor = PADDING
    canvas_w = 500

    if title_obj:
        node_map[title_obj["id"]] = {
            "x": canvas_w / 2, "y": y_cursor + 14,
            "w": canvas_w - PADDING * 2, "h": 28
        }
        y_cursor += 40

    adj_out = {}
    adj_in = {}
    for a in arrows:
        fp, tp = a.get("from_point", ""), a.get("to_point", "")
        adj_out.setdefault(fp, []).append(tp)
        adj_in.setdefault(tp, []).append(fp)

    node_ids = [n["id"] for n in nodes]
    layers = []
    placed = set()

    roots = [nid for nid in node_ids if nid not in adj_in or not adj_in[nid]]
    if not roots:
        roots = node_ids[:1] if node_ids else []

    current_layer = roots
    while current_layer:
        layer_nodes = [nid for nid in current_layer if nid not in placed]
        if not layer_nodes:
            break
        layers.append(layer_nodes)
        for nid in layer_nodes:
            placed.add(nid)
        next_layer = []
        for nid in layer_nodes:
            for child in adj_out.get(nid, []):
                if child not in placed and child in set(node_ids):
                    next_layer.append(child)
        current_layer = next_layer

    orphans = [nid for nid in node_ids if nid not in placed]
    if orphans:
        layers.append(orphans)

    max_layer_width = max((len(layer) for layer in layers), default=1)
    canvas_w = max(500, max_layer_width * (BOX_W + 20) + PADDING * 2)

    for layer in layers:
        total_w = len(layer) * BOX_W + (len(layer) - 1) * 20
        x_start = (canvas_w - total_w) / 2 + BOX_W / 2

        for i, nid in enumerate(layer):
            node_obj = next((n for n in nodes if n["id"] == nid), None)
            text = ""
            if node_obj:
                text = node_obj.get("text", node_obj.get("formula", ""))

            est_lines = max(1, len(text) // 30 + text.count("\n"))
            h = max(BOX_H, est_lines * 20 + 24)

            node_map[nid] = {
                "x": x_start + i * (BOX_W + 20),
                "y": y_cursor + h / 2,
                "w": BOX_W,
                "h": h,
                "text": text,
                "obj": node_obj,
            }
        max_h = max((node_map[nid]["h"] for nid in layer), default=BOX_H)
        y_cursor += max_h + GAP_Y

    for t in texts:
        y_cursor += 10
        node_map[t["id"]] = {
            "x": canvas_w / 2, "y": y_cursor + 10,
            "w": canvas_w - PADDING * 2, "h": 24,
            "text": t.get("text", ""), "obj": t,
        }
        y_cursor += 30

    canvas_h = max(300, y_cursor + PADDING)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(canvas_w)}" height="{int(canvas_h)}">',
        "  <defs>",
        '    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">',
        '      <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>',
        "    </marker>",
        "  </defs>",
        f'  <rect width="{int(canvas_w)}" height="{int(canvas_h)}" fill="white"/>',
    ]

    if title_obj:
        info = node_map.get(title_obj["id"])
        if info:
            svg.append(
                f'  <text x="{info["x"]:.0f}" y="{info["y"]:.0f}" '
                f'text-anchor="middle" font-size="{FONT + 4}" font-weight="bold" fill="#333">'
                f'{html_mod.escape(title_obj.get("text", ""))}</text>'
            )

    for a in arrows:
        fp_info = node_map.get(a.get("from_point"))
        tp_info = node_map.get(a.get("to_point"))
        if fp_info and tp_info:
            x1 = fp_info["x"]
            y1 = fp_info["y"] + fp_info["h"] / 2
            x2 = tp_info["x"]
            y2 = tp_info["y"] - tp_info["h"] / 2
            svg.append(
                f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="#333" stroke-width="1.5" marker-end="url(#arrowhead)"/>'
            )
            if a.get("label"):
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                svg.append(f'  <rect x="{mx - 50}" y="{my - 10}" width="100" height="16" fill="white" stroke="none"/>')
                svg.append(
                    f'  <text x="{mx:.1f}" y="{my + 3:.1f}" text-anchor="middle" '
                    f'font-size="{FONT - 2}" fill="#666">{html_mod.escape(a["label"])}</text>'
                )

    for node_obj in nodes:
        info = node_map.get(node_obj["id"])
        if not info:
            continue
        x, y, bw, bh = info["x"], info["y"], info["w"], info["h"]
        rx = x - bw / 2
        ry = y - bh / 2

        obj_style = node_obj.get("style") or {}
        fill = obj_style.get("fill", style.get("fill_color", "#f5f5f5"))
        stroke = obj_style.get("stroke", style.get("stroke_color", "#333"))

        svg.append(
            f'  <rect x="{rx:.1f}" y="{ry:.1f}" width="{bw}" height="{bh:.1f}" '
            f'rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )

        text = info.get("text", "")
        text_lines = text.split("\n")
        line_h = FONT + 4
        ty_start = y - (len(text_lines) * line_h) / 2 + line_h / 2 + 2
        for li, line in enumerate(text_lines):
            if len(line) > 35:
                line = line[:33] + "…"
            svg.append(
                f'  <text x="{x:.1f}" y="{ty_start + li * line_h:.1f}" '
                f'text-anchor="middle" font-size="{FONT}" fill="#333">'
                f'{html_mod.escape(line)}</text>'
            )

    for t in texts:
        info = node_map.get(t["id"])
        if info:
            svg.append(
                f'  <text x="{info["x"]:.1f}" y="{info["y"]:.1f}" '
                f'text-anchor="middle" font-size="{FONT}" fill="#555">'
                f'{html_mod.escape(info.get("text", ""))}</text>'
            )

    svg.append("</svg>")
    return {"svg": "\n".join(svg), "warnings": []}


def try_render(scene_dict: dict) -> dict:
    """Try full SVG generator, fall back to built-in renderer."""
    result = render_scene_svg(scene_dict)
    if result["svg"] is None:
        result = render_scene_svg_fallback(scene_dict)
        if result["svg"]:
            result["warnings"].append("used fallback renderer")
    return result


def run_pipeline(conspect_path: Path, api_key: str, model: str) -> dict:
    """Run full pipeline on one conspect file."""
    print(f"\n{'=' * 60}")
    print(f"Конспект: {conspect_path.name}")
    print(f"{'=' * 60}")

    text = conspect_path.read_text(encoding="utf-8")

    planner = VisualPlannerV2(api_key=api_key, model=model)
    print("  [1/3] Запуск планировщика v2...")
    t0 = time.time()
    plan_result = planner.plan_conspect(text)
    plan_time = time.time() - t0
    print(f"        Секций: {plan_result['total_sections']}, "
          f"визуалов: {plan_result['visuals_planned']}, "
          f"время: {plan_time:.1f}s")

    task_name = conspect_path.stem
    task_dir = OUTPUT_DIR / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    (task_dir / "plan.json").write_text(
        json.dumps(plan_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("  [2/3] Конвертация и рендеринг SVG...")
    svg_results = []
    for entry in plan_result["plans"]:
        plan = entry["plan"]
        if not plan.get("need_visual"):
            continue

        scene = convert_plan_to_scene(plan)
        if scene is None:
            continue

        scene_file = task_dir / f"scene_{plan['section_id']}_{plan['visual_type']}.json"
        scene_file.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")

        render_result = try_render(scene)
        svg = render_result["svg"]
        warnings = render_result["warnings"]

        svg_file = None
        if svg:
            svg_file = task_dir / f"visual_{plan['section_id']}_{plan['visual_type']}.svg"
            svg_file.write_text(svg, encoding="utf-8")

        svg_results.append({
            "section_id": plan["section_id"],
            "section_title": plan.get("section_title", ""),
            "visual_type": plan["visual_type"],
            "scene_type": scene["scene_type"],
            "caption": plan.get("caption", ""),
            "priority": plan.get("priority", ""),
            "svg_file": str(svg_file) if svg_file else None,
            "svg_ok": svg is not None,
            "warnings": warnings,
        })

        status = "OK" if svg else "FAIL"
        warn_str = f" ({len(warnings)} warnings)" if warnings else ""
        print(f"        [{status}] S{plan['section_id']} {plan['visual_type']} → {scene['scene_type']}{warn_str}")

    ok = sum(1 for r in svg_results if r["svg_ok"])
    total = len(svg_results)
    print(f"  [3/3] Результат: {ok}/{total} SVG отрендерены")

    return {
        "conspect": task_name,
        "plan_result": plan_result,
        "svg_results": svg_results,
        "stats": {
            "total_visuals": total,
            "rendered_ok": ok,
            "plan_time_sec": round(plan_time, 2),
        },
    }


def generate_html_preview(all_results: list[dict]):
    """Generate an HTML page showing all rendered SVGs."""
    html_parts = ["""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>Pipeline: Планировщик → SVG-генератор</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 1200px; margin: 0 auto; padding: 20px; background: #f8f9fa; }
  h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
  h2 { color: #2c3e50; margin-top: 40px; }
  .task-card { background: white; border-radius: 12px; padding: 20px;
               margin: 20px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  .stats { display: flex; gap: 20px; flex-wrap: wrap; margin: 10px 0; }
  .stat { background: #ebf5fb; padding: 8px 16px; border-radius: 8px; font-size: 14px; }
  .visual-card { border: 1px solid #dee2e6; border-radius: 8px; margin: 16px 0;
                 overflow: hidden; }
  .visual-header { background: #f1f3f5; padding: 12px 16px; display: flex;
                   justify-content: space-between; align-items: center; }
  .visual-header h4 { margin: 0; font-size: 14px; }
  .badge { padding: 3px 10px; border-radius: 12px; font-size: 11px; color: white; }
  .badge-fp { background: #3498db; }
  .badge-geo { background: #27ae60; }
  .badge-dia { background: #8e44ad; }
  .badge-high { background: #e74c3c; }
  .badge-medium { background: #f39c12; }
  .badge-low { background: #95a5a6; }
  .visual-body { padding: 16px; text-align: center; background: white; }
  .visual-body svg { max-width: 100%; height: auto; }
  .caption { font-style: italic; color: #666; margin-top: 8px; font-size: 13px; }
  .warnings { color: #e67e22; font-size: 12px; margin-top: 4px; }
  .summary-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
  .summary-table th, .summary-table td { border: 1px solid #dee2e6;
    padding: 8px 12px; text-align: left; }
  .summary-table th { background: #f1f3f5; }
</style>
</head>
<body>
<h1>Пайплайн: Планировщик визуалов → SVG-генератор</h1>
<p>Автоматическая генерация визуалов для конспектов ЕГЭ по математике.</p>
"""]

    total_visuals = 0
    total_ok = 0

    for res in all_results:
        task = res["conspect"]
        stats = res["stats"]
        total_visuals += stats["total_visuals"]
        total_ok += stats["rendered_ok"]

        html_parts.append(f"""
<div class="task-card">
<h2>{html_mod.escape(task)}</h2>
<div class="stats">
  <div class="stat">Секций: {res['plan_result']['total_sections']}</div>
  <div class="stat">Визуалов запланировано: {stats['total_visuals']}</div>
  <div class="stat">SVG отрендерено: {stats['rendered_ok']}/{stats['total_visuals']}</div>
  <div class="stat">Время планирования: {stats['plan_time_sec']}s</div>
</div>
""")

        for svgr in res["svg_results"]:
            scene_badge = {"function_plot": "fp", "geometry": "geo", "diagram": "dia"}.get(svgr["scene_type"], "dia")
            pri_badge = svgr.get("priority", "medium")

            html_parts.append(f"""
<div class="visual-card">
  <div class="visual-header">
    <h4>Секция {svgr['section_id']}: {html_mod.escape(svgr.get('section_title', ''))}</h4>
    <div>
      <span class="badge badge-{scene_badge}">{svgr['scene_type']}</span>
      <span class="badge badge-{pri_badge}">{svgr.get('priority', '')}</span>
    </div>
  </div>
  <div class="visual-body">
""")

            svg_file = svgr.get("svg_file")
            if svg_file and os.path.exists(svg_file):
                svg_content = Path(svg_file).read_text(encoding="utf-8")
                html_parts.append(svg_content)
            elif not svgr["svg_ok"]:
                html_parts.append('<p style="color:#e74c3c;">Ошибка рендеринга</p>')

            if svgr.get("caption"):
                html_parts.append(f'<div class="caption">{html_mod.escape(svgr["caption"])}</div>')
            if svgr.get("warnings"):
                html_parts.append(f'<div class="warnings">⚠ {"; ".join(svgr["warnings"])}</div>')

            html_parts.append("</div></div>")

        html_parts.append("</div>")

    html_parts.append(f"""
<h2>Сводка</h2>
<table class="summary-table">
<tr><th>Конспект</th><th>Секций</th><th>Визуалов</th><th>SVG OK</th><th>Время (сек)</th></tr>
""")
    for res in all_results:
        s = res["stats"]
        html_parts.append(
            f"<tr><td>{res['conspect']}</td>"
            f"<td>{res['plan_result']['total_sections']}</td>"
            f"<td>{s['total_visuals']}</td>"
            f"<td>{s['rendered_ok']}/{s['total_visuals']}</td>"
            f"<td>{s['plan_time_sec']}</td></tr>"
        )
    html_parts.append(f"""
<tr style="font-weight:bold;"><td>ИТОГО</td><td>—</td>
<td>{total_visuals}</td><td>{total_ok}/{total_visuals}</td><td>—</td></tr>
</table>

<p style="color:#888; margin-top:40px; font-size:12px;">
  Модель планировщика: {MODEL} | SVG-генератор: svg-generator (3 scene types)
</p>
</body>
</html>""")

    html_path = OUTPUT_DIR / "preview.html"
    html_path.write_text("\n".join(html_parts), encoding="utf-8")
    print(f"\nHTML-превью: {html_path}")
    return html_path


def main():
    api_key = API_KEY
    if not api_key:
        print("ERROR: TOGETHER_API_KEY not set. Set it via environment variable.")
        print("  export TOGETHER_API_KEY='your_key'")
        sys.exit(1)

    if len(sys.argv) > 1:
        paths = [Path(sys.argv[1])]
    else:
        paths = [p for p in CONSPECTS if p.exists()]

    if not paths:
        print("No conspect files found.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_results = []

    for path in paths:
        result = run_pipeline(path, api_key, MODEL)
        all_results.append(result)

    (OUTPUT_DIR / "results.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    generate_html_preview(all_results)

    print(f"\n{'=' * 60}")
    print("ИТОГО:")
    total_v = sum(r["stats"]["total_visuals"] for r in all_results)
    total_ok = sum(r["stats"]["rendered_ok"] for r in all_results)
    print(f"  Визуалов: {total_v}, SVG отрендерено: {total_ok}/{total_v}")
    print(f"  Результаты: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
