from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field

from .common import Canvas, Style
from .objects import Label, SceneObject


# ---------------------------------------------------------------------------
# Constraints — дополнительные геометрические построения
# ---------------------------------------------------------------------------

class MedianConstraint(BaseModel):
    """Медиана треугольника из указанной вершины."""

    type: Literal["median"] = "median"
    id: str
    triangle: str
    vertex: str


class AltitudeConstraint(BaseModel):
    """Высота треугольника из указанной вершины."""

    type: Literal["altitude"] = "altitude"
    id: str
    triangle: str
    vertex: str


class BisectorConstraint(BaseModel):
    """Биссектриса треугольника из указанной вершины."""

    type: Literal["bisector"] = "bisector"
    id: str
    triangle: str
    vertex: str


class MidpointConstraint(BaseModel):
    """Середина отрезка. result_id — id создаваемой точки."""

    type: Literal["midpoint"] = "midpoint"
    id: str
    segment: str
    result_id: str


class RightAngleMarkerConstraint(BaseModel):
    """Пометка прямого угла при вершине vertex между лучами ray1 и ray2."""

    type: Literal["right_angle_marker"] = "right_angle_marker"
    id: str
    vertex: str
    ray1: str
    ray2: str


Constraint = Annotated[
    Union[
        MedianConstraint,
        AltitudeConstraint,
        BisectorConstraint,
        MidpointConstraint,
        RightAngleMarkerConstraint,
    ],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Основные модели pipeline
# ---------------------------------------------------------------------------

class InputRequest(BaseModel):
    """Входной запрос к сервису. scene_type обязателен и передаётся извне."""

    scene_type: Literal["function_plot", "geometry", "diagram"]
    content: str
    context: Optional[str] = None
    options: Optional[dict[str, Any]] = None


class Scene(BaseModel):
    """Структурированное описание сцены — основной контракт системы."""

    scene_type: Literal["function_plot", "geometry", "diagram"]
    canvas: Canvas = Field(default_factory=Canvas)
    style: Style = Field(default_factory=Style)
    objects: list[SceneObject]
    constraints: list[Constraint] = []
    annotations: list[Label] = []


class RenderResult(BaseModel):
    """Результат рендера: SVG-строка, предупреждения и метаданные."""

    svg: Optional[str] = None
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
