"""Temperature ablation on task4 (probability conspect).

Run the conspect planner on a fixed conspect file at multiple sampling
temperatures, with N independent runs per temperature, and aggregate the
metrics. Designed to attack the variance observed in task4 in the main
benchmark, where `visuals_planned` had very high dispersion (mean ~7,
range 5--11 across three runs).

Hypothesis: the dispersion is driven mostly by sampling temperature; at
T=0.0 (greedy decoding) the planner should produce identical or near-identical
outputs, at T=0.7 the dispersion should grow.

Outputs:
    pipeline/output_temperature/T{t}/run{i}/plan.json
    pipeline/output_temperature/temperature_ablation_summary.json
    pipeline/output_temperature/temperature_ablation_summary.md

Usage:
    TOGETHER_API_KEY=... python3 pipeline/run_temperature_ablation.py
    TOGETHER_API_KEY=... python3 pipeline/run_temperature_ablation.py \
        --conspect conspects/task4.md --temperatures 0.0 0.3 0.7 --runs 3
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from visual_planner_v2 import VisualPlannerV2  # noqa: E402


METRIC_FIELDS = (
    "total_sections",
    "sections_analyzed",
    "visuals_planned",
    "total_tokens_in",
    "total_tokens_out",
    "total_time_sec",
)


def aggregate(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 2),
        "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
        "min": round(min(values), 2),
        "max": round(max(values), 2),
    }


def render_md_report(summary: dict) -> str:
    lines = [
        "# Temperature ablation on task4",
        "",
        f"- Conspect: `{summary['conspect']}`",
        f"- Model: `{summary['model']}`",
        f"- Runs per temperature: **{summary['runs']}**",
        f"- Temperatures: {summary['temperatures']}",
        f"- Generated at: {summary['generated_at']}",
        f"- Total wall time: {summary['elapsed_overall_sec']} s",
        "",
        "## Per-temperature aggregates",
        "",
    ]
    for t, agg in summary["per_temperature"].items():
        lines.append(f"### T = {t}")
        lines.append("")
        lines.append("| Metric | mean | stdev | min | max |")
        lines.append("|---|---:|---:|---:|---:|")
        for m in METRIC_FIELDS:
            a = agg.get(m, {})
            if a.get("n"):
                lines.append(
                    f"| {m} | {a['mean']} | {a['stdev']} | {a['min']} | {a['max']} |"
                )
        lines.append("")

    lines.append("## Distinct outputs per temperature")
    lines.append("")
    lines.append("| T | distinct visuals_planned | values |")
    lines.append("|---|---:|---|")
    for t, ds in summary["distinct_visuals_planned"].items():
        lines.append(f"| {t} | {ds['distinct']} | {', '.join(map(str, ds['values']))} |")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--conspect", type=Path,
                    default=ROOT / "conspects" / "task4.md",
                    help="Path to the conspect markdown file.")
    ap.add_argument(
        "--temperatures", type=float, nargs="+",
        default=[0.0, 0.3, 0.7],
        help="Sampling temperatures to test (default: 0.0 0.3 0.7).",
    )
    ap.add_argument("--runs", type=int, default=3,
                    help="Reruns per temperature (default: 3).")
    ap.add_argument(
        "--model",
        default="Qwen/Qwen2.5-7B-Instruct-Turbo",
        help="LLM model name (Together AI).",
    )
    args = ap.parse_args()

    api_key = os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        print("ERROR: TOGETHER_API_KEY is not set. Export it before running.")
        return 1

    if not args.conspect.exists():
        print(f"ERROR: Conspect not found: {args.conspect}")
        return 2

    base_out = ROOT / "pipeline" / "output_temperature"
    base_out.mkdir(parents=True, exist_ok=True)

    text = args.conspect.read_text(encoding="utf-8")
    planner = VisualPlannerV2(api_key=api_key, model=args.model)

    raw_per_temperature: dict[str, list[dict]] = {
        f"{t}": [] for t in args.temperatures
    }

    overall_t0 = time.time()
    for t in args.temperatures:
        for run_idx in range(1, args.runs + 1):
            print(f"\n[T={t}] run {run_idx}/{args.runs}...")
            t0 = time.time()
            try:
                plan_result = planner.plan_conspect(text, temperature=t)
            except Exception as exc:  # noqa: BLE001
                print(f"  FAILED: {exc}")
                raw_per_temperature[f"{t}"].append(
                    {"error": str(exc), "run": run_idx, "temperature": t}
                )
                continue
            elapsed = round(time.time() - t0, 2)
            run_dir = base_out / f"T{t}" / f"run{run_idx}"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "plan.json").write_text(
                json.dumps(plan_result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            metrics = {m: plan_result.get(m, 0) for m in METRIC_FIELDS}
            metrics["run"] = run_idx
            metrics["temperature"] = t
            metrics["wall_sec"] = elapsed
            raw_per_temperature[f"{t}"].append(metrics)
            print(
                f"  visuals_planned={metrics['visuals_planned']}, "
                f"tokens={metrics['total_tokens_in']}+{metrics['total_tokens_out']}, "
                f"time={elapsed}s"
            )

    overall_elapsed = round(time.time() - overall_t0, 1)

    per_temperature_agg: dict[str, dict] = {}
    distinct_visuals_planned: dict[str, dict] = {}
    for t_str, runs in raw_per_temperature.items():
        clean = [r for r in runs if "error" not in r]
        agg: dict = {}
        for m in METRIC_FIELDS:
            values = [r[m] for r in clean if isinstance(r.get(m), (int, float))]
            agg[m] = aggregate(values)
        per_temperature_agg[t_str] = agg

        vp_values = [r["visuals_planned"] for r in clean]
        distinct_visuals_planned[t_str] = {
            "distinct": len(set(vp_values)),
            "values": vp_values,
        }

    summary = {
        "conspect": str(args.conspect.relative_to(ROOT)),
        "model": args.model,
        "runs": args.runs,
        "temperatures": args.temperatures,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_overall_sec": overall_elapsed,
        "raw_per_temperature": raw_per_temperature,
        "per_temperature": per_temperature_agg,
        "distinct_visuals_planned": distinct_visuals_planned,
    }

    summary_path = base_out / "temperature_ablation_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path = base_out / "temperature_ablation_summary.md"
    md_path.write_text(render_md_report(summary), encoding="utf-8")

    print()
    print("=" * 70)
    print(f"Done. Total wall time: {overall_elapsed} s")
    print(f"Aggregated summary:    {summary_path}")
    print(f"Markdown report:       {md_path}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
