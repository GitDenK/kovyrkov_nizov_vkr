"""
Backend report: geometry conspect → planner → Scene JSON → step-by-step SVG.

Shows the full pipeline for a geometry conspect, including:
  - The conspect text
  - What the planner outputs (visual plan)
  - The Scene JSON generated
  - Step-by-step progressive SVG rendering
"""

import json
import math
import os
import sys
import html as html_mod
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.geometry_renderer import render_geometry_svg, StepByStepGeo, solve_constraints

OUTPUT_DIR = ROOT / "pipeline" / "output_geometry"


# ═══════════════════════════════════════════════════════════════
# Sample geometry conspect (realistic EGE task 16 style)
# ═══════════════════════════════════════════════════════════════

CONSPECT_SECTIONS = [
    {
        "id": 1,
        "title": "Что проверяет задание",
        "text": """Задание проверяет умение решать планиметрические задачи.
Нужно уметь:
- находить элементы треугольника (высоты, медианы, биссектрисы)
- работать с вписанными и описанными окружностями
- применять теорему Пифагора, теоремы синусов и косинусов
- доказывать геометрические факты""",
        "visual_plan": None,
    },
    {
        "id": 2,
        "title": "Высота треугольника",
        "text": """**Высота** — перпендикуляр, опущенный из вершины на противоположную сторону (или её продолжение).

Свойства:
- Три высоты пересекаются в одной точке (ортоцентр)
- Основание высоты — проекция вершины на сторону
- Площадь треугольника: S = ½ · a · h_a

**Пример**: В треугольнике ABC: A(0,0), B(7,0), C(3,5.5).
Найти высоту из C на AB и площадь треугольника.""",
        "visual_plan": {
            "need_visual": True,
            "visual_type": "geometry_stepbystep",
            "description": "Пошаговое построение высоты и вычисление площади",
            "params": {
                "construction": "altitude",
                "vertices": {"A": [0, 0], "B": [7, 0], "C": [3, 5.5]},
                "target_vertex": "C",
            },
            "caption": "Высота треугольника: построение и площадь",
            "priority": "high",
        },
        "steps_builder": "altitude",
    },
    {
        "id": 3,
        "title": "Медианы и центроид",
        "text": """**Медиана** — отрезок, соединяющий вершину с серединой противоположной стороны.

Свойства:
- Три медианы пересекаются в одной точке — **центроиде** (центре масс)
- Центроид делит каждую медиану в отношении 2:1 от вершины
- Медиана делит треугольник на два равновеликих

**Пример**: Построить все три медианы треугольника ABC:
A(0,0), B(8,0), C(3,7).""",
        "visual_plan": {
            "need_visual": True,
            "visual_type": "geometry_stepbystep",
            "description": "Пошаговое построение медиан и нахождение центроида",
            "params": {
                "construction": "medians",
                "vertices": {"A": [0, 0], "B": [8, 0], "C": [3, 7]},
            },
            "caption": "Три медианы пересекаются в центроиде",
            "priority": "high",
        },
        "steps_builder": "medians",
    },
    {
        "id": 4,
        "title": "Описанная окружность",
        "text": """**Описанная окружность** — проходит через все три вершины треугольника.

Как построить:
1. Найти середины двух сторон
2. Провести серединные перпендикуляры
3. Их пересечение — центр описанной окружности (O)
4. R = OA = OB = OC

Формула: R = abc / (4S), где a, b, c — стороны, S — площадь.

**Пример**: Построить описанную окружность треугольника ABC:
A(0,0), B(8,0), C(3,7).""",
        "visual_plan": {
            "need_visual": True,
            "visual_type": "geometry_stepbystep",
            "description": "Пошаговое построение описанной окружности",
            "params": {
                "construction": "circumscribed",
                "vertices": {"A": [0, 0], "B": [8, 0], "C": [3, 7]},
            },
            "caption": "Описанная окружность через серединные перпендикуляры",
            "priority": "high",
        },
        "steps_builder": "circumscribed",
    },
    {
        "id": 5,
        "title": "Вписанная окружность",
        "text": """**Вписанная окружность** — касается всех трёх сторон треугольника изнутри.

Как построить:
1. Провести биссектрисы углов
2. Их пересечение — центр вписанной окружности (I — инцентр)
3. Радиус = расстояние от I до любой стороны

Формула: r = S / p, где p — полупериметр.

**Пример**: Построить вписанную окружность треугольника ABC:
A(0,0), B(9,0), C(4,7).""",
        "visual_plan": {
            "need_visual": True,
            "visual_type": "geometry_stepbystep",
            "description": "Пошаговое построение вписанной окружности через биссектрисы",
            "params": {
                "construction": "inscribed",
                "vertices": {"A": [0, 0], "B": [9, 0], "C": [4, 7]},
            },
            "caption": "Вписанная окружность через биссектрисы",
            "priority": "high",
        },
        "steps_builder": "inscribed",
    },
    {
        "id": 6,
        "title": "Теорема Пифагора",
        "text": """В прямоугольном треугольнике квадрат гипотенузы равен сумме квадратов катетов:
c² = a² + b²

Применение:
- Нахождение третьей стороны по двум известным
- Проверка, является ли треугольник прямоугольным (обратная теорема)

**Пример**: Прямоугольный треугольник с катетами a=5, b=4.
Найти гипотенузу c.""",
        "visual_plan": {
            "need_visual": True,
            "visual_type": "geometry_static",
            "description": "Прямоугольный треугольник с подписями сторон",
            "params": {
                "construction": "pythagorean",
                "vertices": {"A": [0, 0], "B": [5, 0], "C": [0, 4]},
            },
            "caption": "Теорема Пифагора: c² = a² + b²",
            "priority": "high",
        },
        "steps_builder": "pythagorean",
    },
]


