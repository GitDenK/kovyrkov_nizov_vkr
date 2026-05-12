"""
Минимальная проверка связи с OpenRouter.

Запуск из папки service/:
    python tools/check_openrouter.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.llm.config import settings

if not settings.openrouter_api_key:
    print("❌ OPENROUTER_API_KEY не задан в .env")
    sys.exit(1)

from openai import OpenAI

client = OpenAI(
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
)

print(f"Модель: {settings.llm_model}")
print("Отправляю запрос...")

response = client.chat.completions.create(
    model=settings.llm_model,
    max_tokens=50,
    messages=[{"role": "user", "content": "Напиши анекдот про программистов"}],
)

print(f"Ответ: {response.choices[0].message.content}")
print("✓ OpenRouter работает")
