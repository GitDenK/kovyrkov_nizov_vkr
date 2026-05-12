"""
Конвертер: visual plan (planner v2) → Scene JSON (SVG generator).

Маппинг 13 типов планировщика → 3 типа SVG-генератора:
  function_graph / tangent_line_graph / derivative_sign_chart / number_line / coordinate_plane
      → function_plot
  venn_diagram
      → geometry
  step_by_step_diagram / flowchart / formula_card / outcome_tree /
  comparison_chart / table / annotated_example
      → diagram
"""

import math
import re


SCENE_TYPE_MAP = {
    "function_graph": "function_plot",
    "tangent_line_graph": "function_plot",
    "derivative_sign_chart": "function_plot",
    "number_line": "function_plot",
    "coordinate_plane": "function_plot",
    "venn_diagram": "geometry",
    "step_by_step_diagram": "diagram",
    "flowchart": "diagram",
    "formula_card": "diagram",
    "outcome_tree": "diagram",
    "comparison_chart": "diagram",
    "table": "diagram",
    "annotated_example": "diagram",
}

_CONVERTERS = {}


def _register(visual_type):
    def decorator(fn):
        _CONVERTERS[visual_type] = fn
        return fn
    return decorator


def _default_style():
    return {
        "theme": "light",
        "stroke_color": "#333333",
        "fill_color": "#f5f5f5",
        "font_size": 13,
        "font_family": "sans-serif",
    }


def _normalize_expr(raw: str) -> str:
    """LaTeX-like math → Python/sympy expression."""
    s = raw.strip()
    s = s.replace("^", "**")
    s = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", s)
    s = re.sub(r"([a-zA-Z])(\d)", r"\1*\2", s)  # unlikely, but handle "x2"
    s = s.replace(")(", ")*(")
    s = re.sub(r"(\d)\(", r"\1*(", s)
    s = s.replace("·", "*").replace("×", "*").replace("−", "-")
    s = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt\{([^}]+)\}", r"sqrt(\1)", s)
    s = s.replace("\\cdot", "*").replace("\\pi", "pi")
    s = re.sub(r"\\[a-zA-Z]+", "", s)  # strip remaining LaTeX commands
    return s.strip()


def _safe_eval_y(expr: str, x_val: float) -> float | None:
    """Evaluate expression at x=x_val, return None on failure."""
    try:
        result = eval(expr, {"__builtins__": {}}, {
            "x": x_val, "math": math, "pi": math.pi, "e": math.e,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "sqrt": math.sqrt, "abs": abs, "log": math.log,
            "exp": math.exp,
        })
        if isinstance(result, (int, float)) and math.isfinite(result):
            return float(result)
    except Exception:
        pass
    return None


def _estimate_y_range(expr: str, x_min: float, x_max: float):
    """Estimate reasonable y-range by sampling the expression."""
    ys = []
    for i in range(21):
        xv = x_min + (x_max - x_min) * i / 20
        yv = _safe_eval_y(expr, xv)
        if yv is not None:
            ys.append(yv)
    if not ys:
        return -5.0, 5.0
    lo, hi = min(ys), max(ys)
    margin = max(1.0, (hi - lo) * 0.15)
    return math.floor(lo - margin), math.ceil(hi + margin)


def convert_plan_to_scene(plan: dict) -> dict | None:
    """Convert a single visual plan dict to a Scene JSON dict.

    Returns None if conversion is not possible.
    """
    vtype = plan.get("visual_type", "none")
    if vtype == "none" or not plan.get("need_visual"):
        return None

    converter = _CONVERTERS.get(vtype)
    if converter is None:
        return _fallback_diagram(plan)

    try:
        return converter(plan)
    except Exception:
        return _fallback_diagram(plan)


# ═══════════════════════════════════════════════════════════════
# function_plot converters
# ═══════════════════════════════════════════════════════════════

