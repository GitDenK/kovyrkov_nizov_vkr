from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ключ OpenRouter — читается из OPENROUTER_API_KEY в .env или env-переменной
    openrouter_api_key: Optional[str] = None

    # Модель по умолчанию; меняется через LLM_MODEL в .env
    llm_model: str = "deepseek/deepseek-v3.2"

    # Лимит токенов ответа (scene JSON редко превышает 800 токенов)
    llm_max_tokens: int = 5000

    # Таймаут запроса к LLM в секундах; None — без таймаута
    llm_timeout: float = 60.0

    # 0.0 — детерминированный вывод (для тестирования), 0.7–1.0 — креативнее
    llm_temperature: float = 0.0

    # Режим instructor для from_openai():
    #   JSON         — json_object, работает с любым OpenAI-совместимым провайдером (дефолт)
    #   JSON_SCHEMA  — строгая схема, только OpenAI/Mistral/Cohere
    #   TOOLS        — function calling, если модель поддерживает
    llm_instructor_mode: str = "JSON"

    # Сохранение артефактов (включить/выключить без смены кода)
    save_artifacts: bool = True
    artifacts_dir: str = "artifacts"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
