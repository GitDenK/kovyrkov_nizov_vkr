#!/usr/bin/env bash
# ============================================================================
# ONLINE-репроизведение task 16: полный прогон геометрической ветки конвейера
# с обращением к языковой модели Llama-3.3-70B-Instruct-Turbo через Together AI.
#
# Что нужно:
#   - Python 3.10+ и зависимости из requirements.txt
#   - Переменная окружения TOGETHER_API_KEY с действующим ключом Together AI
#
# Что получите:
#   - JSON-план визуализации, сформированный языковой моделью (auto_task16_plan.json)
#   - HTML с пошаговым визуализированным решением (auto_task16.html)
#   - Метрики прогона (число запросов, токены, задержка)
#
# При успешном прогоне план должен быть структурно эквивалентным
# expected/auto_task16_plan.json, однако точные координаты и формулировки
# шагов могут несущественно отличаться между прогонами из-за стохастичности
# языковой модели.
# ============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

if [ -z "${TOGETHER_API_KEY:-}" ]; then
  echo "ERROR: TOGETHER_API_KEY не задан. Получите ключ на https://api.together.xyz" >&2
  exit 1
fi

echo "[1/2] Запускаю онлайн-прогон геометрической ветки на task16..."
python3 -m pipeline.geometry_corpus --tasks task16_trapezoid --runs 1

echo "[2/2] Готово. Сравните выход с эталоном:"
echo "  diff -u examples/task16_trapezoid_repro/expected/auto_task16_plan.json \\"
echo "          pipeline/output_geometry/auto_task16_plan.json"
