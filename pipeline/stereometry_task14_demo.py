"""
Semi-automated step-by-step stereometry demo for EGE Task 14.

Regular triangular pyramid SABC:
  - Height SO = 4
  - Angle between lateral face SBC and base = 60°
  - Find: distance from vertex A to plane SBC

Source: https://ege-study.ru/45703-2/

Uses oblique 3D→2D projection for the pyramid view,
plus a flat 2D cross-section of plane ASM for the calculation.
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
    """Oblique cabinet projection: y-depth into page, z-height up."""
    x2 = x3 - y3 * 0.35
    y2 = z3 + y3 * 0.25
    return round(x2 + 6, 2), round(y2 + 2.5, 2)


# ═══════════════════════════════════════════════════════════════
# Computed 3D coordinates
# ═══════════════════════════════════════════════════════════════

SO = 4
OM = SO / math.sqrt(3)           # ≈ 2.309
AM_len = 3 * OM                  # ≈ 6.928
side = 8                         # equilateral triangle side
SM_len = 2 * OM                  # ≈ 4.619

# 3D: base in z=0, y-axis is depth (A in front, BC behind)
A3 = (0,        AM_len * 2/3, 0)    # (0, 4.62, 0) — front vertex
B3 = (-side/2, -AM_len / 3,  0)     # (-4, -2.31, 0) — back-left
C3 = ( side/2, -AM_len / 3,  0)     # (4, -2.31, 0) — back-right
S3 = (0, 0, SO)                      # (0, 0, 4) — apex
O3 = (0, 0, 0)                       # center of base
M3 = (0, -AM_len / 3, 0)            # midpoint of BC

# H = foot of perpendicular from A to line SM (in plane ASM, x=0)
dy = M3[1] - S3[1]
dz = M3[2] - S3[2]
t_H = ((A3[1] - S3[1]) * dy + (A3[2] - S3[2]) * dz) / (dy*dy + dz*dz)
H3 = (0, S3[1] + t_H * dy, S3[2] + t_H * dz)

AH_dist = math.sqrt((A3[1]-H3[1])**2 + (A3[2]-H3[2])**2)

# 2D projections for pyramid view
A  = proj(*A3)
B  = proj(*B3)
C  = proj(*C3)
S  = proj(*S3)
O  = proj(*O3)
M  = proj(*M3)
H  = proj(*H3)

# Cross-section coordinates (plane ASM in y-z as flat 2D)
CS_OX, CS_OY = 2.5, 0.5
A_cs = (round(A3[1] * 0.85 + CS_OX, 2), round(A3[2] * 0.85 + CS_OY, 2))
S_cs = (round(S3[1] * 0.85 + CS_OX, 2), round(S3[2] * 0.85 + CS_OY, 2))
M_cs = (round(M3[1] * 0.85 + CS_OX, 2), round(M3[2] * 0.85 + CS_OY, 2))
O_cs = (round(O3[1] * 0.85 + CS_OX, 2), round(O3[2] * 0.85 + CS_OY, 2))
H_cs = (round(H3[1] * 0.85 + CS_OX, 2), round(H3[2] * 0.85 + CS_OY, 2))

# Canvas parameters
CANVAS_3D = {
    "width": 560, "height": 420,
    "x_min": 0.5, "x_max": 12.5, "y_min": 0.5, "y_max": 8.5
}
CANVAS_CS = {
    "width": 560, "height": 340,
    "x_min": -1.5, "x_max": 8.5, "y_min": -0.5, "y_max": 5.5
}
STYLE = {
    "theme": "light", "stroke_color": "#333333", "fill_color": "none",
    "font_size": 13, "font_family": "sans-serif"
}


# ═══════════════════════════════════════════════════════════════
# Build conspect blocks (text + visual interleaved)
# ═══════════════════════════════════════════════════════════════

def build_conspect():
    geo3d = StepByStepGeo(CANVAS_3D, STYLE)
    geo_cs = StepByStepGeo(CANVAS_CS, STYLE)
    blocks = []

    # ── STEP 1: Problem statement + base triangle ──
    blocks.append({"type": "text", "content": """## Задание 14. Стереометрия. Задача 1

Высота правильной треугольной пирамиды равна 4, а угол между боковой гранью и плоскостью основания равен $60°$.

**Найдите расстояние от вершины основания до плоскости противолежащей ей боковой грани.**

---

### Решение

Пусть $SABC$ — правильная треугольная пирамида с вершиной $S$ и основанием $ABC$.

