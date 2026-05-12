"""
Semi-automated step-by-step stereometry demo for EGE Task 14, Problem 2.

Regular hexagonal prism ABCDEF–A₁B₁C₁D₁E₁F₁, all edges = 1.
G = midpoint of A₁B₁.
Find: angle between line AG and plane BDD₁.
Answer: arctan(1/2)

Source: https://ege-study.ru/zadanie-14-profilnogo-ege-po-matematike-stereometriya-zadacha-2/
"""

import math
import re
import sys
import html as html_mod
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.geometry_renderer import StepByStepGeo

OUTPUT_DIR = ROOT / "pipeline" / "output_geometry"

# ═══════════════════════════════════════════════════════════════
# 3D → 2D oblique projection
# ═══════════════════════════════════════════════════════════════

def proj(x3, y3, z3):
    """Oblique cabinet projection for hexagonal prism.
    x: left-right, y: depth (positive = behind), z: height (up)."""
    x2 = x3 - y3 * 0.4
    y2 = z3 + y3 * 0.2
    return round(x2 * 2.2 + 6.5, 2), round(y2 * 2.5 + 1.5, 2)


# ═══════════════════════════════════════════════════════════════
# 3D coordinates — regular hexagonal prism, edge = 1
# ═══════════════════════════════════════════════════════════════

VNAMES = ['A', 'B', 'C', 'D', 'E', 'F']
p3 = {}
for i, nm in enumerate(VNAMES):
    a = i * math.pi / 3
    p3[nm] = (math.cos(a), math.sin(a), 0)
    p3[nm + '1'] = (math.cos(a), math.sin(a), 1)

p3['G'] = tuple((a + b) / 2 for a, b in zip(p3['A1'], p3['B1']))
p3['T'] = tuple((a + b) / 2 for a, b in zip(p3['A'], p3['B']))

p2 = {k: proj(*v) for k, v in p3.items()}

# Flat hexagon cross-section (base plane, true shape)
HX_S, HX_OX, HX_OY = 2.0, 5.0, 3.0

def hpt(name):
    x3, y3, _ = p3[name]
    return round(x3 * HX_S + HX_OX, 2), round(y3 * HX_S + HX_OY, 2)


# ═══════════════════════════════════════════════════════════════
# Canvas & style
# ═══════════════════════════════════════════════════════════════

CAN3D = {"width": 560, "height": 440,
         "x_min": 3, "x_max": 10, "y_min": 0, "y_max": 5.5}
CAN_HEX = {"width": 500, "height": 380,
            "x_min": 1.5, "x_max": 8.5, "y_min": 0, "y_max": 6}
STY = {"theme": "light", "stroke_color": "#333333", "fill_color": "none",
       "font_size": 13, "font_family": "sans-serif"}

# Label offsets (pixels) — tuned for this projection
LBL3 = {
    'A': (10, 8), 'B': (-4, 10), 'C': (-14, 6), 'D': (-14, 8),
    'E': (-4, 12), 'F': (8, 12),
    'A1': (10, -10), 'B1': (-4, -14), 'C1': (-14, -10), 'D1': (-14, -8),
    'E1': (-4, 8), 'F1': (8, 6),
    'G': (8, -10), 'T': (8, 10),
}
LBL_H = {
    'A': (10, 0), 'B': (4, -14), 'C': (-14, -10), 'D': (-14, 0),
    'E': (-10, 12), 'F': (10, 12), 'T': (10, -6),
}

HIDDEN_BOT = {'CD', 'DE'}


def _lbl(name):
    return name.replace('1', '₁')


def _pt(geo, pid, xy, label, ldx, ldy, **kw):
    geo.add_object({"type": "point", "id": pid,
                     "x": xy[0], "y": xy[1], "label": label,
                     "label_dx": ldx, "label_dy": ldy, **kw})


def _seg(geo, sid, a, b, style=None):
    o = {"type": "segment", "id": sid, "from_point": a, "to_point": b}
    if style:
        o["style"] = style
    geo.add_object(o)


# ═══════════════════════════════════════════════════════════════
# Build conspect blocks
# ═══════════════════════════════════════════════════════════════

