"""
Geometry examples: static scenes + step-by-step progressive constructions.

Generates SVGs and an HTML report.
"""

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.geometry_renderer import render_geometry_svg, StepByStepGeo

OUTPUT_DIR = Path(__file__).resolve().parent / "output_geometry"


# ═══════════════════════════════════════════════════════════════
# Static geometry examples
# ═══════════════════════════════════════════════════════════════

STATIC_SCENES = [
    {
        "name": "triangle_altitude",
        "title": "Треугольник с высотой",
        "description": "Треугольник ABC с высотой из вершины C на сторону AB. Используется constraint 'altitude' из кода коллеги.",
        "scene": {
            "scene_type": "geometry",
            "canvas": {"width": 450, "height": 400, "x_min": -1, "x_max": 8, "y_min": -1, "y_max": 7},
            "style": {"theme": "light", "stroke_color": "#333333", "fill_color": "none", "font_size": 13, "font_family": "sans-serif"},
            "objects": [
                {"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 16},
                {"type": "point", "id": "B", "x": 7, "y": 0, "label": "B", "label_dx": 10, "label_dy": 16},
                {"type": "point", "id": "C", "x": 3, "y": 5.5, "label": "C", "label_dx": 0, "label_dy": -12},
                {"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                 "style": {"fill": "rgba(52,152,219,0.06)"}},
            ],
            "constraints": [
                {"type": "altitude", "id": "alt_C", "triangle": "tri", "vertex": "C"},
                {"type": "right_angle_marker", "id": "ram", "vertex": "alt_C_foot", "ray1": "A", "ray2": "C"},
            ],
            "annotations": [
                {"type": "label", "id": "ann_h", "text": "h", "anchor": "C", "dx": 0.3, "dy": -1.5,
                 "color": "#e74c3c", "font_size": 14},
            ],
        },
    },
    {
        "name": "circumscribed_circle",
        "title": "Описанная окружность треугольника",
        "description": "Треугольник с описанной окружностью, проходящей через все три вершины.",
        "scene": {
            "scene_type": "geometry",
            "canvas": {"width": 450, "height": 450, "x_min": -2, "x_max": 9, "y_min": -2, "y_max": 8},
            "style": {"theme": "light", "stroke_color": "#333333", "fill_color": "none", "font_size": 13, "font_family": "sans-serif"},
            "objects": [
                {"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 16},
                {"type": "point", "id": "B", "x": 7, "y": 0, "label": "B", "label_dx": 12, "label_dy": 16},
                {"type": "point", "id": "C", "x": 2, "y": 6, "label": "C", "label_dx": -6, "label_dy": -12},
                {"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                 "style": {"fill": "rgba(52,152,219,0.06)"}},
            ],
            "constraints": [
                {"type": "circumscribed_circle", "id": "cc", "triangle": "tri"},
            ],
            "annotations": [
                {"type": "label", "id": "ann_r", "text": "R", "anchor": "cc_center", "dx": 0.3, "dy": 0.3,
                 "color": "#2980b9"},
            ],
        },
    },
    {
        "name": "right_triangle_pythagorean",
        "title": "Прямоугольный треугольник — теорема Пифагора",
        "description": "Прямоугольный треугольник с маркером прямого угла и подписями сторон a, b, c.",
        "scene": {
            "scene_type": "geometry",
            "canvas": {"width": 450, "height": 400, "x_min": -1, "x_max": 7, "y_min": -1.5, "y_max": 5.5},
            "style": {"theme": "light", "stroke_color": "#333333", "fill_color": "none", "font_size": 13, "font_family": "sans-serif"},
            "objects": [
                {"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 14},
                {"type": "point", "id": "B", "x": 5, "y": 0, "label": "B", "label_dx": 12, "label_dy": 14},
                {"type": "point", "id": "C", "x": 0, "y": 4, "label": "C", "label_dx": -14, "label_dy": -8},
                {"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                 "style": {"fill": "rgba(155,89,182,0.06)"}},
                {"type": "segment", "id": "seg_ab", "from_point": "A", "to_point": "B"},
                {"type": "segment", "id": "seg_ac", "from_point": "A", "to_point": "C"},
                {"type": "segment", "id": "seg_bc", "from_point": "B", "to_point": "C"},
            ],
            "constraints": [
                {"type": "right_angle_marker", "id": "ram_A", "vertex": "A", "ray1": "B", "ray2": "C"},
            ],
            "annotations": [
                {"type": "label", "id": "ann_a", "text": "a = 5", "anchor": "A", "dx": 1.2, "dy": -0.3,
                 "color": "#333"},
                {"type": "label", "id": "ann_b", "text": "b = 4", "anchor": "A", "dx": -0.6, "dy": 1.0,
                 "color": "#333"},
                {"type": "label", "id": "ann_c", "text": "c = √41", "anchor": "B", "dx": -0.8, "dy": 1.2,
                 "color": "#e74c3c"},
            ],
        },
    },
    {
        "name": "medians_triangle",
        "title": "Медианы треугольника",
        "description": "Все три медианы пересекаются в одной точке (центроид). Constraints: median×3.",
        "scene": {
            "scene_type": "geometry",
            "canvas": {"width": 450, "height": 420, "x_min": -1, "x_max": 9, "y_min": -1, "y_max": 8},
            "style": {"theme": "light", "stroke_color": "#333333", "fill_color": "none", "font_size": 13, "font_family": "sans-serif"},
            "objects": [
                {"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 14},
                {"type": "point", "id": "B", "x": 8, "y": 0, "label": "B", "label_dx": 12, "label_dy": 14},
                {"type": "point", "id": "C", "x": 3, "y": 7, "label": "C", "label_dx": 0, "label_dy": -12},
                {"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                 "style": {"fill": "rgba(46,204,113,0.06)"}},
            ],
            "constraints": [
                {"type": "median", "id": "med_A", "triangle": "tri", "vertex": "A"},
                {"type": "median", "id": "med_B", "triangle": "tri", "vertex": "B"},
                {"type": "median", "id": "med_C", "triangle": "tri", "vertex": "C"},
            ],
            "annotations": [],
        },
    },
    {
        "name": "inscribed_circle",
        "title": "Вписанная окружность",
        "description": "Окружность, вписанная в треугольник — касается всех трёх сторон.",
        "scene": {
            "scene_type": "geometry",
            "canvas": {"width": 450, "height": 420, "x_min": -1, "x_max": 9, "y_min": -1, "y_max": 7},
            "style": {"theme": "light", "stroke_color": "#333333", "fill_color": "none", "font_size": 13, "font_family": "sans-serif"},
            "objects": [
                {"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 14},
                {"type": "point", "id": "B", "x": 8, "y": 0, "label": "B", "label_dx": 12, "label_dy": 14},
                {"type": "point", "id": "C", "x": 3, "y": 6, "label": "C", "label_dx": 0, "label_dy": -12},
                {"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                 "style": {"fill": "rgba(230,126,34,0.06)"}},
            ],
            "constraints": [
                {"type": "inscribed_circle", "id": "ic", "triangle": "tri"},
            ],
            "annotations": [
                {"type": "label", "id": "ann_r", "text": "r", "anchor": "ic_center", "dx": 0.3, "dy": 0.3,
                 "color": "#e67e22"},
            ],
        },
    },
]


# ═══════════════════════════════════════════════════════════════
# Step-by-step: finding area of triangle via altitude
# ═══════════════════════════════════════════════════════════════

def build_stepbystep_altitude():
    canvas = {"width": 480, "height": 420, "x_min": -1, "x_max": 9, "y_min": -1.5, "y_max": 7}

    geo = StepByStepGeo(canvas)

    # Step 1: draw triangle
    geo.add_object({"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 16})
    geo.add_object({"type": "point", "id": "B", "x": 7, "y": 0, "label": "B", "label_dx": 12, "label_dy": 16})
    geo.add_object({"type": "point", "id": "C", "x": 3, "y": 5.5, "label": "C", "label_dx": 0, "label_dy": -12})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(52,152,219,0.06)"}})
    geo.snapshot(
        "Шаг 1: Строим треугольник ABC",
        "Дано: треугольник ABC с вершинами A(0,0), B(7,0), C(3,5.5)"
    )

    # Step 2: mark the base
    geo.add_annotation({"type": "label", "id": "ann_base", "text": "основание a = AB",
                        "anchor": "A", "dx": 1.6, "dy": -0.35, "color": "#2980b9"})
    geo.snapshot(
        "Шаг 2: Определяем основание",
        "Выбираем AB как основание: a = AB = 7"
    )

    # Step 3: draw altitude
    geo.add_constraint({"type": "altitude", "id": "alt_C", "triangle": "tri", "vertex": "C"})
    geo.snapshot(
        "Шаг 3: Проводим высоту из C",
        "Опускаем перпендикуляр из C на прямую AB — это высота h"
    )

    # Step 4: mark right angle
    geo.add_constraint({"type": "right_angle_marker", "id": "ram_H", "vertex": "alt_C_foot", "ray1": "A", "ray2": "C"})
    geo.add_annotation({"type": "label", "id": "ann_H", "text": "H", "anchor": "alt_C_foot",
                        "dx": 0.15, "dy": -0.3, "color": "#e74c3c"})
    geo.add_annotation({"type": "label", "id": "ann_h", "text": "h = CH = 5.5",
                        "anchor": "C", "dx": 0.5, "dy": -1.4, "color": "#e74c3c"})
    geo.snapshot(
        "Шаг 4: Отмечаем прямой угол в H",
        "H — основание высоты. CH ⊥ AB. Высота h = CH = 5.5"
    )

    # Step 5: formula
    geo.add_annotation({"type": "label", "id": "ann_formula", "text": "S = ½ · a · h = ½ · 7 · 5.5 = 19.25",
                        "anchor": "A", "dx": 1.5, "dy": -0.8, "color": "#8e44ad", "font_size": 14})
    geo.snapshot(
        "Шаг 5: Вычисляем площадь",
        "S = ½ · AB · CH = ½ · 7 · 5.5 = 19.25"
    )

    return {
        "name": "stepbystep_altitude",
        "title": "Пошаговое построение: площадь треугольника через высоту",
        "steps": geo.get_steps(),
    }


# ═══════════════════════════════════════════════════════════════
# Step-by-step: circumscribed circle construction
# ═══════════════════════════════════════════════════════════════

def build_stepbystep_circumscribed():
    canvas = {"width": 480, "height": 460, "x_min": -2, "x_max": 10, "y_min": -2, "y_max": 9}

    geo = StepByStepGeo(canvas)

    # Step 1: triangle
    geo.add_object({"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 14})
    geo.add_object({"type": "point", "id": "B", "x": 8, "y": 0, "label": "B", "label_dx": 12, "label_dy": 14})
    geo.add_object({"type": "point", "id": "C", "x": 3, "y": 7, "label": "C", "label_dx": 0, "label_dy": -12})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(52,152,219,0.06)"}})
    geo.snapshot("Шаг 1: Треугольник ABC", "Дано: треугольник ABC")

    # Step 2: midpoints of sides
    geo.add_object({"type": "segment", "id": "seg_AB", "from_point": "A", "to_point": "B"})
    geo.add_object({"type": "segment", "id": "seg_BC", "from_point": "B", "to_point": "C"})
    geo.add_constraint({"type": "midpoint", "id": "mid_AB", "segment": "seg_AB", "result_id": "M1"})
    geo.add_constraint({"type": "midpoint", "id": "mid_BC", "segment": "seg_BC", "result_id": "M2"})
    geo.add_annotation({"type": "label", "id": "ann_M1", "text": "M₁", "anchor": "M1", "dx": 0, "dy": -0.35})
    geo.add_annotation({"type": "label", "id": "ann_M2", "text": "M₂", "anchor": "M2", "dx": 0.35, "dy": 0})
    geo.snapshot(
        "Шаг 2: Находим середины сторон",
        "M₁ — середина AB, M₂ — середина BC"
    )

    # Step 3: perpendicular bisectors (shown as dashed lines through midpoints)
    # Approximate perpendicular bisector segments
    geo.add_object({"type": "point", "id": "perp1_end", "x": 4, "y": 7.5, "style": {"visible": False}})
    geo.add_object({"type": "segment", "id": "perp1", "from_point": "M1", "to_point": "perp1_end",
                     "style": {"dash": "dashed", "stroke": "#27ae60"}})
    geo.add_object({"type": "point", "id": "perp2_end", "x": 1, "y": 1, "style": {"visible": False}})
    geo.add_object({"type": "segment", "id": "perp2", "from_point": "M2", "to_point": "perp2_end",
                     "style": {"dash": "dashed", "stroke": "#27ae60"}})
    geo.snapshot(
        "Шаг 3: Серединные перпендикуляры",
        "Проводим перпендикуляры к AB через M₁ и к BC через M₂"
    )

    # Step 4: circumscribed circle
    geo.add_constraint({"type": "circumscribed_circle", "id": "cc", "triangle": "tri"})
    geo.add_annotation({"type": "label", "id": "ann_O", "text": "O — центр", "anchor": "cc_center",
                        "dx": 0.5, "dy": 0.4, "color": "#2980b9"})
    geo.snapshot(
        "Шаг 4: Описанная окружность",
        "Серединные перпендикуляры пересекаются в точке O — центре описанной окружности. OA = OB = OC = R"
    )

    # Step 5: annotate
    geo.add_annotation({"type": "label", "id": "ann_R", "text": "R — радиус описанной окружности",
                        "anchor": "cc_center", "dx": 0.5, "dy": -0.5, "color": "#8e44ad", "font_size": 12})
    geo.snapshot(
        "Шаг 5: Результат",
        "Окружность проходит через все три вершины. Все точки на окружности равноудалены от центра O на расстояние R."
    )

    return {
        "name": "stepbystep_circumscribed",
        "title": "Пошаговое построение: описанная окружность",
        "steps": geo.get_steps(),
    }


# ═══════════════════════════════════════════════════════════════
# Step-by-step: inscribed circle + bisectors
# ═══════════════════════════════════════════════════════════════

def build_stepbystep_inscribed():
    canvas = {"width": 480, "height": 420, "x_min": -1, "x_max": 10, "y_min": -1.5, "y_max": 8}

    geo = StepByStepGeo(canvas)

    geo.add_object({"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 14})
    geo.add_object({"type": "point", "id": "B", "x": 9, "y": 0, "label": "B", "label_dx": 12, "label_dy": 14})
    geo.add_object({"type": "point", "id": "C", "x": 4, "y": 7, "label": "C", "label_dx": 0, "label_dy": -12})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(230,126,34,0.06)"}})
    geo.snapshot("Шаг 1: Треугольник ABC", "Дано: треугольник ABC")

    # Step 2: bisector from A
    geo.add_constraint({"type": "bisector", "id": "bis_A", "triangle": "tri", "vertex": "A"})
    geo.add_annotation({"type": "label", "id": "ann_bisA", "text": "биссектриса из A",
                        "anchor": "A", "dx": 2.0, "dy": 1.2, "color": "#27ae60", "font_size": 11})
    geo.snapshot(
        "Шаг 2: Биссектриса из вершины A",
        "Биссектриса делит угол A пополам и пересекает сторону BC"
    )

    # Step 3: bisector from B
    geo.add_constraint({"type": "bisector", "id": "bis_B", "triangle": "tri", "vertex": "B"})
    geo.snapshot(
        "Шаг 3: Биссектриса из вершины B",
        "Две биссектрисы пересекаются в точке I — центре вписанной окружности"
    )

    # Step 4: bisector from C
    geo.add_constraint({"type": "bisector", "id": "bis_C", "triangle": "tri", "vertex": "C"})
    geo.snapshot(
        "Шаг 4: Все три биссектрисы",
        "Все три биссектрисы проходят через одну точку I (инцентр)"
    )

    # Step 5: inscribed circle
    geo.add_constraint({"type": "inscribed_circle", "id": "ic", "triangle": "tri"})
    geo.add_annotation({"type": "label", "id": "ann_I", "text": "I",
                        "anchor": "ic_center", "dx": 0.3, "dy": 0.3, "color": "#e67e22"})
    geo.add_annotation({"type": "label", "id": "ann_r", "text": "r — радиус вписанной",
                        "anchor": "ic_center", "dx": 0.8, "dy": -0.4, "color": "#e67e22", "font_size": 12})
    geo.snapshot(
        "Шаг 5: Вписанная окружность",
        "Окружность с центром I и радиусом r касается всех трёх сторон треугольника"
    )

    return {
        "name": "stepbystep_inscribed",
        "title": "Пошаговое построение: вписанная окружность через биссектрисы",
        "steps": geo.get_steps(),
    }


# ═══════════════════════════════════════════════════════════════
# HTML report
# ═══════════════════════════════════════════════════════════════

def generate_html_report(static_results, stepbystep_results):
    import html as html_mod

    total_static = len(static_results)
    total_steps = sum(len(s["steps"]) for s in stepbystep_results)

    html = [f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>Геометрия: статические примеры и пошаговое построение</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f0f2f5; color: #1a1a2e; }}
  .header {{ background: linear-gradient(135deg, #0f3460 0%, #16213e 50%, #1a1a2e 100%);
             padding: 40px 20px; text-align: center; color: white; }}
  .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
  .header p {{ opacity: 0.8; font-size: 15px; }}
  .stats-bar {{ display: flex; justify-content: center; gap: 30px; margin-top: 20px; }}
  .stat {{ background: rgba(255,255,255,0.15); padding: 10px 24px; border-radius: 8px; text-align: center; }}
  .stat-val {{ font-size: 24px; font-weight: bold; }}
  .stat-label {{ font-size: 11px; opacity: 0.7; text-transform: uppercase; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 30px 20px; }}
  h2 {{ font-size: 22px; color: #1a1a2e; margin: 40px 0 16px; padding-bottom: 8px;
        border-bottom: 2px solid #0f3460; }}
  h3 {{ font-size: 18px; color: #2c3e50; margin: 24px 0 12px; }}
  .card {{ background: white; border-radius: 12px; margin-bottom: 24px;
           box-shadow: 0 2px 12px rgba(0,0,0,0.08); overflow: hidden; }}
  .card-header {{ padding: 16px 20px; border-bottom: 1px solid #f0f0f0; }}
  .card-header h4 {{ font-size: 15px; color: #333; margin-bottom: 4px; }}
  .card-header .desc {{ font-size: 13px; color: #666; }}
  .card-body {{ padding: 20px; text-align: center; background: #fafbfc; }}
  .card-body svg {{ max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 8px; }}
  .step-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }}
  .step-card {{ background: white; border-radius: 10px; overflow: hidden;
                box-shadow: 0 1px 8px rgba(0,0,0,0.06); }}
  .step-num {{ display: inline-block; background: #0f3460; color: white;
               width: 28px; height: 28px; line-height: 28px; border-radius: 50%;
               text-align: center; font-size: 13px; font-weight: bold; margin-right: 8px; }}
  .step-title {{ font-size: 14px; font-weight: 600; color: #2c3e50; }}
  .step-desc {{ font-size: 12px; color: #666; margin-top: 4px; }}
  .step-header {{ padding: 12px 16px; border-bottom: 1px solid #f0f0f0; }}
  .step-body {{ padding: 12px; text-align: center; background: #fafbfc; }}
  .step-body svg {{ max-width: 100%; height: auto; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 10px;
            font-size: 11px; color: white; margin-right: 6px; }}
  .badge-static {{ background: #2980b9; }}
  .badge-step {{ background: #e67e22; }}
</style>
</head>
<body>
<div class="header">
  <h1>Генерация геометрии для конспектов ЕГЭ</h1>
  <p>На базе SVG-генератора коллеги: solver (constraints) → geometry renderer</p>
  <div class="stats-bar">
    <div class="stat"><div class="stat-val">{total_static}</div><div class="stat-label">статических</div></div>
    <div class="stat"><div class="stat-val">{len(stepbystep_results)}</div><div class="stat-label">пошаговых</div></div>
    <div class="stat"><div class="stat-val">{total_steps}</div><div class="stat-label">шагов</div></div>
  </div>
</div>
<div class="container">

<h2>Статические геометрические построения</h2>
<p style="color:#666; margin-bottom:20px;">
  Каждая фигура описывается как Scene JSON (формат коллеги): точки, отрезки, треугольники,
  окружности + constraints (altitude, median, bisector, circumscribed/inscribed circle).
</p>
"""]

    for r in static_results:
        html.append(f"""
<div class="card">
  <div class="card-header">
    <span class="badge badge-static">geometry</span>
    <h4>{html_mod.escape(r['title'])}</h4>
    <div class="desc">{html_mod.escape(r['description'])}</div>
  </div>
  <div class="card-body">{r['svg']}</div>
</div>
""")

    html.append("""
<h2>Пошаговое построение геометрии</h2>
<p style="color:#666; margin-bottom:20px;">
  Постепенная дорисовка элементов: каждый шаг добавляет новые объекты к предыдущей фигуре.
  Подходит для конспектов, где нужно объяснять построение последовательно.
</p>
""")

    for sbs in stepbystep_results:
        html.append(f'<h3>{html_mod.escape(sbs["title"])}</h3>')
        html.append('<div class="step-grid">')
        for i, step in enumerate(sbs["steps"]):
            html.append(f"""
<div class="step-card">
  <div class="step-header">
    <span class="step-num">{i+1}</span>
    <span class="step-title">{html_mod.escape(step['title'])}</span>
    <div class="step-desc">{html_mod.escape(step.get('description', ''))}</div>
  </div>
  <div class="step-body">{step['svg']}</div>
</div>
""")
        html.append('</div>')

    html.append("""
</div>
</body>
</html>""")

    out_path = OUTPUT_DIR / "geometry_report.html"
    out_path.write_text("\n".join(html), encoding="utf-8")
    return out_path


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Static examples
    print("Статические примеры...")
    static_results = []
    for scene_def in STATIC_SCENES:
        svg = render_geometry_svg(scene_def["scene"])
        svg_path = OUTPUT_DIR / f"{scene_def['name']}.svg"
        svg_path.write_text(svg, encoding="utf-8")
        print(f"  [OK] {scene_def['name']}: {len(svg)} chars")
        static_results.append({
            "name": scene_def["name"],
            "title": scene_def["title"],
            "description": scene_def["description"],
            "svg": svg,
        })

    # Step-by-step
    print("\nПошаговые построения...")
    stepbystep_results = []
    for builder in [build_stepbystep_altitude, build_stepbystep_circumscribed, build_stepbystep_inscribed]:
        result = builder()
        for i, step in enumerate(result["steps"]):
            svg_path = OUTPUT_DIR / f"{result['name']}_step{i+1}.svg"
            svg_path.write_text(step["svg"], encoding="utf-8")
        print(f"  [OK] {result['name']}: {len(result['steps'])} шагов")
        stepbystep_results.append(result)

    # Report
    report_path = generate_html_report(static_results, stepbystep_results)
    print(f"\nОтчёт: {report_path}")


if __name__ == "__main__":
    main()
