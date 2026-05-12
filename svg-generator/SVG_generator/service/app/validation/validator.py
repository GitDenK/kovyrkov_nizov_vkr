import re

from app.renderer.text_engine import ZiaTextEngine
from app.schemas import Scene


_UNICODE_MATH_RE = re.compile(r"[ε∀∃∈√≈≤≥≠∞∑∫π₀-₉⁰-⁹]")
_TEXT_ENGINE = ZiaTextEngine()


def validate_and_normalize(scene: Scene) -> tuple[Scene, list[str]]:
    """Проверяет ссылки между объектами. Возвращает (scene, warnings)."""
    warnings: list[str] = []
    object_ids = {obj.id for obj in scene.objects}

    for c in scene.constraints:
        for attr in ("triangle", "vertex", "segment", "ray1", "ray2"):
            ref = getattr(c, attr, None)
            if ref and ref not in object_ids:
                warnings.append(f"Constraint '{c.id}': {attr} '{ref}' not found")

    # Для diagram предупреждаем, если математика пришла Unicode-символами вне `$...$`.
    if scene.scene_type == "diagram":
        diagram_nodes = {obj.id for obj in scene.objects if obj.type in {"box", "formula_block"}}

        def _warn_unicode_math(owner: str, text: str) -> None:
            if "$" in text:
                return
            if _UNICODE_MATH_RE.search(text):
                warnings.append(
                    f"{owner}: detected unicode math outside '$...$'; prefer LaTeX markup"
                )

        def _warn_empty_text(owner: str, text: str) -> None:
            if not text.strip():
                warnings.append(f"{owner}: empty text")

        def _warn_unsupported_math(owner: str, text: str, font_size: int) -> None:
            for kind, value in _TEXT_ENGINE.split_math_segments(text):
                if kind != "math":
                    continue
                supported, message = _TEXT_ENGINE.formula_supported(value, font_size)
                if not supported:
                    warnings.append(
                        message if message is not None else f"{owner}: unsupported formula"
                    )

        for obj in scene.objects:
            if obj.type in {"box", "text", "title"}:
                _warn_empty_text(f"Object '{obj.id}'", obj.text)
                _warn_unicode_math(f"Object '{obj.id}'", obj.text)
                _warn_unsupported_math(f"Object '{obj.id}'", obj.text, scene.style.font_size)
            elif obj.type == "arrow" and obj.label:
                if obj.from_point not in diagram_nodes:
                    warnings.append(
                        f"Arrow '{obj.id}': from_point '{obj.from_point}' must reference box/formula_block"
                    )
                if obj.to_point not in diagram_nodes:
                    warnings.append(
                        f"Arrow '{obj.id}': to_point '{obj.to_point}' must reference box/formula_block"
                    )
                if not obj.label.strip():
                    warnings.append(f"Arrow '{obj.id}' label: empty text")
                _warn_unicode_math(f"Arrow '{obj.id}' label", obj.label)
                _warn_unsupported_math(f"Arrow '{obj.id}' label", obj.label, max(8, scene.style.font_size - 2))
            elif obj.type == "arrow":
                if obj.from_point not in diagram_nodes:
                    warnings.append(
                        f"Arrow '{obj.id}': from_point '{obj.from_point}' must reference box/formula_block"
                    )
                if obj.to_point not in diagram_nodes:
                    warnings.append(
                        f"Arrow '{obj.id}': to_point '{obj.to_point}' must reference box/formula_block"
                    )
            elif obj.type == "formula_block":
                _warn_empty_text(f"FormulaBlock '{obj.id}'", obj.formula)
                formula_font_size = obj.font_size if obj.font_size is not None else max(scene.style.font_size + 2, 14)
                supported, message = _TEXT_ENGINE.formula_supported(obj.formula, formula_font_size)
                if not supported:
                    warnings.append(
                        message if message is not None else f"FormulaBlock '{obj.id}': unsupported formula"
                    )

    return scene, warnings
