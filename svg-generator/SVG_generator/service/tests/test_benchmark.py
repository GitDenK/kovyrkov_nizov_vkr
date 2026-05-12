"""
Benchmark-тесты качества SVG.

Режимы запуска:
  pytest tests/test_benchmark.py
      — прогоняет чекеры качества на существующих golden SVG-файлах

  pytest tests/test_benchmark.py --benchmark
      — прогоняет чекеры + инварианты на сохранённых результатах
        из tests/benchmark/results/ (нужен предварительный запуск run_benchmark.py)
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.benchmark.checkers import run_all_checks

_GOLDEN_DIR = Path(__file__).parent / "golden" / "preview"
_RESULTS_DIR = Path(__file__).parent / "benchmark" / "results"
_INVARIANTS_PATH = Path(__file__).parent / "benchmark" / "invariants.json"

_NS = "http://www.w3.org/2000/svg"


# ---------------------------------------------------------------------------
# Вспомогательные функции для проверки инвариантов
# ---------------------------------------------------------------------------

def _count_tag(root: ET.Element, tag: str) -> int:
    return len(list(root.iter(f"{{{_NS}}}{tag}")))


def _check_invariants(svg: str, inv: dict) -> list[str]:
    """Возвращает список нарушенных инвариантов (пустой = всё ок)."""
    failures = []
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return ["SVG XML невалиден"]

    if (n := inv.get("min_polyline_count")) and _count_tag(root, "polyline") < n:
        failures.append(f"polyline < {n} (найдено {_count_tag(root, 'polyline')})")
    if (n := inv.get("min_line_count")) and _count_tag(root, "line") < n:
        failures.append(f"line < {n} (найдено {_count_tag(root, 'line')})")
    if (n := inv.get("min_circle_count")) and _count_tag(root, "circle") < n:
        failures.append(f"circle < {n} (найдено {_count_tag(root, 'circle')})")
    if (n := inv.get("min_rect_count")) and _count_tag(root, "rect") < n:
        failures.append(f"rect < {n} (найдено {_count_tag(root, 'rect')})")
    if inv.get("has_text") and _count_tag(root, "text") == 0:
        failures.append("нет <text>-элементов")
    if inv.get("has_polyline") and _count_tag(root, "polyline") == 0:
        failures.append("нет <polyline>-элементов")

    return failures


# ---------------------------------------------------------------------------
# Тест 1: чекеры качества на golden SVG (всегда запускается)
# ---------------------------------------------------------------------------

def _golden_svgs() -> list[tuple[str, str]]:
    """Возвращает [(name, svg_content), ...] для всех golden SVG-файлов."""
    if not _GOLDEN_DIR.exists():
        return []
    return [
        (f.stem, f.read_text(encoding="utf-8"))
        for f in sorted(_GOLDEN_DIR.glob("*.svg"))
    ]


@pytest.mark.parametrize("name,svg", _golden_svgs(), ids=[f[0] for f in _golden_svgs()])
def test_golden_svg_quality(name: str, svg: str) -> None:
    """Запускает SVG-чекеры на каждом golden SVG-файле."""
    results = run_all_checks(svg)
    failures = [f"{check}: {r.message}" for check, r in results.items() if not r.ok]
    assert not failures, f"Golden SVG '{name}' не прошёл проверки:\n" + "\n".join(f"  - {f}" for f in failures)


# ---------------------------------------------------------------------------
# Тест 2: чекеры + инварианты на сохранённых результатах (--benchmark)
# ---------------------------------------------------------------------------

def _saved_results() -> list[tuple[str, dict]]:
    """Читает сохранённые результаты из benchmark/results/."""
    if not _RESULTS_DIR.exists():
        return []
    return [
        (f.stem, json.loads(f.read_text(encoding="utf-8")))
        for f in sorted(_RESULTS_DIR.glob("*.json"))
        if f.stem != "report"
    ]


@pytest.mark.benchmark
@pytest.mark.parametrize("case_id,meta", _saved_results(), ids=[r[0] for r in _saved_results()])
def test_benchmark_results(case_id: str, meta: dict) -> None:
    """Проверяет сохранённые результаты: SVG-чекеры + ручные инварианты."""
    # Чекеры уже записаны в meta во время run_benchmark.py
    failed_checks = [
        f"{name}: {c['message']}"
        for name, c in meta.get("checks", {}).items()
        if not c["ok"]
    ]
    assert not failed_checks, (
        f"Кейс '{case_id}' не прошёл SVG-проверки:\n" +
        "\n".join(f"  - {f}" for f in failed_checks)
    )

    # Инварианты (если есть для данного кейса)
    if _INVARIANTS_PATH.exists():
        invariants = json.loads(_INVARIANTS_PATH.read_text(encoding="utf-8"))
        if case_id in invariants:
            svg_path = _RESULTS_DIR / f"{case_id}.svg"
            if svg_path.exists():
                svg = svg_path.read_text(encoding="utf-8")
                failures = _check_invariants(svg, invariants[case_id])
                assert not failures, (
                    f"Кейс '{case_id}' нарушает инварианты:\n" +
                    "\n".join(f"  - {f}" for f in failures)
                )
