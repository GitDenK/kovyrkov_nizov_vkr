"""
Demo: geometry conspect with interleaved text + step-by-step visuals.

Text paragraph → SVG → text paragraph → SVG → ...
Exactly how it would look in a real conspect shown to a student.
"""

import copy
import json
import math
import sys
import html as html_mod
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.geometry_renderer import render_geometry_svg, StepByStepGeo

OUTPUT_DIR = ROOT / "pipeline" / "output_geometry"


# ═══════════════════════════════════════════════════════════════
# Conspect content: list of (text, visual) pairs
# Each entry is either {"type": "text", "content": "..."} or
# {"type": "visual", "svg": "...", "caption": "..."}
# ═══════════════════════════════════════════════════════════════

def build_conspect_altitude():
    """Full conspect section: finding triangle area via altitude."""

    canvas = {"width": 480, "height": 380, "x_min": -1, "x_max": 9, "y_min": -1.5, "y_max": 7}
    geo = StepByStepGeo(canvas)

    blocks = []

    # --- Block 1: problem statement ---
    blocks.append({"type": "text", "content": """### Задача
В треугольнике $ABC$ даны координаты вершин: $A(0,\\,0)$, $B(7,\\,0)$, $C(3,\\,5{,}5)$.

**Найти:** высоту из вершины $C$ на сторону $AB$ и площадь треугольника.

**Решение.** Начнём с построения треугольника по заданным координатам."""})

    # Visual 1: just the triangle
    geo.add_object({"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 16})
    geo.add_object({"type": "point", "id": "B", "x": 7, "y": 0, "label": "B", "label_dx": 12, "label_dy": 16})
    geo.add_object({"type": "point", "id": "C", "x": 3, "y": 5.5, "label": "C", "label_dx": 0, "label_dy": -12})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(52,152,219,0.06)"}})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Треугольник ABC по заданным координатам"})

    # --- Block 2: identify base ---
    blocks.append({"type": "text", "content": """Заметим, что точки $A$ и $B$ лежат на оси $Ox$ (у обоих $y = 0$). Значит, сторона $AB$ — горизонтальная, и её длину легко найти:

$$a = AB = x_B - x_A = 7 - 0 = 7$$

Выберем $AB$ как **основание** треугольника."""})

    # Visual 2: base labeled
    geo.add_annotation({"type": "label", "id": "ann_base", "text": "a = AB = 7",
                        "anchor": "A", "dx": 1.5, "dy": -0.3, "color": "#2980b9", "font_size": 13})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Основание a = AB = 7"})

    # --- Block 3: draw altitude ---
    blocks.append({"type": "text", "content": """Теперь проведём **высоту** — перпендикуляр из вершины $C$ на прямую $AB$.

Поскольку $AB$ лежит на оси $Ox$, высота — это просто вертикальный отрезок от $C$ до точки $H$ на $AB$. Точка $H$ имеет ту же абсциссу, что и $C$:

$$H = (x_C,\\; 0) = (3,\\; 0)$$"""})

    # Visual 3: altitude drawn
    geo.add_constraint({"type": "altitude", "id": "alt_C", "triangle": "tri", "vertex": "C"})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Высота CH опущена из C на AB"})

    # --- Block 4: right angle + height value ---
    blocks.append({"type": "text", "content": """Отметим прямой угол в точке $H$ — это подтверждает, что $CH \\perp AB$.

Длина высоты равна ординате вершины $C$:

$$h = y_C = 5{,}5$$"""})

    # Visual 4: right angle marker + labels
    geo.add_constraint({"type": "right_angle_marker", "id": "ram_H", "vertex": "alt_C_foot", "ray1": "A", "ray2": "C"})
    geo.add_annotation({"type": "label", "id": "ann_H", "text": "H", "anchor": "alt_C_foot",
                        "dx": 0.15, "dy": -0.3, "color": "#e74c3c"})
    geo.add_annotation({"type": "label", "id": "ann_h", "text": "h = 5.5",
                        "anchor": "C", "dx": 0.5, "dy": -1.2, "color": "#e74c3c", "font_size": 13})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "CH ⊥ AB, высота h = 5.5"})

    # --- Block 5: area formula ---
    blocks.append({"type": "text", "content": """Теперь вычислим площадь по формуле:

$$S = \\frac{1}{2} \\cdot a \\cdot h = \\frac{1}{2} \\cdot 7 \\cdot 5{,}5 = 19{,}25$$

**Ответ:** высота $CH = 5{,}5$; площадь $S = 19{,}25$."""})

    # Visual 5: final with area
    geo.add_annotation({"type": "label", "id": "ann_S", "text": "S = ½ · 7 · 5.5 = 19.25",
                        "anchor": "A", "dx": 1.5, "dy": -0.85, "color": "#8e44ad", "font_size": 14})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Площадь S = ½ · a · h = 19.25"})

    return {
        "title": "Площадь треугольника через высоту",
        "blocks": blocks,
    }