Построим основание — правильный треугольник $ABC$."""})

    for pid, pt, lbl, ldx, ldy in [
        ("A", A, "A", -12, 10),
        ("B", B, "B", -14, 6),
        ("C", C, "C", 8, 6),
    ]:
        geo3d.add_object({
            "type": "point", "id": pid,
            "x": pt[0], "y": pt[1], "label": lbl,
            "label_dx": ldx, "label_dy": ldy
        })
    geo3d.add_object({"type": "segment", "id": "AB", "from_point": "A", "to_point": "B",
                       "style": {"stroke": "#2980b9", "stroke_width": 1.8}})
    geo3d.add_object({"type": "segment", "id": "AC", "from_point": "A", "to_point": "C",
                       "style": {"stroke": "#2980b9", "stroke_width": 1.8}})
    geo3d.add_object({"type": "segment", "id": "BC", "from_point": "B", "to_point": "C",
                       "style": {"stroke": "#2980b9", "dash": "dashed"}})
    geo3d.snapshot()
    blocks.append({"type": "visual", "svg": geo3d.steps[-1]["svg"],
                   "caption": "Основание пирамиды — правильный треугольник ABC"})

    # ── STEP 2: Apex S + lateral edges ──
    blocks.append({"type": "text", "content": """Добавим вершину $S$ и боковые рёбра $SA$, $SB$, $SC$.

Высота пирамиды $SO = 4$ опущена из $S$ в центр основания $O$."""})

    geo3d.add_object({"type": "point", "id": "S",
                       "x": S[0], "y": S[1], "label": "S",
                       "label_dx": 8, "label_dy": -8})
    geo3d.add_object({"type": "segment", "id": "SA", "from_point": "S", "to_point": "A",
                       "style": {"stroke": "#333"}})
    geo3d.add_object({"type": "segment", "id": "SB", "from_point": "S", "to_point": "B",
                       "style": {"stroke": "#333"}})
    geo3d.add_object({"type": "segment", "id": "SC", "from_point": "S", "to_point": "C",
                       "style": {"stroke": "#333"}})
    geo3d.add_object({"type": "point", "id": "O",
                       "x": O[0], "y": O[1], "label": "O",
                       "label_dx": 8, "label_dy": 8,
                       "style": {"fill": "#e74c3c", "stroke": "#e74c3c", "radius": 3}})
    geo3d.add_object({"type": "segment", "id": "SO", "from_point": "S", "to_point": "O",
                       "style": {"dash": "dashed", "stroke": "#e74c3c", "stroke_width": 1.5}})
    geo3d.add_annotation({"type": "label", "id": "lbl_SO", "text": "SO = 4",
                          "anchor": "S", "dx": 0.5, "dy": -0.6, "color": "#e74c3c", "font_size": 12})
    geo3d.snapshot()
    blocks.append({"type": "visual", "svg": geo3d.steps[-1]["svg"],
                   "caption": "Правильная треугольная пирамида SABC, SO = 4"})

    # ── STEP 3: Medians AM, SM and angle ──
    blocks.append({"type": "text", "content": """Пусть $M$ — середина $BC$.

- $AM$ — медиана и высота правильного треугольника $ABC$, значит $AM \\perp BC$.
- $SM$ — медиана и высота равнобедренного треугольника $SBC$, значит $SM \\perp BC$.

Отсюда следует, что плоскость $(ASM) \\perp BC$, а **угол $AMS$** — это двугранный угол между боковой гранью $SBC$ и основанием.

$$\\angle AMS = 60°$$"""})

    geo3d.add_object({"type": "point", "id": "M",
                       "x": M[0], "y": M[1], "label": "M",
                       "label_dx": 8, "label_dy": 10,
                       "style": {"fill": "#27ae60", "stroke": "#27ae60", "radius": 3}})
    geo3d.add_object({"type": "segment", "id": "AM", "from_point": "A", "to_point": "M",
                       "style": {"dash": "dashed", "stroke": "#27ae60", "stroke_width": 1.5}})
    geo3d.add_object({"type": "segment", "id": "SM", "from_point": "S", "to_point": "M",
                       "style": {"stroke": "#8e44ad", "stroke_width": 1.8}})
    geo3d.add_annotation({"type": "label", "id": "lbl_60", "text": "60°",
                          "anchor": "M", "dx": -0.6, "dy": 0.5, "color": "#e74c3c", "font_size": 13})
    geo3d.snapshot()
    blocks.append({"type": "visual", "svg": geo3d.steps[-1]["svg"],
                   "caption": "M — середина BC. ∠AMS = 60° — угол между гранью SBC и основанием"})

    # ── STEP 4: Cross-section — triangle ASM ──
    blocks.append({"type": "text", "content": """### Сечение плоскостью ASM

Рассмотрим плоское сечение пирамиды плоскостью $ASM$ (проходящей через вершину $A$, точку $M$ и вершину $S$).

