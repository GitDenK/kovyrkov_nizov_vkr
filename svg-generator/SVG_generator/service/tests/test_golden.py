import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.orchestrator.orchestrator import render_scene

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_FILES = sorted(GOLDEN_DIR.glob("*.json"))


@pytest.mark.parametrize("golden_file", GOLDEN_FILES, ids=[f.name for f in GOLDEN_FILES])
def test_golden(golden_file: Path) -> None:
    data = json.loads(golden_file.read_text())
    result = render_scene(data)
    assert result.svg is not None, f"svg is None for {golden_file.name}"
    assert "<svg" in result.svg, f"svg tag missing in {golden_file.name}"
    assert "</svg>" in result.svg, f"closing svg tag missing in {golden_file.name}"


def test_xml_special_chars_in_labels() -> None:
    """Гипотеза A: спецсимволы XML в тексте не должны ломать SVG."""
    data = {
        "scene_type": "geometry",
        "canvas": {"width": 400, "height": 400, "x_min": -5, "x_max": 5, "y_min": -5, "y_max": 5},
        "style": {"theme": "light", "stroke_color": "#333333", "fill_color": "none", "font_size": 12, "font_family": "sans-serif"},
        "objects": [
            {"type": "point", "id": "p1", "x": 0, "y": 0, "label": "x < 0"},
            {"type": "point", "id": "p2", "x": 1, "y": 1, "label": "f(x) & g(x)"},
            {"type": "box", "id": "b1", "text": "a > b", "x": 10, "y": 10, "width": 100, "height": 40},
        ],
        "constraints": [],
        "annotations": [
            {"type": "label", "id": "ann1", "text": "x < 2 & y > 0", "anchor": "p1", "dx": 0, "dy": 0.3}
        ],
    }
    result = render_scene(data)
    assert result.svg is not None, f"svg is None, warnings: {result.warnings}"
    assert "<svg" in result.svg


def test_diagram_inline_math_mixed_content() -> None:
    """Inline `$...$` в диаграмме должен рендериться без падений."""
    data = {
        "scene_type": "diagram",
        "style": {"theme": "light", "stroke_color": "#333333", "fill_color": "#f8f8f8", "font_size": 12, "font_family": "sans-serif"},
        "objects": [
            {"type": "title", "id": "t", "text": "Предел: $x_n \\to a$"},
            {"type": "box", "id": "b1", "text": "Условие: $\\forall n>N$"},
            {"type": "box", "id": "b2", "text": "Оценка: $|x_n-a|<\\varepsilon$"},
            {"type": "arrow", "id": "arr", "from_point": "b1", "to_point": "b2", "label": "$N(\\varepsilon)$"},
            {"type": "text", "id": "txt", "text": "Следствие: $\\frac{1}{n}<\\varepsilon$"},
            {"type": "formula_block", "id": "f1", "formula": "\\lim_{n\\to\\infty}x_n=a"},
        ],
        "constraints": [],
        "annotations": [],
    }
    result = render_scene(data)
    assert result.svg is not None, f"svg is None, warnings: {result.warnings}"
    ET.fromstring(result.svg)
    # Маркеры $...$ не должны попадать в финальный SVG-текст.
    assert "$" not in result.svg


def test_diagram_mathtext_aliases_are_normalized() -> None:
    """Проблемные алиасы/Unicode в формулах не должны уходить в сырой текст."""
    data = {
        "scene_type": "diagram",
        "style": {"theme": "light", "stroke_color": "#333333", "fill_color": "#f8f8f8", "font_size": 12, "font_family": "sans-serif"},
        "objects": [
            {"type": "box", "id": "b1", "text": "Котангенс: $\\ctg \\alpha$"},
            {"type": "box", "id": "b2", "text": "Тангенс: $\\tg \\alpha$"},
            {"type": "arrow", "id": "a1", "from_point": "b1", "to_point": "b2", "label": "$x ≤ y → x × y$"},
            {"type": "formula_block", "id": "f1", "formula": "\\ctg\\alpha = \\frac{1}{\\tg\\alpha},\\; x ≠ y"},
        ],
        "constraints": [],
        "annotations": [],
    }
    result = render_scene(data)
    assert result.svg is not None, f"svg is None, warnings: {result.warnings}"
    ET.fromstring(result.svg)

    # Если нормализация не сработает, часть формулы попадёт в plain text как \ctg/\tg.
    assert "\\ctg" not in result.svg
    assert "\\tg" not in result.svg
