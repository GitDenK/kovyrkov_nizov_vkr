"""Offline analysis of scene-type distribution across the conspect variance runs.

Reads the saved `pipeline/output_runs/run{i}/task{j}/plan.json` files (no LLM
calls) and aggregates the distribution of resulting scene types
(`function_plot` / `geometry` / `diagram`) across (run, task) cells.

The mapping from pedagogical visual_type to scene_type is taken from
`pipeline.converter.SCENE_TYPE_MAP`; visual types not present in the map fall
back to `diagram`, mirroring the runtime behaviour of `convert_plan_to_scene`.

Outputs a Markdown summary suitable for inclusion in the thesis (§3.7).
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.converter import SCENE_TYPE_MAP  # noqa: E402

RUNS = (1, 2, 3)
TASKS = ("task4", "task6", "task8", "task12")
SCENE_TYPES = ("function_plot", "geometry", "diagram")


def cell_scene_distribution(plan_path: Path) -> Counter:
    """Return Counter[scene_type] for one plan.json (one run, one task)."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    counts: Counter = Counter()
    for entry in plan.get("plans", []):
        pl = entry.get("plan") or {}
        if not pl.get("need_visual"):
            continue
        vtype = pl.get("visual_type", "")
        scene_type = SCENE_TYPE_MAP.get(vtype, "diagram")
        counts[scene_type] += 1
    return counts


def main() -> int:
    base = ROOT / "pipeline" / "output_runs"
    if not base.exists():
        print(f"ERROR: {base} not found")
        return 1

    cells: dict[tuple[int, str], Counter] = {}
    for run in RUNS:
        for task in TASKS:
            p = base / f"run{run}" / task / "plan.json"
            if not p.exists():
                print(f"  skip missing: {p}")
                continue
            cells[(run, task)] = cell_scene_distribution(p)

    print("\n# Scene-type distribution across conspect variance runs")
    print()
    print("Source: pipeline/output_runs/run{1,2,3}/task{4,6,8,12}/plan.json")
    print(
        "Mapping: pipeline.converter.SCENE_TYPE_MAP "
        "(unknown types -> diagram, mirroring convert_plan_to_scene)."
    )
    print()

    print("## Per (run, task) cells")
    print()
    print("| run | task | function_plot | geometry | diagram | total |")
    print("|---|---|---:|---:|---:|---:|")
    for (run, task), c in sorted(cells.items()):
        total = sum(c.values())
        print(
            f"| {run} | {task} | {c.get('function_plot', 0)} | "
            f"{c.get('geometry', 0)} | {c.get('diagram', 0)} | {total} |"
        )

    print()
    print("## Per task aggregated across the three runs")
    print()
    print("| task | function_plot mean (range) | geometry mean (range) "
          "| diagram mean (range) | total mean (range) |")
    print("|---|---|---|---|---|")
    per_task: dict[str, dict] = {}
    for task in TASKS:
        per_run = []
        for run in RUNS:
            c = cells.get((run, task))
            if c is None:
                continue
            per_run.append({
                "fp": c.get("function_plot", 0),
                "geo": c.get("geometry", 0),
                "diag": c.get("diagram", 0),
                "tot": sum(c.values()),
            })
        if not per_run:
            continue
        agg = {
            k: (
                statistics.fmean(r[k] for r in per_run),
                min(r[k] for r in per_run),
                max(r[k] for r in per_run),
            )
            for k in ("fp", "geo", "diag", "tot")
        }
        per_task[task] = agg

        def fmt(v):
            mean, lo, hi = v
            if lo == hi:
                return f"{mean:.1f}"
            return f"{mean:.1f} ({lo}–{hi})"

        print(
            f"| {task} | {fmt(agg['fp'])} | {fmt(agg['geo'])} | "
            f"{fmt(agg['diag'])} | {fmt(agg['tot'])} |"
        )

    print()
    print("## Pooled overall (12 cells = 3 runs × 4 tasks)")
    print()
    pooled: Counter = Counter()
    for c in cells.values():
        pooled.update(c)
    total = sum(pooled.values())
    print(f"Total visuals across all cells: **{total}**")
    print()
    print("| scene_type | count | share |")
    print("|---|---:|---:|")
    for st in SCENE_TYPES:
        n = pooled.get(st, 0)
        share = n / total if total else 0
        print(f"| {st} | {n} | {share*100:.1f}% |")

    print()
    print("## Per scene type, mean share by run")
    print()
    print("| run | function_plot | geometry | diagram | total |")
    print("|---|---:|---:|---:|---:|")
    for run in RUNS:
        c: Counter = Counter()
        for task in TASKS:
            cell = cells.get((run, task))
            if cell:
                c.update(cell)
        tot = sum(c.values())
        if tot == 0:
            continue
        print(
            f"| {run} | "
            f"{c.get('function_plot',0)} ({c.get('function_plot',0)/tot*100:.1f}%) | "
            f"{c.get('geometry',0)} ({c.get('geometry',0)/tot*100:.1f}%) | "
            f"{c.get('diagram',0)} ({c.get('diagram',0)/tot*100:.1f}%) | "
            f"{tot} |"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
