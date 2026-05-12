"""
Benchmark runner: запускает все кейсы параллельно через реальный LLM-pipeline.

Использование:
    python tests/run_benchmark.py
    python tests/run_benchmark.py --cases tests/benchmark/cases.json --out tests/benchmark/results/

Результат каждого кейса сохраняется в --out:
    {id}.svg   — SVG-файл для просмотра в браузере
    {id}.json  — метаданные: input, warnings, результаты чекеров

Итоговый отчёт: tests/benchmark/results/report.md
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# Добавляем корень сервиса в sys.path, чтобы импортировать app.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.orchestrator.orchestrator import generate_svg_from_request
from app.schemas import InputRequest
from tests.benchmark.checkers import run_all_checks


async def _run_case(case: dict, out_dir: Path) -> dict:
    """Запускает один кейс через pipeline и возвращает сводку."""
    case_id = case["id"]
    scene_type = case["scene_type"]
    content = case["content"]

    t0 = time.monotonic()
    error = None
    svg = None
    warnings: list[str] = []

    try:
        request = InputRequest(scene_type=scene_type, content=content)
        result = await generate_svg_from_request(request)
        svg = result.svg
        warnings = result.warnings or []
    except Exception as e:
        error = str(e)

    elapsed = time.monotonic() - t0

    checks: dict = {}
    if svg:
        check_results = run_all_checks(svg)
        checks = {name: {"ok": r.ok, "message": r.message} for name, r in check_results.items()}

        # Сохраняем SVG
        (out_dir / f"{case_id}.svg").write_text(svg, encoding="utf-8")
    else:
        checks = {name: {"ok": False, "message": "SVG отсутствует"} for name in
                  ["svg_valid", "no_nan", "within_canvas", "labels_readable", "diagram_label_boxes_overlap"]}

    # Сохраняем метаданные
    meta = {
        "id": case_id,
        "scene_type": scene_type,
        "content": content,
        "elapsed_s": round(elapsed, 2),
        "svg_generated": svg is not None,
        "warnings": warnings,
        "error": error,
        "checks": checks,
    }
    (out_dir / f"{case_id}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    all_ok = svg is not None and all(c["ok"] for c in checks.values())
    status = "✓" if all_ok else "✗"
    print(f"  {status} [{elapsed:5.1f}s] {case_id} ({scene_type})" +
          ("" if all_ok else f"  ← {error or ', '.join(k for k, c in checks.items() if not c['ok'])}"))

    return meta


def _build_report(summaries: list[dict], out_dir: Path) -> str:
    """Строит Markdown-отчёт и сохраняет его в out_dir/report.md."""
    total = len(summaries)
    passed = sum(1 for s in summaries if s["svg_generated"] and all(c["ok"] for c in s["checks"].values()))
    failed_ids = [s["id"] for s in summaries if not (s["svg_generated"] and all(c["ok"] for c in s["checks"].values()))]

    lines = [
        "# Benchmark Report",
        "",
        f"**Кейсов:** {total}  |  **Прошли:** {passed}  |  **Провалились:** {total - passed}",
        "",
        "## Сводная таблица",
        "",
        "| id | scene_type | time | svg | svg_valid | no_nan | within_canvas | labels_readable | diagram_label_boxes_overlap |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for s in summaries:
        checks = s["checks"]
        row = [
            s["id"],
            s["scene_type"],
            f"{s['elapsed_s']:.1f}s",
            "✓" if s["svg_generated"] else "✗",
            "✓" if checks.get("svg_valid", {}).get("ok") else "✗",
            "✓" if checks.get("no_nan", {}).get("ok") else "✗",
            "✓" if checks.get("within_canvas", {}).get("ok") else "✗",
            "✓" if checks.get("labels_readable", {}).get("ok") else "✗",
            "✓" if checks.get("diagram_label_boxes_overlap", {}).get("ok") else "✗",
        ]
        lines.append("| " + " | ".join(row) + " |")

    lines += [
        "",
        "## Провалившиеся кейсы",
        "",
    ]

    if not failed_ids:
        lines.append("Все кейсы прошли проверку.")
    else:
        for s in summaries:
            if s["id"] not in failed_ids:
                continue
            lines.append(f"### {s['id']}")
            if s.get("error"):
                lines.append(f"- **Ошибка pipeline:** {s['error']}")
            if not s["svg_generated"]:
                lines.append("- SVG не сгенерирован")
            for check_name, c in s["checks"].items():
                if not c["ok"]:
                    lines.append(f"- **{check_name}:** {c['message']}")
            if s.get("warnings"):
                for w in s["warnings"]:
                    lines.append(f"- ⚠ {w}")
            lines.append("")

    report = "\n".join(lines)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    return report


async def main(cases_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    print(f"Запуск {len(cases)} кейсов параллельно...\n")

    t_start = time.monotonic()
    tasks = [_run_case(case, out_dir) for case in cases]
    summaries = await asyncio.gather(*tasks)
    elapsed_total = time.monotonic() - t_start

    print(f"\nВсего: {elapsed_total:.1f}s")

    report = _build_report(list(summaries), out_dir)
    print(f"\nОтчёт сохранён: {out_dir / 'report.md'}")
    print("\n" + "─" * 60)
    print(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SVG Generator Benchmark Runner")
    parser.add_argument(
        "--cases",
        default="tests/benchmark/cases.json",
        help="Путь к файлу с кейсами (по умолчанию: tests/benchmark/cases.json)",
    )
    parser.add_argument(
        "--out",
        default="tests/benchmark/results",
        help="Директория для сохранения результатов (по умолчанию: tests/benchmark/results/)",
    )
    args = parser.parse_args()

    asyncio.run(main(Path(args.cases), Path(args.out)))