# ═══════════════════════════════════════════════════════════════
# Step-by-step builders for each construction type
# ═══════════════════════════════════════════════════════════════

def build_altitude_steps(vertices):
    A, B, C = vertices["A"], vertices["B"], vertices["C"]
    canvas = {"width": 480, "height": 400, "x_min": -1, "x_max": max(A[0],B[0],C[0])+2,
              "y_min": -1.5, "y_max": max(A[1],B[1],C[1])+1.5}
    geo = StepByStepGeo(canvas)

    geo.add_object({"type": "point", "id": "A", "x": A[0], "y": A[1], "label": "A", "label_dx": -14, "label_dy": 16})
    geo.add_object({"type": "point", "id": "B", "x": B[0], "y": B[1], "label": "B", "label_dx": 12, "label_dy": 16})
    geo.add_object({"type": "point", "id": "C", "x": C[0], "y": C[1], "label": "C", "label_dx": 0, "label_dy": -12})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(52,152,219,0.06)"}})
    geo.snapshot("Строим треугольник ABC", "Дано: треугольник с вершинами A, B, C")

    geo.add_annotation({"type": "label", "id": "ann_base", "text": f"a = AB = {B[0]-A[0]}",
                        "anchor": "A", "dx": 1.5, "dy": -0.35, "color": "#2980b9"})
    geo.snapshot("Определяем основание", f"Выбираем AB как основание: a = {B[0]-A[0]}")

    geo.add_constraint({"type": "altitude", "id": "alt_C", "triangle": "tri", "vertex": "C"})
    geo.snapshot("Проводим высоту CH", "Опускаем перпендикуляр из C на прямую AB")

    geo.add_constraint({"type": "right_angle_marker", "id": "ram_H", "vertex": "alt_C_foot", "ray1": "A", "ray2": "C"})
    geo.add_annotation({"type": "label", "id": "ann_H", "text": "H", "anchor": "alt_C_foot",
                        "dx": 0.15, "dy": -0.3, "color": "#e74c3c"})
    geo.add_annotation({"type": "label", "id": "ann_h", "text": f"h = {C[1]}",
                        "anchor": "C", "dx": 0.4, "dy": -1.2, "color": "#e74c3c"})
    geo.snapshot("Отмечаем прямой угол и высоту", f"CH ⊥ AB, высота h = {C[1]}")

    area = 0.5 * (B[0] - A[0]) * C[1]
    geo.add_annotation({"type": "label", "id": "ann_S", "text": f"S = ½·{B[0]-A[0]}·{C[1]} = {area}",
                        "anchor": "A", "dx": 1.5, "dy": -0.85, "color": "#8e44ad", "font_size": 14})
    geo.snapshot("Вычисляем площадь", f"S = ½ · a · h = {area}")

    return geo.get_steps()


