"""Dump individual SVG snapshots from a saved geometry plan.

Reads a plan JSON, executes it (without LLM call), and writes each step's
rendered SVG to a separate file. Useful for embedding individual steps as
figures in academic writeups (e.g. PDF inclusion in a thesis).

Usage:
    python3 pipeline/dump_step_svgs.py PLAN_JSON [--output-prefix NAME] \
        [--output-dir DIR]

Default output_dir is the same directory as PLAN_JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.geometry_auto import (  # noqa: E402
    _extract_json,
    _postprocess_plan,
    _validate_plan,
    execute_plan,
)


def dump_plan(plan_path: Path, output_prefix: str | None,
              output_dir: Path | None) -> list[Path]:
    raw = plan_path.read_text(encoding="utf-8")
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        plan = _extract_json(raw)
        if not plan:
            raise SystemExit(f"Could not parse plan from {plan_path}")
    _postprocess_plan(plan)
    _validate_plan(plan)

    blocks = execute_plan(plan)
    visuals = [b for b in blocks if b["type"] == "visual"]

    if output_prefix is None:
        output_prefix = plan_path.stem
        if output_prefix.endswith("_plan"):
            output_prefix = output_prefix[: -len("_plan")]

    if output_dir is None:
        output_dir = plan_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for idx, vis in enumerate(visuals, start=1):
        out_path = output_dir / f"{output_prefix}_step{idx}.svg"
        out_path.write_text(vis["svg"], encoding="utf-8")
        written.append(out_path)
        print(f"  step {idx}: {out_path}")
    print(f"[dump_step_svgs] {len(written)} SVG(s) written to {output_dir}")
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan", type=Path, help="Path to *_plan.json")
    ap.add_argument("--output-prefix", type=str, default=None,
                    help="File-name prefix for emitted SVGs "
                         "(default: stem of plan file with '_plan' stripped)")
    ap.add_argument("--output-dir", type=Path, default=None,
                    help="Directory for emitted SVGs (default: plan's dir)")
    args = ap.parse_args()
    dump_plan(args.plan, args.output_prefix, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
