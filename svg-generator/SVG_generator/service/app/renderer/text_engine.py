from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass
class TextRenderResult:
    width: float
    height: float
    min_x: float
    min_y: float
    inner_svg: str
    warnings: list[str]


class ZiaTextEngine:
    """Единый движок рендера текста и формул на базе Ziamath."""

    def __init__(self) -> None:
        self._measure_cache: dict[tuple[str, int], tuple[float, float]] = {}
        self._render_cache: dict[tuple[str, int, str], TextRenderResult] = {}

    def split_math_segments(self, text: str) -> list[tuple[str, str]]:
        """Делит строку на plain/math сегменты по `$...$`."""
        segments: list[tuple[str, str]] = []
        buf: list[str] = []
        in_math = False
        i = 0

        while i < len(text):
            ch = text[i]
            if ch == "\\" and i + 1 < len(text) and text[i + 1] == "$":
                buf.append("$")
                i += 2
                continue
            if ch == "$":
                if in_math:
                    segments.append(("math", "".join(buf)))
                    buf = []
                    in_math = False
                else:
                    if buf:
                        segments.append(("plain", "".join(buf)))
                    buf = []
                    in_math = True
                i += 1
                continue
            buf.append(ch)
            i += 1

        # Незакрытый math-сегмент не валим: рендерим как plain.
        if in_math:
            return [("plain", text.replace("\\$", "$"))]
        if buf:
            segments.append(("plain", "".join(buf)))

        return segments or [("plain", "")]

    def wrap_text(self, text: str, max_width_px: float, font_size: int) -> list[str]:
        """Переносит строку по ширине, сохраняя inline-формулы неделимыми."""
        paragraphs = text.replace("\\n", "\n").split("\n")
        result: list[str] = []

        for para in paragraphs:
            if not para.strip():
                result.append("")
                continue

            tokens: list[str] = []
            for kind, value in self.split_math_segments(para):
                if kind == "math":
                    tokens.append(f"${value}$")
                else:
                    tokens.extend(value.split())

            current = ""
            for token in tokens:
                candidate = (current + " " + token).strip() if current else token
                width, _ = self.measure(candidate, font_size)
                if width <= max_width_px:
                    current = candidate
                else:
                    if current:
                        result.append(current)
                    current = token

            if current:
                result.append(current)

        return result or [""]

    def measure(self, text: str, font_size: int) -> tuple[float, float]:
        """Измеряет строку в px через Ziamath."""
        key = (text, font_size)
        cached = self._measure_cache.get(key)
        if cached is not None:
            return cached

        source = self._to_ziamath_source(text)
        try:
            import ziamath

            ztxt = ziamath.Text(source, size=font_size)
            xmin, xmax, ymin, ymax = ztxt.bbox()
            width = max(1.0, float(xmax - xmin))
            height = max(1.0, float(ymax - ymin))
        except Exception:
            width = max(1.0, len(text) * font_size * 0.56)
            height = max(1.0, font_size * 1.2)

        measured = (width, height)
        self._measure_cache[key] = measured
        return measured

    def render_line(
        self,
        text: str,
        x: float,
        y: float,
        font_size: int,
        fill: str,
        text_anchor: str = "start",
    ) -> tuple[list[str], list[str]]:
        """
        Рендерит строку в SVG.
        Возвращает (svg_lines, warnings).
        """
        warnings: list[str] = []
        result = self._render_svg_inner(text=text, font_size=font_size, fill=fill)
        if result is None or not result.inner_svg.strip():
            fallback_text = _strip_math_markers(text)
            fallback = [
                f'  <text x="{x:.1f}" y="{y:.1f}" text-anchor="{text_anchor}" dominant-baseline="middle" '
                f'font-size="{font_size}" fill="{fill}">{html.escape(fallback_text)}</text>'
            ]
            fallback_warning = f"Ziamath fallback for text: {text[:80]}"
            if result is not None and result.warnings:
                return fallback, result.warnings + [fallback_warning]
            return fallback, [fallback_warning]

        warnings.extend(result.warnings)
        if text_anchor == "middle":
            start_x = x - result.width / 2.0
        elif text_anchor == "end":
            start_x = x - result.width
        else:
            start_x = x
        # Учитываем смещение viewBox, чтобы центрирование совпадало с визуальной рамкой текста.
        start_x -= result.min_x
        start_y = y - result.height / 2.0 - result.min_y

        return [
            f'  <g transform="translate({start_x:.1f}, {start_y:.1f})">',
            result.inner_svg,
            "  </g>",
        ], warnings

    def formula_supported(self, formula: str, font_size: int) -> tuple[bool, str | None]:
        """Проверяет, поддерживается ли формула движком Ziamath."""
        source = formula.strip()
        if source.startswith("$") and source.endswith("$") and len(source) > 2:
            source = source[1:-1].strip()
        try:
            import ziamath

            ziamath.Text(source, size=font_size).bbox()
            return True, None
        except Exception as exc:
            return False, f"Formula unsupported by Ziamath: {formula[:80]} ({exc})"

    def _render_svg_inner(self, text: str, font_size: int, fill: str) -> TextRenderResult:
        key = (text, font_size, fill)
        cached = self._render_cache.get(key)
        if cached is not None:
            return cached

        source = self._to_ziamath_source(text)
        try:
            import ziamath

            svg = ziamath.Text(source, size=font_size, color=fill).svg()
            root = ET.fromstring(svg)
            width = _parse_svg_length(root.get("width"))
            height = _parse_svg_length(root.get("height"))
            if (width <= 0 or height <= 0) and root.get("viewBox"):
                view_box = root.get("viewBox", "").split()
                if len(view_box) == 4:
                    width = float(view_box[2])
                    height = float(view_box[3])
            min_x = 0.0
            min_y = 0.0
            parsed_viewbox = _parse_viewbox(root.get("viewBox"))
            if parsed_viewbox is not None:
                min_x, min_y, vb_width, vb_height = parsed_viewbox
                if width <= 0:
                    width = vb_width
                if height <= 0:
                    height = vb_height
            if width <= 0 or height <= 0:
                width, height = self.measure(text, font_size)

            inner = "\n".join(ET.tostring(child, encoding="unicode") for child in root)
            rendered = TextRenderResult(
                width=max(1.0, width),
                height=max(1.0, height),
                min_x=min_x,
                min_y=min_y,
                inner_svg=inner,
                warnings=[],
            )
            self._render_cache[key] = rendered
            return rendered
        except Exception as exc:
            return TextRenderResult(
                width=max(1.0, len(text) * font_size * 0.56),
                height=max(1.0, font_size * 1.2),
                min_x=0.0,
                min_y=0.0,
                inner_svg="",
                warnings=[f"Ziamath render error: {exc}"],
            )

    def _to_ziamath_source(self, text: str) -> str:
        """
        Готовит исходник для Ziamath без агрессивных преобразований.
        Важно: не оборачиваем plain-текст в ``\\text{...}``, иначе LaTeX-команды
        (например, ``\\text{...}`` из входа) начинают отображаться как литералы.
        """
        source = text.replace("\\n", "\n").strip()
        if not source:
            return " "
        return source


def _strip_math_markers(text: str) -> str:
    clean = re.sub(r"(?<!\\)\$", "", text)
    return clean.replace("\\$", "$")


def _parse_svg_length(value: str | None) -> float:
    if not value:
        return 0.0
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", value)
    return float(match.group(1)) if match else 0.0


def _parse_viewbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parts = value.strip().replace(",", " ").split()
    if len(parts) != 4:
        return None
    try:
        min_x, min_y, width, height = (float(part) for part in parts)
        return min_x, min_y, width, height
    except ValueError:
        return None
