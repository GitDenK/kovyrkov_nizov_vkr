"""Re-aggregate geometry pipeline metrics from existing *_metrics.json sidecars.

Used when individual cells were re-run separately (e.g. a single problem
re-run after a bugfix) and the master summary needs to be regenerated
without firing additional LLM calls.

Usage:
    python3 pipeline/aggregate_geometry_metrics.py \
        --runs-dir pipeline/output_geometry_runs --runs 3
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.geometry_corpus import PROBLEMS, by_slug  # noqa: E402
from pipeline.run_geometry_variance import (  # noqa: E402
    METRIC_FIELDS,
    aggregate,
    compute_answer_vis_rate,
    compute_fix_rate,
    extract_run_metrics,
    render_md_report,
)


def _offline_answer_vis_warnings(plan_path: Path, problem_text: str) -> int | None:
    """Run the answer-visualization post-validator on a saved plan offline.

    Returns the warning count, or None if the plan file is missing/unparseable.
    Imported lazily to keep this module usable without the LLM dependency.
    """
    if not plan_path.exists():
        return None
    try:
        from pipeline.geometry_auto import (  # noqa: WPS433
            _validate_answer_visualization,
            _postprocess_plan,
        )
    except Exception:
        return None
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    try:
        _postprocess_plan(plan)  # mutates in place, returns None
    except Exception:
        pass
    try:
        warnings = _validate_answer_visualization(plan, problem_text)
    except Exception:
        return None
    return len(warnings)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs-dir", type=Path,
                    default=ROOT / "pipeline" / "output_geometry_runs")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument(
        "--model",
        default="meta-llama/Llama-3.3-70B-Instruct-Turbo",
    )
    ap.add_argument(
        "--rerun-answer-vis", action="store_true",
        help="Re-run the answer-visualization post-validator offline on the "
             "saved *_plan.json file for each cell, overriding the value "
             "from *_metrics.json (useful for legacy runs).",
    )
    args = ap.parse_args()

    if not args.runs_dir.exists():
        print(f"ERROR: runs dir not found: {args.runs_dir}")
        return 1

    per_problem_runs: dict[str, list[dict]] = {p.slug: [] for p in PROBLEMS}

    for run_idx in range(1, args.runs + 1):
        run_dir = args.runs_dir / f"run{run_idx}"
        if not run_dir.exists():
            print(f"  skip missing dir: {run_dir}")
            continue
        for slug in per_problem_runs:
            metrics_path = run_dir / f"{slug}_metrics.json"
            if not metrics_path.exists():
                per_problem_runs[slug].append(
                    {"error": "no metrics file", "run": run_idx}
                )
                continue
            metrics_obj = json.loads(metrics_path.read_text(encoding="utf-8"))
            row = extract_run_metrics(metrics_obj)
            row["run"] = run_idx
            row["domain"] = next(
                (p.domain for p in PROBLEMS if p.slug == slug), ""
            )
            if args.rerun_answer_vis or "answer_vis_warnings" not in row:
                plan_path = run_dir / f"{slug}_plan.json"
                try:
                    problem = by_slug(slug)
                    n = _offline_answer_vis_warnings(
                        plan_path, problem.problem_text
                    )
                except Exception:
                    n = None
                if n is not None:
                    row["answer_vis_warnings"] = n
            per_problem_runs[slug].append(row)

    per_problem_agg: dict[str, dict] = {}
    for slug, runs in per_problem_runs.items():
        clean = [r for r in runs if "error" not in r]
        agg: dict = {}
        for m in METRIC_FIELDS:
            vals = [r[m] for r in clean if m in r]
            agg[m] = aggregate(vals)
        per_problem_agg[slug] = agg

    summary = {
        "model": args.model,
        "runs": args.runs,
        "problems": [p.slug for p in PROBLEMS],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_overall_sec": 0.0,
        "raw_per_run": per_problem_runs,
        "per_problem": per_problem_agg,
        "fix_rate": compute_fix_rate(per_problem_runs),
        "answer_vis_rate": compute_answer_vis_rate(per_problem_runs),
        "note": "Re-aggregated from existing metrics files; "
                "elapsed_overall_sec set to 0.",
    }

    summary_path = args.runs_dir / "geometry_variance_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path = args.runs_dir / "geometry_variance_summary.md"
    md_path.write_text(render_md_report(summary), encoding="utf-8")

    print(f"Re-aggregated summary: {summary_path}")
    print(f"Re-aggregated markdown: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
