"""Offline smoke test for pipeline/run_unified.py.

Exercises the pure parts of the unified entry point:
  * `detect_input_kind` on each supported extension and a few edge cases;
  * `build_parser` correctly registers all subcommands and required flags;
  * dispatch table wires each subcommand to the right handler.

Does NOT call any LLM and does not require TOGETHER_API_KEY.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.run_unified import (  # noqa: E402
    build_parser,
    cmd_auto,
    cmd_conspect,
    cmd_geometry,
    cmd_geometry_replay,
    detect_input_kind,
)


def test_detect_input_kind_md():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "task.md"
        p.write_text("# Title\nbody", encoding="utf-8")
        assert detect_input_kind(p) == "conspect"


def test_detect_input_kind_txt():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "problem.txt"
        p.write_text("Дано: ...", encoding="utf-8")
        assert detect_input_kind(p) == "geometry-text"


def test_detect_input_kind_geometry_plan():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "foo_plan.json"
        p.write_text(json.dumps({
            "title": "x",
            "points": {"A": {"x": 0, "y": 0}},
            "steps": [{"caption": "1", "objects": []}],
        }), encoding="utf-8")
        assert detect_input_kind(p) == "geometry-plan"


def test_detect_input_kind_random_json_is_unknown():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "data.json"
        p.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        assert detect_input_kind(p) == "unknown"


def test_detect_input_kind_invalid_json_is_unknown():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "broken.json"
        p.write_text("{not valid json", encoding="utf-8")
        assert detect_input_kind(p) == "unknown"


def test_detect_input_kind_other_extension_is_unknown():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "image.png"
        p.write_bytes(b"\x89PNG")
        assert detect_input_kind(p) == "unknown"


def test_parser_help_does_not_error():
    parser = build_parser()
    try:
        parser.parse_args(["--help"])
    except SystemExit as e:
        assert e.code == 0


def test_parser_dispatch_targets():
    parser = build_parser()
    a = parser.parse_args(["conspect", "--all"])
    assert a.command == "conspect"
    assert a.func is cmd_conspect

    b = parser.parse_args(["geometry", "--slug", "task16_trapezoid"])
    assert b.command == "geometry"
    assert b.func is cmd_geometry
    assert b.slug == "task16_trapezoid"
    assert b.max_answer_vis_retries == 1
    assert b.no_enforce_answer_vis is False

    c = parser.parse_args([
        "geometry-replay", "--plan", "/tmp/dummy_plan.json",
    ])
    assert c.command == "geometry-replay"
    assert c.func is cmd_geometry_replay
    assert c.plan == "/tmp/dummy_plan.json"

    d = parser.parse_args([
        "auto", "conspects/task4.md", "problem.txt",
    ])
    assert d.command == "auto"
    assert d.func is cmd_auto
    assert d.paths == ["conspects/task4.md", "problem.txt"]


def test_geometry_subcommand_mutual_exclusion():
    parser = build_parser()
    try:
        parser.parse_args([
            "geometry", "--slug", "x", "--file", "y.txt",
        ])
        raised = False
    except SystemExit:
        raised = True
    assert raised, "expected --slug/--file/--text to be mutually exclusive"


def test_no_enforce_answer_vis_flag():
    parser = build_parser()
    a = parser.parse_args([
        "geometry", "--slug", "task16_trapezoid",
        "--no-enforce-answer-vis", "--max-answer-vis-retries", "3",
    ])
    assert a.no_enforce_answer_vis is True
    assert a.max_answer_vis_retries == 3


def test_geometry_no_input_returns_error_code(monkeypatch=None):
    """When no API key and no input source is provided, the geometry handler
    returns a non-zero exit code instead of raising."""
    import argparse as ap
    ns = ap.Namespace(
        slug=None, file=None, text=None,
        title=None, output_name=None,
        api_key="dummy",
        model=None,
        output_dir=None,
        no_save_plan=False, no_save_metrics=False,
        animated=False,
        no_enforce_answer_vis=True,  # bypass the LLM-only path
        max_answer_vis_retries=0,
    )
    rc = cmd_geometry(ns)
    assert rc == 1, f"expected error code, got {rc}"


def main() -> int:
    tests = [
        ("detect_input_kind .md", test_detect_input_kind_md),
        ("detect_input_kind .txt", test_detect_input_kind_txt),
        ("detect_input_kind plan.json", test_detect_input_kind_geometry_plan),
        ("detect_input_kind random json", test_detect_input_kind_random_json_is_unknown),
        ("detect_input_kind invalid json", test_detect_input_kind_invalid_json_is_unknown),
        ("detect_input_kind other ext", test_detect_input_kind_other_extension_is_unknown),
        ("parser --help no-throw", test_parser_help_does_not_error),
        ("parser dispatch", test_parser_dispatch_targets),
        ("parser mutex (slug/file/text)", test_geometry_subcommand_mutual_exclusion),
        ("parser no-enforce flag", test_no_enforce_answer_vis_flag),
        ("geometry no input -> rc=1", test_geometry_no_input_returns_error_code),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  OK  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR  {name}: {type(e).__name__}: {e}")

    if failed:
        print(f"\n{failed} test(s) failed.")
        return 1
    print(f"\nAll {len(tests)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