@_register("function_graph")
def _conv_function_graph(plan: dict) -> dict:
    params = plan.get("params", {})
    raw_eq = params.get("equation", params.get("function", "x**2"))
    expr = _normalize_expr(raw_eq)

    x_range = params.get("x_range", [-5, 5])
    if isinstance(x_range, list) and len(x_range) >= 2:
        xmin, xmax = float(x_range[0]), float(x_range[1])
    else:
        xmin, xmax = -5.0, 5.0

    ymin, ymax = _estimate_y_range(expr, xmin, xmax)
    objects = [
        {"type": "function_curve", "id": "func_main", "expression": expr,
         "x_min": xmin, "x_max": xmax}
    ]

    for i, pt in enumerate(_extract_points(params, "highlight_points")):
        objects.append({
            "type": "point", "id": f"hl_{i}",
            "x": pt[0], "y": pt[1],
            "label": pt[2] if len(pt) > 2 else f"({pt[0]}, {pt[1]})"
        })

    for i, rx in enumerate(_extract_scalars(params, "highlight_roots", "roots")):
        objects.append({
            "type": "point", "id": f"root_{i}",
            "x": rx, "y": 0, "label": f"x={rx}"
        })

    annotations = []
    if params.get("equation") or params.get("function"):
        label_text = f"y = {raw_eq}"
        objects.append({"type": "point", "id": "ann_anchor", "x": xmax * 0.7, "y": _safe_eval_y(expr, xmax * 0.7) or 0})
        annotations.append({
            "type": "label", "id": "ann_eq", "text": label_text,
            "anchor": "ann_anchor", "dx": 0.3, "dy": 0.5
        })

    return {
        "scene_type": "function_plot",
        "canvas": {"width": 400, "height": 400,
                    "x_min": xmin - 1, "x_max": xmax + 1,
                    "y_min": ymin, "y_max": ymax},
        "style": {**_default_style(), "fill_color": "none"},
        "objects": objects,
        "constraints": [],
        "annotations": annotations,
    }


@_register("tangent_line_graph")
def _conv_tangent_line(plan: dict) -> dict:
    params = plan.get("params", {})
    raw_eq = params.get("equation", params.get("function", "x**2"))
    expr = _normalize_expr(raw_eq)

    tp = params.get("tangent_point", params.get("point", {}))
    if isinstance(tp, dict):
        tx, ty = float(tp.get("x", 1)), float(tp.get("y", 1))
    elif isinstance(tp, (list, tuple)) and len(tp) >= 2:
        tx, ty = float(tp[0]), float(tp[1])
    else:
        tx, ty = 1.0, _safe_eval_y(expr, 1.0) or 1.0

    tang_eq = params.get("tangent_equation", params.get("tangent", ""))
    tang_expr = _normalize_expr(tang_eq) if tang_eq else None

    xmin, xmax = -5.0, 5.0
    x_range = params.get("x_range", None)
    if isinstance(x_range, list) and len(x_range) >= 2:
        xmin, xmax = float(x_range[0]), float(x_range[1])

    ymin, ymax = _estimate_y_range(expr, xmin, xmax)

    objects = [
        {"type": "function_curve", "id": "func_main", "expression": expr,
         "x_min": xmin, "x_max": xmax},
        {"type": "point", "id": "tangent_pt", "x": tx, "y": ty,
         "label": f"({tx}, {ty})"},
    ]
    if tang_expr:
        objects.append({
            "type": "function_curve", "id": "tangent_line",
            "expression": tang_expr, "x_min": xmin, "x_max": xmax,
            "style": {"stroke": "#e74c3c", "dash": "dashed"},
        })

    return {
        "scene_type": "function_plot",
        "canvas": {"width": 400, "height": 400,
                    "x_min": xmin - 1, "x_max": xmax + 1,
                    "y_min": ymin, "y_max": ymax},
        "style": {**_default_style(), "fill_color": "none"},
        "objects": objects,
        "constraints": [],
        "annotations": [],
    }


