"""
LLM Adapter: генерирует Scene из текстового описания задачи.

Использует OpenRouter (OpenAI-совместимый API) + instructor для structured output.
Модель и режим настраиваются через .env без изменения кода.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import instructor
from openai import AsyncOpenAI

from app.llm.config import settings
from app.schemas import Scene

_PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class GenerateResult:
    """Результат вызова LLM: сцена + данные для логирования."""
    scene: Scene
    request_messages: list[dict]
    response_raw: str
    usage: dict = field(default_factory=dict)


def _load_prompt(scene_type: str) -> str:
    """Загружает системный промпт для заданного типа сцены."""
    path = _PROMPTS_DIR / f"{scene_type}.txt"
    return path.read_text(encoding="utf-8")


def _make_async_client() -> instructor.AsyncInstructor:
    """Создаёт async instructor-клиент поверх AsyncOpenAI с настройками из config."""
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY не задан. Добавь его в .env или переменные окружения."
        )
    mode = getattr(instructor.Mode, settings.llm_instructor_mode, instructor.Mode.JSON)
    raw = AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=settings.llm_timeout,
    )
    return instructor.from_openai(raw, mode=mode)


logger = logging.getLogger(__name__)


async def generate_scene(text: str, scene_type: str) -> GenerateResult:
    """
    Асинхронно вызывает LLM и возвращает GenerateResult со сценой и данными для логирования.

    instructor делает до max_retries повторов при ValidationError,
    передавая описание ошибки обратно модели.
    """
    client = _make_async_client()
    system_prompt = _load_prompt(scene_type)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]

    logger.info("  → LLM request | model=%s | mode=%s", settings.llm_model, settings.llm_instructor_mode)

    scene, completion = await client.chat.completions.create_with_completion(
        model=settings.llm_model,
        response_model=Scene,
        max_retries=2,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
        messages=messages,
    )

    response_raw = completion.choices[0].message.content or ""
    usage = {}
    if completion.usage:
        usage = {
            "prompt_tokens": completion.usage.prompt_tokens,
            "completion_tokens": completion.usage.completion_tokens,
            "total_tokens": completion.usage.total_tokens,
        }

    return GenerateResult(
        scene=scene,
        request_messages=messages,
        response_raw=response_raw,
        usage=usage,
    )
