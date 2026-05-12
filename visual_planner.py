"""
Планировщик визуалов для конспектов ЕГЭ.

Принимает текст конспекта, разбивает его на секции,
определяет для каждой секции необходимость визуала,
тип визуализации и генерирует структурное описание (scene JSON).
"""

import json
import re
import time
import requests
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Таксономия типов визуалов
# ---------------------------------------------------------------------------

class VisualType(str, Enum):
    FUNCTION_GRAPH = "function_graph"
    TABLE = "table"
    STEP_BY_STEP = "step_by_step_diagram"
    OUTCOME_TREE = "outcome_tree"
    NUMBER_LINE = "number_line"
    COORDINATE_PLANE = "coordinate_plane"
    TANGENT_LINE_GRAPH = "tangent_line_graph"
    DERIVATIVE_SIGN_CHART = "derivative_sign_chart"
    FORMULA_CARD = "formula_card"
    COMPARISON_CHART = "comparison_chart"
    FLOWCHART = "flowchart"
    VENN_DIAGRAM = "venn_diagram"
    ANNOTATED_EXAMPLE = "annotated_example"
    NONE = "none"


VISUAL_TYPE_DESCRIPTIONS = {
    "function_graph": "График математической функции на координатной плоскости (парабола, прямая, и т.д.)",
    "table": "Таблица сравнения, классификации или данных",
    "step_by_step_diagram": "Пошаговая схема решения задачи с стрелками и промежуточными результатами",
    "outcome_tree": "Дерево/перечисление возможных исходов (для вероятности, комбинаторики)",
    "number_line": "Числовая прямая с отмеченными точками, интервалами, знаками",
    "coordinate_plane": "Координатная плоскость с точками, областями, геометрическими объектами",
    "tangent_line_graph": "График функции с касательной линией, демонстрирующий наклон",
    "derivative_sign_chart": "Схема знаков производной: интервалы +/-, экстремумы, возрастание/убывание",
    "formula_card": "Карточка с ключевой формулой, выделением компонентов и пояснениями",
    "comparison_chart": "Визуальное сравнение двух или более концепций/методов (side-by-side)",
    "flowchart": "Блок-схема алгоритма/выбора метода решения",
    "venn_diagram": "Диаграмма Венна для пересечения/объединения множеств или событий",
    "annotated_example": "Пример решения с визуальными аннотациями (выделение, стрелки, комментарии)",
    "none": "Визуал не нужен для данного фрагмента",
}


# ---------------------------------------------------------------------------
# Схема данных
# ---------------------------------------------------------------------------

@dataclass
class VisualPlan:
    """Один запланированный визуал для секции конспекта."""
    section_id: int
    section_title: str
    section_text_preview: str
    need_visual: bool
    visual_type: str = "none"
    pedagogical_goal: str = ""
    description: str = ""
    params: dict = field(default_factory=dict)
    caption: str = ""
    placement: str = "after_section"
    priority: str = "medium"


# ---------------------------------------------------------------------------
# Парсер конспекта: разбиение на секции
# ---------------------------------------------------------------------------

def split_conspect_into_sections(markdown_text: str) -> list[dict]:
    """Разбивает markdown-конспект на секции по заголовкам ##/###."""
    lines = markdown_text.strip().split("\n")

    # Skip YAML front matter
    content_start = 0
    if lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                content_start = i + 1
                break

    sections = []
    current_title = "Вводная часть"
    current_lines = []
    section_id = 0

    for line in lines[content_start:]:
        header_match = re.match(r'^(#{1,4})\s+(.+)', line)
        if header_match:
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    sections.append({
                        "id": section_id,
                        "title": current_title,
                        "text": text,
                    })
                    section_id += 1
            current_title = header_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        text = "\n".join(current_lines).strip()
        if text:
            sections.append({
                "id": section_id,
                "title": current_title,
                "text": text,
            })

    return sections


# ---------------------------------------------------------------------------
# Системный промпт для LLM
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Ты — планировщик визуалов для учебных конспектов ЕГЭ по математике. Твоя задача — проанализировать секцию конспекта и определить, нужен ли визуал, и если да — какой именно.

## Доступные типы визуалов:

{visual_types}

## Правила:

1. НЕ каждая секция требует визуала. Текстовые описания, советы, мотивация — обычно не нуждаются в визуале.
2. Визуал НУЖЕН, когда:
   - Описывается математическая функция или её свойства → function_graph
   - Есть классификация или сравнение типов задач → table или comparison_chart  
   - Описывается пошаговый алгоритм решения → step_by_step_diagram или flowchart
   - Перечисляются возможные исходы (вероятность) → outcome_tree
   - Работа с числовой прямой, интервалами, знаками → number_line или derivative_sign_chart
   - Ключевая формула, которую надо запомнить → formula_card
   - Пример решения, который выиграет от визуальных аннотаций → annotated_example
   - Описывается касательная к графику → tangent_line_graph
3. Для таблиц, уже присутствующих в тексте в markdown-формате: если таблица уже хорошо оформлена — ставь "none", т.к. она уже есть. Но если данные можно лучше показать визуально — предложи альтернативу.
4. Приоритет "high" — если визуал критически важен для понимания. "medium" — полезен. "low" — опционален.

## Формат ответа:

Верни ТОЛЬКО валидный JSON (без markdown-обёртки, без ```json```), строго следующей структуры:

<<EXAMPLE_START>>
  "need_visual": true или false,
  "visual_type": "тип_из_списка_выше",
  "pedagogical_goal": "что ученик должен понять/увидеть благодаря визуалу",
  "description": "подробное описание того, что должно быть изображено",
  "params": ... параметры зависящие от типа визуала ...,
  "caption": "подпись под визуалом",
  "placement": "before_section" или "after_section" или "inline",
  "priority": "high" или "medium" или "low"
