#!/usr/bin/env bash
# ============================================================================
# OFFLINE-репроизведение task 16 (трапеция с перпендикулярными диагоналями).
#
# Запускает скрипт-демонстрацию pipeline/geometry_task16_demo.py, который
# использует уже найденные координаты и пошагово рисует тот же чертёж,
# что попадает в figure 3.2 диплома (без обращения к языковой модели —
# для проверки работы движка рендеринга).
#
# Что нужно: только Python 3.10+ и зависимости из requirements.txt.
# Что получите: HTML с пошаговым решением + четыре PDF/SVG-кадра.
# ============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

echo "[1/2] Запускаю офлайн-демо геометрической ветки task16..."
python3 -m pipeline.geometry_task16_demo

echo "[2/2] Готово. Артефакты сохранены в:"
ls -la pipeline/output_geometry/task16_trapezoid.html
echo "  Эталон для сравнения:"
echo "  examples/task16_trapezoid_repro/expected/task16_trapezoid_4steps.html"