def build_conspect():
    geo = StepByStepGeo(CAN3D, STY)
    ghex = StepByStepGeo(CAN_HEX, STY)
    blocks = []

    # ═══════ 1. Problem + prism ═══════
    blocks.append({"type": "text", "content": """## Задание 14. Стереометрия. Задача 2

В правильной шестиугольной призме $ABCDEF A_1B_1C_1D_1E_1F_1$, все рёбра которой равны 1, точка $G$ — середина ребра $A_1B_1$.

**Найдите угол между прямой $AG$ и плоскостью $BDD_1$.**

---

### Решение

Построим правильную шестиугольную призму."""})

    show_labels = {'A', 'B', 'D', 'A1', 'B1', 'D1'}
    for nm in VNAMES:
        for suf in ('', '1'):
            pid = nm + suf
            ldx, ldy = LBL3.get(pid, (8, -8))
            lbl = _lbl(pid) if pid in show_labels else ""
            _pt(geo, pid, p2[pid], lbl, ldx, ldy)

    for i in range(6):
        a, b = VNAMES[i], VNAMES[(i + 1) % 6]
        tag = a + b
        dash = tag in HIDDEN_BOT or (b + a) in HIDDEN_BOT
        sty = {"stroke": "#aaa", "dash": "dashed"} if dash else {"stroke": "#555"}
        _seg(geo, 'b_' + tag, a, b, sty)

    for i in range(6):
        a1, b1 = VNAMES[i] + '1', VNAMES[(i + 1) % 6] + '1'
        _seg(geo, 't_' + VNAMES[i] + VNAMES[(i + 1) % 6], a1, b1, {"stroke": "#555"})

    for nm in VNAMES:
        sty = {"stroke": "#aaa", "dash": "dashed"} if nm == 'C' else {"stroke": "#555"}
        _seg(geo, 'l_' + nm, nm, nm + '1', sty)

    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Правильная шестиугольная призма (рёбра = 1)"})

    # ═══════ 2. Mark G, draw AG ═══════
    blocks.append({"type": "text", "content": """Отметим точку $G$ — середину ребра $A_1B_1$ — и проведём отрезок $AG$."""})

    _pt(geo, 'G', p2['G'], 'G', *LBL3['G'],
        style={"fill": "#e74c3c", "stroke": "#e74c3c", "radius": 4})
    _seg(geo, 'AG', 'A', 'G', {"stroke": "#e74c3c", "stroke_width": 2})

    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Прямая AG (красная). G — середина A₁B₁"})

    # ═══════ 3. Plane BDD₁ ═══════
    blocks.append({"type": "text", "content": """Выделим плоскость $(BDD_1)$ — это прямоугольник $BDD_1B_1$ внутри призмы.

Прямая $AG$ и плоскость $BDD_1$ пересекаются **вне призмы**. Поэтому воспользуемся приёмом: проведём через точку $B_1 \\in (BDD_1)$ прямую, параллельную $AG$, и найдём угол с плоскостью для неё."""})

    _seg(geo, 'BD', 'B', 'D',
         {"stroke": "#2980b9", "stroke_width": 2, "dash": "dashed"})
    _seg(geo, 'B1D1', 'B1', 'D1',
         {"stroke": "#2980b9", "stroke_width": 2})

    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Плоскость BDD₁ (синие диагонали)"})

    # ═══════ 4. Construct B₁T ∥ AG ═══════
    blocks.append({"type": "text", "content": """Пусть $T$ — середина ребра $AB$.

$AT = GB_1 = \\frac{1}{2}$ и $AT \\parallel GB_1$ (оба — половины параллельных рёбер $AB$ и $A_1B_1$).

Значит, $ATB_1G$ — **параллелограмм**, и $B_1T \\parallel AG$.

Искомый угол между $AG$ и $(BDD_1)$ равен углу между $B_1T$ и $(BDD_1)$."""})

    _pt(geo, 'T', p2['T'], 'T', *LBL3['T'],
        style={"fill": "#27ae60", "stroke": "#27ae60", "radius": 4})
    _seg(geo, 'B1T', 'B1', 'T', {"stroke": "#27ae60", "stroke_width": 2})
    _seg(geo, 'AT_d', 'A', 'T', {"stroke": "#27ae60", "dash": "dashed"})
    _seg(geo, 'GB1_d', 'G', 'B1', {"stroke": "#27ae60", "dash": "dashed"})

    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Параллелограмм ATB₁G → B₁T ∥ AG"})

    # ═══════ 5. Hexagon base — prove ∠ABD = 90° ═══════
    blocks.append({"type": "text", "content": """### Доказательство: $TB \\perp DB$

Рассмотрим основание — правильный шестиугольник.

Угол правильного шестиугольника: $\\angle ABC = 120°$.

Треугольник $BCD$ равнобедренный ($BC = CD = 1$), значит:
$$\\angle DBC = \\angle BDC = \\frac{180° - 120°}{2} = 30°$$

Тогда:
$$\\angle ABD = \\angle ABC - \\angle DBC = 120° - 30° = 90°$$

Точка $T$ лежит на отрезке $AB$, значит $TB \\perp DB$."""})

    for nm in VNAMES:
        ldx, ldy = LBL_H.get(nm, (8, -8))
        _pt(ghex, 'h_' + nm, hpt(nm), nm, ldx, ldy)

    for i in range(6):
        a, b = VNAMES[i], VNAMES[(i + 1) % 6]
        _seg(ghex, 'hx_' + a + b, 'h_' + a, 'h_' + b, {"stroke": "#555"})

    _seg(ghex, 'hx_BD', 'h_B', 'h_D',
         {"stroke": "#2980b9", "stroke_width": 2})

    ldx, ldy = LBL_H['T']
    _pt(ghex, 'h_T', hpt('T'), 'T', ldx, ldy,
        style={"fill": "#27ae60", "stroke": "#27ae60", "radius": 4})
    _seg(ghex, 'hx_TB', 'h_T', 'h_B',
         {"stroke": "#27ae60", "stroke_width": 2})
    _seg(ghex, 'hx_AB_hi', 'h_A', 'h_T',
         {"stroke": "#27ae60", "dash": "dashed"})

    ghex.add_constraint({"type": "right_angle_marker", "id": "ra_hex",
                         "vertex": "h_B", "ray1": "h_T", "ray2": "h_D"})
    ghex.add_annotation({"type": "label", "id": "lbl_90h", "text": "90°",
                         "anchor": "h_B", "dx": -0.5, "dy": -0.4,
                         "color": "#e74c3c", "font_size": 14})
    ghex.add_annotation({"type": "label", "id": "lbl_120", "text": "120°",
                         "anchor": "h_B", "dx": -0.4, "dy": 0.3,
                         "color": "#888", "font_size": 11})

    ghex.snapshot()
    blocks.append({"type": "visual", "svg": ghex.steps[-1]["svg"],
                   "caption": "Основание: ∠ABD = 90° → TB ⊥ BD"})

    # ═══════ 6. TB ⊥ (BDD₁) — final 3D ═══════
    blocks.append({"type": "text", "content": """### $TB \\perp (BDD_1)$

Итак:
- $TB \\perp DB$ (доказано выше, в плоскости основания)
- $TB \\perp BB_1$ (так как $BB_1 \\perp (ABC)$ как боковое ребро призмы, а $TB$ лежит в $(ABC)$)

По **признаку перпендикулярности**: $TB$ перпендикулярна двум пересекающимся прямым ($DB$ и $BB_1$) в плоскости $(BDD_1)$, поэтому:

$$TB \\perp (BDD_1)$$

Значит, $B$ — проекция точки $T$ на $(BDD_1)$, а **искомый угол** — это $\\angle TB_1B$."""})

    _seg(geo, 'TB', 'T', 'B', {"stroke": "#e67e22", "stroke_width": 2})
    geo.add_annotation({"type": "label", "id": "lbl_perp", "text": "⊥",
                        "anchor": "T", "dx": -0.2, "dy": 0.15,
                        "color": "#e74c3c", "font_size": 16})
    geo.add_annotation({"type": "label", "id": "lbl_phi", "text": "φ",
                        "anchor": "B1", "dx": 0.3, "dy": 0.15,
                        "color": "#8e44ad", "font_size": 15})

    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "TB ⊥ (BDD₁). Угол φ = ∠TB₁B"})

    # ═══════ 7. Compute ═══════
    blocks.append({"type": "text", "content": """### Вычисление угла

В **прямоугольном треугольнике $TBB_1$** (прямой угол при $B$):

$$BT = \\frac{1}{2} AB = \\frac{1}{2}, \\qquad BB_1 = 1$$

$$\\tan \\varphi = \\frac{BT}{BB_1} = \\frac{1/2}{1} = \\frac{1}{2}$$

$$\\boxed{\\varphi = \\arctan \\frac{1}{2}}$$"""})

    geo.add_annotation({"type": "label", "id": "lbl_bt", "text": "BT = ½",
                        "anchor": "T", "dx": 0.1, "dy": 0.25,
                        "color": "#e67e22", "font_size": 12})
    geo.add_annotation({"type": "label", "id": "lbl_bb1", "text": "BB₁ = 1",
                        "anchor": "B", "dx": -0.55, "dy": 0.45,
                        "color": "#555", "font_size": 12})
    geo.add_annotation({"type": "label", "id": "lbl_ans", "text": "φ = arctan ½",
                        "anchor": "B1", "dx": 0.5, "dy": -0.35,
                        "color": "#8e44ad", "font_size": 14})

    geo.snapshot()
    blocks.append({"type": "visual", "svg": geo.steps[-1]["svg"],
                   "caption": "Ответ: φ = arctan(1/2)"})

    return blocks


