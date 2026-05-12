"""
Geometry SVG renderer — self-contained, based on the colleague's svg-generator.

Scene JSON format:
  - scene_type: "geometry"
  - objects: point, segment, triangle, polygon, circle, ellipse, arc, sector,
             cylinder, cone, label
  - constraints: altitude, median, bisector, midpoint, right_angle_marker,
                 angle_arc, midline, tangent_line, cross_section, perpendicular,
                 intersection
  - annotations: label objects

Also provides StepByStepGeo for progressive construction rendering.
"""

import copy
import math
import html as html_mod


# ═══════════════════════════════════════════════════════════════
# Solver — resolves constraints into concrete points/segments
# (port of svg-generator/service/app/solver/solver.py)
# ═══════════════════════════════════════════════════════════════

def solve_constraints(scene: dict) -> tuple[dict, list[str]]:
    """Process constraints, add computed points/segments to objects list."""
    warnings = []
    new_objs = list(scene.get("objects", []))

    pts = {}
    objs_by_id = {}
    for obj in new_objs:
        objs_by_id[obj["id"]] = obj
        if obj["type"] == "point":
            pts[obj["id"]] = obj

    existing_ids = set(objs_by_id.keys())

    def _add(obj):
        if obj["id"] not in existing_ids:
            new_objs.append(obj)
            objs_by_id[obj["id"]] = obj
            existing_ids.add(obj["id"])
            if obj["type"] == "point":
                pts[obj["id"]] = obj

    for c in scene.get("constraints", []):
        ctype = c.get("type")

        if ctype == "midpoint":
            seg = objs_by_id.get(c.get("segment"))
            if not seg:
                continue
            p1, p2 = pts.get(seg["from_point"]), pts.get(seg["to_point"])
            if not p1 or not p2:
                continue
            _add({"type": "point", "id": c["result_id"],
                  "x": (p1["x"] + p2["x"]) / 2,
                  "y": (p1["y"] + p2["y"]) / 2})

        elif ctype == "median":
            tri = objs_by_id.get(c.get("triangle"))
            if not tri or c["vertex"] not in tri["vertices"]:
                continue
            others = [v for v in tri["vertices"] if v != c["vertex"]]
            pv, p1, p2 = pts.get(c["vertex"]), pts.get(others[0]), pts.get(others[1])
            if not all([pv, p1, p2]):
                continue
            mid_id = f"{c['id']}_mid"
            seg_id = f"{c['id']}_seg"
            _add({"type": "point", "id": mid_id,
                  "x": (p1["x"] + p2["x"]) / 2,
                  "y": (p1["y"] + p2["y"]) / 2})
            _add({"type": "segment", "id": seg_id,
                  "from_point": c["vertex"], "to_point": mid_id})

        elif ctype == "altitude":
            tri = objs_by_id.get(c.get("triangle"))
            if not tri or c["vertex"] not in tri["vertices"]:
                continue
            others = [v for v in tri["vertices"] if v != c["vertex"]]
            pv = pts.get(c["vertex"])
            p1, p2 = pts.get(others[0]), pts.get(others[1])
            if not all([pv, p1, p2]):
                continue
            dx, dy = p2["x"] - p1["x"], p2["y"] - p1["y"]
            denom = dx * dx + dy * dy
            if denom == 0:
                continue
            t = ((pv["x"] - p1["x"]) * dx + (pv["y"] - p1["y"]) * dy) / denom
            foot_id = f"{c['id']}_foot"
            seg_id = f"{c['id']}_seg"
            _add({"type": "point", "id": foot_id,
                  "x": p1["x"] + t * dx, "y": p1["y"] + t * dy})
            _add({"type": "segment", "id": seg_id,
                  "from_point": c["vertex"], "to_point": foot_id,
                  "style": {"dash": "dashed", "stroke": "#e74c3c"}})

        elif ctype == "bisector":
            tri = objs_by_id.get(c.get("triangle"))
            if not tri or c["vertex"] not in tri["vertices"]:
                continue
            others = [v for v in tri["vertices"] if v != c["vertex"]]
            pv = pts.get(c["vertex"])
            p1, p2 = pts.get(others[0]), pts.get(others[1])
            if not all([pv, p1, p2]):
                continue
            d1 = math.dist((pv["x"], pv["y"]), (p1["x"], p1["y"]))
            d2 = math.dist((pv["x"], pv["y"]), (p2["x"], p2["y"]))
            total = d1 + d2
            if total == 0:
                continue
            bx = (d2 * p1["x"] + d1 * p2["x"]) / total
            by = (d2 * p1["y"] + d1 * p2["y"]) / total
            bis_id = f"{c['id']}_pt"
            seg_id = f"{c['id']}_seg"
            _add({"type": "point", "id": bis_id, "x": bx, "y": by})
            _add({"type": "segment", "id": seg_id,
                  "from_point": c["vertex"], "to_point": bis_id,
                  "style": {"dash": "dashed", "stroke": "#27ae60"}})

        elif ctype == "circumscribed_circle":
            tri = objs_by_id.get(c.get("triangle"))
            if not tri:
                continue
            verts = [pts.get(v) for v in tri["vertices"]]
            if not all(verts):
                continue
            cc = _circumcenter(*verts)
            if cc is None:
                continue
            cx, cy, r = cc
            center_id = c.get("center_id", f"{c['id']}_center")
            _add({"type": "point", "id": center_id, "x": cx, "y": cy, "label": "O"})
            _add({"type": "circle", "id": f"{c['id']}_circ",
                  "center": center_id, "radius": r,
                  "style": {"stroke": "#2980b9", "dash": "dashed"}})

        elif ctype == "inscribed_circle":
            tri = objs_by_id.get(c.get("triangle"))
            if not tri:
                continue
            verts = [pts.get(v) for v in tri["vertices"]]
            if not all(verts):
                continue
            ic = _incircle(*verts)
            if ic is None:
                continue
            cx, cy, r = ic
            center_id = c.get("center_id", f"{c['id']}_center")
            _add({"type": "point", "id": center_id, "x": cx, "y": cy, "label": "I"})
            _add({"type": "circle", "id": f"{c['id']}_circ",
                  "center": center_id, "radius": r,
                  "style": {"stroke": "#e67e22", "dash": "dashed"}})

        elif ctype == "midline":
            pairs = c.get("pairs")
            if not pairs or len(pairs) != 2:
                continue
            p1 = pts.get(pairs[0][0])
            p2 = pts.get(pairs[0][1])
            p3 = pts.get(pairs[1][0])
            p4 = pts.get(pairs[1][1])
            if not all([p1, p2, p3, p4]):
                continue
            mid1_id = f"{c['id']}_mid1"
            mid2_id = f"{c['id']}_mid2"
            _add({"type": "point", "id": mid1_id,
                  "x": (p1["x"] + p2["x"]) / 2,
                  "y": (p1["y"] + p2["y"]) / 2})
            _add({"type": "point", "id": mid2_id,
                  "x": (p3["x"] + p4["x"]) / 2,
                  "y": (p3["y"] + p4["y"]) / 2})
            _add({"type": "segment", "id": f"{c['id']}_seg",
                  "from_point": mid1_id, "to_point": mid2_id,
                  "style": c.get("style", {"stroke": "#8e44ad", "dash": "dashed"})})

        elif ctype == "tangent_line":
            circle_obj = objs_by_id.get(c.get("circle"))
            if not circle_obj:
                continue
            center = pts.get(circle_obj.get("center"))
            if not center:
                continue
            r = circle_obj.get("radius", 1)
            if c.get("external_point"):
                ext = pts.get(c["external_point"])
                if not ext:
                    continue
                tdx = ext["x"] - center["x"]
                tdy = ext["y"] - center["y"]
                d = math.hypot(tdx, tdy)
                if d <= r + 1e-10:
                    continue
                alpha = math.atan2(tdy, tdx)
                beta = math.acos(r / d)
                side = c.get("side", 1)
                theta = alpha + side * beta
                tx = center["x"] + r * math.cos(theta)
                ty = center["y"] + r * math.sin(theta)
                t_id = c.get("touch_id", f"{c['id']}_touch")
                _add({"type": "point", "id": t_id, "x": tx, "y": ty})
                _add({"type": "segment", "id": f"{c['id']}_seg",
                      "from_point": c["external_point"], "to_point": t_id,
                      "style": c.get("style", {"stroke": "#e74c3c"})})
            elif c.get("touch_point"):
                tp = pts.get(c["touch_point"])
                if not tp:
                    continue
                tdx = tp["x"] - center["x"]
                tdy = tp["y"] - center["y"]
                d = math.hypot(tdx, tdy) or 1
                perp_x, perp_y = -tdy / d, tdx / d
                length = c.get("length", 3)
                p1_id = f"{c['id']}_p1"
                p2_id = f"{c['id']}_p2"
                _add({"type": "point", "id": p1_id,
                      "x": tp["x"] - perp_x * length / 2,
                      "y": tp["y"] - perp_y * length / 2,
                      "style": {"visible": False}})
                _add({"type": "point", "id": p2_id,
                      "x": tp["x"] + perp_x * length / 2,
                      "y": tp["y"] + perp_y * length / 2,
                      "style": {"visible": False}})
                _add({"type": "segment", "id": f"{c['id']}_seg",
                      "from_point": p1_id, "to_point": p2_id,
                      "style": c.get("style", {"stroke": "#e74c3c"})})

        elif ctype == "cross_section":
            vertices = c.get("vertices", [])
            if len(vertices) < 3 or not all(pts.get(v) for v in vertices):
                continue
            _add({"type": "polygon", "id": f"{c['id']}_poly",
                  "vertices": vertices,
                  "style": c.get("style", {
                      "fill": "rgba(155,89,182,0.15)",
                      "stroke": "#8e44ad", "stroke_width": 2})})

        elif ctype == "perpendicular":
            pv = pts.get(c.get("point"))
            lp1 = pts.get(c.get("line_point1"))
            lp2 = pts.get(c.get("line_point2"))
            if not all([pv, lp1, lp2]):
                continue
            pdx = lp2["x"] - lp1["x"]
            pdy = lp2["y"] - lp1["y"]
            denom = pdx * pdx + pdy * pdy
            if denom < 1e-10:
                continue
            t = ((pv["x"] - lp1["x"]) * pdx + (pv["y"] - lp1["y"]) * pdy) / denom
            foot_id = c.get("foot_id", f"{c['id']}_foot")
            _add({"type": "point", "id": foot_id,
                  "x": lp1["x"] + t * pdx, "y": lp1["y"] + t * pdy})
            _add({"type": "segment", "id": f"{c['id']}_seg",
                  "from_point": c["point"], "to_point": foot_id,
                  "style": c.get("style", {"dash": "dashed", "stroke": "#e74c3c"})})

        elif ctype == "intersection":
            # Intersection of two lines: line1=[P1,P2], line2=[P3,P4]
            line1 = c.get("line1", [])
            line2 = c.get("line2", [])
            if len(line1) != 2 or len(line2) != 2:
                continue
            p1, p2 = pts.get(line1[0]), pts.get(line1[1])
            p3, p4 = pts.get(line2[0]), pts.get(line2[1])
            if not all([p1, p2, p3, p4]):
                continue
            ix, iy = _line_intersection(
                p1["x"], p1["y"], p2["x"], p2["y"],
                p3["x"], p3["y"], p4["x"], p4["y"])
            if ix is None:
                continue
            result_id = c.get("result_id", f"{c['id']}_pt")
            _add({"type": "point", "id": result_id, "x": ix, "y": iy})

    result = dict(scene)
    result["objects"] = new_objs
    return result, warnings