def build_medians_steps(vertices):
    A, B, C = vertices["A"], vertices["B"], vertices["C"]
    canvas = {"width": 480, "height": 420, "x_min": -1, "x_max": max(A[0],B[0],C[0])+2,
              "y_min": -1, "y_max": max(A[1],B[1],C[1])+1.5}
    geo = StepByStepGeo(canvas)

    geo.add_object({"type": "point", "id": "A", "x": A[0], "y": A[1], "label": "A", "label_dx": -14, "label_dy": 14})
    geo.add_object({"type": "point", "id": "B", "x": B[0], "y": B[1], "label": "B", "label_dx": 12, "label_dy": 14})
    geo.add_object({"type": "point", "id": "C", "x": C[0], "y": C[1], "label": "C", "label_dx": 0, "label_dy": -12})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(46,204,113,0.06)"}})
    geo.snapshot("Треугольник ABC", "Дано: треугольник ABC")

    geo.add_constraint({"type": "median", "id": "med_A", "triangle": "tri", "vertex": "A"})
    m_bc = ((B[0]+C[0])/2, (B[1]+C[1])/2)
    geo.add_annotation({"type": "label", "id": "ann_mA", "text": "M₁", "anchor": "med_A_mid",
                        "dx": 0.3, "dy": 0.3, "color": "#27ae60"})
    geo.snapshot("Медиана из A", f"M₁ — середина BC = ({m_bc[0]:.0f}, {m_bc[1]:.1f})")

    geo.add_constraint({"type": "median", "id": "med_B", "triangle": "tri", "vertex": "B"})
    m_ac = ((A[0]+C[0])/2, (A[1]+C[1])/2)
    geo.add_annotation({"type": "label", "id": "ann_mB", "text": "M₂", "anchor": "med_B_mid",
                        "dx": -0.4, "dy": 0.2, "color": "#27ae60"})
    geo.snapshot("Медиана из B", f"M₂ — середина AC = ({m_ac[0]:.1f}, {m_ac[1]:.1f})")

    geo.add_constraint({"type": "median", "id": "med_C", "triangle": "tri", "vertex": "C"})
    m_ab = ((A[0]+B[0])/2, (A[1]+B[1])/2)
    geo.add_annotation({"type": "label", "id": "ann_mC", "text": "M₃", "anchor": "med_C_mid",
                        "dx": 0, "dy": 0.35, "color": "#27ae60"})
    geo.snapshot("Медиана из C", f"M₃ — середина AB = ({m_ab[0]:.0f}, {m_ab[1]:.0f})")

    gx = (A[0]+B[0]+C[0])/3
    gy = (A[1]+B[1]+C[1])/3
    geo.add_object({"type": "point", "id": "G", "x": gx, "y": gy, "label": "G",
                     "style": {"fill": "#e74c3c", "stroke": "#e74c3c"}, "label_dx": 10, "label_dy": -6})
    geo.add_annotation({"type": "label", "id": "ann_G", "text": f"G({gx:.1f}, {gy:.1f}) — центроид",
                        "anchor": "G", "dx": 0.8, "dy": -0.4, "color": "#e74c3c", "font_size": 12})
    geo.snapshot("Центроид", f"Все медианы пересекаются в G({gx:.1f}, {gy:.1f})")

    return geo.get_steps()