@_register("derivative_sign_chart")
def _conv_derivative_sign_chart(plan: dict) -> dict:
    params = plan.get("params", {})
    raw_func = params.get("function", "x**2")
    expr = _normalize_expr(raw_func)
    raw_deriv = params.get("derivative", "")
    deriv_expr = _normalize_expr(raw_deriv) if raw_deriv else None

    critical_pts = params.get("critical_points", [])
    extrema = params.get("extrema", [])

    if critical_pts:
        nums = [float(c) for c in critical_pts if isinstance(c, (int, float))]
        if nums:
            xmin = min(nums) - 3
            xmax = max(nums) + 3
        else:
            xmin, xmax = -5.0, 5.0
    else:
        xmin, xmax = -5.0, 5.0

    ymin, ymax = _estimate_y_range(expr, xmin, xmax)

    objects = [
        {"type": "function_curve", "id": "func_main", "expression": expr,
         "x_min": xmin, "x_max": xmax},
    ]
    if deriv_expr:
        objects.append({
            "type": "function_curve", "id": "func_deriv",
            "expression": deriv_expr, "x_min": xmin, "x_max": xmax,
            "style": {"stroke": "#e74c3c", "dash": "dashed"},
        })

    annotations = []
    for i, cp in enumerate(critical_pts):
        cpf = float(cp) if isinstance(cp, (int, float)) else 0
        y_val = _safe_eval_y(expr, cpf) or 0
        pt_id = f"cp_{i}"
        objects.append({"type": "point", "id": pt_id, "x": cpf, "y": y_val,
                        "label": f"x={cpf}"})

    for i, ext in enumerate(extrema):
        if isinstance(ext, dict):
            ex = float(ext.get("x", 0))
            ey = float(ext.get("y", _safe_eval_y(expr, ex) or 0))
            etype = ext.get("type", "экстремум")
            pt_id = f"ext_{i}"
            objects.append({"type": "point", "id": pt_id, "x": ex, "y": ey})
            annotations.append({
                "type": "label", "id": f"ann_ext_{i}",
                "text": f"{etype}: ({ex}, {ey})",
                "anchor": pt_id, "dx": 0.3, "dy": -0.5
            })

    intervals = params.get("intervals", [])
    for i, iv in enumerate(intervals):
        if isinstance(iv, dict):
            sign = iv.get("sign", "")
            behavior = iv.get("behavior", "")
            iv_range = iv.get("range", "")
            label = f"{iv_range}: f'{sign}  ({behavior})" if iv_range else ""
            if label and i < len(critical_pts):
                cp_x = float(critical_pts[min(i, len(critical_pts) - 1)])
                anchor_x = cp_x - 1.5 if i == 0 else cp_x + 1.5
                y_val = _safe_eval_y(expr, anchor_x) or 0
                aid = f"iv_anchor_{i}"
                objects.append({"type": "point", "id": aid, "x": anchor_x, "y": y_val})
                annotations.append({
                    "type": "label", "id": f"ann_iv_{i}", "text": label,
                    "anchor": aid, "dx": 0, "dy": -0.8
                })

    return {
        "scene_type": "function_plot",
        "canvas": {"width": 500, "height": 400,
                    "x_min": xmin - 1, "x_max": xmax + 1,
                    "y_min": ymin, "y_max": ymax},
        "style": {**_default_style(), "fill_color": "none"},
        "objects": objects,
        "constraints": [],
        "annotations": annotations,
    }


