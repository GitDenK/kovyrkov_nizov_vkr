import asyncio
import logging
import time
import xml.etree.ElementTree as ET

from app.renderer.renderer import render
from app.schemas import InputRequest, RenderResult, Scene
from app.solver.solver import solve
from app.validation.validator import validate_and_normalize

logger = logging.getLogger(__name__)


def render_scene(data: dict) -> RenderResult:
    """Полный pipeline: validator → solver → renderer → svg_validation."""
    scene = Scene.model_validate(data)
    scene, val_warnings = validate_and_normalize(scene)
    scene, solve_warnings = solve(scene)
    warnings = val_warnings + solve_warnings

    svg = render(scene)

    try:
        ET.fromstring(svg)
    except ET.ParseError as e:
        return RenderResult(svg=None, warnings=warnings + [f"SVG XML invalid: {e}"])

    return RenderResult(svg=svg, warnings=warnings)


async def generate_svg_from_request(request: InputRequest) -> RenderResult:
    """
    Async LLM pipeline: text → scene (LLM) → render → сохранить артефакт.

    Импорты adapter и artifact_store отложены, чтобы сервис запускался
    без OPENROUTER_API_KEY (ошибка возникает только при вызове).
    """
    from app.llm.adapter import generate_scene
    from app.llm.artifact_store import save

    t_start = time.monotonic()
    logger.info("▶ pipeline start | scene_type=%s | content=%r", request.scene_type, request.content[:80])

    # --- LLM (async) ---
    t0 = time.monotonic()
    llm_result = await generate_scene(request.content, request.scene_type)
    t_llm = time.monotonic() - t0
    usage = llm_result.usage
    logger.info(
        "  LLM done | %.1fs | tokens: %s prompt + %s completion = %s total",
        t_llm,
        usage.get("prompt_tokens", "?"),
        usage.get("completion_tokens", "?"),
        usage.get("total_tokens", "?"),
    )

    # --- Validate ---
    t0 = time.monotonic()
    scene = llm_result.scene
    scene, val_warnings = validate_and_normalize(scene)
    logger.info("  validate | %.3fs | warnings: %d", time.monotonic() - t0, len(val_warnings))
    if val_warnings:
        for w in val_warnings:
            logger.warning("    ⚠ validate: %s", w)

    # --- Solve ---
    t0 = time.monotonic()
    scene, solve_warnings = solve(scene)
    logger.info("  solve    | %.3fs | warnings: %d", time.monotonic() - t0, len(solve_warnings))
    if solve_warnings:
        for w in solve_warnings:
            logger.warning("    ⚠ solve: %s", w)

    # --- Render ---
    t0 = time.monotonic()
    svg = render(scene)
    render_warnings = val_warnings + solve_warnings
    try:
        ET.fromstring(svg)
        svg_ok = True
    except ET.ParseError as e:
        render_warnings.append(f"SVG XML invalid: {e}")
        svg = None
        svg_ok = False
    logger.info("  render   | %.3fs | svg_ok=%s | svg_len=%s", time.monotonic() - t0, svg_ok, len(svg) if svg else 0)

    result = RenderResult(svg=svg, warnings=render_warnings)

    # --- Total ---
    logger.info("◀ pipeline done | total=%.1fs | warnings=%d", time.monotonic() - t_start, len(render_warnings))

    # --- Artifact (в thread, чтобы не блокировать event loop) ---
    try:
        await asyncio.to_thread(save, {
            "scene_type": request.scene_type,
            "input": request.model_dump(),
            "llm_request": {
                "model": request.scene_type,
                "messages": llm_result.request_messages,
            },
            "llm_response_raw": llm_result.response_raw,
            "llm_usage": usage,
            "scene_json": llm_result.scene.model_dump(),
            "render_warnings": render_warnings,
            "svg": svg,
        })
    except Exception as e:
        logger.warning("artifact_store: не удалось сохранить: %s", e)

    return result
