"""
Interleaved conspect for EGE Task 16, Problem 1:
Trapezoid with perpendicular diagonals (5-12-13 triple).

Source: https://ege-study.ru/zadanie-16-profilnogo-ege-po-matematike-planimetriya-zadacha-1/
"""

import copy
import math
import re
import sys
import html as html_mod
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.geometry_renderer import render_geometry_svg, StepByStepGeo

OUTPUT_DIR = ROOT / "pipeline" / "output_geometry"

# Schematic coordinates (matching the textbook figure style)
A = (1, 0)
B = (3.5, 5)
C = (7.5, 5)
D = (10, 0)
F = (14, 0)

# Diagonal intersection (computed: t=9/13 on AC)
P_x = A[0] + (C[0] - A[0]) * 9 / 13  # ≈ 5.5
P_y = A[1] + (C[1] - A[1]) * 9 / 13  # ≈ 3.46

# Foot of altitude from C to AF
H = (C[0], 0)

CANVAS = {"width": 560, "height": 380,
          "x_min": -0.5, "x_max": 15.5, "y_min": -2.2, "y_max": 7}
STYLE = {"theme": "light", "stroke_color": "#333333", "fill_color": "none",
         "font_size": 13, "font_family": "sans-serif"}


def build_conspect():
    geo = StepByStepGeo(CANVAS, STYLE)
    blocks = []

    # ═══════════════════════════════════════════════
    # УСЛОВИЕ
    # ═══════════════════════════════════════════════
    blocks.append({"type": "text", "content": """## Задание 16. Планиметрия. Задача 1

Основания трапеции равны 4 и 9, а её диагонали равны 5 и 12.

**а)** Докажите, что диагонали трапеции перпендикулярны.

**б)** Найдите высоту трапеции.

---

### Решение

Пусть $BC = 4$, $AD = 9$, $AC = 12$, $BD = 5$.

Построим трапецию $ABCD$."""})

    # Visual 1: trapezoid only
    geo.add_object({"type": "point", "id": "A", "x": A[0], "y": A[1], "label": "A",
                     "label_dx": -12, "label_dy": 14})
    geo.add_object({"type": "point", "id": "B", "x": B[0], "y": B[1], "label": "B",
                     "label_dx": -6, "label_dy": -14})
    geo.add_object({"type": "point", "id": "C", "x": C[0], "y": C[1], "label": "C",
                     "label_dx": 6, "label_dy": -14})
    geo.add_object({"type": "point", "id": "D", "x": D[0], "y": D[1], "label": "D",
                     "label_dx": 4, "label_dy": 14})
    # sides
    geo.add_object({"type": "segment", "id": "AB", "from_point": "A", "to_point": "B"})
    geo.add_object({"type": "segment", "id": "BC", "from_point": "B", "to_point": "C"})
    geo.add_object({"type": "segment", "id": "CD", "from_point": "C", "to_point": "D"})
    geo.add_object({"type": "segment", "id": "AD", "from_point": "A", "to_point": "D"})
    # length labels
    geo.add_annotation({"type": "label", "id": "lbl_BC", "text": "4",
                        "anchor": "B", "dx": 1.7, "dy": 0.3, "color": "#333"})
    geo.add_annotation({"type": "label", "id": "lbl_AD", "text": "9",
                        "anchor": "A", "dx": 4.0, "dy": -0.4, "color": "#333"})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Трапеция ABCD: BC = 4, AD = 9"})

    # ═══════════════════════════════════════════════
    # ЧАСТЬ А: диагонали
    # ═══════════════════════════════════════════════
    blocks.append({"type": "text", "content": """### Часть а)

Проведём диагонали $AC$ и $BD$. Нам нужно доказать, что они перпендикулярны."""})

    # Visual 2: add diagonals
    geo.add_object({"type": "segment", "id": "diag_AC", "from_point": "A", "to_point": "C",
                     "style": {"stroke": "#2980b9", "stroke_width": 1.8}})
    geo.add_object({"type": "segment", "id": "diag_BD", "from_point": "B", "to_point": "D",
                     "style": {"stroke": "#e74c3c", "stroke_width": 1.8}})
    geo.add_object({"type": "point", "id": "P", "x": P_x, "y": P_y,
                     "style": {"fill": "#333", "stroke": "#333", "radius": 3}})
    geo.add_annotation({"type": "label", "id": "lbl_AC", "text": "AC = 12",
                        "anchor": "A", "dx": 0.9, "dy": 1.4, "color": "#2980b9", "font_size": 12})
    geo.add_annotation({"type": "label", "id": "lbl_BD", "text": "BD = 5",
                        "anchor": "B", "dx": 1.9, "dy": -1.0, "color": "#e74c3c", "font_size": 12})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Диагонали AC = 12 (синяя) и BD = 5 (красная)"})

    blocks.append({"type": "text", "content": """В условии есть тонкий намёк. Вспомним **пифагорову тройку**: $5, 12, 13$. Как бы нам построить треугольник с такими же длинами сторон?

**Идея:** проведём $CF \\parallel BD$. Тогда $BCFD$ — параллелограмм."""})

    # Visual 3: add point F and CF
    geo.add_object({"type": "point", "id": "F", "x": F[0], "y": F[1], "label": "F",
                     "label_dx": 8, "label_dy": 14})
    geo.add_object({"type": "segment", "id": "DF", "from_point": "D", "to_point": "F",
                     "style": {"dash": "dashed"}})
    geo.add_object({"type": "segment", "id": "CF", "from_point": "C", "to_point": "F",
                     "style": {"stroke": "#e67e22", "stroke_width": 1.8}})
    geo.add_annotation({"type": "label", "id": "lbl_DF", "text": "DF = 4",
                        "anchor": "D", "dx": 1.0, "dy": 0.2, "color": "#666", "font_size": 12})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Проведём CF ∥ BD. Тогда BCFD — параллелограмм"})

    blocks.append({"type": "text", "content": """Из свойств параллелограмма $BCFD$:
- $DF = BC = 4$
- $CF = BD = 5$

Значит, $AF = AD + DF = 9 + 4 = 13$.

Рассмотрим **треугольник $ACF$** со сторонами:
$$AC = 12, \\quad CF = 5, \\quad AF = 13$$"""})

    # Visual 4: highlight triangle ACF
    # Draw AF as a segment
    geo.add_object({"type": "segment", "id": "AF", "from_point": "A", "to_point": "F",
                     "style": {"stroke": "#8e44ad", "stroke_width": 1.8}})
    geo.add_annotation({"type": "label", "id": "lbl_AF", "text": "AF = 13",
                        "anchor": "A", "dx": 5.5, "dy": -0.5, "color": "#8e44ad", "font_size": 12})
    geo.add_annotation({"type": "label", "id": "lbl_CF", "text": "CF = 5",
                        "anchor": "C", "dx": 1.8, "dy": -1.2, "color": "#e67e22", "font_size": 12})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Треугольник ACF: стороны 5, 12, 13"})

    blocks.append({"type": "text", "content": """Проверим:
$$AF^2 = 13^2 = 169$$
$$AC^2 + CF^2 = 12^2 + 5^2 = 144 + 25 = 169$$

Значит, $AF^2 = AC^2 + CF^2$ — **треугольник $ACF$ прямоугольный**, с прямым углом при вершине $C$."""})

    # Visual 5: right angle at C (square marker = standard 90° notation)
    geo.add_constraint({"type": "right_angle_marker", "id": "ra_C",
                        "vertex": "C", "ray1": "A", "ray2": "F"})
    geo.add_annotation({"type": "label", "id": "lbl_90", "text": "90°",
                        "anchor": "C", "dx": -0.1, "dy": -1.7, "color": "#e74c3c", "font_size": 13})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "∠ACF = 90° (пифагорова тройка 5-12-13)"})

    blocks.append({"type": "text", "content": """Поскольку $CF \\parallel BD$ и $\\angle ACF = 90°$, угол между $AC$ и $BD$ тоже равен $90°$.

**Значит, $AC \\perp BD$ — диагонали трапеции перпендикулярны.** $\\square$

---

### Часть б)

Высота трапеции равна расстоянию между прямыми $BC$ и $AD$. Заметим, что это также равно высоте **треугольника $ACF$**, опущенной из вершины $C$ на сторону $AF$."""})

    # Visual 6: draw height from C to AF
    geo.add_object({"type": "point", "id": "H", "x": H[0], "y": H[1],
                     "label": "H", "label_dx": 4, "label_dy": 14,
                     "style": {"fill": "#27ae60", "stroke": "#27ae60"}})
    geo.add_object({"type": "segment", "id": "CH", "from_point": "C", "to_point": "H",
                     "style": {"dash": "dashed", "stroke": "#27ae60", "stroke_width": 1.8}})
    geo.add_constraint({"type": "right_angle_marker", "id": "ram_H", "vertex": "H", "ray1": "A", "ray2": "C"})
    geo.add_annotation({"type": "label", "id": "lbl_h", "text": "h",
                        "anchor": "C", "dx": 0.25, "dy": -1.3, "color": "#27ae60", "font_size": 15})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Высота h = CH — перпендикуляр из C на AF"})

    blocks.append({"type": "text", "content": """Обозначим высоту $h$. Вычислим площадь треугольника $ACF$ двумя способами:

$$S_{ACF} = \\frac{1}{2} \\cdot AF \\cdot h = \\frac{1}{2} \\cdot AC \\cdot CF$$

Второе равенство верно, потому что $\\angle ACF = 90°$ (доказано в пункте а).

Подставляем:
$$\\frac{1}{2} \\cdot 13 \\cdot h = \\frac{1}{2} \\cdot 12 \\cdot 5$$

$$13h = 60$$

$$\\boxed{h = \\dfrac{60}{13}}$$"""})

    # Visual 7: final with answer
    geo.add_annotation({"type": "label", "id": "lbl_ans", "text": "h = 60/13 ≈ 4.62",
                        "anchor": "H", "dx": 1.5, "dy": 1.1, "color": "#27ae60", "font_size": 14})
    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Ответ: h = 60/13"})

    return blocks