@_register("number_line")
def _conv_number_line(plan: dict) -> dict:
    params = plan.get("params", {})
    points = params.get("points", params.get("marks", []))

    nums = []
    for p in points:
        if isinstance(p, (int, float)):
            nums.append(float(p))
        elif isinstance(p, dict):
            v = p.get("value", p.get("x", 0))
            nums.append(float(v))

    if nums:
        lo, hi = min(nums), max(nums)
        margin = max(2.0, (hi - lo) * 0.3)
    else:
        lo, hi, margin = -5, 5, 1

    objects = [
        {"type": "function_curve", "id": "axis_line",
         "expression": "0", "x_min": lo - margin, "x_max": hi + margin},
    ]
    for i, p in enumerate(points):
        if isinstance(p, (int, float)):
            objects.append({"type": "point", "id": f"nl_{i}", "x": float(p), "y": 0, "label": str(p)})
        elif isinstance(p, dict):
            v = float(p.get("value", p.get("x", 0)))
            lbl = p.get("label", str(v))
            objects.append({"type": "point", "id": f"nl_{i}", "x": v, "y": 0, "label": lbl})

    return {
        "scene_type": "function_plot",
        "canvas": {"width": 500, "height": 200,
                    "x_min": lo - margin, "x_max": hi + margin,
                    "y_min": -2, "y_max": 2},
        "style": {**_default_style(), "fill_color": "none"},
        "objects": objects,
        "constraints": [],
        "annotations": [],
    }


@_register("coordinate_plane")
def _conv_coordinate_plane(plan: dict) -> dict:
    params = plan.get("params", {})
    pts = params.get("points", [])
    objects = []
    xs, ys = [], []

    for i, p in enumerate(pts):
        if isinstance(p, dict):
            px, py = float(p.get("x", 0)), float(p.get("y", 0))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            px, py = float(p[0]), float(p[1])
        else:
            continue
        xs.append(px)
        ys.append(py)
        lbl = p.get("label", f"({px}, {py})") if isinstance(p, dict) else f"({px}, {py})"
        objects.append({"type": "point", "id": f"pt_{i}", "x": px, "y": py, "label": lbl})

    if not xs:
        xs, ys = [-5, 5], [-5, 5]

    funcs = params.get("functions", params.get("equations", []))
    for i, f in enumerate(funcs):
        raw = f if isinstance(f, str) else f.get("equation", f.get("expression", ""))
        if raw:
            expr = _normalize_expr(raw)
            objects.append({"type": "function_curve", "id": f"func_{i}", "expression": expr})
            for xv in [v / 5.0 for v in range(-25, 26)]:
                yv = _safe_eval_y(expr, xv)
                if yv is not None:
                    ys.append(yv)

    margin = 2
    return {
        "scene_type": "function_plot",
        "canvas": {"width": 400, "height": 400,
                    "x_min": min(xs) - margin, "x_max": max(xs) + margin,
                    "y_min": min(ys) - margin, "y_max": max(ys) + margin},
        "style": {**_default_style(), "fill_color": "none"},
        "objects": objects,
        "constraints": [],
        "annotations": [],
    }


# ═══════════════════════════════════════════════════════════════
# geometry converters
# ═══════════════════════════════════════════════════════════════

@_register("venn_diagram")
def _conv_venn(plan: dict) -> dict:
    params = plan.get("params", {})
    sets = params.get("sets", params.get("circles", []))

    objects = []
    n = max(len(sets), 2)
    for i, s in enumerate(sets):
        name = s.get("name", f"Set{i}") if isinstance(s, dict) else str(s)
        cx = 2.0 + i * 2.5
        cy = 3.0
        r = 2.0
        center_id = f"center_{i}"
        objects.append({"type": "point", "id": center_id, "x": cx, "y": cy, "label": name})
        objects.append({"type": "circle", "id": f"circle_{i}", "center": center_id, "radius": r,
                        "style": {"fill": f"rgba(100,150,{200 + i * 30},0.15)", "dash": "solid"}})

    xmax = 2.0 + (n - 1) * 2.5 + 3
    return {
        "scene_type": "geometry",
        "canvas": {"width": 400, "height": 400,
                    "x_min": -1, "x_max": xmax,
                    "y_min": -1, "y_max": 7},
        "style": {**_default_style(), "fill_color": "none"},
        "objects": objects,
        "constraints": [],
        "annotations": [],
    }


# ═══════════════════════════════════════════════════════════════
# diagram converters
# ═══════════════════════════════════════════════════════════════