В этом сечении — треугольник $ASM$, а точка $O$ лежит на $AM$ (центр основания)."""})

    for pid, pt, lbl, ldx, ldy, col in [
        ("cA", A_cs, "A", 8, 14, "#333"),
        ("cS", S_cs, "S", -14, -8, "#333"),
        ("cM", M_cs, "M", -14, 14, "#333"),
        ("cO", O_cs, "O", 8, 8, "#e74c3c"),
    ]:
        st = {"fill": col, "stroke": col, "radius": 4}
        if col == "#e74c3c":
            st["radius"] = 3
        geo_cs.add_object({
            "type": "point", "id": pid,
            "x": pt[0], "y": pt[1], "label": lbl,
            "label_dx": ldx, "label_dy": ldy,
            "style": st,
        })
    geo_cs.add_object({"type": "segment", "id": "cs_AM", "from_point": "cA", "to_point": "cM",
                        "style": {"stroke": "#27ae60", "stroke_width": 1.8}})
    geo_cs.add_object({"type": "segment", "id": "cs_SM", "from_point": "cS", "to_point": "cM",
                        "style": {"stroke": "#8e44ad", "stroke_width": 1.8}})
    geo_cs.add_object({"type": "segment", "id": "cs_AS", "from_point": "cA", "to_point": "cS",
                        "style": {"stroke": "#333", "stroke_width": 1.5}})
    geo_cs.add_object({"type": "segment", "id": "cs_SO", "from_point": "cS", "to_point": "cO",
                        "style": {"dash": "dashed", "stroke": "#e74c3c", "stroke_width": 1.5}})
    geo_cs.add_annotation({"type": "label", "id": "cs_lbl_60", "text": "60°",
                           "anchor": "cM", "dx": 0.6, "dy": 0.3, "color": "#e74c3c", "font_size": 14})
    geo_cs.snapshot()
    blocks.append({"type": "visual", "svg": geo_cs.steps[-1]["svg"],
                   "caption": "Сечение пирамиды плоскостью ASM"})

    # ── STEP 5: Compute OM, SM, AM from triangle SOM ──
    blocks.append({"type": "text", "content": f"""### Вычисления в сечении

Из прямоугольного треугольника $SOM$ (угол $O$ = 90°, угол $M$ = 60°):

$$\\tan 60° = \\frac{{SO}}{{OM}} \\quad \\Rightarrow \\quad \\sqrt{{3}} = \\frac{{4}}{{OM}} \\quad \\Rightarrow \\quad OM = \\frac{{4}}{{\\sqrt{{3}}}}$$

$$SM = \\frac{{SO}}{{\\sin 60°}} = \\frac{{4}}{{\\sqrt{{3}}/2}} = \\frac{{8}}{{\\sqrt{{3}}}}$$

По свойству правильного треугольника точка $O$ делит медиану $AM$ в отношении $2:1$ от вершины:

$$AM = 3 \\cdot OM = \\frac{{12}}{{\\sqrt{{3}}}} = 4\\sqrt{{3}}$$"""})

    geo_cs.add_constraint({"type": "right_angle_marker", "id": "cs_ra_O",
                           "vertex": "cO", "ray1": "cS", "ray2": "cM"})
    geo_cs.add_annotation({"type": "label", "id": "cs_lbl_SO", "text": "SO = 4",
                           "anchor": "cS", "dx": 0.3, "dy": -0.5, "color": "#e74c3c", "font_size": 12})
    geo_cs.add_annotation({"type": "label", "id": "cs_lbl_OM", "text": "OM = 4/√3",
                           "anchor": "cO", "dx": -0.3, "dy": 0.3, "color": "#27ae60", "font_size": 12})
    geo_cs.add_annotation({"type": "label", "id": "cs_lbl_SM", "text": "SM = 8/√3",
                           "anchor": "cM", "dx": -0.8, "dy": 0.8, "color": "#8e44ad", "font_size": 12})
    geo_cs.snapshot()
    blocks.append({"type": "visual", "svg": geo_cs.steps[-1]["svg"],
                   "caption": "Прямоугольный треугольник SOM: вычисляем OM, SM, AM"})

    # ── STEP 6: Draw AH perpendicular to SM ──
    blocks.append({"type": "text", "content": """### Расстояние от A до плоскости SBC

Проведём $AH \\perp SM$ в плоскости $(ASM)$.

Поскольку $AH \\perp SM$ и $AH \\perp BC$ (так как $AH \\in (ASM)$ и $(ASM) \\perp BC$), отрезок $AH$ перпендикулярен двум пересекающимся прямым в плоскости $SBC$.

