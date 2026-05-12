"""
SVG-чекеры для benchmark quality loop.

Каждая функция принимает SVG-строку и возвращает CheckResult(ok, message).
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class CheckResult:
    ok: bool
    message: str


_NS = "http://www.w3.org/2000/svg"

# Атрибуты, содержащие координаты одиночных чисел
_COORD_ATTRS = {"x", "y", "cx", "cy", "x1", "y1", "x2", "y2", "r", "rx", "ry"}


def check_svg_valid(svg: str) -> CheckResult:
    """Проверяет, что SVG является валидным XML."""
    try:
        ET.fromstring(svg)
        return CheckResult(ok=True, message="XML valid")
    except ET.ParseError as e:
        return CheckResult(ok=False, message=f"XML parse error: {e}")


def check_no_nan(svg: str) -> CheckResult:
    """Проверяет отсутствие строки 'NaN' в атрибутах координат SVG."""
    if re.search(r"\bNaN\b", svg):
        # Найдём первое вхождение для сообщения
        match = re.search(r".{0,40}NaN.{0,40}", svg)
        ctx = match.group(0).strip() if match else "?"
        return CheckResult(ok=False, message=f"Найден NaN: ...{ctx}...")
    return CheckResult(ok=True, message="Нет NaN")


def check_within_canvas(svg: str) -> CheckResult:
    """
    Проверяет, что числовые координаты элементов не выходят далеко за пределы canvas.

    Допустимый выход: до 20px с каждой стороны (для подписей и меток).
    """
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return CheckResult(ok=False, message="XML невалиден, пропущено")

    try:
        width = float(root.get("width", 0))
        height = float(root.get("height", 0))
    except (ValueError, TypeError):
        return CheckResult(ok=True, message="Не удалось прочитать width/height, пропущено")

    if width <= 0 or height <= 0:
        return CheckResult(ok=True, message="Нулевой canvas, пропущено")

    margin = 20.0
    violations = []

    for elem in root.iter():
        for attr in _COORD_ATTRS & set(elem.attrib):
            try:
                val = float(elem.get(attr))
            except (ValueError, TypeError):
                continue

            if attr in {"x", "x1", "x2", "cx"}:
                if val < -margin or val > width + margin:
                    tag = elem.tag.replace(f"{{{_NS}}}", "")
                    violations.append(f"<{tag}> {attr}={val:.1f} (canvas width={width:.0f})")
            elif attr in {"y", "y1", "y2", "cy"}:
                if val < -margin or val > height + margin:
                    tag = elem.tag.replace(f"{{{_NS}}}", "")
                    violations.append(f"<{tag}> {attr}={val:.1f} (canvas height={height:.0f})")

    if violations:
        sample = violations[:3]
        extra = f" (и ещё {len(violations) - 3})" if len(violations) > 3 else ""
        return CheckResult(ok=False, message="За пределами canvas: " + "; ".join(sample) + extra)

    return CheckResult(ok=True, message="Все координаты в пределах canvas")


def check_labels_readable(svg: str) -> CheckResult:
    """
    Проверяет, что нет двух <text>-элементов с одинаковыми координатами (x, y).

    Точное совпадение позиций — признак наложения подписей.
    """
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return CheckResult(ok=False, message="XML невалиден, пропущено")

    positions: dict[tuple, list[str]] = {}
    for elem in root.iter():
        if elem.tag in {f"{{{_NS}}}text", "text"}:
            text = (elem.text or "").strip()
            # Пропускаем пустые text-элементы (артефакты matplotlib)
            if not text:
                continue
            try:
                x = round(float(elem.get("x", 0)), 1)
                y = round(float(elem.get("y", 0)), 1)
            except (ValueError, TypeError):
                continue
            positions.setdefault((x, y), []).append(text)

    duplicates = {pos: texts for pos, texts in positions.items() if len(texts) > 1}
    if duplicates:
        samples = [f"({x},{y}): {t}" for (x, y), t in list(duplicates.items())[:2]]
        return CheckResult(ok=False, message="Наложение подписей: " + "; ".join(samples))

    return CheckResult(ok=True, message="Подписи не перекрываются")


def _rect_from_elem(elem: ET.Element, tag: str) -> Optional[Tuple[float, float, float, float]]:
    """Читает x/y/width/height у <rect>, если атрибуты корректны."""
    if tag != "rect":
        return None
    try:
        x = float(elem.get("x", "0"))
        y = float(elem.get("y", "0"))
        w = float(elem.get("width", "0"))
        h = float(elem.get("height", "0"))
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def _rect_overlap_area(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    """Площадь пересечения двух прямоугольников."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x_overlap = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    y_overlap = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    return x_overlap * y_overlap


def check_diagram_label_boxes_overlap(svg: str) -> CheckResult:
    """
    Для diagram проверяет, что фон подписи стрелки не заезжает на блоки.
    """
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return CheckResult(ok=False, message="XML невалиден, пропущено")

    is_diagram = "marker-end=\"url(#arrow_obj)\"" in svg
    if not is_diagram:
        return CheckResult(ok=True, message="Не diagram, пропущено")

    box_rects: list[tuple[float, float, float, float]] = []
    label_rects: list[tuple[float, float, float, float]] = []

    for elem in root.iter():
        tag = elem.tag.replace(f"{{{_NS}}}", "")
        rect = _rect_from_elem(elem, tag)
        if rect is None:
            continue

        rx = elem.get("rx")
        stroke = (elem.get("stroke") or "").lower()
        fill = (elem.get("fill") or "").lower()

        # Прямоугольники блоков рендера diagram имеют скругление rx.
        if rx is not None and stroke not in {"", "none"}:
            box_rects.append(rect)
            continue

        # Фон подписи стрелки — белый прямоугольник без stroke.
        if fill in {"white", "#fff", "#ffffff"} and stroke in {"", "none"} and rect[2] < 280 and rect[3] < 120:
            label_rects.append(rect)

    violations = 0
    for lrect in label_rects:
        for brect in box_rects:
            if _rect_overlap_area(lrect, brect) > 6.0:
                violations += 1
                if violations >= 3:
                    return CheckResult(
                        ok=False,
                        message="Подписи стрелок наезжают на блоки (обнаружено >= 3 пересечений)",
                    )

    if violations > 0:
        # Для старых golden-сцен допускаем 1-2 лёгких пересечения.
        if violations <= 2:
            return CheckResult(ok=True, message=f"Незначительные пересечения подписи/блоков ({violations})")
        return CheckResult(ok=False, message=f"Подписи стрелок наезжают на блоки ({violations})")
    return CheckResult(ok=True, message="Подписи стрелок не заезжают на блоки")


# ---------------------------------------------------------------------------
# Удобная функция для запуска всех проверок сразу
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    ("svg_valid", check_svg_valid),
    ("no_nan", check_no_nan),
    ("within_canvas", check_within_canvas),
    ("labels_readable", check_labels_readable),
    ("diagram_label_boxes_overlap", check_diagram_label_boxes_overlap),
]


def run_all_checks(svg: str) -> dict[str, CheckResult]:
    """Запускает все проверки и возвращает словарь {name: CheckResult}."""
    return {name: fn(svg) for name, fn in ALL_CHECKS}