def build_circumscribed_steps(vertices):
    A, B, C = vertices["A"], vertices["B"], vertices["C"]
    xmax = max(A[0],B[0],C[0]) + 2
    ymax = max(A[1],B[1],C[1]) + 2
    canvas = {"width": 480, "height": 460, "x_min": -2, "x_max": xmax,
              "y_min": -2, "y_max": ymax}
    geo = StepByStepGeo(canvas)

    geo.add_object({"type": "point", "id": "A", "x": A[0], "y": A[1], "label": "A", "label_dx": -14, "label_dy": 14})
    geo.add_object({"type": "point", "id": "B", "x": B[0], "y": B[1], "label": "B", "label_dx": 12, "label_dy": 14})
    geo.add_object({"type": "point", "id": "C", "x": C[0], "y": C[1], "label": "C", "label_dx": 0, "label_dy": -12})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(52,152,219,0.06)"}})
    geo.snapshot("Треугольник ABC", "Дано: треугольник ABC")

    geo.add_object({"type": "segment", "id": "seg_AB", "from_point": "A", "to_point": "B"})
    geo.add_object({"type": "segment", "id": "seg_BC", "from_point": "B", "to_point": "C"})
    geo.add_constraint({"type": "midpoint", "id": "mid_AB", "segment": "seg_AB", "result_id": "M1"})
    geo.add_constraint({"type": "midpoint", "id": "mid_BC", "segment": "seg_BC", "result_id": "M2"})
    geo.add_annotation({"type": "label", "id": "ann_M1", "text": "M₁", "anchor": "M1", "dx": 0, "dy": -0.35})
    geo.add_annotation({"type": "label", "id": "ann_M2", "text": "M₂", "anchor": "M2", "dx": 0.35, "dy": 0})
    geo.snapshot("Середины сторон", "M₁ — середина AB, M₂ — середина BC")

    # Approximate perpendicular bisectors
    m1 = ((A[0]+B[0])/2, (A[1]+B[1])/2)
    m2 = ((B[0]+C[0])/2, (B[1]+C[1])/2)
    # Perp to AB at M1: AB is horizontal (if A[1]==B[1]==0), so perp is vertical
    dx_ab = B[0]-A[0]
    dy_ab = B[1]-A[1]
    geo.add_object({"type": "point", "id": "pb1", "x": m1[0]-dy_ab*0.6, "y": m1[1]+dx_ab*0.6,
                     "style": {"visible": False}})
    geo.add_object({"type": "segment", "id": "perp1", "from_point": "M1", "to_point": "pb1",
                     "style": {"dash": "dashed", "stroke": "#3498db"}})
    dx_bc = C[0]-B[0]
    dy_bc = C[1]-B[1]
    geo.add_object({"type": "point", "id": "pb2", "x": m2[0]-dy_bc*0.6, "y": m2[1]+dx_bc*0.6,
                     "style": {"visible": False}})
    geo.add_object({"type": "segment", "id": "perp2", "from_point": "M2", "to_point": "pb2",
                     "style": {"dash": "dashed", "stroke": "#3498db"}})
    geo.snapshot("Серединные перпендикуляры", "Проводим перпендикуляры к AB и BC через их середины")

    geo.add_constraint({"type": "circumscribed_circle", "id": "cc", "triangle": "tri"})
    geo.add_annotation({"type": "label", "id": "ann_O", "text": "O", "anchor": "cc_center",
                        "dx": 0.25, "dy": 0.35, "color": "#2980b9"})
    geo.snapshot("Описанная окружность", "O — центр, окружность проходит через A, B, C. OA = OB = OC = R")

    return geo.get_steps()


def build_inscribed_steps(vertices):
    A, B, C = vertices["A"], vertices["B"], vertices["C"]
    canvas = {"width": 480, "height": 420, "x_min": -1, "x_max": max(A[0],B[0],C[0])+2,
              "y_min": -1.5, "y_max": max(A[1],B[1],C[1])+1.5}
    geo = StepByStepGeo(canvas)

    geo.add_object({"type": "point", "id": "A", "x": A[0], "y": A[1], "label": "A", "label_dx": -14, "label_dy": 14})
    geo.add_object({"type": "point", "id": "B", "x": B[0], "y": B[1], "label": "B", "label_dx": 12, "label_dy": 14})
    geo.add_object({"type": "point", "id": "C", "x": C[0], "y": C[1], "label": "C", "label_dx": 0, "label_dy": -12})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(230,126,34,0.06)"}})
    geo.snapshot("Треугольник ABC", "Дано: треугольник ABC")

    geo.add_constraint({"type": "bisector", "id": "bis_A", "triangle": "tri", "vertex": "A"})
    geo.snapshot("Биссектриса из A", "Биссектриса делит угол A пополам")

    geo.add_constraint({"type": "bisector", "id": "bis_B", "triangle": "tri", "vertex": "B"})
    geo.snapshot("Биссектриса из B", "Пересечение двух биссектрис даёт инцентр I")

    geo.add_constraint({"type": "bisector", "id": "bis_C", "triangle": "tri", "vertex": "C"})
    geo.snapshot("Все три биссектрисы", "Все три биссектрисы проходят через одну точку")

    geo.add_constraint({"type": "inscribed_circle", "id": "ic", "triangle": "tri"})
    geo.add_annotation({"type": "label", "id": "ann_I", "text": "I",
                        "anchor": "ic_center", "dx": 0.3, "dy": 0.3, "color": "#e67e22"})
    geo.snapshot("Вписанная окружность", "Окружность с центром I касается всех трёх сторон")

    return geo.get_steps()


