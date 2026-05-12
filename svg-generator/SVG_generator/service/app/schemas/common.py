from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Canvas(BaseModel):
    """Параметры холста: размер в пикселях и диапазон мировых координат."""

    width: float = 400
    height: float = 400
    x_min: float = -5.0
    x_max: float = 5.0
    y_min: float = -5.0
    y_max: float = 5.0


class Style(BaseModel):
    """Глобальный стиль сцены."""

    theme: Literal["light", "dark"] = "light"
    stroke_color: str = "#333333"
    fill_color: str = "none"
    font_size: int = 12
    font_family: str = "sans-serif"


class ObjectStyle(BaseModel):
    """Локальное переопределение стиля для отдельного объекта."""

    stroke: Optional[str] = None
    fill: Optional[str] = None
    stroke_width: Optional[float] = None
    # "solid" | "dashed" | "dotted"
    dash: Optional[Literal["solid", "dashed", "dotted"]] = None