def build_conspect_circumscribed():
    """Full conspect section: circumscribed circle."""

    canvas = {"width": 480, "height": 440, "x_min": -2, "x_max": 10, "y_min": -3, "y_max": 9}
    geo = StepByStepGeo(canvas)

    blocks = []

    blocks.append({"type": "text", "content": """### Задача
Дан треугольник $ABC$: $A(0,\\,0)$, $B(8,\\,0)$, $C(3,\\,7)$.

**Найти:** центр и радиус описанной окружности.

**Решение.** Описанная окружность проходит через все три вершины. Чтобы найти её центр, нужно построить серединные перпендикуляры к сторонам — их пересечение и есть центр $O$.

Построим треугольник."""})

    geo.add_object({"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 14})
    geo.add_object({"type": "point", "id": "B", "x": 8, "y": 0, "label": "B", "label_dx": 12, "label_dy": 14})
    geo.add_object({"type": "point", "id": "C", "x": 3, "y": 7, "label": "C", "label_dx": 0, "label_dy": -12})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(52,152,219,0.06)"}})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Треугольник ABC"})

    blocks.append({"type": "text", "content": """**Шаг 1.** Находим середины сторон $AB$ и $BC$:

$$M_1 = \\frac{A + B}{2} = \\left(\\frac{0+8}{2},\\; \\frac{0+0}{2}\\right) = (4,\\; 0)$$

$$M_2 = \\frac{B + C}{2} = \\left(\\frac{8+3}{2},\\; \\frac{0+7}{2}\\right) = (5{,}5;\\; 3{,}5)$$"""})

    geo.add_object({"type": "segment", "id": "seg_AB", "from_point": "A", "to_point": "B"})
    geo.add_object({"type": "segment", "id": "seg_BC", "from_point": "B", "to_point": "C"})
    geo.add_constraint({"type": "midpoint", "id": "mid_AB", "segment": "seg_AB", "result_id": "M1"})
    geo.add_constraint({"type": "midpoint", "id": "mid_BC", "segment": "seg_BC", "result_id": "M2"})
    geo.add_annotation({"type": "label", "id": "ann_M1", "text": "M₁(4, 0)", "anchor": "M1", "dx": 0, "dy": -0.35})
    geo.add_annotation({"type": "label", "id": "ann_M2", "text": "M₂(5.5, 3.5)", "anchor": "M2", "dx": 0.5, "dy": 0})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Середины сторон M₁ и M₂"})

    blocks.append({"type": "text", "content": """**Шаг 2.** Проводим серединные перпендикуляры через $M_1$ и $M_2$.

Серединный перпендикуляр к $AB$: так как $AB$ горизонтальная, перпендикуляр — вертикальная прямая $x = 4$.

Серединный перпендикуляр к $BC$: направлен перпендикулярно вектору $\\vec{BC} = (-5,\\, 7)$."""})

    geo.add_object({"type": "point", "id": "pb1", "x": 4, "y": 7, "style": {"visible": False}})
    geo.add_object({"type": "segment", "id": "perp1", "from_point": "M1", "to_point": "pb1",
                     "style": {"dash": "dashed", "stroke": "#3498db"}})
    geo.add_object({"type": "point", "id": "pb2", "x": 2.1, "y": 1.1, "style": {"visible": False}})
    geo.add_object({"type": "segment", "id": "perp2", "from_point": "M2", "to_point": "pb2",
                     "style": {"dash": "dashed", "stroke": "#3498db"}})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Серединные перпендикуляры (синий пунктир)"})

    blocks.append({"type": "text", "content": """**Шаг 3.** Находим пересечение серединных перпендикуляров — это центр описанной окружности $O$.

Радиус: $R = OA = OB = OC$ — расстояние от центра до любой вершины.

Строим окружность через все три вершины."""})

    geo.add_constraint({"type": "circumscribed_circle", "id": "cc", "triangle": "tri"})
    geo.add_annotation({"type": "label", "id": "ann_O", "text": "O — центр",
                        "anchor": "cc_center", "dx": 0.4, "dy": 0.4, "color": "#2980b9"})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Описанная окружность: проходит через A, B, C"})

    blocks.append({"type": "text", "content": """Описанная окружность построена. Центр $O$ равноудалён от всех трёх вершин: $OA = OB = OC = R$.

**Ответ:** центр $O$ — пересечение серединных перпендикуляров; окружность проходит через все вершины треугольника."""})

    return {
        "title": "Описанная окружность треугольника",
        "blocks": blocks,
    }