def _circumcenter(a, b, c):
    ax, ay = a["x"], a["y"]
    bx, by = b["x"], b["y"]
    cx, cy = c["x"], c["y"]
    D = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(D) < 1e-10:
        return None
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / D
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / D
    r = math.dist((ux, uy), (ax, ay))
    return ux, uy, r


def _incircle(a, b, c):
    ax, ay = a["x"], a["y"]
    bx, by = b["x"], b["y"]
    cx, cy = c["x"], c["y"]
    da = math.dist((bx, by), (cx, cy))
    db = math.dist((ax, ay), (cx, cy))
    dc = math.dist((ax, ay), (bx, by))
    p = da + db + dc
    if p < 1e-10:
        return None
    ix = (da * ax + db * bx + dc * cx) / p
    iy = (da * ay + db * by + dc * cy) / p
    s = abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2
    r = 2 * s / p
    return ix, iy, r


def _line_intersection(x1, y1, x2, y2, x3, y3, x4, y4):
    """Intersection of line through (x1,y1)-(x2,y2) and line through (x3,y3)-(x4,y4).
    Returns (x, y) or (None, None) if parallel."""
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-10:
        return None, None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    ix = x1 + t * (x2 - x1)
    iy = y1 + t * (y2 - y1)
    return ix, iy


