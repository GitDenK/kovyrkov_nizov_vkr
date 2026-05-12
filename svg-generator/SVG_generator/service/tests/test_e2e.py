"""
E2E тесты: text → scene → svg.

- Мок-тесты (всегда запускаются): патчат generate_scene, не тратят токены.
- Интеграционные (@pytest.mark.integration): реальные LLM-вызовы.
  Запуск: pytest --integration
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.llm.adapter import GenerateResult
from app.orchestrator.orchestrator import generate_svg_from_request
from app.schemas import InputRequest, Scene

# ---------------------------------------------------------------------------
# Вспомогательные scene JSON для мок-тестов
# ---------------------------------------------------------------------------

_MOCK_SCENES: dict[str, dict] = {
    "function_plot": {
        "scene_type": "function_plot",
        "objects": [
            {"type": "function_curve", "id": "f", "expression": "x**2", "x_min": -3, "x_max": 3},
            {"type": "point", "id": "v", "x": 0, "y": 0, "label": "O"},
        ],
        "constraints": [],
        "annotations": [],
    },
    "geometry": {
        "scene_type": "geometry",
        "objects": [
            {"type": "point", "id": "A", "x": 0, "y": 0, "label": "A"},
            {"type": "point", "id": "B", "x": 4, "y": 0, "label": "B"},
            {"type": "point", "id": "C", "x": 2, "y": 3, "label": "C"},
            {"type": "triangle", "id": "tri", "vertices": ["A", "B", "C"]},
        ],
        "constraints": [{"type": "altitude", "id": "alt", "triangle": "tri", "vertex": "C"}],
        "annotations": [],
    },
    "diagram": {
        "scene_type": "diagram",
        "objects": [
            {"type": "box", "id": "a", "text": "f(x)"},
            {"type": "box", "id": "b", "text": "f'(x)"},
            {"type": "arrow", "id": "arr", "from_point": "a", "to_point": "b"},
        ],
        "constraints": [],
        "annotations": [],
    },
}


def _make_mock_result(scene_type: str) -> GenerateResult:
    scene = Scene.model_validate(_MOCK_SCENES[scene_type])
    return GenerateResult(
        scene=scene,
        request_messages=[{"role": "user", "content": "mock"}],
        response_raw='{"mock": true}',
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )


# ---------------------------------------------------------------------------
# Мок-тесты (не требуют LLM, всегда запускаются)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("scene_type,content", [
    ("function_plot", "График параболы y = x²"),
    ("function_plot", "Синус на отрезке [-pi, pi]"),
    ("geometry", "Треугольник ABC с высотой из вершины C"),
    ("geometry", "Прямоугольный треугольник с биссектрисой"),
    ("diagram", "Связь функции и её производной"),
    ("diagram", "Понятие предела последовательности"),
])
async def test_mock_pipeline(scene_type: str, content: str) -> None:
    """Мок: проверяет весь pipeline orchestrator→renderer без LLM."""
    request = InputRequest(scene_type=scene_type, content=content)
    mock_result = _make_mock_result(scene_type)

    # AsyncMock — generate_scene теперь async, save остаётся синхронным
    with patch("app.llm.adapter.generate_scene", new=AsyncMock(return_value=mock_result)), \
         patch("app.llm.artifact_store.save"):
        result = await generate_svg_from_request(request)

    assert result.svg is not None, f"svg is None для {scene_type!r}: {result.warnings}"
    assert "<svg" in result.svg
    assert "</svg>" in result.svg


# ---------------------------------------------------------------------------
# Интеграционные тесты (реальные LLM-вызовы, только с --integration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("scene_type,content", [
    # function_plot
    ("function_plot", "График параболы y = x² на отрезке [-3, 3]"),
    ("function_plot", "График синуса и косинуса на одних осях"),
    ("function_plot", "График функции f(x) = e^(-x²) — колокол Гаусса"),
    # geometry
    ("geometry", "Треугольник ABC, где AB=6, высота из C, медиана из A"),
    ("geometry", "Прямоугольный треугольник с биссектрисой из прямого угла"),
    ("geometry", "Окружность, вписанная в треугольник ABC"),
    # diagram
    ("diagram", "Схема: понятие производной функции в точке"),
    ("diagram", "Связь между интегралом и площадью под графиком"),
    ("diagram", "Алгоритм нахождения корней квадратного уравнения"),
    ("diagram", "Концептуальная схема: теорема Пифагора и её следствия"),
])
async def test_integration_pipeline(scene_type: str, content: str) -> None:
    """Интеграционный тест: реальный вызов LLM → scene → svg."""
    request = InputRequest(scene_type=scene_type, content=content)
    result = await generate_svg_from_request(request)
    assert result.svg is not None, (
        f"svg is None для {scene_type!r} ({content!r}): warnings={result.warnings}"
    )
    assert "<svg" in result.svg
    assert "</svg>" in result.svg
