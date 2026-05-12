from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from .common import ObjectStyle


class Point(BaseModel):
    """Точка на плоскости. Координаты задаются в мировой системе."""

    type: Literal["point"] = "point"
    id: str
    x: float
    y: float
    label: Optional[str] = None
    style: Optional[ObjectStyle] = None


class Segment(BaseModel):
    """Отрезок между двумя точками. Ссылается на id объектов Point."""

    type: Literal["segment"] = "segment"
    id: str
    from_point: str
    to_point: str
    style: Optional[ObjectStyle] = None


class Circle(BaseModel):
    """Окружность с центром в точке Point и заданным радиусом."""

    type: Literal["circle"] = "circle"
    id: str
    center: str
    radius: float
    style: Optional[ObjectStyle] = None


class Triangle(BaseModel):
    """Треугольник, заданный тремя вершинами (id объектов Point)."""

    type: Literal["triangle"] = "triangle"
    id: str
    vertices: list[str] = Field(..., min_length=3, max_length=3)
    style: Optional[ObjectStyle] = None


class FunctionCurve(BaseModel):
    """График функции одной переменной. expression — Python-выражение от x."""

    type: Literal["function_curve"] = "function_curve"
    id: str
    expression: str
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    style: Optional[ObjectStyle] = None


class Label(BaseModel):
    """Текстовая подпись, привязанная к точке (anchor = id Point)."""

    type: Literal["label"] = "label"
    id: str
    text: str
    anchor: str
    dx: float = 0.0
    dy: float = 0.0
    style: Optional[ObjectStyle] = None


class Box(BaseModel):
    """Смысловой блок диаграммы. Геометрию вычисляет renderer."""

    type: Literal["box"] = "box"
    id: str
    text: str
    style: Optional[ObjectStyle] = None


class Arrow(BaseModel):
    """Стрелка между двумя объектами (Point или Box) для диаграмм."""

    type: Literal["arrow"] = "arrow"
    id: str
    from_point: str
    to_point: str
    label: Optional[str] = None
    style: Optional[ObjectStyle] = None


class Text(BaseModel):
    """Произвольный смысловой текст диаграммы. Позицию выбирает renderer."""

    type: Literal["text"] = "text"
    id: str
    text: str
    font_size: Optional[int] = None
    style: Optional[ObjectStyle] = None


class Title(BaseModel):
    """Заголовок диаграммы. Позицию и перенос вычисляет renderer."""

    type: Literal["title"] = "title"
    id: str
    text: str
    style: Optional[ObjectStyle] = None


class FormulaBlock(BaseModel):
    """Формульный блок диаграммы. Формат — LaTeX-подмножество для Ziamath."""

    type: Literal["formula_block"] = "formula_block"
    id: str
    formula: str
    font_size: Optional[int] = None
    style: Optional[ObjectStyle] = None


# Дискриминированный union всех объектов сцены
SceneObject = Annotated[
    Union[Point, Segment, Circle, Triangle, FunctionCurve, Label, Box, Arrow, Text, Title, FormulaBlock],
    Field(discriminator="type"),
]
