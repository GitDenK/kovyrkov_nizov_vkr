"""Smoke tests for the answer-visualization post-condition validator.

Runs offline; no API key needed. Exercises:

- _detect_answer_types on a small set of EGE-style prompts;
- _validate_answer_visualization on synthetic plans that either visualize
  the answer correctly or only place it as a caption;
- _validate_answer_visualization on real saved plans from the variance
  benchmark, to make sure the heuristic is calibrated reasonably (no
  false alarms on plans we already accept).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.geometry_auto import (  # noqa: E402
    _detect_answer_types,
    _extract_answer_value_from_plan,
    _validate_answer_visualization,
)


def _segment(seg_id: str, a: str, b: str, length_label: str = "") -> dict:
    return {"type": "segment", "id": seg_id,
            "from_point": a, "to_point": b,
            "length_label": length_label}


def _point(pid: str) -> dict:
    return {"type": "point", "id": pid}


# ----------------------------------------------------------------------
# 1. Pattern detection
# ----------------------------------------------------------------------


def test_detect_height():
    types = _detect_answer_types(
        "В трапеции ABCD основания BC = 4 и AD = 9. Найдите высоту трапеции."
    )
    assert "height" in types, types
    print("    OK detect height ->", types)


def test_detect_distance():
    types = _detect_answer_types(
        "Найдите расстояние от вершины A до плоскости SBC."
    )
    assert "distance" in types, types
    print("    OK detect distance ->", types)


def test_detect_angle():
    types = _detect_answer_types("Найдите двугранный угол при ребре AB.")
    assert "angle" in types, types
    print("    OK detect angle ->", types)


def test_detect_area():
    types = _detect_answer_types(
        "Найдите площадь сечения призмы плоскостью."
    )
    assert "area" in types, types
    print("    OK detect area ->", types)


def test_detect_proof_only():
    types = _detect_answer_types("Докажите, что диагонали перпендикулярны.")
    assert "proof" in types, types
    print("    OK detect proof ->", types)


def test_detect_combined():
    types = _detect_answer_types(
        "а) Докажите, что диагонали перпендикулярны. "
        "б) Найдите высоту трапеции."
    )
    assert "proof" in types and "height" in types, types
    print("    OK detect combined ->", types)


# ----------------------------------------------------------------------
# 2. Synthetic plans
# ----------------------------------------------------------------------

# Plan with no answer object: only a caption mentioning h = 2.5.
PLAN_HEIGHT_ONLY_CAPTION = {
    "title": "Трапеция",
    "points": {p: {"x": 0, "y": 0} for p in ("A", "B", "C", "D", "E", "F")},
    "steps": [
        {
            "caption": "Трапеция ABCD",
            "objects": [
                _point("A"), _point("B"), _point("C"), _point("D"),
                _segment("s_AB", "A", "B"),
                _segment("s_BC", "B", "C", "4"),
                _segment("s_CD", "C", "D"),
                _segment("s_AD", "A", "D", "9"),
            ],
            "constraints": [],
            "annotations": [],
        },
        {
            "caption": "Ответ: h = 2.5",
            "objects": [_segment("s_EF", "E", "F")],
            "constraints": [],
            "annotations": [],
        },
    ],
}

# Plan that explicitly visualizes the answer as a perpendicular labeled
# segment (the "good" case).
PLAN_HEIGHT_VISUALIZED = {
    "title": "Трапеция",
    "points": {p: {"x": 0, "y": 0} for p in ("A", "B", "C", "D", "H")},
    "steps": [
        {
            "caption": "Трапеция ABCD",
            "objects": [
                _segment("s_BC", "B", "C", "4"),
                _segment("s_AD", "A", "D", "9"),
            ],
            "constraints": [],
            "annotations": [],
        },
        {
            "caption": "Высота BH",
            "objects": [_segment("s_BH", "B", "H", "2.5")],
            "constraints": [{"type": "perpendicular", "id": "p_BH",
                              "line1": "BH", "line2": "AD"}],
            "annotations": [],
        },
    ],
}


def test_validate_caption_only_emits_warnings():
    problem = ("В трапеции ABCD основания BC = 4 и AD = 9. "
               "Найдите высоту трапеции.")
    warnings = _validate_answer_visualization(
        PLAN_HEIGHT_ONLY_CAPTION, problem)
    # Expected warnings: at least one of {missing perpendicular,
    # missing length label naming the answer}
    assert any("perpendicular" in w or "right_angle" in w for w in warnings), \
        warnings
    assert any("2.5" in w for w in warnings), warnings
    print("    OK caption-only -> warnings:")
    for w in warnings:
        print("       ·", w)


def test_validate_visualized_passes():
    problem = ("В трапеции ABCD основания BC = 4 и AD = 9. "
               "Найдите высоту трапеции.")
    warnings = _validate_answer_visualization(
        PLAN_HEIGHT_VISUALIZED, problem)
    assert warnings == [], warnings
    print("    OK visualized -> no warnings")


def test_extract_answer_value():
    pair = _extract_answer_value_from_plan(PLAN_HEIGHT_ONLY_CAPTION)
    assert pair == ("h", "2.5"), pair
    print("    OK extracted answer ->", pair)


def test_extract_skips_given_quantities():
    """If '4' appears in step 1 (BC = 4), we must not return it as the answer."""
    plan = {
        "steps": [
            {"caption": "Дано BC = 4", "objects": [], "annotations": [],
             "constraints": []},
            {"caption": "Ответ: AC = 8", "objects": [], "annotations": [],
             "constraints": []},
        ],
    }
    pair = _extract_answer_value_from_plan(plan)
    assert pair == ("AC", "8"), pair
    print("    OK skipped given ->", pair)


def test_proof_only_no_warnings():
    plan = {"steps": [{"caption": "Доказано", "objects": [], "annotations": [],
                       "constraints": []}]}
    problem = "Докажите, что диагонали перпендикулярны."
    warnings = _validate_answer_visualization(plan, problem)
    assert warnings == [], warnings
    print("    OK proof-only -> no warnings")


# ----------------------------------------------------------------------
# 3. Calibration on real saved plans
# ----------------------------------------------------------------------


def calibration_real_plans():
    """Run the validator on every saved plan from the recent geometry
    variance run. This is a calibration check: we report counts but do
    not assert anything specific (real LLM plans are messy)."""
    runs_dir = ROOT / "pipeline" / "output_geometry_runs"
    if not runs_dir.exists():
        print("    SKIP: no runs dir")
        return

    from pipeline.geometry_corpus import PROBLEMS  # noqa: WPS433
    problem_by_slug = {p.slug: p for p in PROBLEMS}

    total = 0
    flagged = 0
    by_slug: dict[str, int] = {}
    for run_idx in (1, 2, 3):
        run_dir = runs_dir / f"run{run_idx}"
        if not run_dir.exists():
            continue
        for slug, problem in problem_by_slug.items():
            plan_path = run_dir / f"{slug}_plan.json"
            if not plan_path.exists():
                continue
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            warnings = _validate_answer_visualization(
                plan, problem.problem_text)
            total += 1
            if warnings:
                flagged += 1
                by_slug[slug] = by_slug.get(slug, 0) + 1

    print(f"    calibration: {flagged}/{total} plans triggered "
          f"answer-vis warnings")
    if by_slug:
        for slug, count in sorted(by_slug.items()):
            print(f"      · {slug}: {count}")


def main() -> int:
    print("[1] Pattern detection")
    test_detect_height()
    test_detect_distance()
    test_detect_angle()
    test_detect_area()
    test_detect_proof_only()
    test_detect_combined()

    print("\n[2] Synthetic plans")
    test_validate_caption_only_emits_warnings()
    test_validate_visualized_passes()
    test_extract_answer_value()
    test_extract_skips_given_quantities()
    test_proof_only_no_warnings()

    print("\n[3] Calibration on saved plans")
    calibration_real_plans()

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