@_register("step_by_step_diagram")
def _conv_steps(plan: dict) -> dict:
    params = plan.get("params", {})
    steps = params.get("steps", [])
    caption = plan.get("caption", "")

    if not steps:
        return _fallback_diagram(plan)

    objects = []
    if caption:
        objects.append({"type": "title", "id": "title", "text": caption})

    for i, step in enumerate(steps):
        if isinstance(step, dict):
            label = step.get("label", step.get("name", f"Шаг {i + 1}"))
            detail = step.get("detail", step.get("description", ""))
            text = f"{label}\n{detail}" if detail else label
        else:
            text = str(step)
        objects.append({"type": "box", "id": f"step_{i}", "text": text})

    for i in range(len(steps) - 1):
        objects.append({
            "type": "arrow", "id": f"arr_{i}",
            "from_point": f"step_{i}", "to_point": f"step_{i + 1}"
        })

    return _wrap_diagram(objects)


@_register("flowchart")
def _conv_flowchart(plan: dict) -> dict:
    params = plan.get("params", {})
    nodes = params.get("nodes", [])
    edges = params.get("edges", [])
    caption = plan.get("caption", "")

    objects = []
    if caption:
        objects.append({"type": "title", "id": "title", "text": caption})

    node_ids = set()
    for n in nodes:
        if isinstance(n, dict):
            nid = n.get("id", f"n_{len(node_ids)}")
            text = n.get("label", n.get("text", nid))
        else:
            nid = f"n_{len(node_ids)}"
            text = str(n)
        node_ids.add(nid)
        objects.append({"type": "box", "id": nid, "text": text})

    for i, e in enumerate(edges):
        if isinstance(e, dict):
            fr = e.get("from", e.get("from_point", ""))
            to = e.get("to", e.get("to_point", ""))
            label = e.get("label", None)
            if fr in node_ids and to in node_ids:
                arr = {"type": "arrow", "id": f"edge_{i}",
                       "from_point": fr, "to_point": to}
                if label:
                    arr["label"] = label
                objects.append(arr)

    return _wrap_diagram(objects)


@_register("formula_card")
def _conv_formula_card(plan: dict) -> dict:
    params = plan.get("params", {})
    formula = params.get("formula_latex", params.get("formula", ""))
    components = params.get("components", {})
    caption = plan.get("caption", "")

    objects = []
    if caption:
        objects.append({"type": "title", "id": "title", "text": caption})

    if formula:
        clean = formula.strip()
        if not clean.startswith("$"):
            clean = f"${clean}$"
        objects.append({"type": "formula_block", "id": "formula_main", "formula": clean})

    comp_ids = []
    for i, (key, desc) in enumerate(components.items()):
        cid = f"comp_{i}"
        comp_ids.append(cid)
        objects.append({"type": "box", "id": cid, "text": f"{key} — {desc}"})

    for cid in comp_ids:
        objects.append({
            "type": "arrow", "id": f"arr_{cid}",
            "from_point": "formula_main", "to_point": cid
        })

    return _wrap_diagram(objects)


@_register("outcome_tree")
def _conv_outcome_tree(plan: dict) -> dict:
    params = plan.get("params", {})
    experiment = params.get("experiment", "")
    outcomes = params.get("outcomes", [])
    favorable = params.get("favorable", [])
    caption = plan.get("caption", "")

    objects = []
    if caption:
        objects.append({"type": "title", "id": "title", "text": caption})

    root_text = experiment if experiment else "Эксперимент"
    objects.append({"type": "box", "id": "root", "text": root_text})

    fav_set = {str(f) for f in favorable}
    for i, outcome in enumerate(outcomes):
        if isinstance(outcome, list):
            text = ", ".join(str(o) for o in outcome)
        else:
            text = str(outcome)
        oid = f"out_{i}"
        is_fav = str(outcome) in fav_set or text in fav_set
        style = {"fill": "#d4edda", "stroke": "#28a745"} if is_fav else None
        box = {"type": "box", "id": oid, "text": text}
        if style:
            box["style"] = style
        objects.append(box)
        objects.append({
            "type": "arrow", "id": f"arr_out_{i}",
            "from_point": "root", "to_point": oid
        })

    total = params.get("total_n", len(outcomes))
    fav_n = params.get("favorable_m", len(favorable))
    if total:
        objects.append({
            "type": "text", "id": "summary",
            "text": f"Всего исходов: {total}, благоприятных: {fav_n}"
        })

    return _wrap_diagram(objects)


