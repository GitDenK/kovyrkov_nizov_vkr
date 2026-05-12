"""Unified entry point for the conspect and geometry visualization pipelines.

The pipeline has historically been driven by two top-level scripts:

* `pipeline/run_pipeline.py`     -- conspect -> visual planner -> SVG renderer
* `pipeline/geometry_auto.py`    -- geometry problem -> step-by-step LLM plan
                                    -> animated HTML

This module exposes a single CLI that dispatches to the appropriate branch and
shares argument names across both. It is a thin wrapper: it does not duplicate
any rendering logic, and it does not change the behaviour of the underlying
modules. Calling the legacy entry points still works.

Subcommands
-----------
conspect          Generate visuals for one or more conspect Markdown files.
geometry          Generate a step-by-step geometry visualization from a problem.
geometry-replay   Re-render a previously saved geometry plan (no LLM call).
auto              Detect input type by file extension and dispatch.

Usage examples
--------------
TOGETHER_API_KEY=... python3 pipeline/run_unified.py conspect --all
TOGETHER_API_KEY=... python3 pipeline/run_unified.py conspect conspects/task4.md
TOGETHER_API_KEY=... python3 pipeline/run_unified.py geometry \
    --slug task14_pyramid_apex_to_face --animated
TOGETHER_API_KEY=... python3 pipeline/run_unified.py geometry \
    --file problem.txt --output-name my_problem
python3 pipeline/run_unified.py geometry-replay \
    --plan pipeline/output_geometry_runs/run1/task16_trapezoid_plan.json
python3 pipeline/run_unified.py auto conspects/task4.md problem.txt

The `auto` subcommand requires a TOGETHER_API_KEY when the detected input type
needs LLM access (conspect or fresh geometry text); plan replays do not.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Input detection (pure, unit-testable)
# ---------------------------------------------------------------------------


def detect_input_kind(path: Path) -> str:
    """Classify a filesystem path as one of `conspect`, `geometry-text`,
    `geometry-plan`, or `unknown`.

    Detection rules:
      * `*.md`              -> conspect
      * `*.txt`             -> geometry-text
      * `*.json` containing keys {"points", "steps"} -> geometry-plan
      * `*.json` otherwise  -> unknown
      * any other extension -> unknown
    """
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "conspect"
    if suffix == ".txt":
        return "geometry-text"
    if suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return "unknown"
        if isinstance(data, dict) and {"points", "steps"} <= set(data.keys()):
            return "geometry-plan"
        return "unknown"
    return "unknown"


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_conspect(args: argparse.Namespace) -> int:
    from pipeline import run_pipeline as rp

    api_key = args.api_key or os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        print("ERROR: TOGETHER_API_KEY is not set "
              "(use --api-key or export the env var).")
        return 1

    if args.all and not args.paths:
        paths = [p for p in rp.CONSPECTS if p.exists()]
    elif args.paths:
        paths = [Path(p) for p in args.paths]
    else:
        print("ERROR: provide one or more conspect paths "
              "or pass --all to run on the default corpus.")
        return 1

    if args.output_dir is not None:
        rp.OUTPUT_DIR = Path(args.output_dir)
    rp.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model = args.model or rp.MODEL
    all_results: list[dict] = []
    for path in paths:
        if not path.exists():
            print(f"  skip {path}: not found")
            continue
        result = rp.run_pipeline(path, api_key, model)
        all_results.append(result)

    if not all_results:
        print("  no conspects processed.")
        return 1

    (rp.OUTPUT_DIR / "results.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    rp.generate_html_preview(all_results)

    total_v = sum(r["stats"]["total_visuals"] for r in all_results)
    total_ok = sum(r["stats"]["rendered_ok"] for r in all_results)
    print()
    print("=" * 60)
    print("ИТОГО (conspect):")
    print(f"  Визуалов: {total_v}, SVG отрендерено: {total_ok}/{total_v}")
    print(f"  Результаты: {rp.OUTPUT_DIR}")
    print("=" * 60)
    return 0


def cmd_geometry(args: argparse.Namespace) -> int:
    from pipeline import geometry_auto as ga
    from pipeline.geometry_corpus import by_slug

    api_key = args.api_key or os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        print("ERROR: TOGETHER_API_KEY is not set "
              "(use --api-key or export the env var).")
        return 1

    if args.slug:
        problem = by_slug(args.slug)
        problem_text = problem.problem_text
        title = args.title or problem.title
        output_name = args.output_name or args.slug
    elif args.file:
        problem_text = Path(args.file).read_text(encoding="utf-8").strip()
        title = args.title or "Геометрическая задача"
        output_name = args.output_name or Path(args.file).stem
    elif args.text:
        problem_text = args.text
        title = args.title or "Геометрическая задача"
        output_name = args.output_name or "auto_geometry"
    else:
        print("ERROR: provide one of --slug, --file, --text.")
        return 1

    if args.output_dir is not None:
        ga.OUTPUT_DIR = Path(args.output_dir)

    ga.run(
        problem_text=problem_text,
        output_name=output_name,
        title=title,
        api_key=api_key,
        model=args.model or ga.DEFAULT_MODEL,
        save_plan=not args.no_save_plan,
        save_metrics=not args.no_save_metrics,
        animated=args.animated,
        enforce_answer_vis=not args.no_enforce_answer_vis,
        max_answer_vis_retries=args.max_answer_vis_retries,
    )
    return 0


def cmd_geometry_replay(args: argparse.Namespace) -> int:
    from pipeline import geometry_auto as ga

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"ERROR: plan file not found: {plan_path}")
        return 1

    if args.output_dir is not None:
        ga.OUTPUT_DIR = Path(args.output_dir)

    output_name = (
        args.output_name
        or plan_path.stem.replace("_plan", "")
        or "replay"
    )
    ga.run_from_plan(
        plan_path=str(plan_path),
        output_name=output_name,
        title=args.title or "Геометрическая задача",
        animated=args.animated,
        save_metrics=not args.no_save_metrics,
    )
    return 0


def cmd_auto(args: argparse.Namespace) -> int:
    rc = 0
    for path_str in args.paths:
        path = Path(path_str)
        if not path.exists():
            print(f"  skip {path}: not found")
            rc = 1
            continue
        kind = detect_input_kind(path)
        print(f"\n[auto] {path}: detected as `{kind}`")
        if kind == "conspect":
            sub = argparse.Namespace(
                paths=[str(path)],
                all=False,
                api_key=args.api_key,
                model=args.model,
                output_dir=args.output_dir,
            )
            rc = max(rc, cmd_conspect(sub))
        elif kind == "geometry-text":
            sub = argparse.Namespace(
                slug=None, file=str(path), text=None,
                title=None, output_name=None,
                api_key=args.api_key,
                model=args.model,
                output_dir=args.output_dir,
                no_save_plan=False,
                no_save_metrics=False,
                animated=args.animated,
                no_enforce_answer_vis=args.no_enforce_answer_vis,
                max_answer_vis_retries=args.max_answer_vis_retries,
            )
            rc = max(rc, cmd_geometry(sub))
        elif kind == "geometry-plan":
            sub = argparse.Namespace(
                plan=str(path),
                output_name=None,
                title=None,
                animated=args.animated,
                no_save_metrics=False,
                output_dir=args.output_dir,
            )
            rc = max(rc, cmd_geometry_replay(sub))
        else:
            print(f"  unsupported input kind: {kind} (skipped).")
            rc = 1
    return rc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _add_geometry_runtime_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--api-key", default=None,
                   help="Together AI API key (defaults to TOGETHER_API_KEY env).")
    p.add_argument("--model", default=None, help="LLM model id.")
    p.add_argument("--output-dir", default=None,
                   help="Override output directory.")
    p.add_argument("--animated", action="store_true",
                   help="Render an animated step-by-step HTML.")
    p.add_argument("--no-enforce-answer-vis", action="store_true",
                   help="Skip the answer-visualization post-condition retry "
                        "loop (default: enforced).")
    p.add_argument("--max-answer-vis-retries", type=int, default=1,
                   help="Maximum number of fix-requests issued by the "
                        "answer-vis post-validator (default: 1).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_unified",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # conspect
    sp_c = sub.add_parser("conspect",
                          help="Run the conspect pipeline on Markdown files.")
    sp_c.add_argument("paths", nargs="*",
                      help="One or more conspect .md files.")
    sp_c.add_argument("--all", action="store_true",
                      help="Run on all built-in conspects (task4, task6, "
                           "task8, task12).")
    sp_c.add_argument("--api-key", default=None)
    sp_c.add_argument("--model", default=None)
    sp_c.add_argument("--output-dir", default=None)
    sp_c.set_defaults(func=cmd_conspect)

    # geometry
    sp_g = sub.add_parser("geometry",
                          help="Run the geometry pipeline on a single problem.")
    src = sp_g.add_mutually_exclusive_group()
    src.add_argument("--slug", default=None,
                     help="Geometry corpus slug (see geometry_corpus.PROBLEMS).")
    src.add_argument("--file", default=None,
                     help="Read the problem text from a UTF-8 file.")
    src.add_argument("--text", default=None,
                     help="Inline problem text.")
    sp_g.add_argument("--title", default=None,
                      help="Title shown in the rendered HTML.")
    sp_g.add_argument("--output-name", default=None,
                      help="Base name for output files.")
    sp_g.add_argument("--no-save-plan", action="store_true")
    sp_g.add_argument("--no-save-metrics", action="store_true")
    _add_geometry_runtime_flags(sp_g)
    sp_g.set_defaults(func=cmd_geometry)

    # geometry-replay
    sp_r = sub.add_parser(
        "geometry-replay",
        help="Re-render a saved geometry plan without calling the LLM.",
    )
    sp_r.add_argument("--plan", required=True,
                      help="Path to a *_plan.json file.")
    sp_r.add_argument("--output-name", default=None)
    sp_r.add_argument("--title", default=None)
    sp_r.add_argument("--no-save-metrics", action="store_true")
    sp_r.add_argument("--output-dir", default=None)
    sp_r.add_argument("--animated", action="store_true")
    sp_r.set_defaults(func=cmd_geometry_replay)

    # auto
    sp_a = sub.add_parser(
        "auto",
        help="Detect input type by extension/content and dispatch.",
    )
    sp_a.add_argument("paths", nargs="+",
                      help="One or more input files (.md, .txt, .json).")
    _add_geometry_runtime_flags(sp_a)
    sp_a.set_defaults(func=cmd_auto)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