<<EXAMPLE_END>>

Если визуал не нужен, верни JSON с "need_visual": false и "visual_type": "none".

## Примеры params для разных типов:

- function_graph: equation, x_range, highlight_roots, highlight_points
- step_by_step_diagram: steps (список шагов)
- derivative_sign_chart: function, critical_points, intervals (с range, sign, behavior)
- formula_card: formula_latex, components (словарь компонент с пояснениями)
- outcome_tree: experiment, outcomes, favorable
- flowchart: nodes (с id и label), edges (с from и to)
- table: headers, rows
"""


# ---------------------------------------------------------------------------
# Вызов LLM через Together AI
# ---------------------------------------------------------------------------

TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"


def call_llm(
    api_key: str,
    model: str,
    section_title: str,
    section_text: str,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict:
    """Вызывает LLM для анализа одной секции конспекта."""

    visual_types_str = "\n".join(
        f"- **{k}**: {v}" for k, v in VISUAL_TYPE_DESCRIPTIONS.items() if k != "none"
    )
    system = SYSTEM_PROMPT.replace("{visual_types}", visual_types_str)

    user_msg = f"""Проанализируй следующую секцию конспекта ЕГЭ и определи, нужен ли визуал.

### Название секции: {section_title}

### Текст секции:
{section_text}

Верни JSON с планом визуала."""

    start_time = time.time()
    resp = requests.post(
        TOGETHER_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    elapsed = time.time() - start_time
    resp.raise_for_status()
    data = resp.json()

    raw = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage", {})
    tokens_in = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)

    parsed = _extract_json(raw)

    return {
        "raw_response": raw,
        "parsed": parsed,
        "model": model,
        "elapsed_sec": round(elapsed, 2),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }


def _extract_json(text: str) -> Optional[dict]:
    """Извлекает JSON из ответа LLM, обрабатывая markdown-обёртки."""
    # Убираем ```json ... ``` обёртку
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())

    # Пробуем найти JSON-объект
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Основной класс планировщика
# ---------------------------------------------------------------------------

class VisualPlannerEngine:
    """Движок планировщика визуалов."""

    def __init__(self, api_key: str, model: str = "Qwen/Qwen2.5-7B-Instruct-Turbo"):
        self.api_key = api_key
        self.model = model

    def plan_conspect(
        self,
        markdown_text: str,
        temperature: float = 0.3,
    ) -> dict:
        """Анализирует весь конспект и возвращает план визуалов."""
        sections = split_conspect_into_sections(markdown_text)
        plans = []
        total_tokens_in = 0
        total_tokens_out = 0
        total_time = 0

        for section in sections:
            if len(section["text"].strip()) < 30:
                continue

            result = call_llm(
                api_key=self.api_key,
                model=self.model,
                section_title=section["title"],
                section_text=section["text"],
                temperature=temperature,
            )

            total_tokens_in += result["tokens_in"]
            total_tokens_out += result["tokens_out"]
            total_time += result["elapsed_sec"]

            parsed = result["parsed"]
            if parsed is None:
                parsed = {"need_visual": False, "visual_type": "none"}

            plan = VisualPlan(
                section_id=section["id"],
                section_title=section["title"],
                section_text_preview=section["text"][:200],
                need_visual=parsed.get("need_visual", False),
                visual_type=parsed.get("visual_type", "none"),
                pedagogical_goal=parsed.get("pedagogical_goal", ""),
                description=parsed.get("description", ""),
                params=parsed.get("params", {}),
                caption=parsed.get("caption", ""),
                placement=parsed.get("placement", "after_section"),
                priority=parsed.get("priority", "medium"),
            )
            plans.append({
                "plan": asdict(plan),
                "llm_meta": {
                    "model": result["model"],
                    "elapsed_sec": result["elapsed_sec"],
                    "tokens_in": result["tokens_in"],
                    "tokens_out": result["tokens_out"],
                    "raw_response": result["raw_response"],
                },
            })

        visuals_needed = sum(1 for p in plans if p["plan"]["need_visual"])

        return {
            "model": self.model,
            "total_sections": len(sections),
            "sections_analyzed": len(plans),
            "visuals_planned": visuals_needed,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_time_sec": round(total_time, 2),
            "plans": plans,
        }


# ---------------------------------------------------------------------------
# Модели для сравнения
# ---------------------------------------------------------------------------

MODELS_TO_COMPARE = [
    "Qwen/Qwen2.5-7B-Instruct-Turbo",
    "mistralai/Mistral-Small-24B-Instruct-2501",
    "google/gemma-3n-E4B-it",
]


def compare_models(
    api_key: str,
    markdown_text: str,
    models: list[str] = None,
    temperature: float = 0.3,
) -> dict:
    """Сравнивает несколько моделей на одном конспекте."""
    if models is None:
        models = MODELS_TO_COMPARE

    results = {}
    for model in models:
        print(f"\n{'='*60}")
        print(f"Модель: {model}")
        print(f"{'='*60}")
        engine = VisualPlannerEngine(api_key=api_key, model=model)
        try:
            result = engine.plan_conspect(markdown_text, temperature=temperature)
            results[model] = result
            print(f"  Секций: {result['total_sections']}")
            print(f"  Визуалов запланировано: {result['visuals_planned']}")
            print(f"  Время: {result['total_time_sec']}s")
            print(f"  Токены: {result['total_tokens_in']} in / {result['total_tokens_out']} out")
        except Exception as e:
            print(f"  ОШИБКА: {e}")
            results[model] = {"error": str(e)}

    return results
