"""Variance benchmark: run the conspect pipeline N times on the same corpus.

Captures per-run metrics (tokens_in, tokens_out, total_time_sec, visuals_planned)
and aggregates mean/std/min/max across runs for each conspect.

Usage:
    TOGETHER_API_KEY=... python3 pipeline/run_variance.py
    TOGETHER_API_KEY=... python3 pipeline/run_variance.py --runs 5

Outputs:
    pipeline/output_runs/run{i}/{task}/...     # raw artifacts of each run
    pipeline/output_runs/variance_summary.json # aggregated metrics
    pipeline/output_runs/variance_summary.md   # human-readable report
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

from pipeline import run_pipeline as rp


CONSPECTS = [
    ROOT / "conspects" / "task4.md",
    ROOT / "conspects" / "task6.md",
    ROOT / "conspects" / "task8.md",
    ROOT / "conspects" / "task12.md",
]

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
        "# Variance benchmark of the conspect pipeline",
        "",
        f"- Model: `{summary['model']}`",
        f"- Runs per conspect: **{summary['runs']}**",
        f"- Generated at: {summary['generated_at']}",
        "",
        "## Per-conspect aggregates",
        "",
    ]
    for conspect, agg in summary["per_conspect"].items():
        lines.append(f"### {conspect}")
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
    lines.append("## Totals across conspects")
    lines.append("")
    lines.append("| Metric | mean | stdev | min | max |")
    lines.append("|---|---:|---:|---:|---:|")
    for m in METRIC_FIELDS:
        a = summary["totals_per_run"].get(m, {})
        if a.get("n"):
            lines.append(
                f"| {m} | {a['mean']} | {a['stdev']} | {a['min']} | {a['max']} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3, help="Reruns per conspect")
    parser.add_argument(
        "--model",
        default="Qwen/Qwen2.5-7B-Instruct-Turbo",
        help="LLM model name (Together AI)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        print("ERROR: TOGETHER_API_KEY is not set. Export it before running.")
        return 1

    base_out = ROOT / "pipeline" / "output_runs"
    base_out.mkdir(parents=True, exist_ok=True)

    raw: dict[str, list[dict]] = {c.stem: [] for c in CONSPECTS}

    overall_t0 = time.time()
    for run_idx in range(1, args.runs + 1):
        print(f"\n{'#' * 70}")
        print(f"# RUN {run_idx} / {args.runs}")
        print(f"{'#' * 70}")
        run_dir = base_out / f"run{run_idx}"
        run_dir.mkdir(parents=True, exist_ok=True)
        rp.OUTPUT_DIR = run_dir

        for conspect in CONSPECTS:
            try:
                result = rp.run_pipeline(conspect, api_key, args.model)
            except Exception as exc:
                print(f"  [run{run_idx}/{conspect.stem}] FAILED: {exc}")
                raw[conspect.stem].append({"error": str(exc), "run": run_idx})
                continue
            pr = result.get("plan_result", {})
            metrics = {m: pr.get(m, 0) for m in METRIC_FIELDS}
            metrics["run"] = run_idx
            metrics["rendered_ok"] = result["stats"]["rendered_ok"]
            metrics["total_visuals"] = result["stats"]["total_visuals"]
            raw[conspect.stem].append(metrics)

    overall_elapsed = round(time.time() - overall_t0, 1)

    per_conspect: dict[str, dict] = {}
    for name, runs in raw.items():
        agg: dict = {}
        for m in METRIC_FIELDS:
            values = [r.get(m) for r in runs if isinstance(r.get(m), (int, float))]
            agg[m] = aggregate(values)
        per_conspect[name] = agg

    totals_per_run: dict[str, dict] = {}
    for m in METRIC_FIELDS:
        run_totals = []
        for run_idx in range(1, args.runs + 1):
            s = 0.0
            ok = True
            for runs in raw.values():
                match = [r for r in runs if r.get("run") == run_idx]
                if not match or not isinstance(match[0].get(m), (int, float)):
                    ok = False
                    break
                s += match[0][m]
            if ok:
                run_totals.append(s)
        totals_per_run[m] = aggregate(run_totals)

    summary = {
        "model": args.model,
        "runs": args.runs,
        "conspects": [c.stem for c in CONSPECTS],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_overall_sec": overall_elapsed,
        "raw_per_run": raw,
        "per_conspect": per_conspect,
        "totals_per_run": totals_per_run,
    }

    summary_path = base_out / "variance_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path = base_out / "variance_summary.md"
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
