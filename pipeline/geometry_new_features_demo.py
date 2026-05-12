"""
Демонстрация всех новых геометрических типов движка.

Запуск: python3 pipeline/geometry_new_features_demo.py

Генерирует pipeline/output_geometry/new_features_report.html
"""

import math
import sys
import html as html_mod
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.geometry_renderer import render_geometry_svg

OUTPUT_DIR = Path(__file__).resolve().parent / "output_geometry"


# ═══════════════════════════════════════════════════════════════
# Helper: regular polygon vertices
# ═══════════════════════════════════════════════════════════════

def regular_polygon_pts(cx, cy, r, n, start_angle=90):
    """Return list of (x, y) for a regular n-gon centred at (cx, cy)."""
    pts = []
    for i in range(n):
        a = math.radians(start_angle + 360 * i / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ═══════════════════════════════════════════════════════════════
# 1. Rectangle with diagonals & perpendicular
# ═══════════════════════════════════════════════════════════════

def scene_rectangle():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 420, "height": 320, "x_min": -1, "x_max": 9, "y_min": -1, "y_max": 7},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 10},
            {"type": "point", "id": "B", "x": 8, "y": 0, "label": "B", "label_dx": 8, "label_dy": 10},
            {"type": "point", "id": "C", "x": 8, "y": 5, "label": "C", "label_dx": 8, "label_dy": -8},
            {"type": "point", "id": "D", "x": 0, "y": 5, "label": "D", "label_dx": -14, "label_dy": -8},
            {"type": "polygon", "id": "rect", "vertices": ["A", "B", "C", "D"],
             "style": {"fill": "rgba(41,128,185,0.08)", "stroke": "#2980b9", "stroke_width": 2}},
            {"type": "segment", "id": "d_AC", "from_point": "A", "to_point": "C",
             "style": {"stroke": "#e74c3c", "dash": "dashed"}},
            {"type": "segment", "id": "d_BD", "from_point": "B", "to_point": "D",
             "style": {"stroke": "#e74c3c", "dash": "dashed"}},
        ],
        "constraints": [
            {"type": "right_angle_marker", "id": "ra_A", "vertex": "A", "ray1": "B", "ray2": "D"},
        ],
        "annotations": [
            {"type": "label", "id": "lbl_ab", "text": "a = 8", "anchor": "A", "dx": 3.5, "dy": -0.5, "color": "#2980b9"},
            {"type": "label", "id": "lbl_ad", "text": "b = 5", "anchor": "A", "dx": -0.8, "dy": 2.0, "color": "#2980b9"},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 2. Parallelogram
# ═══════════════════════════════════════════════════════════════

def scene_parallelogram():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 420, "height": 320, "x_min": -1, "x_max": 11, "y_min": -1, "y_max": 7},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 10},
            {"type": "point", "id": "B", "x": 7, "y": 0, "label": "B", "label_dx": 8, "label_dy": 10},
            {"type": "point", "id": "C", "x": 9, "y": 5, "label": "C", "label_dx": 8, "label_dy": -8},
            {"type": "point", "id": "D", "x": 2, "y": 5, "label": "D", "label_dx": -14, "label_dy": -8},
            {"type": "polygon", "id": "pgram", "vertices": ["A", "B", "C", "D"],
             "style": {"fill": "rgba(39,174,96,0.08)", "stroke": "#27ae60", "stroke_width": 2}},
            {"type": "segment", "id": "d_AC", "from_point": "A", "to_point": "C",
             "style": {"stroke": "#e67e22", "dash": "dashed"}},
            {"type": "segment", "id": "d_BD", "from_point": "B", "to_point": "D",
             "style": {"stroke": "#8e44ad", "dash": "dashed"}},
        ],
        "constraints": [],
        "annotations": [
            {"type": "label", "id": "lbl1", "text": "AB ∥ CD", "anchor": "A", "dx": 3.0, "dy": -0.5, "color": "#27ae60"},
            {"type": "label", "id": "lbl2", "text": "AD ∥ BC", "anchor": "D", "dx": -0.3, "dy": -2.0, "color": "#27ae60"},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 3. Regular hexagon
# ═══════════════════════════════════════════════════════════════

def scene_hexagon():
    pts = regular_polygon_pts(4, 4, 3.5, 6, start_angle=0)
    names = list("ABCDEF")
    offsets = [(10, 0), (10, -10), (-14, -10), (-14, 0), (-14, 10), (10, 10)]
    objects = []
    for i, (name, (x, y)) in enumerate(zip(names, pts)):
        objects.append({"type": "point", "id": name, "x": x, "y": y, "label": name,
                        "label_dx": offsets[i][0], "label_dy": offsets[i][1]})
    objects.append({
        "type": "polygon", "id": "hex", "vertices": names,
        "style": {"fill": "rgba(142,68,173,0.08)", "stroke": "#8e44ad", "stroke_width": 2}
    })
    objects.append({"type": "point", "id": "O", "x": 4, "y": 4, "label": "O"})
    for name in names:
        objects.append({"type": "segment", "id": f"r_{name}", "from_point": "O", "to_point": name,
                        "style": {"stroke": "#bbb", "dash": "dashed"}})
    return {
        "scene_type": "geometry",
        "canvas": {"width": 400, "height": 400, "x_min": -0.5, "x_max": 8.5, "y_min": -0.5, "y_max": 8.5},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": objects,
        "constraints": [],
        "annotations": [
            {"type": "label", "id": "lbl_r", "text": "R", "anchor": "O", "dx": 1.2, "dy": 0.5, "color": "#8e44ad"},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 4. Rhombus with diagonals & right angle marker
# ═══════════════════════════════════════════════════════════════

def scene_rhombus():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 400, "height": 360, "x_min": -1, "x_max": 9, "y_min": -1, "y_max": 7},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "A", "x": 0, "y": 3, "label": "A", "label_dx": -14, "label_dy": 0},
            {"type": "point", "id": "B", "x": 4, "y": 6, "label": "B", "label_dx": 0, "label_dy": -12},
            {"type": "point", "id": "C", "x": 8, "y": 3, "label": "C", "label_dx": 10, "label_dy": 0},
            {"type": "point", "id": "D", "x": 4, "y": 0, "label": "D", "label_dx": 0, "label_dy": 12},
            {"type": "point", "id": "O", "x": 4, "y": 3, "label": "O", "label_dx": 8, "label_dy": 8},
            {"type": "polygon", "id": "rhombus", "vertices": ["A", "B", "C", "D"],
             "style": {"fill": "rgba(230,126,34,0.08)", "stroke": "#e67e22", "stroke_width": 2}},
            {"type": "segment", "id": "d_AC", "from_point": "A", "to_point": "C",
             "style": {"stroke": "#2980b9", "stroke_width": 1.5}},
            {"type": "segment", "id": "d_BD", "from_point": "B", "to_point": "D",
             "style": {"stroke": "#e74c3c", "stroke_width": 1.5}},
        ],
        "constraints": [
            {"type": "right_angle_marker", "id": "ra_O", "vertex": "O", "ray1": "A", "ray2": "B"},
        ],
        "annotations": [
            {"type": "label", "id": "d1", "text": "d₁ = 8", "anchor": "A", "dx": 3.5, "dy": -0.5, "color": "#2980b9"},
            {"type": "label", "id": "d2", "text": "d₂ = 6", "anchor": "B", "dx": 0.5, "dy": -1.5, "color": "#e74c3c"},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 5. Trapezoid with midline
# ═══════════════════════════════════════════════════════════════

def scene_trapezoid_midline():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 440, "height": 320, "x_min": -1, "x_max": 12, "y_min": -1, "y_max": 7},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -12, "label_dy": 10},
            {"type": "point", "id": "B", "x": 3, "y": 5, "label": "B", "label_dx": -12, "label_dy": -8},
            {"type": "point", "id": "C", "x": 8, "y": 5, "label": "C", "label_dx": 8, "label_dy": -8},
            {"type": "point", "id": "D", "x": 11, "y": 0, "label": "D", "label_dx": 8, "label_dy": 10},
            {"type": "polygon", "id": "trap", "vertices": ["A", "B", "C", "D"],
             "style": {"fill": "rgba(26,188,156,0.08)", "stroke": "#1abc9c", "stroke_width": 2}},
        ],
        "constraints": [
            {"type": "midline", "id": "ml", "pairs": [["A", "B"], ["D", "C"]],
             "style": {"stroke": "#e74c3c", "dash": "dashed", "stroke_width": 2}},
        ],
        "annotations": [
            {"type": "label", "id": "lbl_ad", "text": "AD = 11", "anchor": "A", "dx": 5.0, "dy": -0.5, "color": "#1abc9c"},
            {"type": "label", "id": "lbl_bc", "text": "BC = 5", "anchor": "B", "dx": 2.0, "dy": 0.5, "color": "#1abc9c"},
            {"type": "label", "id": "lbl_ml", "text": "MN = 8", "anchor": "A", "dx": 5.0, "dy": 2.8, "color": "#e74c3c"},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 6. Circle with tangent lines
# ═══════════════════════════════════════════════════════════════

def scene_tangent():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 440, "height": 380, "x_min": -2, "x_max": 12, "y_min": -2, "y_max": 8},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "O", "x": 3, "y": 3, "label": "O", "label_dx": -14, "label_dy": -4},
            {"type": "circle", "id": "circ", "center": "O", "radius": 2.5,
             "style": {"stroke": "#2980b9", "stroke_width": 1.5}},
            {"type": "point", "id": "P", "x": 10, "y": 3, "label": "P", "label_dx": 8, "label_dy": 0},
        ],
        "constraints": [
            {"type": "tangent_line", "id": "tl1", "circle": "circ", "external_point": "P",
             "side": 1, "touch_id": "T1",
             "style": {"stroke": "#e74c3c", "stroke_width": 1.5}},
            {"type": "tangent_line", "id": "tl2", "circle": "circ", "external_point": "P",
             "side": -1, "touch_id": "T2",
             "style": {"stroke": "#e74c3c", "stroke_width": 1.5}},
        ],
        "annotations": [
            {"type": "label", "id": "lbl_r", "text": "r", "anchor": "O", "dx": 0.8, "dy": 1.0, "color": "#2980b9"},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 7. Sector and arc
# ═══════════════════════════════════════════════════════════════

def scene_sector_arc():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 420, "height": 380, "x_min": -1, "x_max": 9, "y_min": -1, "y_max": 7},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "O", "x": 4, "y": 3, "label": "O", "label_dx": -12, "label_dy": 8},
            {"type": "circle", "id": "c_full", "center": "O", "radius": 3,
             "style": {"stroke": "#ccc", "stroke_width": 1, "dash": "dotted"}},
            {"type": "sector", "id": "sec", "center": "O", "radius": 3,
             "start_angle": 20, "end_angle": 110,
             "style": {"fill": "rgba(41,128,185,0.18)", "stroke": "#2980b9", "stroke_width": 2}},
            {"type": "arc", "id": "arc1", "center": "O", "radius": 3,
             "start_angle": 200, "end_angle": 320,
             "style": {"stroke": "#e74c3c", "stroke_width": 2.5}},
        ],
        "constraints": [],
        "annotations": [
            {"type": "label", "id": "lbl_sec", "text": "сектор 90°", "anchor": "O",
             "dx": 0.8, "dy": 2.5, "color": "#2980b9", "font_size": 12},
            {"type": "label", "id": "lbl_arc", "text": "дуга 120°", "anchor": "O",
             "dx": -0.5, "dy": -2.8, "color": "#e74c3c", "font_size": 12},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 8. Cylinder
# ═══════════════════════════════════════════════════════════════

def scene_cylinder():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 340, "height": 400, "x_min": -1, "x_max": 7, "y_min": -1, "y_max": 9},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "O", "x": 3, "y": 1, "label": "O", "label_dx": 8, "label_dy": 10},
            {"type": "point", "id": "O1", "x": 3, "y": 7, "label": "O₁", "label_dx": 8, "label_dy": -8},
            {"type": "cylinder", "id": "cyl", "base_center": "O", "top_center": "O1",
             "radius": 2.2, "tilt": 0.28,
             "style": {"stroke": "#2980b9", "fill": "rgba(41,128,185,0.05)", "stroke_width": 1.8}},
            {"type": "segment", "id": "axis", "from_point": "O", "to_point": "O1",
             "style": {"stroke": "#e74c3c", "dash": "dashed"}},
        ],
        "constraints": [],
        "annotations": [
            {"type": "label", "id": "lbl_h", "text": "h", "anchor": "O", "dx": -0.8, "dy": 2.5, "color": "#e74c3c"},
            {"type": "label", "id": "lbl_r", "text": "R", "anchor": "O", "dx": 1.5, "dy": -0.3, "color": "#2980b9"},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 9. Cone
# ═══════════════════════════════════════════════════════════════

def scene_cone():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 340, "height": 400, "x_min": -1, "x_max": 7, "y_min": -1, "y_max": 9},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "O", "x": 3, "y": 1, "label": "O", "label_dx": 8, "label_dy": 10},
            {"type": "point", "id": "S", "x": 3, "y": 8, "label": "S", "label_dx": 8, "label_dy": -8},
            {"type": "cone", "id": "cone1", "base_center": "O", "apex": "S",
             "radius": 2.5, "tilt": 0.25,
             "style": {"stroke": "#27ae60", "fill": "rgba(39,174,96,0.05)", "stroke_width": 1.8}},
            {"type": "segment", "id": "height", "from_point": "O", "to_point": "S",
             "style": {"stroke": "#e74c3c", "dash": "dashed"}},
        ],
        "constraints": [],
        "annotations": [
            {"type": "label", "id": "lbl_h", "text": "h", "anchor": "O", "dx": -0.8, "dy": 3.0, "color": "#e74c3c"},
            {"type": "label", "id": "lbl_r", "text": "R", "anchor": "O", "dx": 1.5, "dy": -0.3, "color": "#27ae60"},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 10. Cube with cross-section  (oblique projection, manual 2D)
# ═══════════════════════════════════════════════════════════════

def scene_cube_cross_section():
    k = 0.4
    # bottom face (z=0): A B C D
    A = (1, 0)
    B = (6, 0)
    C = (6 + 5 * k, 5 * 0.2 + 0)
    D = (1 + 5 * k, 5 * 0.2)
    # top face (z=5): A1 B1 C1 D1
    A1 = (A[0], A[1] + 5)
    B1 = (B[0], B[1] + 5)
    C1 = (C[0], C[1] + 5)
    D1 = (D[0], D[1] + 5)
    # cross-section: midpoint AB → midpoint B1C1 → midpoint D1A1
    M = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
    N = ((B1[0] + C1[0]) / 2, (B1[1] + C1[1]) / 2)
    P = ((D1[0] + A1[0]) / 2, (D1[1] + A1[1]) / 2)

    all_pts = {"A": A, "B": B, "C": C, "D": D,
               "A1": A1, "B1": B1, "C1": C1, "D1": D1,
               "M": M, "N": N, "P": P}

    objects = []
    ldx_map = {"A": -14, "B": 8, "C": 10, "D": -14,
               "A1": -14, "B1": 8, "C1": 10, "D1": -14,
               "M": -8, "N": 10, "P": -14}
    ldy_map = {"A": 10, "B": 10, "C": 0, "D": 0,
               "A1": -8, "B1": -8, "C1": 0, "D1": 0,
               "M": 10, "N": 0, "P": 0}
    labels_map = {"A1": "A₁", "B1": "B₁", "C1": "C₁", "D1": "D₁"}

    for pid, (x, y) in all_pts.items():
        objects.append({"type": "point", "id": pid, "x": x, "y": y,
                        "label": labels_map.get(pid, pid),
                        "label_dx": ldx_map.get(pid, 8),
                        "label_dy": ldy_map.get(pid, -8)})

    edges = [
        ("A", "B"), ("B", "C"), ("A", "D"),
        ("A1", "B1"), ("B1", "C1"), ("C1", "D1"), ("D1", "A1"),
        ("A", "A1"), ("B", "B1"), ("C", "C1"), ("D", "D1"),
    ]
    hidden = {("B", "C"), ("A", "D"), ("D", "D1")}
    for i, (p1, p2) in enumerate(edges):
        st = {"stroke": "#aaa", "dash": "dashed"} if (p1, p2) in hidden else {"stroke": "#333"}
        objects.append({"type": "segment", "id": f"e_{i}", "from_point": p1, "to_point": p2, "style": st})

    # D-C edge (bottom back)
    objects.append({"type": "segment", "id": "e_dc", "from_point": "D", "to_point": "C",
                    "style": {"stroke": "#aaa", "dash": "dashed"}})

    return {
        "scene_type": "geometry",
        "canvas": {"width": 480, "height": 400, "x_min": -0.5, "x_max": 10, "y_min": -1, "y_max": 7},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": objects,
        "constraints": [
            {"type": "cross_section", "id": "cs", "vertices": ["M", "N", "P"],
             "style": {"fill": "rgba(155,89,182,0.2)", "stroke": "#8e44ad", "stroke_width": 2.5}},
        ],
        "annotations": [
            {"type": "label", "id": "lbl_cs", "text": "сечение", "anchor": "N",
             "dx": -2.5, "dy": 0.8, "color": "#8e44ad", "font_size": 14},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 11. Ellipse demo
# ═══════════════════════════════════════════════════════════════

def scene_ellipse():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 400, "height": 320, "x_min": -1, "x_max": 9, "y_min": -1, "y_max": 7},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "O", "x": 4, "y": 3, "label": "O", "label_dx": 8, "label_dy": 8},
            {"type": "point", "id": "F1", "x": 2.5, "y": 3, "label": "F₁", "label_dx": -6, "label_dy": 10},
            {"type": "point", "id": "F2", "x": 5.5, "y": 3, "label": "F₂", "label_dx": 6, "label_dy": 10},
            {"type": "ellipse", "id": "ell", "center": "O", "rx": 3.5, "ry": 2.2,
             "style": {"stroke": "#2980b9", "stroke_width": 2}},
            {"type": "segment", "id": "f1f2", "from_point": "F1", "to_point": "F2",
             "style": {"stroke": "#e74c3c", "dash": "dashed"}},
        ],
        "constraints": [],
        "annotations": [
            {"type": "label", "id": "lbl_a", "text": "a", "anchor": "O", "dx": 2.0, "dy": -0.3, "color": "#2980b9"},
            {"type": "label", "id": "lbl_b", "text": "b", "anchor": "O", "dx": 0.3, "dy": 1.5, "color": "#2980b9"},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 12. Triangle with midline (connects midpoints of two sides)
# ═══════════════════════════════════════════════════════════════

def scene_triangle_midline():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 420, "height": 360, "x_min": -1, "x_max": 9, "y_min": -1, "y_max": 7},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "A", "x": 0, "y": 0, "label": "A", "label_dx": -14, "label_dy": 10},
            {"type": "point", "id": "B", "x": 8, "y": 0, "label": "B", "label_dx": 8, "label_dy": 10},
            {"type": "point", "id": "C", "x": 3, "y": 6, "label": "C", "label_dx": -8, "label_dy": -12},
            {"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"],
             "style": {"fill": "rgba(52,152,219,0.06)"}},
        ],
        "constraints": [
            {"type": "midline", "id": "ml", "pairs": [["A", "C"], ["B", "C"]],
             "style": {"stroke": "#e74c3c", "stroke_width": 2, "dash": "dashed"}},
        ],
        "annotations": [
            {"type": "label", "id": "lbl_ml", "text": "средняя линия ∥ AB", "anchor": "C",
             "dx": 1.2, "dy": -1.5, "color": "#e74c3c", "font_size": 12},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 13. Perpendicular from point to line
# ═══════════════════════════════════════════════════════════════

def scene_perpendicular():
    return {
        "scene_type": "geometry",
        "canvas": {"width": 420, "height": 320, "x_min": -1, "x_max": 9, "y_min": -1, "y_max": 7},
        "style": {"stroke_color": "#333", "font_size": 13, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "A", "x": 0, "y": 1, "label": "A", "label_dx": -12, "label_dy": 8},
            {"type": "point", "id": "B", "x": 8, "y": 3, "label": "B", "label_dx": 8, "label_dy": 8},
            {"type": "point", "id": "P", "x": 3, "y": 6, "label": "P", "label_dx": -12, "label_dy": -8},
            {"type": "segment", "id": "line_AB", "from_point": "A", "to_point": "B",
             "style": {"stroke": "#2980b9", "stroke_width": 2}},
        ],
        "constraints": [
            {"type": "perpendicular", "id": "perp1", "point": "P",
             "line_point1": "A", "line_point2": "B", "foot_id": "H",
             "style": {"stroke": "#e74c3c", "dash": "dashed", "stroke_width": 1.5}},
        ],
        "annotations": [
            {"type": "label", "id": "lbl_h", "text": "H", "anchor": "A", "dx": 2.3, "dy": 0.3,
             "color": "#e74c3c", "font_size": 14},
        ],
    }


