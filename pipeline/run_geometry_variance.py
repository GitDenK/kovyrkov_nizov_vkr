"""Variance benchmark for the geometry pipeline.

For each problem in `geometry_corpus.PROBLEMS` runs the full LLM-driven
geometry pipeline N times (default N=3) and aggregates metrics:

- total wall time per run;
- number of LLM calls per run, split by role (`plan` vs `fix`);
- total prompt and completion tokens per run;
- number of executed steps and total points/objects/annotations;
- "fix rate" --- fraction of (problem x run) cells where at least one
  retry-on-validation-error call (`role == "fix"`) was issued.

Per-run outputs land in `pipeline/output_geometry_runs/run{i}/` and the
aggregated report is written to
`pipeline/output_geometry_runs/geometry_variance_summary.{json,md}`.

Usage:
    TOGETHER_API_KEY=... python3 pipeline/run_geometry_variance.py
    TOGETHER_API_KEY=... python3 pipeline/run_geometry_variance.py --runs 5
    TOGETHER_API_KEY=... python3 pipeline/run_geometry_variance.py \
        --slugs task16_trapezoid task14_pyramid_apex_to_face

The script intentionally does NOT import the LLM-calling code at module top
level so that aggregation utilities can be exercised in unit-style smoke
tests without an API key.
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

from pipeline.geometry_corpus import PROBLEMS, by_slug  # noqa: E402


# Numeric metric fields extracted from each per-run *_metrics.json.
METRIC_FIELDS = (
    "wall_sec",
    "llm_sec",
    "llm_calls_total",
    "llm_calls_plan",
    "llm_calls_fix",
    "tokens_in",
    "tokens_out",
    "steps_total",
    "objects_total",
    "annotations_total",
)


# ---------------------------------------------------------------------------
# Aggregation helpers (no API dependency, unit-testable)
# ---------------------------------------------------------------------------


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


def extract_answer_vis_warnings(metrics_obj: dict) -> int | None:
    """Read the number of answer-visualization advisory warnings from the
    `answer_vis_check` phase entry, or return None if the phase is absent
    (legacy metrics file that pre-dates the post-validator)."""
    phases = metrics_obj.get("phases") or {}
    bucket = phases.get("answer_vis_check")
    if not bucket:
        return None
    extras = bucket.get("extra") or []
    if not extras:
        return None
    last = extras[-1] or {}
    n = last.get("warnings")
    return int(n) if n is not None else None


def extract_run_metrics(metrics_obj: dict) -> dict:
    """Project a `_metrics.json` sidecar onto a flat dict of scalar metrics."""
    totals = metrics_obj.get("totals", {}) or {}
    llm_calls = metrics_obj.get("llm_calls", []) or []
    steps = metrics_obj.get("steps", []) or []

    plan_calls = [c for c in llm_calls if c.get("role") == "plan"]
    fix_calls = [c for c in llm_calls if c.get("role") == "fix"]

    row = {
        "wall_sec": float(totals.get("wall_sec", 0.0)),
        "llm_sec": float(totals.get("llm_sec", 0.0)),
        "llm_calls_total": int(totals.get("llm_calls", len(llm_calls))),
        "llm_calls_plan": len(plan_calls),
        "llm_calls_fix": len(fix_calls),
        "tokens_in": int(totals.get(
            "llm_tokens_in",
            sum(c.get("tokens_in", 0) or 0 for c in llm_calls),
        )),
        "tokens_out": int(totals.get(
            "llm_tokens_out",
            sum(c.get("tokens_out", 0) or 0 for c in llm_calls),
        )),
        "steps_total": int(totals.get("steps_count", len(steps))),
        "objects_total": int(
            sum((s.get("n_objects", 0) or 0) for s in steps)
        ),
        "annotations_total": int(
            sum((s.get("n_annotations", 0) or 0) for s in steps)
        ),
    }
    av = extract_answer_vis_warnings(metrics_obj)
    if av is not None:
        row["answer_vis_warnings"] = av
    return row


def compute_fix_rate(per_problem_runs: dict[str, list[dict]]) -> dict:
    """Fix-rate over all (problem, run) cells; >0 fix calls counts as a hit."""
    total_cells = 0
    fix_cells = 0
    per_problem: dict[str, dict] = {}
    for slug, runs in per_problem_runs.items():
        cells = 0
        hits = 0
        for r in runs:
            if "error" in r:
                continue
            cells += 1
            if (r.get("llm_calls_fix") or 0) > 0:
                hits += 1
        per_problem[slug] = {
            "cells": cells,
            "fix_cells": hits,
            "rate": round(hits / cells, 3) if cells else None,
        }
        total_cells += cells
        fix_cells += hits
    overall = {
        "cells": total_cells,
        "fix_cells": fix_cells,
        "rate": round(fix_cells / total_cells, 3) if total_cells else None,
    }
    return {"per_problem": per_problem, "overall": overall}


def compute_answer_vis_rate(per_problem_runs: dict[str, list[dict]]) -> dict:
    """Share of (problem, run) cells where the answer-visualization
    post-condition validator emitted at least one advisory warning.
    Cells that errored out before validation are excluded; cells that ran
    without the validator (legacy metrics files) are reported as `None`."""
    total_cells = 0
    flagged = 0
    per_problem: dict[str, dict] = {}
    for slug, runs in per_problem_runs.items():
        cells = 0
        hits = 0
        for r in runs:
            if "error" in r:
                continue
            n = r.get("answer_vis_warnings")
            if n is None:
                continue
            cells += 1
            if n > 0:
                hits += 1
        per_problem[slug] = {
            "cells": cells,
            "flagged_cells": hits,
            "rate": round(hits / cells, 3) if cells else None,
        }
        total_cells += cells
        flagged += hits
    overall = {
        "cells": total_cells,
        "flagged_cells": flagged,
        "rate": round(flagged / total_cells, 3) if total_cells else None,
    }
    return {"per_problem": per_problem, "overall": overall}


def render_md_report(summary: dict) -> str:
    lines = [
        "# Variance benchmark of the geometry pipeline",
        "",
        f"- Model: `{summary['model']}`",
        f"- Runs per problem: **{summary['runs']}**",
        f"- Generated at: {summary['generated_at']}",
        f"- Total wall time: {summary['elapsed_overall_sec']} s",
        "",
        "## Per-problem aggregates",
        "",
    ]
    for slug, agg in summary["per_problem"].items():
        lines.append(f"### {slug}")
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
    lines.append("## Fix-rate (validation triggered LLM retry)")
    lines.append("")
    fr = summary["fix_rate"]
    lines.append(
        f"Overall: **{fr['overall']['rate']}** "
        f"({fr['overall']['fix_cells']}/{fr['overall']['cells']} cells)."
    )
    lines.append("")
    lines.append("| Problem | cells | fix cells | rate |")
    lines.append("|---|---:|---:|---:|")
    for slug, pp in fr["per_problem"].items():
        lines.append(
            f"| {slug} | {pp['cells']} | {pp['fix_cells']} | {pp['rate']} |"
        )
    lines.append("")

    avr = summary.get("answer_vis_rate")
    if avr and avr["overall"]["cells"]:
        lines.append("## Answer-vis warning rate (post-condition validator)")
        lines.append("")
        lines.append(
            f"Overall: **{avr['overall']['rate']}** "
            f"({avr['overall']['flagged_cells']}/"
            f"{avr['overall']['cells']} cells flagged)."
        )
        lines.append("")
        lines.append("| Problem | cells | flagged | rate |")
        lines.append("|---|---:|---:|---:|")
        for slug, pp in avr["per_problem"].items():
            if not pp["cells"]:
                continue
            lines.append(
                f"| {slug} | {pp['cells']} | "
                f"{pp['flagged_cells']} | {pp['rate']} |"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main runner (calls LLM via geometry_auto.run)
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3,
                        help="Reruns per problem (default: 3)")
    parser.add_argument(
        "--model",
        default="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        help="LLM model name (Together AI). Defaults to the 70B model "
             "used in the geometry branch.",
    )
    parser.add_argument(
        "--slugs", nargs="+", default=None,
        help="Optional subset of problem slugs to run. Defaults to all.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Override output directory "
             "(default: pipeline/output_geometry_runs).",
    )
    parser.add_argument(
        "--enforce-answer-vis", action="store_true",
        help="Run the planner with the hard answer-visualization "
             "post-validator (default: soft / advisory only).",
    )
    parser.add_argument(
        "--max-answer-vis-retries", type=int, default=1,
        help="Max LLM fix-requests issued by the answer-vis post-validator "
             "when --enforce-answer-vis is set (default: 1).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        print("ERROR: TOGETHER_API_KEY is not set. Export it before running.")
        return 1

    if args.slugs:
        problems = [by_slug(s) for s in args.slugs]
    else:
        problems = list(PROBLEMS)

    base_out = args.output_dir or (ROOT / "pipeline" / "output_geometry_runs")
    base_out.mkdir(parents=True, exist_ok=True)

    # Late import so unit-style smoke tests of aggregators don't pull in the
    # network-bound modules.
    from pipeline import geometry_auto as ga  # noqa: WPS433

    per_problem_runs: dict[str, list[dict]] = {p.slug: [] for p in problems}

    overall_t0 = time.time()
    for run_idx in range(1, args.runs + 1):
        print(f"\n{'#' * 70}")
        print(f"# RUN {run_idx} / {args.runs}")
        print(f"{'#' * 70}")
        run_dir = base_out / f"run{run_idx}"
        run_dir.mkdir(parents=True, exist_ok=True)
        ga.OUTPUT_DIR = run_dir

        for problem in problems:
            output_name = problem.slug
            try:
                ga.run(
                    problem_text=problem.problem_text,
                    output_name=output_name,
                    title=problem.title,
                    api_key=api_key,
                    model=args.model,
                    save_plan=True,
                    save_metrics=True,
                    enforce_answer_vis=args.enforce_answer_vis,
                    max_answer_vis_retries=args.max_answer_vis_retries,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [run{run_idx}/{problem.slug}] FAILED: {exc}")
                per_problem_runs[problem.slug].append(
                    {"error": str(exc), "run": run_idx}
                )
                continue

            metrics_path = run_dir / f"{output_name}_metrics.json"
            if not metrics_path.exists():
                print(f"  [run{run_idx}/{problem.slug}] WARN: no metrics file")
                per_problem_runs[problem.slug].append(
                    {"error": "no metrics file", "run": run_idx}
                )
                continue
            metrics_obj = json.loads(metrics_path.read_text(encoding="utf-8"))
            row = extract_run_metrics(metrics_obj)
            row["run"] = run_idx
            row["domain"] = problem.domain
            per_problem_runs[problem.slug].append(row)

    overall_elapsed = round(time.time() - overall_t0, 1)

    per_problem_agg: dict[str, dict] = {}
    for slug, runs in per_problem_runs.items():
        agg: dict = {}
        clean = [r for r in runs if "error" not in r]
        for m in METRIC_FIELDS:
            vals = [r[m] for r in clean if m in r]
            agg[m] = aggregate(vals)
        per_problem_agg[slug] = agg

    summary = {
        "model": args.model,
        "runs": args.runs,
        "problems": [p.slug for p in problems],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_overall_sec": overall_elapsed,
        "enforce_answer_vis": bool(args.enforce_answer_vis),
        "max_answer_vis_retries": int(args.max_answer_vis_retries),
        "raw_per_run": per_problem_runs,
        "per_problem": per_problem_agg,
        "fix_rate": compute_fix_rate(per_problem_runs),
        "answer_vis_rate": compute_answer_vis_rate(per_problem_runs),
    }

    summary_path = base_out / "geometry_variance_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path = base_out / "geometry_variance_summary.md"
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