def build_pythagorean_steps(vertices):
    A, B, C = vertices["A"], vertices["B"], vertices["C"]
    a = B[0] - A[0]
    b = C[1] - A[1]
    c_val = math.sqrt(a**2 + b**2)
    canvas = {"width": 450, "height": 380, "x_min": -1, "x_max": a+2, "y_min": -1.5, "y_max": b+2}
    geo = StepByStepGeo(canvas)

    geo.add_object({"type": "point", "id": "A", "x": A[0], "y": A[1], "label": "A", "label_dx": -14, "label_dy": 14})
    geo.add_object({"type": "point", "id": "B", "x": B[0], "y": B[1], "label": "B", "label_dx": 12, "label_dy": 14})
    geo.add_object({"type": "point", "id": "C", "x": C[0], "y": C[1], "label": "C", "label_dx": -14, "label_dy": -8})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(155,89,182,0.06)"}})
    geo.snapshot("Прямоугольный треугольник", "Дано: прямоугольный треугольник ABC, ∠A = 90°")

    geo.add_constraint({"type": "right_angle_marker", "id": "ram", "vertex": "A", "ray1": "B", "ray2": "C"})
    geo.snapshot("Прямой угол в A", "Отмечаем ∠A = 90°")

    geo.add_annotation({"type": "label", "id": "ann_a", "text": f"a = {a}",
                        "anchor": "A", "dx": 1.2, "dy": -0.3, "color": "#2980b9"})
    geo.add_annotation({"type": "label", "id": "ann_b", "text": f"b = {b}",
                        "anchor": "A", "dx": -0.5, "dy": 0.9, "color": "#27ae60"})
    geo.snapshot("Катеты", f"a = AB = {a}, b = AC = {b}")

    geo.add_annotation({"type": "label", "id": "ann_c", "text": f"c = √({a}²+{b}²) = √{a**2+b**2} ≈ {c_val:.2f}",
                        "anchor": "B", "dx": -1.0, "dy": 1.2, "color": "#e74c3c", "font_size": 13})
    geo.snapshot("Гипотенуза", f"c² = a² + b² = {a**2} + {b**2} = {a**2+b**2}, c ≈ {c_val:.2f}")

    return geo.get_steps()


BUILDERS = {
    "altitude": build_altitude_steps,
    "medians": build_medians_steps,
    "circumscribed": build_circumscribed_steps,
    "inscribed": build_inscribed_steps,
    "pythagorean": build_pythagorean_steps,
}


# ═══════════════════════════════════════════════════════════════
# HTML report
# ═══════════════════════════════════════════════════════════════