# ═══════════════════════════════════════════════════════════════
# HTML report
# ═══════════════════════════════════════════════════════════════

SCENES = [
    ("Прямоугольник (polygon + right_angle_marker)", scene_rectangle),
    ("Параллелограмм (polygon + диагонали)", scene_parallelogram),
    ("Правильный шестиугольник (polygon)", scene_hexagon),
    ("Ромб (polygon + перпенд. диагонали)", scene_rhombus),
    ("Трапеция + средняя линия (midline)", scene_trapezoid_midline),
    ("Треугольник + средняя линия (midline)", scene_triangle_midline),
    ("Касательные к окружности (tangent_line)", scene_tangent),
    ("Сектор и дуга (sector + arc)", scene_sector_arc),
    ("Эллипс (ellipse)", scene_ellipse),
    ("Цилиндр (cylinder)", scene_cylinder),
    ("Конус (cone)", scene_cone),
    ("Куб с сечением (cross_section)", scene_cube_cross_section),
    ("Перпендикуляр к прямой (perpendicular)", scene_perpendicular),
]


def generate_report():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    esc = html_mod.escape

    cards = []
    for title, builder in SCENES:
        scene = builder()
        svg = render_geometry_svg(scene)
        cards.append((title, svg))
        print(f"  ✓ {title}")

    parts = [f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"/>
<title>Новые геометрические типы — демо</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#f5f5f7; color:#1d1d1f; }}
  .header {{ background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460); padding:40px 20px;
             text-align:center; color:white; }}
  .header h1 {{ font-size:28px; margin-bottom:8px; }}
  .header p {{ opacity:0.75; font-size:14px; }}
  .grid {{ max-width:1100px; margin:32px auto; padding:0 20px;
           display:grid; grid-template-columns:repeat(auto-fill,minmax(460px,1fr)); gap:24px; }}
  .card {{ background:white; border-radius:14px; overflow:hidden;
           box-shadow:0 2px 12px rgba(0,0,0,0.06); }}
  .card-title {{ padding:14px 20px; font-size:15px; font-weight:600; color:#2c3e50;
                 border-bottom:1px solid #eee; }}
  .card-body {{ padding:16px; text-align:center; }}
  .card-body svg {{ max-width:100%; height:auto; }}
  .footer {{ text-align:center; padding:30px 20px; color:#aaa; font-size:11px;
             border-top:1px solid #eee; margin-top:20px; }}
</style></head><body>
<div class="header">
  <h1>Новые геометрические типы</h1>
  <p>polygon · ellipse · arc · sector · cylinder · cone · midline · tangent_line · cross_section · perpendicular</p>
</div>
<div class="grid">
"""]

    for title, svg in cards:
        parts.append(f"""<div class="card">
  <div class="card-title">{esc(title)}</div>
  <div class="card-body">{svg}</div>
</div>""")

    parts.append(f"""</div>
<div class="footer">{len(cards)} фигур · geometry_renderer.py · {len(SCENES)} сцен</div>
</body></html>""")

    out = OUTPUT_DIR / "new_features_report.html"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"\n[new_features_demo] Report: {out}")
    return out


if __name__ == "__main__":
    generate_report()