# ═══════════════════════════════════════════════════
# HTML
# ═══════════════════════════════════════════════════

def render_md(text):
    """Markdown-to-HTML with LaTeX kept intact for MathJax."""
    lines = text.strip().split("\n")
    result = []

    for line in lines:
        stripped = line.strip()

        if stripped == "---":
            result.append('<hr style="border:none;border-top:1px solid #ddd;margin:24px 0;"/>')
            continue

        if stripped.startswith("## "):
            result.append(f'<h2>{fmt_inline(stripped[3:])}</h2>')
            continue
        if stripped.startswith("### "):
            result.append(f'<h3>{fmt_inline(stripped[4:])}</h3>')
            continue

        # display math $$...$$ — keep delimiters for MathJax
        if stripped.startswith("$$") and stripped.endswith("$$"):
            result.append(f'<div class="formula">{stripped}</div>')
            continue

        if stripped.startswith("- "):
            result.append(f'<div style="padding-left:16px;">• {fmt_inline(stripped[2:])}</div>')
            continue

        if stripped == "":
            result.append("<br/>")
        else:
            result.append(f'<p>{fmt_inline(stripped)}</p>')

    return "\n".join(result)


def fmt_inline(s):
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = s.replace("\\square", "\\(\\blacksquare\\)")
    return s


