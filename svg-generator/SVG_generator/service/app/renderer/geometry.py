import html
import math
from typing import Optional

from app.schemas import (
    Canvas,
    Circle,
    Label,
    Point,
    Scene,
    Segment,
    Style,
    Triangle,
)
from app.schemas.common import ObjectStyle
from app.schemas.scene import RightAngleMarkerConstraint


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


def _render_triangle(obj: Triangle, pts: dict, c: Canvas, style: Style) -> list[str]:
    verts = [pts.get(v) for v in obj.vertices]
    if not all(verts):
        return []
    attrs = _style_attrs(obj.style, style)
    lines = []
    for i in range(3):
        p1, p2 = verts[i], verts[(i + 1) % 3]
        lines.append(
            f'  <line x1="{_sx(p1.x, c):.1f}" y1="{_sy(p1.y, c):.1f}" '
            f'x2="{_sx(p2.x, c):.1f}" y2="{_sy(p2.y, c):.1f}" {attrs}/>'
        )
    return lines


def _render_circle(obj: Circle, pts: dict, c: Canvas, style: Style) -> list[str]:
    center = pts.get(obj.center)
    if not center:
        return []
    sx, sy = _sx(center.x, c), _sy(center.y, c)
    # Используем минимум из двух масштабов, чтобы окружность не превращалась в эллипс
    # при несимметричном canvas (разные масштабы по X и Y)
    scale_x = c.width / (c.x_max - c.x_min)
    scale_y = c.height / (c.y_max - c.y_min)
    r_px = obj.radius * min(scale_x, scale_y)
    stroke = obj.style.stroke if (obj.style and obj.style.stroke) else style.stroke_color
    fill = obj.style.fill if (obj.style and obj.style.fill) else "none"
    sw = obj.style.stroke_width if (obj.style and obj.style.stroke_width is not None) else 1.5
    return [f'  <circle cx="{sx:.1f}" cy="{sy:.1f}" r="{r_px:.1f}" stroke="{stroke}" fill="{fill}" stroke-width="{sw}"/>']


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
# Маркер прямого угла
# ---------------------------------------------------------------------------

def _render_right_angle_marker(
    c: Canvas,
    vertex: Point,
    ray1: Point,
    ray2: Point,
    style: Style,
    size_px: float = 10.0,
) -> list[str]:
    """
    Рисует маленький квадрат у вершины vertex между лучами ray1 и ray2.
    size_px — размер стороны квадрата в экранных пикселях.
    """
    vx, vy = _sx(vertex.x, c), _sy(vertex.y, c)

    # Направление от вершины к ray1 и ray2 в экранных координатах
    def unit(px: float, py: float, qx: float, qy: float) -> tuple[float, float]:
        dx, dy = qx - px, qy - py
        d = math.hypot(dx, dy)
        if d < 1e-9:
            return 0.0, 0.0
        return dx / d, dy / d

    r1x, r1y = _sx(ray1.x, c), _sy(ray1.y, c)
    r2x, r2y = _sx(ray2.x, c), _sy(ray2.y, c)

    u1x, u1y = unit(vx, vy, r1x, r1y)
    u2x, u2y = unit(vx, vy, r2x, r2y)

    # Четыре вершины квадрата
    ax = vx + u1x * size_px
    ay = vy + u1y * size_px
    bx = ax + u2x * size_px
    by = ay + u2y * size_px
    cx2 = vx + u2x * size_px
    cy2 = vy + u2y * size_px

    stroke = style.stroke_color
    pts_str = f"{ax:.1f},{ay:.1f} {bx:.1f},{by:.1f} {cx2:.1f},{cy2:.1f} {vx:.1f},{vy:.1f}"
    return [
        f'  <polyline points="{pts_str}" fill="none" stroke="{stroke}" stroke-width="1.2"/>'
    ]


# ---------------------------------------------------------------------------
# Главная функция рендера geometry
# ---------------------------------------------------------------------------

def render_geometry(scene: Scene, header_lines: list[str]) -> list[str]:
    """Рендерит geometry-сцену; header_lines — уже открытый <svg>+<defs>."""
    c = scene.canvas
    style = scene.style

    pts: dict = {}
    objs: dict = {}
    for obj in scene.objects:
        objs[obj.id] = obj
        if obj.type == "point":
            pts[obj.id] = obj

    lines = list(header_lines)

    for obj in scene.objects:
        if obj.type == "point":
            lines.extend(_render_point(obj, c, style))
        elif obj.type == "segment":
            lines.extend(_render_segment(obj, pts, c, style))
        elif obj.type == "triangle":
            lines.extend(_render_triangle(obj, pts, c, style))
        elif obj.type == "circle":
            lines.extend(_render_circle(obj, pts, c, style))
        elif obj.type == "label":
            lines.extend(_render_label_obj(obj, pts, c, style))

    # Маркеры прямого угла отрисовываются по constraints
    for con in scene.constraints:
        if con.type == "right_angle_marker":
            vertex = pts.get(con.vertex)
            ray1 = pts.get(con.ray1)
            ray2 = pts.get(con.ray2)
            if vertex and ray1 and ray2:
                lines.extend(_render_right_angle_marker(c, vertex, ray1, ray2, style))

    for label in scene.annotations:
        lines.extend(_render_label_obj(label, pts, c, style))

    return lines