def build_conspect_inscribed():
    """Full conspect section: inscribed circle via bisectors."""

    canvas = {"width": 480, "height": 400, "x_min": -1, "x_max": 11, "y_min": -1.5, "y_max": 8.5}
    geo = StepByStepGeo(canvas)

    blocks = []

    blocks.append({"type": "text", "content": """### Задача
Дан треугольник $ABC$: $A(0,\\,0)$, $B(9,\\,0)$, $C(4,\\,7)$.

**Найти:** вписанную окружность (центр и радиус).

**Решение.** Вписанная окружность касается всех трёх сторон треугольника изнутри. Её центр — точка пересечения **биссектрис** углов (инцентр $I$).

Начнём с построения треугольника."""})

    geo.add_object({"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 14})
    geo.add_object({"type": "point", "id": "B", "x": 9, "y": 0, "label": "B", "label_dx": 12, "label_dy": 14})
    geo.add_object({"type": "point", "id": "C", "x": 4, "y": 7, "label": "C", "label_dx": 0, "label_dy": -12})
    geo.add_object({"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
                     "style": {"fill": "rgba(230,126,34,0.06)"}})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Треугольник ABC"})

    blocks.append({"type": "text", "content": """**Шаг 1.** Проводим биссектрису угла $A$.

Биссектриса делит угол $\\angle BAC$ пополам. По теореме о биссектрисе, она делит противоположную сторону $BC$ в отношении $AB : AC$."""})

    geo.add_constraint({"type": "bisector", "id": "bis_A", "triangle": "tri", "vertex": "A"})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Биссектриса из вершины A (зелёный пунктир)"})

    blocks.append({"type": "text", "content": """**Шаг 2.** Проводим биссектрису угла $B$.

Пересечение двух биссектрис уже даёт нам инцентр — но для наглядности проведём и третью."""})

    geo.add_constraint({"type": "bisector", "id": "bis_B", "triangle": "tri", "vertex": "B"})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Биссектрисы из A и B пересекаются"})

    blocks.append({"type": "text", "content": """**Шаг 3.** Проводим биссектрису угла $C$.

Замечаем важное свойство: **все три биссектрисы пересекаются в одной точке $I$** — это инцентр треугольника."""})

    geo.add_constraint({"type": "bisector", "id": "bis_C", "triangle": "tri", "vertex": "C"})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Все три биссектрисы проходят через одну точку"})

    blocks.append({"type": "text", "content": """**Шаг 4.** Строим вписанную окружность с центром $I$.

Радиус $r$ — расстояние от инцентра $I$ до любой стороны треугольника. Его можно вычислить по формуле:

$$r = \\frac{S}{p}$$

где $S$ — площадь треугольника, $p$ — полупериметр."""})

    geo.add_constraint({"type": "inscribed_circle", "id": "ic", "triangle": "tri"})
    geo.add_annotation({"type": "label", "id": "ann_I", "text": "I", "anchor": "ic_center",
                        "dx": 0.3, "dy": 0.3, "color": "#e67e22"})
    geo.add_annotation({"type": "label", "id": "ann_r", "text": "r",
                        "anchor": "ic_center", "dx": 0.6, "dy": -0.25, "color": "#e67e22", "font_size": 13})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Вписанная окружность касается всех трёх сторон"})

    blocks.append({"type": "text", "content": """Вписанная окружность построена. Она касается каждой стороны треугольника ровно в одной точке.

**Ответ:** центр вписанной окружности $I$ — пересечение биссектрис; радиус $r = S / p$."""})

    return {
        "title": "Вписанная окружность через биссектрисы",
        "blocks": blocks,
    }


# ═══════════════════════════════════════════════════════════════
# HTML generation
# ═══════════════════════════════════════════════════════════════

def render_markdown_simple(text):
    """Very basic markdown → HTML (headings, bold, formulas as-is)."""
    lines = text.strip().split("\n")
    result = []
    for line in lines:
        line = line.strip()
        if line.startswith("### "):
            result.append(f'<h3 style="color:#2c3e50; margin:16px 0 8px;">{html_mod.escape(line[4:])}</h3>')
        elif line.startswith("## "):
            result.append(f'<h2 style="color:#2c3e50; margin:20px 0 10px;">{html_mod.escape(line[3:])}</h2>')
        else:
            processed = line
            # bold
            import re
            processed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', processed)
            # inline math $...$
            processed = re.sub(r'\$\$(.+?)\$\$', r'<div class="math-block">\1</div>', processed)
            processed = re.sub(r'\$(.+?)\$', r'<span class="math-inline">\1</span>', processed)
            if processed:
                result.append(f'<p>{processed}</p>')
            else:
                result.append('<br/>')
    return "\n".join(result)


def generate_conspect_html(conspect_sections):
    total_visuals = sum(
        sum(1 for b in s["blocks"] if b["type"] == "visual")
        for s in conspect_sections
    )

    html = [f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>Конспект по геометрии с пошаговыми визуалами</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Georgia', 'Times New Roman', serif;
         background: #faf9f6; color: #2c2c2c; line-height: 1.8; }}

  .page-header {{ background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
                  padding: 40px 20px; text-align: center; color: white; }}
  .page-header h1 {{ font-size: 26px; margin-bottom: 6px; font-family: sans-serif; }}
  .page-header p {{ opacity: 0.85; font-size: 14px; font-family: sans-serif; }}

  .conspect {{ max-width: 760px; margin: 0 auto; padding: 30px 24px; }}

  .section {{ margin-bottom: 50px; }}
  .section-title {{ font-size: 22px; color: #2c3e50; margin-bottom: 20px;
                    padding-bottom: 8px; border-bottom: 2px solid #3498db;
                    font-family: -apple-system, sans-serif; }}

  .text-block {{ margin: 16px 0; font-size: 16px; }}
  .text-block p {{ margin: 6px 0; }}
  .text-block h3 {{ font-size: 18px; margin: 14px 0 6px; font-family: sans-serif; }}
  .text-block strong {{ color: #2c3e50; }}
  .text-block .math-inline {{ font-family: 'Cambria Math', 'STIX Two Math', serif;
                              background: #f0f4f8; padding: 1px 5px; border-radius: 3px;
                              font-style: italic; color: #1a5276; }}
  .text-block .math-block {{ font-family: 'Cambria Math', serif;
                             background: #f0f4f8; padding: 10px 16px; border-radius: 6px;
                             margin: 10px 0; font-size: 17px; text-align: center;
                             color: #1a5276; font-style: italic; }}

  .visual-block {{ margin: 20px 0; text-align: center; }}
  .visual-frame {{ display: inline-block; background: white; border: 1px solid #e0e0e0;
                   border-radius: 10px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
  .visual-frame svg {{ max-width: 100%; height: auto; }}
  .visual-caption {{ font-family: -apple-system, sans-serif;
                     font-size: 13px; color: #666; margin-top: 8px;
                     font-style: italic; }}

  .section-divider {{ text-align: center; margin: 40px 0; color: #ccc; font-size: 24px;
                      letter-spacing: 8px; }}

  .footer {{ text-align: center; padding: 30px; color: #999; font-size: 12px;
             font-family: sans-serif; }}
</style>
</head>
<body>
<div class="page-header">
  <h1>Конспект: Планиметрия (ЕГЭ, задание 16)</h1>
  <p>Пошаговые геометрические построения, интегрированные в текст</p>
</div>

<div class="conspect">
"""]

    for i, section in enumerate(conspect_sections):
        html.append(f"""
<div class="section">
  <div class="section-title">{html_mod.escape(section['title'])}</div>
""")

        for block in section["blocks"]:
            if block["type"] == "text":
                rendered = render_markdown_simple(block["content"])
                html.append(f'  <div class="text-block">{rendered}</div>')
            elif block["type"] == "visual":
                caption = block.get("caption", "")
                html.append(f"""
  <div class="visual-block">
    <div class="visual-frame">
      {block['svg']}
    </div>
    <div class="visual-caption">{html_mod.escape(caption)}</div>
  </div>
""")

        html.append("</div>")

        if i < len(conspect_sections) - 1:
            html.append('<div class="section-divider">* * *</div>')

    html.append(f"""
</div>
<div class="footer">
  Сгенерировано автоматически: Планировщик визуалов → Конвертер → Solver → SVG Renderer<br/>
  {total_visuals} пошаговых визуалов встроено в текст конспекта
</div>
</body>
</html>""")

    return "\n".join(html)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sections = [
        build_conspect_altitude(),
        build_conspect_circumscribed(),
        build_conspect_inscribed(),
    ]

    report = generate_conspect_html(sections)
    out_path = OUTPUT_DIR / "geometry_conspect_interleaved.html"
    out_path.write_text(report, encoding="utf-8")

    total_visuals = sum(
        sum(1 for b in s["blocks"] if b["type"] == "visual")
        for s in sections
    )
    print(f"Конспект: {out_path}")
    print(f"Секций: {len(sections)}, визуалов: {total_visuals}")


if __name__ == "__main__":
    main()