def generate_report():
    sections_data = []

    for section in CONSPECT_SECTIONS:
        plan = section.get("visual_plan")
        builder_name = section.get("steps_builder")
        steps = []
        scene_json = None

        if builder_name and builder_name in BUILDERS:
            vertices = plan["params"]["vertices"] if plan else {}
            steps = BUILDERS[builder_name](vertices)
            scene_json = json.dumps(plan, ensure_ascii=False, indent=2) if plan else None

        sections_data.append({
            "section": section,
            "plan": plan,
            "scene_json": scene_json,
            "steps": steps,
        })

    n_sections = len(CONSPECT_SECTIONS)
    n_visuals = sum(1 for s in sections_data if s["steps"])
    n_steps = sum(len(s["steps"]) for s in sections_data)

    html = [f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>Бэкенд: конспект по геометрии с пошаговыми визуалами</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f0f2f5; color: #1a1a2e; line-height: 1.6; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
             padding: 40px 20px; text-align: center; color: white; }}
  .header h1 {{ font-size: 26px; margin-bottom: 8px; }}
  .header p {{ opacity: 0.8; font-size: 14px; max-width: 700px; margin: 0 auto; }}
  .stats-bar {{ display: flex; justify-content: center; gap: 30px; margin-top: 20px; flex-wrap: wrap; }}
  .stat {{ background: rgba(255,255,255,0.15); padding: 10px 24px; border-radius: 8px; }}
  .stat-val {{ font-size: 22px; font-weight: bold; }}
  .stat-label {{ font-size: 11px; opacity: 0.7; text-transform: uppercase; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 30px 20px; }}

  .pipeline-arrow {{ text-align: center; padding: 16px; font-size: 18px; color: #888; }}

  .section-block {{ background: white; border-radius: 12px; margin-bottom: 28px;
                    box-shadow: 0 2px 12px rgba(0,0,0,0.08); overflow: hidden; }}
  .section-header {{ padding: 16px 20px; background: #f8f9fa; border-bottom: 1px solid #eee; }}
  .section-header h3 {{ font-size: 16px; color: #2c3e50; }}
  .section-num {{ display: inline-block; background: #0f3460; color: white;
                  width: 26px; height: 26px; line-height: 26px; border-radius: 50%;
                  text-align: center; font-size: 12px; font-weight: bold; margin-right: 8px; }}

  .conspect-text {{ padding: 16px 20px; font-size: 14px; color: #444;
                    white-space: pre-wrap; border-bottom: 1px solid #f0f0f0; }}
  .conspect-text strong {{ color: #2c3e50; }}

  .backend-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; }}
  .backend-col {{ padding: 16px 20px; }}
  .backend-col:first-child {{ border-right: 1px solid #f0f0f0; }}
  .backend-label {{ font-size: 11px; text-transform: uppercase; color: #999;
                    margin-bottom: 8px; letter-spacing: 0.5px; }}
  .plan-json {{ background: #f8f9fa; border-radius: 8px; padding: 12px;
                font-family: 'Fira Code', monospace; font-size: 11px; color: #555;
                max-height: 200px; overflow-y: auto; white-space: pre-wrap; }}
  .scene-json {{ background: #f0f7ff; border-radius: 8px; padding: 12px;
                 font-family: 'Fira Code', monospace; font-size: 11px; color: #555;
                 max-height: 200px; overflow-y: auto; white-space: pre-wrap; }}

  .no-visual {{ padding: 16px 20px; color: #999; font-style: italic; font-size: 13px; }}

  .steps-section {{ padding: 16px 20px; }}
  .steps-title {{ font-size: 13px; text-transform: uppercase; color: #0f3460;
                  margin-bottom: 12px; letter-spacing: 0.5px; font-weight: 600; }}
  .steps-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 12px; }}
  .step-card {{ border: 1px solid #e8e8e8; border-radius: 8px; overflow: hidden; }}
  .step-head {{ padding: 8px 12px; background: #f8f9fa; border-bottom: 1px solid #eee;
                font-size: 13px; font-weight: 600; color: #333; }}
  .step-head .num {{ display: inline-block; background: #e67e22; color: white;
                     width: 22px; height: 22px; line-height: 22px; border-radius: 50%;
                     text-align: center; font-size: 11px; margin-right: 6px; }}
  .step-desc {{ font-size: 11px; color: #888; font-weight: 400; margin-top: 2px; }}
  .step-svg {{ padding: 10px; text-align: center; background: #fefefe; }}
  .step-svg svg {{ max-width: 100%; height: auto; }}

  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 8px;
            font-size: 10px; color: white; }}
  .badge-plan {{ background: #2980b9; }}
  .badge-scene {{ background: #27ae60; }}
  .badge-render {{ background: #e67e22; }}
  .badge-none {{ background: #bbb; }}
</style>
</head>
<body>
<div class="header">
  <h1>Бэкенд конспекта: геометрия с пошаговыми визуалами</h1>
  <p>Полный пайплайн: текст конспекта → планировщик визуалов → Scene JSON (формат коллеги) → solver (constraints) → SVG рендерер → пошаговые построения</p>
  <div class="stats-bar">
    <div class="stat"><div class="stat-val">{n_sections}</div><div class="stat-label">секций</div></div>
    <div class="stat"><div class="stat-val">{n_visuals}</div><div class="stat-label">визуалов</div></div>
    <div class="stat"><div class="stat-val">{n_steps}</div><div class="stat-label">шагов</div></div>
  </div>
</div>

<div class="container">
<div class="pipeline-arrow">
  📝 Конспект → 🔍 Планировщик → 📐 Scene JSON → ⚙️ Solver → 🎨 SVG Renderer
</div>
"""]

    for sd in sections_data:
        sec = sd["section"]
        plan = sd["plan"]
        steps = sd["steps"]

        has_visual = bool(steps)
        badge = '<span class="badge badge-render">пошаговый визуал</span>' if has_visual else '<span class="badge badge-none">без визуала</span>'

        html.append(f"""
<div class="section-block">
  <div class="section-header">
    <span class="section-num">{sec['id']}</span>
    <span style="font-size:16px; font-weight:600;">{html_mod.escape(sec['title'])}</span>
    &nbsp;{badge}
  </div>
  <div class="conspect-text">{html_mod.escape(sec['text'])}</div>
""")

        if not has_visual:
            html.append('  <div class="no-visual">Планировщик: визуал не требуется (нет геометрических построений)</div>')
        else:
            plan_json = json.dumps(plan, ensure_ascii=False, indent=2) if plan else "{}"

            html.append(f"""
  <div class="backend-row">
    <div class="backend-col">
      <div class="backend-label"><span class="badge badge-plan">1</span> Visual Plan (выход планировщика)</div>
      <div class="plan-json">{html_mod.escape(plan_json)}</div>
    </div>
    <div class="backend-col">
      <div class="backend-label"><span class="badge badge-scene">2</span> Scene JSON (формат svg-generator)</div>
      <div class="scene-json">{html_mod.escape(sd.get('scene_json', '{}'))}</div>
    </div>
  </div>

  <div class="steps-section">
    <div class="steps-title"><span class="badge badge-render">3</span> Пошаговый рендеринг ({len(steps)} шагов)</div>
    <div class="steps-grid">
""")

            for i, step in enumerate(steps):
                html.append(f"""
      <div class="step-card">
        <div class="step-head">
          <span class="num">{i+1}</span> {html_mod.escape(step['title'])}
          <div class="step-desc">{html_mod.escape(step.get('description', ''))}</div>
        </div>
        <div class="step-svg">{step['svg']}</div>
      </div>
""")

            html.append("    </div>\n  </div>")

        html.append("</div>")

    html.append("""
<div style="margin-top:30px; padding:20px; background:white; border-radius:12px;
     box-shadow:0 2px 12px rgba(0,0,0,0.08);">
  <h3 style="margin-bottom:12px; color:#2c3e50;">Архитектура бэкенда</h3>
  <pre style="background:#f8f9fa; padding:16px; border-radius:8px; font-size:12px; overflow-x:auto; line-height:1.5;">
Конспект (.md)
     │
     ▼
┌──────────────────────┐
│  Планировщик (LLM)   │  Qwen2.5-7B → VisualPlan JSON
│  visual_planner_v2   │  Тип: geometry_stepbystep / geometry_static
└──────────┬───────────┘
           │  {visual_type, params: {construction, vertices, ...}}
           ▼
┌──────────────────────┐
│  Конвертер            │  VisualPlan → Scene JSON
│  converter.py        │  Формат svg-generator коллеги
└──────────┬───────────┘
           │  {scene_type: "geometry", objects: [...], constraints: [...]}
           ▼
┌──────────────────────┐
│  Solver               │  Обрабатывает constraints:
│  geometry_renderer.py │  altitude, median, bisector,
│                       │  circumscribed_circle, inscribed_circle
└──────────┬───────────┘
           │  Добавляет вычисленные точки и отрезки
           ▼
┌──────────────────────┐
│  SVG Renderer         │  point, segment, triangle,
│  geometry_renderer.py │  circle, right_angle_marker
└──────────┬───────────┘
           │
           ▼
        SVG файл (один на шаг)

Пошаговый режим (StepByStepGeo):
  - Каждый шаг добавляет объекты к сцене
  - После каждого добавления — snapshot → SVG
  - Результат: серия SVG с прогрессивной дорисовкой
  </pre>
</div>
</div>
</body>
</html>""")

    out_path = OUTPUT_DIR / "geometry_backend_report.html"
    out_path.write_text("\n".join(html), encoding="utf-8")
    return out_path


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = generate_report()
    print(f"Отчёт: {report}")


if __name__ == "__main__":
    main()