@_register("comparison_chart")
def _conv_comparison(plan: dict) -> dict:
    params = plan.get("params", {})
    items = params.get("items", params.get("columns", params.get("concepts", [])))
    caption = plan.get("caption", "")

    objects = []
    if caption:
        objects.append({"type": "title", "id": "title", "text": caption})

    for i, item in enumerate(items):
        if isinstance(item, dict):
            name = item.get("name", item.get("title", f"Вариант {i + 1}"))
            props = item.get("properties", item.get("features", {}))
            if isinstance(props, dict):
                details = "\n".join(f"• {k}: {v}" for k, v in props.items())
            elif isinstance(props, list):
                details = "\n".join(f"• {p}" for p in props)
            else:
                details = str(props)
            text = f"{name}\n{details}" if details else name
        else:
            text = str(item)
        objects.append({"type": "box", "id": f"cmp_{i}", "text": text})

    return _wrap_diagram(objects)


@_register("table")
def _conv_table(plan: dict) -> dict:
    params = plan.get("params", {})
    headers = params.get("headers", [])
    rows = params.get("rows", [])
    caption = plan.get("caption", "")

    if not headers and not rows:
        return _fallback_diagram(plan)

    objects = []
    if caption:
        objects.append({"type": "title", "id": "title", "text": caption})

    if headers:
        header_text = " | ".join(str(h) for h in headers)
        objects.append({"type": "box", "id": "header", "text": header_text,
                        "style": {"fill": "#d6eaf8", "stroke": "#2980b9"}})

    for ri, row in enumerate(rows):
        if isinstance(row, list):
            row_text = " | ".join(str(c) for c in row)
        else:
            row_text = str(row)
        objects.append({"type": "box", "id": f"row_{ri}", "text": row_text})

    prev_id = "header" if headers else None
    for ri in range(len(rows)):
        cur_id = f"row_{ri}"
        if prev_id:
            objects.append({
                "type": "arrow", "id": f"arr_r_{ri}",
                "from_point": prev_id, "to_point": cur_id
            })
        prev_id = cur_id

    return _wrap_diagram(objects)


@_register("annotated_example")
def _conv_annotated_example(plan: dict) -> dict:
    params = plan.get("params", {})
    problem = params.get("problem", "")
    steps = params.get("steps", [])
    caption = plan.get("caption", "")

    if not steps and not problem:
        return _fallback_diagram(plan)

    objects = []
    if caption:
        objects.append({"type": "title", "id": "title", "text": caption})

    if problem:
        objects.append({"type": "box", "id": "problem",
                        "text": f"Задача: {problem}",
                        "style": {"fill": "#fdebd0", "stroke": "#e67e22"}})

    prev_id = "problem" if problem else None
    for i, step in enumerate(steps):
        if isinstance(step, dict):
            expr = step.get("expression", step.get("formula", ""))
            ann = step.get("annotation", step.get("comment", ""))
            if expr:
                clean = expr.strip()
                if not clean.startswith("$"):
                    clean = f"${clean}$"
                fid = f"expr_{i}"
                objects.append({"type": "formula_block", "id": fid, "formula": clean})
                if prev_id:
                    objects.append({"type": "arrow", "id": f"arr_e_{i}",
                                    "from_point": prev_id, "to_point": fid})
                if ann:
                    bid = f"ann_{i}"
                    objects.append({"type": "box", "id": bid, "text": ann})
                    objects.append({"type": "arrow", "id": f"arr_a_{i}",
                                    "from_point": fid, "to_point": bid})
                    prev_id = bid
                else:
                    prev_id = fid
            else:
                text = ann if ann else str(step)
                bid = f"step_{i}"
                objects.append({"type": "box", "id": bid, "text": text})
                if prev_id:
                    objects.append({"type": "arrow", "id": f"arr_s_{i}",
                                    "from_point": prev_id, "to_point": bid})
                prev_id = bid
        else:
            bid = f"step_{i}"
            objects.append({"type": "box", "id": bid, "text": str(step)})
            if prev_id:
                objects.append({"type": "arrow", "id": f"arr_s_{i}",
                                "from_point": prev_id, "to_point": bid})
            prev_id = bid

    return _wrap_diagram(objects)