# ═══════════════════════════════════════════════════════════════
# SVG renderer
# (port of svg-generator/service/app/renderer/geometry.py)
# ═══════════════════════════════════════════════════════════════

def render_geometry_svg(scene: dict) -> str:
    scene, _ = solve_constraints(scene)

    c = scene.get("canvas", {})
    w = c.get("width", 400)
    h = c.get("height", 400)
    xmin, xmax = c.get("x_min", -1), c.get("x_max", 7)
    ymin, ymax = c.get("y_min", -1), c.get("y_max", 6)
    style = scene.get("style", {})
    global_stroke = style.get("stroke_color", "#333333")
    font_size = style.get("font_size", 12)
    font_family = style.get("font_family", "sans-serif")

    def sx(x):
        return (x - xmin) / (xmax - xmin) * w

    def sy(y):
        return (ymax - y) / (ymax - ymin) * h

    def slen(d):
        scale_x = w / (xmax - xmin)
        scale_y = h / (ymax - ymin)
        return d * min(scale_x, scale_y)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" style="background:white;font-family:{font_family}">',
    ]

    pts = {}
    for obj in scene.get("objects", []):
        if obj["type"] == "point":
            pts[obj["id"]] = obj

    # triangles first (as polygon fills)
    for obj in scene.get("objects", []):
        if obj["type"] == "triangle":
            verts = [pts.get(v) for v in obj.get("vertices", [])]
            if not all(verts):
                continue
            coords = " ".join(f"{sx(v['x']):.1f},{sy(v['y']):.1f}" for v in verts)
            obj_style = obj.get("style") or {}
            fill = obj_style.get("fill", "rgba(52,152,219,0.06)")
            stroke = obj_style.get("stroke", global_stroke)
            sw = obj_style.get("stroke_width", 1.5)
            lines.append(f'  <polygon points="{coords}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    # polygons (arbitrary n-gon — generalises triangle)
    for obj in scene.get("objects", []):
        if obj["type"] == "polygon":
            verts = [pts.get(v) for v in obj.get("vertices", [])]
            if len(verts) < 3 or not all(verts):
                continue
            coords = " ".join(f"{sx(v['x']):.1f},{sy(v['y']):.1f}" for v in verts)
            obj_style = obj.get("style") or {}
            fill = obj_style.get("fill", "rgba(52,152,219,0.06)")
            stroke = obj_style.get("stroke", global_stroke)
            sw = obj_style.get("stroke_width", 1.5)
            dash = _dash_attr(obj_style)
            lines.append(
                f'  <polygon points="{coords}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="{sw}"{dash}/>')

    # sectors (filled arc)
    for obj in scene.get("objects", []):
        if obj["type"] == "sector":
            center = pts.get(obj.get("center"))
            if not center:
                continue
            cx, cy = sx(center["x"]), sy(center["y"])
            r = slen(obj.get("radius", 1))
            sa = math.radians(obj.get("start_angle", 0))
            ea = math.radians(obj.get("end_angle", 90))
            x1 = cx + r * math.cos(sa)
            y1 = cy - r * math.sin(sa)
            x2 = cx + r * math.cos(ea)
            y2 = cy - r * math.sin(ea)
            span = (obj.get("end_angle", 90) - obj.get("start_angle", 0)) % 360
            if span == 0:
                span = 360
            large = 1 if span > 180 else 0
            obj_style = obj.get("style") or {}
            fill = obj_style.get("fill", "rgba(52,152,219,0.15)")
            stroke = obj_style.get("stroke", global_stroke)
            sw = obj_style.get("stroke_width", 1.5)
            lines.append(
                f'  <path d="M{cx:.1f},{cy:.1f} L{x1:.1f},{y1:.1f} '
                f'A{r:.1f},{r:.1f} 0 {large},0 {x2:.1f},{y2:.1f} Z" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    # cylinders
    for obj in scene.get("objects", []):
        if obj["type"] == "cylinder":
            _render_cylinder(lines, sx, sy, slen, pts, obj, global_stroke)

    # cones
    for obj in scene.get("objects", []):
        if obj["type"] == "cone":
            _render_cone(lines, sx, sy, slen, pts, obj, global_stroke)

    # circles
    for obj in scene.get("objects", []):
        if obj["type"] == "circle":
            center = pts.get(obj.get("center"))
            if not center:
                continue
            cx, cy = sx(center["x"]), sy(center["y"])
            r = slen(obj.get("radius", 1))
            obj_style = obj.get("style") or {}
            stroke = obj_style.get("stroke", global_stroke)
            fill = obj_style.get("fill", "none")
            sw = obj_style.get("stroke_width", 1.5)
            dash = _dash_attr(obj_style)
            lines.append(
                f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                f'stroke="{stroke}" fill="{fill}" stroke-width="{sw}"{dash}/>'
            )

    # ellipses
    for obj in scene.get("objects", []):
        if obj["type"] == "ellipse":
            center = pts.get(obj.get("center"))
            if not center:
                continue
            ecx, ecy = sx(center["x"]), sy(center["y"])
            erx = slen(obj.get("rx", 1))
            ery = slen(obj.get("ry", 0.5))
            rotation = obj.get("rotation", 0)
            obj_style = obj.get("style") or {}
            stroke = obj_style.get("stroke", global_stroke)
            fill = obj_style.get("fill", "none")
            sw = obj_style.get("stroke_width", 1.5)
            dash = _dash_attr(obj_style)
            lines.append(
                f'  <ellipse cx="{ecx:.1f}" cy="{ecy:.1f}" rx="{erx:.1f}" ry="{ery:.1f}" '
                f'transform="rotate({rotation},{ecx:.1f},{ecy:.1f})" '
                f'stroke="{stroke}" fill="{fill}" stroke-width="{sw}"{dash}/>')

    # arcs (unfilled)
    for obj in scene.get("objects", []):
        if obj["type"] == "arc":
            center = pts.get(obj.get("center"))
            if not center:
                continue
            acx, acy = sx(center["x"]), sy(center["y"])
            ar = slen(obj.get("radius", 1))
            sa = math.radians(obj.get("start_angle", 0))
            ea = math.radians(obj.get("end_angle", 90))
            ax1 = acx + ar * math.cos(sa)
            ay1 = acy - ar * math.sin(sa)
            ax2 = acx + ar * math.cos(ea)
            ay2 = acy - ar * math.sin(ea)
            span = (obj.get("end_angle", 90) - obj.get("start_angle", 0)) % 360
            if span == 0:
                span = 360
            large = 1 if span > 180 else 0
            obj_style = obj.get("style") or {}
            stroke = obj_style.get("stroke", global_stroke)
            sw = obj_style.get("stroke_width", 1.5)
            dash = _dash_attr(obj_style)
            lines.append(
                f'  <path d="M{ax1:.1f},{ay1:.1f} '
                f'A{ar:.1f},{ar:.1f} 0 {large},0 {ax2:.1f},{ay2:.1f}" '
                f'fill="none" stroke="{stroke}" stroke-width="{sw}"{dash}/>')

    # segments
    segment_labels: list[tuple] = []  # collected for collision pass below
    for obj in scene.get("objects", []):
        if obj["type"] == "segment":
            p1, p2 = pts.get(obj.get("from_point")), pts.get(obj.get("to_point"))
            if not p1 or not p2:
                continue
            obj_style = obj.get("style") or {}
            stroke = obj_style.get("stroke", global_stroke)
            sw = obj_style.get("stroke_width", 1.5)
            dash = _dash_attr(obj_style)
            x1, y1 = sx(p1["x"]), sy(p1["y"])
            x2, y2 = sx(p2["x"]), sy(p2["y"])
            lines.append(
                f'  <line x1="{x1:.1f}" y1="{y1:.1f}" '
                f'x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{stroke}" stroke-width="{sw}"{dash}/>'
            )
            length_label = obj.get("length_label")
            if length_label is None or str(length_label).strip() == "":
                continue
            mx = (x1 + x2) / 2.0
            my = (y1 + y2) / 2.0
            dx_seg = x2 - x1
            dy_seg = y2 - y1
            seg_len = math.hypot(dx_seg, dy_seg) or 1.0
            nx = -dy_seg / seg_len
            ny = dx_seg / seg_len
            offset = obj.get("label_offset", 16)
            label_color = obj.get("label_color") or stroke
            offset_dir = obj.get("label_offset_dir", "auto")
            if offset_dir == "auto":
                # Choose the side that points away from the plan's centroid
                # in screen coordinates, so the label drifts outwards. This
                # tends to keep symmetric pairs (e.g. trapezoid diagonals)
                # on opposite sides of the figure instead of clashing in the
                # middle.
                cx_all, cy_all = 0.0, 0.0
                n_pts = 0
                for p in pts.values():
                    cx_all += sx(p["x"])
                    cy_all += sy(p["y"])
                    n_pts += 1
                if n_pts:
                    cx_all /= n_pts
                    cy_all /= n_pts
                    if (mx - cx_all) * nx + (my - cy_all) * ny < 0:
                        nx, ny = -nx, -ny
            elif offset_dir in (-1, 1):
                if offset_dir == -1:
                    nx, ny = -nx, -ny
            lx = mx + nx * offset
            ly = my + ny * offset
            segment_labels.append((
                lx, ly, str(length_label), label_color,
                obj.get("label_font_size", font_size),
            ))

    # right angle markers from constraints
    for c_obj in scene.get("constraints", []):
        if c_obj.get("type") == "right_angle_marker":
            vertex = pts.get(c_obj.get("vertex"))
            ray1 = pts.get(c_obj.get("ray1"))
            ray2 = pts.get(c_obj.get("ray2"))
            if vertex and ray1 and ray2:
                _draw_right_angle(lines, sx, sy, vertex, ray1, ray2, 12, global_stroke)

    # angle arcs from constraints
    for c_obj in scene.get("constraints", []):
        if c_obj.get("type") == "angle_arc":
            vertex = pts.get(c_obj.get("vertex"))
            ray1 = pts.get(c_obj.get("ray1"))
            ray2 = pts.get(c_obj.get("ray2"))
            if vertex and ray1 and ray2:
                color = c_obj.get("color", "#e74c3c")
                label = c_obj.get("label", "")
                radius = c_obj.get("radius", 20)
                _draw_angle_arc(lines, sx, sy, vertex, ray1, ray2, radius, color, label)

    # points on top
    for obj in scene.get("objects", []):
        if obj["type"] == "point":
            px, py = sx(obj["x"]), sy(obj["y"])
            obj_style = obj.get("style") or {}
            fill = obj_style.get("fill", global_stroke)
            stroke = obj_style.get("stroke", global_stroke)
            r = obj_style.get("radius", 4)
            if obj_style.get("visible") is False:
                continue
            lines.append(f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="{r}" stroke="{stroke}" fill="{fill}" stroke-width="1"/>')
            if obj.get("label"):
                lbl = obj["label"]
                ldx = obj.get("label_dx", 8)
                ldy = obj.get("label_dy", -8)
                lines.append(
                    f'  <text x="{px + ldx:.1f}" y="{py + ldy:.1f}" font-size="{font_size + 2}" '
                    f'font-family="{font_family}" font-weight="bold" fill="{global_stroke}">'
                    f'{html_mod.escape(lbl)}</text>'
                )

    # annotations — with collision avoidance.
    # Length labels collected during segment rendering join the same pool
    # so that they cannot overlap with anchor-based annotations either.
    label_positions = [list(t) for t in segment_labels]
    for ann in scene.get("annotations", []):
        if ann.get("type") == "label":
            anchor = pts.get(ann.get("anchor"))
            if not anchor:
                continue
            dx_world = ann.get("dx", 0)
            dy_world = ann.get("dy", 0)
            ax = sx(anchor["x"]) + dx_world * w / (xmax - xmin)
            ay = sy(anchor["y"]) - dy_world * h / (ymax - ymin)
            color = ann.get("color", "#555")
            fs = ann.get("font_size", font_size)
            text = ann.get("text", "")
            label_positions.append([ax, ay, text, color, fs])

    _resolve_label_collisions(label_positions)

    for lx, ly, text, color, fs in label_positions:
        lines.append(
            f'  <text x="{lx:.1f}" y="{ly:.1f}" font-size="{fs}" '
            f'font-family="{font_family}" fill="{color}">'
            f'{html_mod.escape(text)}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def _resolve_label_collisions(labels: list, min_dist_x: float = 40, min_dist_y: float = 16):
    """Shift labels vertically to avoid overlaps. Modifies list in-place.
    Each label is [x, y, text, color, fs]."""
    if len(labels) <= 1:
        return

    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            dx = abs(labels[i][0] - labels[j][0])
            dy = abs(labels[i][1] - labels[j][1])
            if dx < min_dist_x and dy < min_dist_y:
                shift = (min_dist_y - dy) / 2 + 2
                if labels[i][1] <= labels[j][1]:
                    labels[i][1] -= shift
                    labels[j][1] += shift
                else:
                    labels[i][1] += shift
                    labels[j][1] -= shift

    # Second pass for remaining collisions after first shift
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            dx = abs(labels[i][0] - labels[j][0])
            dy = abs(labels[i][1] - labels[j][1])
            if dx < min_dist_x and dy < min_dist_y:
                shift = min_dist_y - dy + 2
                labels[j][1] += shift


def _dash_attr(style: dict) -> str:
    d = style.get("dash", "")
    if d == "dashed":
        return ' stroke-dasharray="8,4"'
    elif d == "dotted":
        return ' stroke-dasharray="2,4"'
    return ""


def _draw_right_angle(lines, sx, sy, vertex, ray1, ray2, size, color):
    vx, vy = sx(vertex["x"]), sy(vertex["y"])
    r1x, r1y = sx(ray1["x"]), sy(ray1["y"])
    r2x, r2y = sx(ray2["x"]), sy(ray2["y"])

    def unit(px, py, qx, qy):
        dx, dy = qx - px, qy - py
        d = math.hypot(dx, dy)
        if d < 1e-9:
            return 0, 0
        return dx / d, dy / d

    u1x, u1y = unit(vx, vy, r1x, r1y)
    u2x, u2y = unit(vx, vy, r2x, r2y)

    ax = vx + u1x * size
    ay = vy + u1y * size
    bx = ax + u2x * size
    by = ay + u2y * size
    cx = vx + u2x * size
    cy = vy + u2y * size

    lines.append(
        f'  <polyline points="{ax:.1f},{ay:.1f} {bx:.1f},{by:.1f} {cx:.1f},{cy:.1f}" '
        f'fill="none" stroke="{color}" stroke-width="1.2"/>'
    )


def _draw_angle_arc(lines, sx, sy, vertex, ray1, ray2, radius, color, label):
    vx, vy = sx(vertex["x"]), sy(vertex["y"])
    r1x, r1y = sx(ray1["x"]), sy(ray1["y"])
    r2x, r2y = sx(ray2["x"]), sy(ray2["y"])

    d1x, d1y = r1x - vx, r1y - vy
    d2x, d2y = r2x - vx, r2y - vy
    len1 = math.hypot(d1x, d1y) or 1
    len2 = math.hypot(d2x, d2y) or 1

    a1x = vx + d1x / len1 * radius
    a1y = vy + d1y / len1 * radius
    a2x = vx + d2x / len2 * radius
    a2y = vy + d2y / len2 * radius

    angle1 = math.atan2(d1y, d1x)
    angle2 = math.atan2(d2y, d2x)
    diff = (angle2 - angle1) % (2 * math.pi)
    large = 1 if diff > math.pi else 0

    lines.append(
        f'  <path d="M{a1x:.1f},{a1y:.1f} A{radius},{radius} 0 {large},1 {a2x:.1f},{a2y:.1f}" '
        f'fill="none" stroke="{color}" stroke-width="1.5"/>'
    )

    if label:
        mid_angle = angle1 + diff / 2
        lx = vx + math.cos(mid_angle) * (radius + 14)
        ly = vy + math.sin(mid_angle) * (radius + 14)
        lines.append(
            f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
            f'font-size="12" fill="{color}">{html_mod.escape(label)}</text>'
        )


def _render_cylinder(lines, sx, sy, slen, pts, obj, global_stroke):
    """Draw a cylinder: two ellipses (top/bottom) + side lines."""
    base = pts.get(obj.get("base_center"))
    top = pts.get(obj.get("top_center"))
    if not base or not top:
        return
    r_world = obj.get("radius", 1)
    tilt = obj.get("tilt", 0.3)
    style = obj.get("style") or {}
    stroke = style.get("stroke", global_stroke)
    fill = style.get("fill", "none")
    sw = style.get("stroke_width", 1.5)

    bx, by = sx(base["x"]), sy(base["y"])
    tx, ty = sx(top["x"]), sy(top["y"])
    r_px = slen(r_world)
    ry_px = r_px * tilt

    dx, dy = tx - bx, ty - by
    ax_len = math.hypot(dx, dy)
    if ax_len < 1e-9:
        return

    perp_x = -dy / ax_len
    perp_y = dx / ax_len
    rotation = math.degrees(math.atan2(perp_y, perp_x))

    lb_x, lb_y = bx + perp_x * r_px, by + perp_y * r_px
    rb_x, rb_y = bx - perp_x * r_px, by - perp_y * r_px
    lt_x, lt_y = tx + perp_x * r_px, ty + perp_y * r_px
    rt_x, rt_y = tx - perp_x * r_px, ty - perp_y * r_px

    lr_x, lr_y = rb_x - lb_x, rb_y - lb_y
    front_dx, front_dy = -dx / ax_len, -dy / ax_len
    cross = lr_x * front_dy - lr_y * front_dx
    front_sweep = 0 if cross < 0 else 1
    back_sweep = 1 - front_sweep

    lines.append(
        f'  <line x1="{lb_x:.1f}" y1="{lb_y:.1f}" '
        f'x2="{lt_x:.1f}" y2="{lt_y:.1f}" '
        f'stroke="{stroke}" stroke-width="{sw}"/>')
    lines.append(
        f'  <line x1="{rb_x:.1f}" y1="{rb_y:.1f}" '
        f'x2="{rt_x:.1f}" y2="{rt_y:.1f}" '
        f'stroke="{stroke}" stroke-width="{sw}"/>')

    # Bottom ellipse — back half dashed, front half solid
    lines.append(
        f'  <path d="M{lb_x:.1f},{lb_y:.1f} '
        f'A{r_px:.1f},{ry_px:.1f} {rotation:.1f} 0 {back_sweep} '
        f'{rb_x:.1f},{rb_y:.1f}" fill="none" stroke="{stroke}" '
        f'stroke-width="{sw}" stroke-dasharray="6,4"/>')
    lines.append(
        f'  <path d="M{lb_x:.1f},{lb_y:.1f} '
        f'A{r_px:.1f},{ry_px:.1f} {rotation:.1f} 0 {front_sweep} '
        f'{rb_x:.1f},{rb_y:.1f}" fill="none" stroke="{stroke}" '
        f'stroke-width="{sw}"/>')

    # Top ellipse — full, solid
    lines.append(
        f'  <ellipse cx="{tx:.1f}" cy="{ty:.1f}" '
        f'rx="{r_px:.1f}" ry="{ry_px:.1f}" '
        f'transform="rotate({rotation:.1f},{tx:.1f},{ty:.1f})" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def _render_cone(lines, sx, sy, slen, pts, obj, global_stroke):
    """Draw a cone: base ellipse + two side lines to apex."""
    base = pts.get(obj.get("base_center"))
    apex = pts.get(obj.get("apex"))
    if not base or not apex:
        return
    r_world = obj.get("radius", 1)
    tilt = obj.get("tilt", 0.3)
    style = obj.get("style") or {}
    stroke = style.get("stroke", global_stroke)
    fill = style.get("fill", "none")
    sw = style.get("stroke_width", 1.5)

    bx, by = sx(base["x"]), sy(base["y"])
    apx, apy = sx(apex["x"]), sy(apex["y"])
    r_px = slen(r_world)
    ry_px = r_px * tilt

    dx, dy = apx - bx, apy - by
    ax_len = math.hypot(dx, dy)
    if ax_len < 1e-9:
        return

    perp_x = -dy / ax_len
    perp_y = dx / ax_len
    rotation = math.degrees(math.atan2(perp_y, perp_x))

    lb_x, lb_y = bx + perp_x * r_px, by + perp_y * r_px
    rb_x, rb_y = bx - perp_x * r_px, by - perp_y * r_px

    lr_x, lr_y = rb_x - lb_x, rb_y - lb_y
    front_dx, front_dy = -dx / ax_len, -dy / ax_len
    cross = lr_x * front_dy - lr_y * front_dx
    front_sweep = 0 if cross < 0 else 1
    back_sweep = 1 - front_sweep

    # Side lines to apex
    lines.append(
        f'  <line x1="{lb_x:.1f}" y1="{lb_y:.1f}" '
        f'x2="{apx:.1f}" y2="{apy:.1f}" '
        f'stroke="{stroke}" stroke-width="{sw}"/>')
    lines.append(
        f'  <line x1="{rb_x:.1f}" y1="{rb_y:.1f}" '
        f'x2="{apx:.1f}" y2="{apy:.1f}" '
        f'stroke="{stroke}" stroke-width="{sw}"/>')

    # Base ellipse — back half dashed, front half solid
    lines.append(
        f'  <path d="M{lb_x:.1f},{lb_y:.1f} '
        f'A{r_px:.1f},{ry_px:.1f} {rotation:.1f} 0 {back_sweep} '
        f'{rb_x:.1f},{rb_y:.1f}" fill="none" stroke="{stroke}" '
        f'stroke-width="{sw}" stroke-dasharray="6,4"/>')
    lines.append(
        f'  <path d="M{lb_x:.1f},{lb_y:.1f} '
        f'A{r_px:.1f},{ry_px:.1f} {rotation:.1f} 0 {front_sweep} '
        f'{rb_x:.1f},{rb_y:.1f}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{sw}"/>')


# ═══════════════════════════════════════════════════════════════
# Step-by-step geometry builder
# ═══════════════════════════════════════════════════════════════

class StepByStepGeo:
    """Progressive geometry construction — snapshot SVG at each step."""

    def __init__(self, canvas, style=None):
        self.scene = {
            "scene_type": "geometry",
            "canvas": canvas,
            "style": style or {
                "theme": "light",
                "stroke_color": "#333333",
                "fill_color": "none",
                "font_size": 12,
                "font_family": "sans-serif",
            },
            "objects": [],
            "constraints": [],
            "annotations": [],
        }
        self._obj_ids = set()
        self.steps = []

    def add_object(self, obj):
        if obj["id"] not in self._obj_ids:
            self.scene["objects"].append(obj)
            self._obj_ids.add(obj["id"])
        return self

    def add_constraint(self, c):
        self.scene["constraints"].append(c)
        return self

    def add_annotation(self, ann):
        self.scene["annotations"].append(ann)
        return self

    def snapshot(self, title="", description=""):
        """Render current state and store as a step."""
        svg = render_geometry_svg(copy.deepcopy(self.scene))
        self.steps.append({"title": title, "description": description, "svg": svg})
        return self

    def get_steps(self):
        return self.steps
