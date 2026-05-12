"""
Re-render SVGs from cached plan.json files (no LLM calls needed).

Usage: python pipeline/rerender.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SVG_SERVICE = ROOT / "svg-generator" / "SVG_generator" / "service"
sys.path.insert(0, str(SVG_SERVICE))

from pipeline.converter import convert_plan_to_scene
from pipeline.run_pipeline import try_render, generate_html_preview, OUTPUT_DIR, MODEL


def rerender_task(task_dir: Path) -> dict:
    plan_file = task_dir / "plan.json"
    if not plan_file.exists():
        return None

    plan_result = json.loads(plan_file.read_text(encoding="utf-8"))
    task_name = task_dir.name
    print(f"\n{task_name}: re-rendering...")

    svg_results = []
    for entry in plan_result["plans"]:
        plan = entry["plan"]
        if not plan.get("need_visual"):
            continue

        scene = convert_plan_to_scene(plan)
        if scene is None:
            continue

        scene_file = task_dir / f"scene_{plan['section_id']}_{plan['visual_type']}.json"
        scene_file.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")

        render_result = try_render(scene)
        svg = render_result["svg"]

        svg_file = None
        if svg:
            svg_file = task_dir / f"visual_{plan['section_id']}_{plan['visual_type']}.svg"
            svg_file.write_text(svg, encoding="utf-8")

        status = "OK" if svg else "FAIL"
        print(f"  [{status}] S{plan['section_id']} {plan['visual_type']} → {scene['scene_type']}")

        svg_results.append({
            "section_id": plan["section_id"],
            "section_title": plan.get("section_title", ""),
            "visual_type": plan["visual_type"],
            "scene_type": scene["scene_type"],
            "caption": plan.get("caption", ""),
            "priority": plan.get("priority", ""),
            "svg_file": str(svg_file) if svg_file else None,
            "svg_ok": svg is not None,
            "warnings": render_result.get("warnings", []),
        })

    ok = sum(1 for r in svg_results if r["svg_ok"])
    return {
        "conspect": task_name,
        "plan_result": plan_result,
        "svg_results": svg_results,
        "stats": {
            "total_visuals": len(svg_results),
            "rendered_ok": ok,
            "plan_time_sec": 0,
        },
    }


def main():
    all_results = []
    for task_dir in sorted(OUTPUT_DIR.iterdir()):
        if not task_dir.is_dir():
            continue
        result = rerender_task(task_dir)
        if result:
            all_results.append(result)

    if all_results:
        generate_html_preview(all_results)
        total_v = sum(r["stats"]["total_visuals"] for r in all_results)
        total_ok = sum(r["stats"]["rendered_ok"] for r in all_results)
        print(f"\nИТОГО: {total_ok}/{total_v} SVG отрендерено")


if __name__ == "__main__":
    main()
