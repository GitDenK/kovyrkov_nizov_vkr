import html
import math
from typing import Optional

import numpy as np
from sympy import lambdify, symbols, sympify

from app.schemas import Canvas, FunctionCurve, Label, Point, Scene, Segment, Style
from app.schemas.common import ObjectStyle

# ---------------------------------------------------------------------------
# Вспомогательные функции координатного преобразования
# ---------------------------------------------------------------------------

def _sx(x: float, c: Canvas) -> float:
    return (x - c.x_min) / (c.x_max - c.x_min) * c.width


def _sy(y: float, c: Canvas) -> float:
    return (c.y_max - y) / (c.y_max - c.y_min) * c.height


def _style_attrs(obj_style: Optional[ObjectStyle], global_style: Style, default_sw: float = 1.5) -> str:
    stroke = obj_style.stroke if (obj_style and obj_style.stroke) else global_style.stroke_color
    fill = obj_style.fill if (obj_style and obj_style.fill) else "none"
    sw = obj_style.stroke_width if (obj_style and obj_style.stroke_width is not None) else default_sw
    dash = ""
    if obj_style and obj_style.dash == "dashed":
        dash = ' stroke-dasharray="8,4"'
    elif obj_style and obj_style.dash == "dotted":
        dash = ' stroke-dasharray="2,4"'
    return f'stroke="{stroke}" fill="{fill}" stroke-width="{sw}"{dash}'


# ---------------------------------------------------------------------------
# Оси, сетка и подписи
# ---------------------------------------------------------------------------

def _render_axes_grid(c: Canvas) -> list[str]:
    """
    Сетка по целым мировым координатам.
    После _add_margins масштабы осей равны → клетки квадратные, 1 клетка = 1 единица.
    """
    lines = []

    for xi in range(math.ceil(c.x_min), math.floor(c.x_max) + 1):
        sx = _sx(xi, c)
        lines.append(f'  <line x1="{sx:.1f}" y1="0" x2="{sx:.1f}" y2="{c.height:.1f}" stroke="#e0e0e0" stroke-width="0.5"/>')

    for yi in range(math.ceil(c.y_min), math.floor(c.y_max) + 1):
        sy = _sy(yi, c)
        lines.append(f'  <line x1="0" y1="{sy:.1f}" x2="{c.width:.1f}" y2="{sy:.1f}" stroke="#e0e0e0" stroke-width="0.5"/>')

    if c.y_min <= 0 <= c.y_max:
        sy0 = _sy(0, c)
        lines.append(f'  <line x1="0" y1="{sy0:.1f}" x2="{c.width:.1f}" y2="{sy0:.1f}" stroke="#888888" stroke-width="1" marker-end="url(#arrow_axis)"/>')
    if c.x_min <= 0 <= c.x_max:
        sx0 = _sx(0, c)
        lines.append(f'  <line x1="{sx0:.1f}" y1="{c.height:.1f}" x2="{sx0:.1f}" y2="0" stroke="#888888" stroke-width="1" marker-end="url(#arrow_axis)"/>')

    return lines


