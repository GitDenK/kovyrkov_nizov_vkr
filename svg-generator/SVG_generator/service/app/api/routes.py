import logging

from fastapi import APIRouter, HTTPException
from openai import APITimeoutError

from app.orchestrator.orchestrator import generate_svg_from_request, render_scene
from app.schemas import InputRequest, RenderResult, Scene

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate-svg", response_model=RenderResult)
async def generate_svg(request: InputRequest) -> RenderResult:
    """Принимает текст задачи и scene_type, возвращает SVG через LLM pipeline."""
    try:
        return await generate_svg_from_request(request)
    except APITimeoutError:
        from app.llm.config import settings
        logger.warning("LLM timeout после %.0fs", settings.llm_timeout)
        raise HTTPException(status_code=504, detail=f"LLM не ответила за {settings.llm_timeout:.0f}с. Попробуй позже.")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/render-scene", response_model=RenderResult)
async def render_scene_endpoint(scene_data: Scene) -> RenderResult:
    """Принимает готовый Scene JSON и возвращает SVG без LLM."""
    return render_scene(scene_data.model_dump())