def esc(s):
    return html_mod.escape(s)


def generate_html(blocks):
    n_visuals = sum(1 for b in blocks if b["type"] == "visual")

    html = [f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>Задание 16 ЕГЭ — Трапеция с перпендикулярными диагоналями</title>
<script>
MathJax = {{
  tex: {{ inlineMath: [['$','$']], displayMath: [['$$','$$']] }},
  svg: {{ fontCache: 'global' }}
}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    font-family: 'Georgia', 'PT Serif', serif;
    background: #faf9f6;
    color: #2c2c2c;
    line-height: 1.85;
  }}

  .page-header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 36px 20px;
    text-align: center;
    color: white;
  }}
  .page-header h1 {{ font-size: 24px; margin-bottom: 6px; font-family: sans-serif; }}
  .page-header p {{ opacity: 0.8; font-size: 13px; font-family: sans-serif; }}
  .page-header a {{ color: #81d4fa; text-decoration: none; }}

  .conspect {{
    max-width: 740px;
    margin: 0 auto;
    padding: 32px 28px 60px;
  }}

  .text-block {{
    margin: 14px 0;
    font-size: 16.5px;
  }}
  .text-block p {{ margin: 5px 0; }}
  .text-block h2 {{ font-size: 21px; color: #2c3e50; font-family: sans-serif; }}
  .text-block h3 {{ font-size: 18px; color: #34495e; font-family: sans-serif; }}
  .text-block strong {{ color: #2c3e50; }}

  .formula {{
    background: #f7f9fc;
    padding: 14px 20px;
    border-radius: 8px;
    margin: 12px 0;
    text-align: center;
    border-left: 3px solid #2980b9;
  }}

  .visual-block {{
    margin: 22px 0;
    text-align: center;
  }}
  .visual-frame {{
    display: inline-block;
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    padding: 14px 18px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
  }}
  .visual-frame svg {{ max-width: 100%; height: auto; }}
  .visual-caption {{
    font-family: -apple-system, sans-serif;
    font-size: 13px;
    color: #777;
    margin-top: 8px;
    font-style: italic;
  }}

  .footer {{
    text-align: center;
    padding: 30px 20px;
    color: #aaa;
    font-size: 11px;
    font-family: sans-serif;
    border-top: 1px solid #eee;
  }}
  .footer a {{ color: #888; }}
</style>
</head>
<body>

<div class="page-header">
  <h1>Задание 16 ЕГЭ по математике. Планиметрия</h1>
  <p>Пошаговое решение с интерактивными геометрическими построениями</p>
  <p style="margin-top:6px;"><a href="https://ege-study.ru/zadanie-16-profilnogo-ege-po-matematike-planimetriya-zadacha-1/">Источник задачи: ege-study.ru</a></p>
</div>

<div class="conspect">
"""]

    for block in blocks:
        if block["type"] == "text":
            html.append(f'<div class="text-block">{render_md(block["content"])}</div>')
        elif block["type"] == "visual":
            cap = block.get("caption", "")
            html.append(f"""
<div class="visual-block">
  <div class="visual-frame">{block['svg']}</div>
  <div class="visual-caption">{esc(cap)}</div>
</div>""")

    html.append(f"""
</div>
<div class="footer">
  Сгенерировано: Планировщик визуалов → Конвертер → Solver → SVG Renderer |
  {n_visuals} пошаговых построений
</div>
</body>
</html>""")

    return "\n".join(html)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    blocks = build_conspect()
    html = generate_html(blocks)
    out = OUTPUT_DIR / "task16_trapezoid.html"
    out.write_text(html, encoding="utf-8")
    n = sum(1 for b in blocks if b["type"] == "visual")
    print(f"Отчёт: {out}")
    print(f"Блоков текста: {sum(1 for b in blocks if b['type'] == 'text')}, визуалов: {n}")


if __name__ == "__main__":
    main()