# ═══════════════════════════════════════════════════════════════
# helpers
# ═══════════════════════════════════════════════════════════════

def _wrap_diagram(objects: list[dict]) -> dict:
    return {
        "scene_type": "diagram",
        "canvas": {"width": 500, "height": 300,
                    "x_min": 0, "x_max": 500,
                    "y_min": 0, "y_max": 300},
        "style": _default_style(),
        "objects": objects,
        "constraints": [],
        "annotations": [],
    }


def _fallback_diagram(plan: dict) -> dict:
    """Fallback: render any plan as a diagram from description and params."""
    caption = plan.get("caption", plan.get("visual_type", ""))
    desc = plan.get("description", "")
    objects = []
    if caption:
        objects.append({"type": "title", "id": "title", "text": caption})

    params = plan.get("params", {})
    box_ids = []

    for i, (k, v) in enumerate(params.items()):
        bid = f"p_{i}"
        if isinstance(v, str):
            objects.append({"type": "box", "id": bid, "text": f"{k}: {v}"})
            box_ids.append(bid)
        elif isinstance(v, list):
            for j, item in enumerate(v[:8]):
                iid = f"p_{i}_{j}"
                text = _format_item(item) if isinstance(item, dict) else str(item)
                objects.append({"type": "box", "id": iid, "text": text})
                box_ids.append(iid)
        elif isinstance(v, dict):
            for j, (dk, dv) in enumerate(v.items()):
                iid = f"p_{i}_{j}"
                objects.append({"type": "box", "id": iid, "text": f"{dk}: {dv}"})
                box_ids.append(iid)
        else:
            objects.append({"type": "box", "id": bid, "text": f"{k}: {v}"})
            box_ids.append(bid)

    for i in range(len(box_ids) - 1):
        objects.append({"type": "arrow", "id": f"fb_arr_{i}",
                        "from_point": box_ids[i], "to_point": box_ids[i + 1]})

    if not box_ids:
        if desc:
            objects.append({"type": "box", "id": "desc", "text": desc})
        else:
            text = (plan.get("pedagogical_goal")
                    or plan.get("section_title")
                    or plan.get("visual_type", "visual"))
            objects.append({"type": "box", "id": "info", "text": text})

    return _wrap_diagram(objects)


def _format_item(d: dict) -> str:
    parts = []
    for k, v in d.items():
        if isinstance(v, str):
            parts.append(f"{k}: {v}")
        elif isinstance(v, (int, float)):
            parts.append(f"{k}: {v}")
    return "\n".join(parts[:4]) if parts else str(d)


def _extract_points(params: dict, *keys) -> list[tuple]:
    for key in keys:
        pts = params.get(key, [])
        if pts:
            result = []
            for p in pts:
                if isinstance(p, dict):
                    result.append((float(p.get("x", 0)), float(p.get("y", 0)),
                                   p.get("label", "")))
                elif isinstance(p, (list, tuple)) and len(p) >= 2:
                    result.append(tuple(float(v) for v in p[:3]) if len(p) > 2 else (float(p[0]), float(p[1])))
            return result
    return []


def _extract_scalars(params: dict, *keys) -> list[float]:
    for key in keys:
        vals = params.get(key, [])
        if vals:
            result = []
            for v in vals:
                try:
                    result.append(float(v))
                except (TypeError, ValueError):
                    pass
            return result
    return []
