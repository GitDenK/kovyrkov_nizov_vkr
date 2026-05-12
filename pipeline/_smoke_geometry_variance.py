"""Smoke test for run_geometry_variance.py aggregators (no API needed).

Runs in <1 s and fails loudly on schema or arithmetic mistakes.
Intended to be deleted once the real benchmark is wired up; kept tiny
on purpose.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.run_geometry_variance import (  # noqa: E402
    METRIC_FIELDS,
    aggregate,
    compute_answer_vis_rate,
    compute_fix_rate,
    extract_answer_vis_warnings,
    extract_run_metrics,
    render_md_report,
)


def _fake_metrics(*, plan_calls: int, fix_calls: int,
                  tokens_in: int, tokens_out: int,
                  wall_sec: float, llm_sec: float,
                  steps: int, n_objects_per_step: int,
                  n_annotations_per_step: int,
                  answer_vis_warnings: int | None = None) -> dict:
    llm_calls = []
    for _ in range(plan_calls):
        llm_calls.append({
            "model": "Llama-3.3-70B",
            "role": "plan",
            "tokens_in": tokens_in // max(plan_calls + fix_calls, 1),
            "tokens_out": tokens_out // max(plan_calls + fix_calls, 1),
            "duration_sec": llm_sec / max(plan_calls + fix_calls, 1),
            "success": True,
        })
    for _ in range(fix_calls):
        llm_calls.append({
            "model": "Llama-3.3-70B",
            "role": "fix",
            "tokens_in": tokens_in // max(plan_calls + fix_calls, 1),
            "tokens_out": tokens_out // max(plan_calls + fix_calls, 1),
            "duration_sec": llm_sec / max(plan_calls + fix_calls, 1),
            "success": True,
        })
    phases: dict = {}
    if answer_vis_warnings is not None:
        phases["answer_vis_check"] = {
            "n": 1,
            "total_sec": 0.0,
            "extra": [{
                "warnings": int(answer_vis_warnings),
                "expected_types": ["height"],
            }],
        }
    return {
        "started_at": "2026-05-08 20:00:00",
        "model": "Llama-3.3-70B",
        "mode": "run",
        "llm_calls": llm_calls,
        "phases": phases,
        "steps": [
            {
                "step_idx": i,
                "duration_sec": 0.05,
                "n_objects": n_objects_per_step,
                "n_annotations": n_annotations_per_step,
                "n_constraints": 1,
                "has_text": True,
            }
            for i in range(steps)
        ],
        "totals": {
            "wall_sec": wall_sec,
            "llm_calls": plan_calls + fix_calls,
            "llm_calls_successful": plan_calls + fix_calls,
            "llm_tokens_in": tokens_in,
            "llm_tokens_out": tokens_out,
            "llm_sec": llm_sec,
            "phases_sec": 0.0,
            "steps_count": steps,
            "steps_sec": 0.05 * steps,
        },
    }


def main() -> int:
    print("[1] extract_run_metrics on a clean plan-only run")
    a = _fake_metrics(plan_calls=1, fix_calls=0,
                      tokens_in=4000, tokens_out=1500,
                      wall_sec=8.4, llm_sec=7.9,
                      steps=4, n_objects_per_step=3,
                      n_annotations_per_step=2)
    a_proj = extract_run_metrics(a)
    expect = {
        "wall_sec": 8.4, "llm_sec": 7.9, "llm_calls_total": 1,
        "llm_calls_plan": 1, "llm_calls_fix": 0,
        "tokens_in": 4000, "tokens_out": 1500,
        "steps_total": 4, "objects_total": 12, "annotations_total": 8,
    }
    for k, v in expect.items():
        assert a_proj[k] == v, f"  FAIL: {k}={a_proj[k]} expected {v}"
    print("    OK")

    print("[2] extract_run_metrics on a plan+fix run")
    b = _fake_metrics(plan_calls=1, fix_calls=1,
                      tokens_in=8000, tokens_out=3000,
                      wall_sec=14.5, llm_sec=13.7,
                      steps=5, n_objects_per_step=2,
                      n_annotations_per_step=1)
    b_proj = extract_run_metrics(b)
    assert b_proj["llm_calls_plan"] == 1, b_proj
    assert b_proj["llm_calls_fix"] == 1, b_proj
    assert b_proj["llm_calls_total"] == 2, b_proj
    print("    OK")

    print("[3] aggregate over multiple runs")
    runs = []
    for proj, run in [(a_proj, 1), (b_proj, 2)]:
        proj = dict(proj)
        proj["run"] = run
        runs.append(proj)
    agg = {}
    for m in METRIC_FIELDS:
        vals = [r[m] for r in runs]
        agg[m] = aggregate(vals)
    assert agg["wall_sec"]["min"] == 8.4
    assert agg["wall_sec"]["max"] == 14.5
    assert agg["llm_calls_fix"]["max"] == 1
    print("    OK,",
          f"wall_sec mean={agg['wall_sec']['mean']}",
          f"llm_calls_fix max={agg['llm_calls_fix']['max']}")

    print("[4] compute_fix_rate")
    per_problem_runs = {
        "p_clean": [a_proj, dict(a_proj, run=2), {"error": "boom", "run": 3}],
        "p_with_fix": [b_proj, dict(a_proj, run=2)],
    }
    fr = compute_fix_rate(per_problem_runs)
    assert fr["per_problem"]["p_clean"] == {"cells": 2, "fix_cells": 0, "rate": 0.0}, fr
    assert fr["per_problem"]["p_with_fix"] == {"cells": 2, "fix_cells": 1, "rate": 0.5}, fr
    assert fr["overall"] == {"cells": 4, "fix_cells": 1, "rate": 0.25}, fr
    print(f"    OK, overall fix-rate {fr['overall']['rate']}")

    print("[5] extract_answer_vis_warnings + compute_answer_vis_rate")
    a_av = _fake_metrics(plan_calls=1, fix_calls=0,
                         tokens_in=4000, tokens_out=1500,
                         wall_sec=8.4, llm_sec=7.9,
                         steps=4, n_objects_per_step=3,
                         n_annotations_per_step=2,
                         answer_vis_warnings=0)
    b_av = _fake_metrics(plan_calls=1, fix_calls=1,
                         tokens_in=8000, tokens_out=3000,
                         wall_sec=14.5, llm_sec=13.7,
                         steps=5, n_objects_per_step=2,
                         n_annotations_per_step=1,
                         answer_vis_warnings=2)
    assert extract_answer_vis_warnings(a_av) == 0
    assert extract_answer_vis_warnings(b_av) == 2
    assert extract_answer_vis_warnings(a) is None  # legacy: no phase entry
    a_av_proj = extract_run_metrics(a_av)
    b_av_proj = extract_run_metrics(b_av)
    assert a_av_proj["answer_vis_warnings"] == 0
    assert b_av_proj["answer_vis_warnings"] == 2
    av_runs = {
        "p_ok": [a_av_proj, dict(a_av_proj, run=2)],
        "p_flagged": [b_av_proj, dict(a_av_proj, run=2)],
        "p_legacy": [a_proj],  # no answer_vis_warnings key -> excluded
    }
    avr = compute_answer_vis_rate(av_runs)
    assert avr["per_problem"]["p_ok"]["rate"] == 0.0, avr
    assert avr["per_problem"]["p_flagged"]["rate"] == 0.5, avr
    assert avr["per_problem"]["p_legacy"]["cells"] == 0, avr
    assert avr["overall"] == {"cells": 4, "flagged_cells": 1, "rate": 0.25}, avr
    print(f"    OK, overall answer-vis rate {avr['overall']['rate']}")

    print("[6] render_md_report renders without error")
    summary = {
        "model": "Llama-3.3-70B",
        "runs": 2,
        "problems": ["p_clean", "p_with_fix"],
        "generated_at": "2026-05-08 20:00:00",
        "elapsed_overall_sec": 25.7,
        "raw_per_run": per_problem_runs,
        "per_problem": {
            "p_clean": {m: aggregate([a_proj[m], a_proj[m]]) for m in METRIC_FIELDS},
            "p_with_fix": {m: aggregate([b_proj[m], a_proj[m]]) for m in METRIC_FIELDS},
        },
        "fix_rate": fr,
        "answer_vis_rate": avr,
    }
    md = render_md_report(summary)
    assert "Variance benchmark" in md, md[:200]
    assert "fix-rate" in md.lower(), md[:300]
    assert "answer-vis" in md.lower(), md[:400]
    print("    OK,", len(md), "chars md output")

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