# ═══════════════════════════════════════════════════════════════
# HTML
# ═══════════════════════════════════════════════════════════════

def render_md(text):
    lines = text.strip().split("\n")
    result = []
    for line in lines:
        s = line.strip()
        if s == "---":
            result.append('<hr style="border:none;border-top:1px solid #ddd;margin:24px 0;"/>')
        elif s.startswith("### "):
            result.append(f'<h3>{_fmt(s[4:])}</h3>')
        elif s.startswith("## "):
            result.append(f'<h2>{_fmt(s[3:])}</h2>')
        elif s.startswith("$$") and s.endswith("$$"):
            result.append(f'<div class="formula">{s}</div>')
        elif s.startswith("- "):
            result.append(f'<div style="padding-left:16px;">• {_fmt(s[2:])}</div>')
        elif s == "":
            result.append("<br/>")
        else:
            result.append(f'<p>{_fmt(s)}</p>')
    return "\n".join(result)


def _fmt(s):
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = s.replace("\\square", "\\(\\blacksquare\\)")
    return s


def generate_html(blocks):
    esc = html_mod.escape
    n_vis = sum(1 for b in blocks if b["type"] == "visual")

    html = [f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>Задание 14 ЕГЭ — Стереометрия (Задача 2)</title>
<script>
MathJax = {{
  tex: {{ inlineMath: [['$','$']], displayMath: [['$$','$$']] }},
  svg: {{ fontCache: 'global' }}
}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Georgia','PT Serif',serif; background:#faf9f6; color:#2c2c2c; line-height:1.85; }}
  .page-header {{ background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%); padding:36px 20px; text-align:center; color:white; }}
  .page-header h1 {{ font-size:24px; margin-bottom:6px; font-family:sans-serif; }}
  .page-header p {{ opacity:0.8; font-size:13px; font-family:sans-serif; }}
  .page-header a {{ color:#81d4fa; text-decoration:none; }}
  .conspect {{ max-width:740px; margin:0 auto; padding:32px 28px 60px; }}
  .text-block {{ margin:14px 0; font-size:16.5px; }}
  .text-block p {{ margin:5px 0; }}
  .text-block h2 {{ font-size:21px; color:#2c3e50; font-family:sans-serif; }}
  .text-block h3 {{ font-size:18px; color:#34495e; font-family:sans-serif; margin-top:18px; }}
  .text-block strong {{ color:#2c3e50; }}
  .formula {{ background:#f7f9fc; padding:14px 20px; border-radius:8px; margin:12px 0; text-align:center; border-left:3px solid #2980b9; }}
  .visual-block {{ margin:22px 0; text-align:center; }}
  .visual-frame {{ display:inline-block; background:white; border:1px solid #e0e0e0; border-radius:10px; padding:14px 18px; box-shadow:0 2px 10px rgba(0,0,0,0.06); }}
  .visual-frame svg {{ max-width:100%; height:auto; }}
  .visual-caption {{ font-family:-apple-system,sans-serif; font-size:13px; color:#777; margin-top:8px; font-style:italic; }}
  .footer {{ text-align:center; padding:30px 20px; color:#aaa; font-size:11px; font-family:sans-serif; border-top:1px solid #eee; }}
</style>
</head>
<body>
<div class="page-header">
  <h1>Задание 14 ЕГЭ. Стереометрия — Задача 2</h1>
  <p>Пошаговое решение: шестиугольная призма, угол между прямой и плоскостью</p>
  <p style="margin-top:6px;"><a href="https://ege-study.ru/zadanie-14-profilnogo-ege-po-matematike-stereometriya-zadacha-2/">Источник задачи: ege-study.ru</a></p>
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
  Стереометрия: 3D→2D косая проекция + StepByStepGeo → SVG |
  {n_vis} пошаговых построений
</div>
</body></html>""")
    return "\n".join(html)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    blocks = build_conspect()
    html = generate_html(blocks)
    out = OUTPUT_DIR / "task14_hex_prism.html"
    out.write_text(html, encoding="utf-8")
    n_t = sum(1 for b in blocks if b['type'] == 'text')
    n_v = sum(1 for b in blocks if b['type'] == 'visual')
    print(f"Report: {out}")
    print(f"Text: {n_t}, Visuals: {n_v}")

    # Verify answer
    BT = 0.5
    BB1 = 1
    phi = math.atan(BT / BB1)
    print(f"tan(φ) = {BT}/{BB1} = {BT/BB1}")
    print(f"φ = arctan(1/2) = {math.degrees(phi):.2f}°")


if __name__ == "__main__":
    main()