def _render_axis_labels(c: Canvas, style: Style) -> list[str]:
    """Числовые подписи делений на осях и tick-риски."""
    lines = []
    tick = 5  # длина риски в пикселях
    font = style.font_size - 2
    color = "#555555"

    # Подписи по оси X (пропускаем 0 — он подпишется по Y)
    sy0 = _sy(0, c) if c.y_min <= 0 <= c.y_max else c.height
    for xi in range(math.ceil(c.x_min), math.floor(c.x_max) + 1):
        if xi == 0:
            continue
        sx = _sx(xi, c)
        lines.append(f'  <line x1="{sx:.1f}" y1="{sy0 - tick:.1f}" x2="{sx:.1f}" y2="{sy0 + tick:.1f}" stroke="{color}" stroke-width="1"/>')
        lines.append(
            f'  <text x="{sx:.1f}" y="{sy0 + tick + font + 2:.1f}" text-anchor="middle" '
            f'font-size="{font}" font-family="{style.font_family}" fill="{color}">{xi}</text>'
        )

    # Подписи по оси Y
    sx0 = _sx(0, c) if c.x_min <= 0 <= c.x_max else 0
    for yi in range(math.ceil(c.y_min), math.floor(c.y_max) + 1):
        if yi == 0:
            continue
        sy = _sy(yi, c)
        lines.append(f'  <line x1="{sx0 - tick:.1f}" y1="{sy:.1f}" x2="{sx0 + tick:.1f}" y2="{sy:.1f}" stroke="{color}" stroke-width="1"/>')
        lines.append(
            f'  <text x="{sx0 - tick - 3:.1f}" y="{sy + font / 2:.1f}" text-anchor="end" '
            f'font-size="{font}" font-family="{style.font_family}" fill="{color}">{yi}</text>'
        )

    # Подпись нуля в начале координат
    if c.x_min <= 0 <= c.x_max and c.y_min <= 0 <= c.y_max:
        lines.append(
            f'  <text x="{sx0 - 4:.1f}" y="{sy0 + font + 2:.1f}" text-anchor="end" '
            f'font-size="{font}" font-family="{style.font_family}" fill="{color}">0</text>'
        )

    return lines


# ---------------------------------------------------------------------------
# Объекты сцены
# ---------------------------------------------------------------------------

def _render_point(obj: Point, c: Canvas, style: Style) -> list[str]:
    sx, sy = _sx(obj.x, c), _sy(obj.y, c)
    stroke = obj.style.stroke if (obj.style and obj.style.stroke) else style.stroke_color
    fill = obj.style.fill if (obj.style and obj.style.fill) else style.stroke_color
    lines = [f'  <circle cx="{sx:.1f}" cy="{sy:.1f}" r="4" stroke="{stroke}" fill="{fill}" stroke-width="1"/>']
    if obj.label:
        lines.append(
            f'  <text x="{sx + 6:.1f}" y="{sy - 6:.1f}" font-size="{style.font_size}" '
            f'font-family="{style.font_family}" fill="{style.stroke_color}">{html.escape(obj.label)}</text>'
        )
    return lines


def _render_segment(obj: Segment, pts: dict, c: Canvas, style: Style) -> list[str]:
    p1, p2 = pts.get(obj.from_point), pts.get(obj.to_point)
    if not p1 or not p2:
        return []
    attrs = _style_attrs(obj.style, style)
    return [
        f'  <line x1="{_sx(p1.x, c):.1f}" y1="{_sy(p1.y, c):.1f}" '
        f'x2="{_sx(p2.x, c):.1f}" y2="{_sy(p2.y, c):.1f}" {attrs}/>'
    ]


def _render_function_curve(obj: FunctionCurve, c: Canvas, style: Style) -> list[str]:
    x_sym = symbols("x")
    expression_for_sympy = obj.expression.replace("math.", "")
    try:
        expr = sympify(expression_for_sympy)
        f = lambdify(x_sym, expr, modules="numpy")
    except Exception:
        return []

    x_min = obj.x_min if obj.x_min is not None else c.x_min
    x_max = obj.x_max if obj.x_max is not None else c.x_max
    x_vals = np.linspace(x_min, x_max, 300)

    try:
        y_vals = f(x_vals)
        if np.isscalar(y_vals):
            y_vals = np.full_like(x_vals, float(y_vals))
    except Exception:
        return []

    stroke = obj.style.stroke if (obj.style and obj.style.stroke) else style.stroke_color
    sw = obj.style.stroke_width if (obj.style and obj.style.stroke_width is not None) else 2.0

    svg_lines = []
    current_pts: list[str] = []
    for xi, yi in zip(x_vals, y_vals):
        if not math.isfinite(float(yi)):
            if len(current_pts) >= 2:
                svg_lines.append(
                    f'  <polyline points="{" ".join(current_pts)}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>'
                )
            current_pts = []
        else:
            current_pts.append(f"{_sx(float(xi), c):.1f},{_sy(float(yi), c):.1f}")

    if len(current_pts) >= 2:
        svg_lines.append(
            f'  <polyline points="{" ".join(current_pts)}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>'
        )
    return svg_lines


