"""
Хранилище артефактов: сохраняет полный след каждого запроса для отладки.

Включается флагом SAVE_ARTIFACTS=true в .env (по умолчанию включено).
Чтобы сменить хранилище (файлы → БД → S3) — менять только этот модуль.

Структура артефакта:
  {ts}_{scene_type}.json  — полный JSON: запрос, ответ модели, scene, warnings, svg
  {ts}_{scene_type}.svg   — SVG-файл для просмотра в браузере
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from app.llm.config import settings

logger = logging.getLogger(__name__)


def save(artifact: dict) -> None:
    """Сохраняет артефакт. При SAVE_ARTIFACTS=false — ничего не делает."""
    if not settings.save_artifacts:
        return
    try:
        out_dir = Path(settings.artifacts_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        scene_type = artifact.get("scene_type", "unknown")
        stem = f"{ts}_{scene_type}"

        # Полный JSON-артефакт (без SVG — он отдельно)
        json_artifact = {k: v for k, v in artifact.items() if k != "svg"}
        (out_dir / f"{stem}.json").write_text(
            json.dumps(json_artifact, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # SVG отдельным файлом для удобного просмотра в браузере
        svg = artifact.get("svg")
        if svg:
            (out_dir / f"{stem}.svg").write_text(svg, encoding="utf-8")

    except Exception as e:
        logger.warning("artifact_store: не удалось сохранить артефакт: %s", e)