**Значит, $AH \\perp (SBC)$ и $|AH|$ — искомое расстояние.**"""})

    geo_cs.add_object({"type": "point", "id": "cH",
                        "x": H_cs[0], "y": H_cs[1], "label": "H",
                        "label_dx": -14, "label_dy": -8,
                        "style": {"fill": "#e67e22", "stroke": "#e67e22", "radius": 3}})
    geo_cs.add_object({"type": "segment", "id": "cs_AH", "from_point": "cA", "to_point": "cH",
                        "style": {"dash": "dashed", "stroke": "#e67e22", "stroke_width": 2}})
    geo_cs.add_constraint({"type": "right_angle_marker", "id": "cs_ra_H",
                           "vertex": "cH", "ray1": "cA", "ray2": "cM"})
    geo_cs.snapshot()
    blocks.append({"type": "visual", "svg": geo_cs.steps[-1]["svg"],
                   "caption": "AH ⊥ SM — расстояние от A до плоскости SBC"})

    # ── STEP 7: Area calculation ──
    blocks.append({"type": "text", "content": """### Вычисление AH методом площадей

Запишем площадь треугольника $ASM$ двумя способами:

$$S_{ASM} = \\frac{1}{2} \\cdot AM \\cdot SO = \\frac{1}{2} \\cdot SM \\cdot AH$$

Первое равенство: основание $AM$, высота $SO$ ($SO \\perp AM$, так как $SO$ — высота пирамиды).

Подставляем:

$$\\frac{1}{2} \\cdot \\frac{12}{\\sqrt{3}} \\cdot 4 = \\frac{1}{2} \\cdot \\frac{8}{\\sqrt{3}} \\cdot AH$$

$$\\frac{48}{\\sqrt{3}} = \\frac{8}{\\sqrt{3}} \\cdot AH$$

$$\\boxed{AH = 6}$$"""})

    geo_cs.add_annotation({"type": "label", "id": "cs_lbl_AH", "text": "AH = 6",
                           "anchor": "cH", "dx": 0.7, "dy": 0.4, "color": "#e67e22", "font_size": 15})
    geo_cs.snapshot()
    blocks.append({"type": "visual", "svg": geo_cs.steps[-1]["svg"],
                   "caption": "Ответ: AH = 6"})

    # ── STEP 8: Final 3D view with AH ──
    geo3d.add_object({"type": "point", "id": "H",
                       "x": H[0], "y": H[1], "label": "H",
                       "label_dx": 10, "label_dy": -4,
                       "style": {"fill": "#e67e22", "stroke": "#e67e22", "radius": 3}})
    geo3d.add_object({"type": "segment", "id": "AH", "from_point": "A", "to_point": "H",
                       "style": {"dash": "dashed", "stroke": "#e67e22", "stroke_width": 2}})
    geo3d.add_constraint({"type": "right_angle_marker", "id": "ra_H",
                          "vertex": "H", "ray1": "A", "ray2": "M"})
    geo3d.add_annotation({"type": "label", "id": "lbl_AH", "text": "AH = 6",
                          "anchor": "H", "dx": 0.5, "dy": 0.3,
                          "color": "#e67e22", "font_size": 14})
    geo3d.snapshot()
    blocks.append({"type": "visual", "svg": geo3d.steps[-1]["svg"],
                   "caption": "Итоговый чертёж: AH ⊥ (SBC), AH = 6"})

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
    n_visuals = sum(1 for b in blocks if b["type"] == "visual")

    html = [f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>Задание 14 ЕГЭ — Стереометрия</title>
<script>
MathJax = {{
  tex: {{ inlineMath: [['$','$']], displayMath: [['$$','$$']] }},
  svg: {{ fontCache: 'global' }}
}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Georgia','PT Serif',serif; background:#faf9f6; color:#2c2c2c; line-height:1.85; }}
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
  <h1>Задание 14 ЕГЭ по математике. Стереометрия</h1>
  <p>Пошаговое решение с 3D-визуализацией (косая проекция → SVG)</p>
  <p style="margin-top:6px;"><a href="https://ege-study.ru/45703-2/">Источник задачи: ege-study.ru</a></p>
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
  Стереометрия: 3D→2D косая проекция + StepByStepGeo → Solver → SVG Renderer |
  {n_visuals} пошаговых построений
</div>
</body></html>""")
    return "\n".join(html)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    blocks = build_conspect()
    html = generate_html(blocks)
    out = OUTPUT_DIR / "task14_stereometry.html"
    out.write_text(html, encoding="utf-8")
    n = sum(1 for b in blocks if b["type"] == "visual")
    print(f"Report: {out}")
    print(f"Text blocks: {sum(1 for b in blocks if b['type'] == 'text')}, visuals: {n}")
    print(f"AH = {AH_dist:.4f} (expected 6.0)")


if __name__ == "__main__":
    main()