def _render_label_obj(obj: Label, pts: dict, c: Canvas, style: Style) -> list[str]:
    anchor = pts.get(obj.anchor)
    if not anchor:
        return []
    sx = _sx(anchor.x, c) + obj.dx * c.width / (c.x_max - c.x_min)
    sy = _sy(anchor.y, c) - obj.dy * c.height / (c.y_max - c.y_min)
    return [
        f'  <text x="{sx:.1f}" y="{sy:.1f}" font-size="{style.font_size}" '
        f'font-family="{style.font_family}" fill="{style.stroke_color}">{html.escape(obj.text)}</text>'
    ]


# ---------------------------------------------------------------------------
# Авто-margins: локально расширяем canvas на 5% по каждому краю
# ---------------------------------------------------------------------------

def _add_margins(c: Canvas, pct: float = 0.05) -> Canvas:
    """
    Добавляет поля и выравнивает масштабы осей: px_x == px_y.
    Это обеспечивает квадратные клетки сетки где 1 клетка = 1 единица.
    Корректирует высоту или ширину SVG (не меняет мировые диапазоны).
    """
    dx = (c.x_max - c.x_min) * pct
    dy = (c.y_max - c.y_min) * pct
    mc = c.model_copy(update={
        "x_min": c.x_min - dx,
        "x_max": c.x_max + dx,
        "y_min": c.y_min - dy,
        "y_max": c.y_max + dy,
    })
    px_x = mc.width / (mc.x_max - mc.x_min)
    px_y = mc.height / (mc.y_max - mc.y_min)
    # Если масштабы уже равны — ничего не делаем
    if abs(px_x - px_y) / max(px_x, px_y) < 0.01:
        return mc
    # Уменьшаем размер SVG по «крупной» оси до масштаба «мелкой»
    if px_y > px_x:
        return mc.model_copy(update={"height": int(round((mc.y_max - mc.y_min) * px_x))})
    else:
        return mc.model_copy(update={"width": int(round((mc.x_max - mc.x_min) * px_y))})


# ---------------------------------------------------------------------------
# Главная функция рендера function_plot
# ---------------------------------------------------------------------------

def render_function_plot(scene: Scene, header_lines: list[str]) -> list[str]:
    """Рендерит function_plot-сцену; header_lines — уже открытый <svg>+<defs>."""
    c = _add_margins(scene.canvas)
    style = scene.style

    pts: dict = {}
    for obj in scene.objects:
        if obj.type == "point":
            pts[obj.id] = obj

    lines = list(header_lines)
    # Обновляем SVG-заголовок: _add_margins мог скорректировать width/height
    lines[0] = f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(c.width)}" height="{int(c.height)}" overflow="hidden">'
    for i, line in enumerate(lines):
        if '<rect' in line and 'fill="white"' in line:
            lines[i] = f'  <rect width="{int(c.width)}" height="{int(c.height)}" fill="white"/>'
            break

    lines.extend(_render_axes_grid(c))
    lines.extend(_render_axis_labels(c, style))

    for obj in scene.objects:
        if obj.type == "point":
            lines.extend(_render_point(obj, c, style))
        elif obj.type == "segment":
            lines.extend(_render_segment(obj, pts, c, style))
        elif obj.type == "function_curve":
            lines.extend(_render_function_curve(obj, c, style))
        elif obj.type == "label":
            lines.extend(_render_label_obj(obj, pts, c, style))

    for label in scene.annotations:
        lines.extend(_render_label_obj(label, pts, c, style))

    return lines
