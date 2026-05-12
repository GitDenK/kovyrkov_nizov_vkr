import math

from app.schemas import Canvas, Scene, Style

from .diagram import prepare_diagram_scene, render_diagram
from .function_plot import render_function_plot
from .geometry import render_geometry


# ---------------------------------------------------------------------------
# Общие утилиты координатного преобразования (используются в тестах и вне модуля)
# ---------------------------------------------------------------------------

def _sx(x: float, c: Canvas) -> float:
    """Мировые координаты X → экранные пиксели."""
    return (x - c.x_min) / (c.x_max - c.x_min) * c.width


def _sy(y: float, c: Canvas) -> float:
    """Мировые координаты Y → экранные пиксели (ось Y инвертирована)."""
    return (c.y_max - y) / (c.y_max - c.y_min) * c.height


def _render_axes_grid(c: Canvas) -> list[str]:
    """Тонкая сетка по целым значениям + оси координат."""
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


# ---------------------------------------------------------------------------
# Главная функция рендера — dispatcher по scene_type
# ---------------------------------------------------------------------------

def render(scene: Scene) -> str:
    if scene.scene_type == "diagram":
        prepare_diagram_scene(scene)
        body = render_diagram(scene)
        body.append("</svg>")
        return "\n".join(body)

    c = scene.canvas
    style = scene.style

    # overflow="hidden" обрезает содержимое по viewport SVG во всех браузерах
    header: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(c.width)}" height="{int(c.height)}" overflow="hidden">',
        "  <defs>",
        '    <marker id="arrow_axis" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto">',
        '      <path d="M0,0 L8,4 L0,8 Z" fill="#888888"/>',
        "    </marker>",
        f'    <marker id="arrow_obj" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">',
        f'      <path d="M0,0 L8,4 L0,8 Z" fill="{style.stroke_color}"/>',
        "    </marker>",
        "  </defs>",
    ]

    if style.theme == "light":
        header.append(f'  <rect width="{int(c.width)}" height="{int(c.height)}" fill="white"/>')

    if scene.scene_type == "function_plot":
        body = render_function_plot(scene, header)
    else:
        body = render_geometry(scene, header)

    body.append("</svg>")
    return "\n".join(body)
