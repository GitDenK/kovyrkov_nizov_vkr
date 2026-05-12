"""
Планировщик визуалов v2 для конспектов ЕГЭ.

Улучшения по сравнению с v1:
1. Two-pass planning: первый проход — глобальный анализ всего конспекта,
   второй — детальное планирование для выбранных секций.
2. Few-shot примеры в промпте для повышения качества.
3. Валидация и пост-обработка: конкретизация params, фильтрация дублей.
"""

import json
import re
import time
import requests
from dataclasses import dataclass, field, asdict
from typing import Optional

from visual_planner import (
    VisualType,
    VISUAL_TYPE_DESCRIPTIONS,
    VisualPlan,
    split_conspect_into_sections,
    _extract_json,
    TOGETHER_API_URL,
)


# ---------------------------------------------------------------------------
# Промпт Pass 1: глобальный анализ конспекта
# ---------------------------------------------------------------------------

PASS1_SYSTEM_PROMPT = """Ты — планировщик визуалов для учебных конспектов ЕГЭ по математике.

Тебе дан ПОЛНЫЙ конспект, разбитый на пронумерованные секции. Твоя задача — определить, каким секциям нужен визуал и какого типа.

## Доступные типы визуалов:

{visual_types}

## Правила:

1. Визуал нужен для 40-70% секций — не каждой, но и не слишком мало.
2. ОБЯЗАТЕЛЬНО нужен визуал для:
   - Ключевых формул → formula_card
   - Примеров решений с вычислениями → annotated_example или outcome_tree
   - Описаний типов/классификаций → table или comparison_chart
   - Алгоритмов решения → step_by_step_diagram или flowchart
   - Описаний функций, графиков, производных → function_graph, tangent_line_graph, derivative_sign_chart
3. НЕ нужен визуал для:
   - Мотивационных блоков, советов, «что делать дальше»
   - Очень коротких секций (заголовок без содержания)
   - Секций, где уже есть хорошо оформленная markdown-таблица
4. Если секция содержит формулу И пошаговое решение — выбери тот тип визуала, который важнее для понимания.

## Формат ответа:

Верни ТОЛЬКО валидный JSON-массив (без markdown-обёртки). Каждый элемент:

[
  {"section_id": 0, "need_visual": true, "visual_type": "тип", "reason": "почему"},
  {"section_id": 1, "need_visual": false, "visual_type": "none", "reason": "почему нет"},
  ...
]

Включи ВСЕ секции в ответ."""


# ---------------------------------------------------------------------------
# Промпт Pass 2: детальное планирование с few-shot примерами
# ---------------------------------------------------------------------------

PASS2_SYSTEM_PROMPT = """Ты — планировщик визуалов для учебных конспектов ЕГЭ. Тебе дана одна секция конспекта, и ты знаешь, что для неё нужен визуал типа "{visual_type}".

Твоя задача — создать детальное описание визуала с КОНКРЕТНЫМИ параметрами.

## Критически важно:
- В params используй КОНКРЕТНЫЕ числа, формулы и значения из текста секции.
- НЕ пиши абстрактные "x1", "x2", "f(x)" — извлекай реальные данные из текста.
- Если в тексте есть формула y = x² - 4x + 5, пиши именно "x^2 - 4x + 5", а не "f(x)".
- Если в тексте есть точки x = 2, x = 3, пиши [2, 3], а не ["x1", "x2"].

## Примеры хороших ответов:

### Пример 1: formula_card для формулы вероятности
{"need_visual": true, "visual_type": "formula_card", "pedagogical_goal": "Запомнить формулу классической вероятности и понять смысл каждого элемента", "description": "Карточка с формулой P = m/n, где каждый элемент подписан и выделен цветом", "params": {"formula_latex": "P = \\frac{m}{n}", "components": {"P": "вероятность события (от 0 до 1)", "m": "число благоприятных исходов", "n": "число всех возможных исходов"}}, "caption": "Формула классической вероятности", "placement": "after_section", "priority": "high"}

### Пример 2: outcome_tree для задачи с монетами
{"need_visual": true, "visual_type": "outcome_tree", "pedagogical_goal": "Увидеть все 4 исхода и выделить 2 благоприятных", "description": "Дерево исходов при бросании двух монет: 4 ветки, 2 подсвечены как благоприятные", "params": {"experiment": "бросок двух монет", "outcomes": [["О","О"], ["О","Р"], ["Р","О"], ["Р","Р"]], "favorable": [["О","Р"], ["Р","О"]], "total_n": 4, "favorable_m": 2}, "caption": "Все исходы бросания двух монет (благоприятные выделены)", "placement": "after_section", "priority": "high"}

### Пример 3: derivative_sign_chart для конкретной функции
{"need_visual": true, "visual_type": "derivative_sign_chart", "pedagogical_goal": "Увидеть где функция возрастает и убывает, найти точку минимума", "description": "Числовая прямая с критической точкой x=2, знаки производной слева и справа", "params": {"function": "x^2 - 4x + 5", "derivative": "2x - 4", "critical_points": [2], "intervals": [{"range": "(-inf, 2)", "sign": "-", "behavior": "убывает"}, {"range": "(2, +inf)", "sign": "+", "behavior": "возрастает"}], "extrema": [{"x": 2, "type": "минимум", "y": 1}]}, "caption": "Знаки производной f'(x) = 2x - 4", "placement": "after_section", "priority": "high"}

### Пример 4: step_by_step_diagram для алгоритма
{"need_visual": true, "visual_type": "step_by_step_diagram", "pedagogical_goal": "Запомнить последовательность шагов решения", "description": "Вертикальная цепочка шагов с стрелками между ними", "params": {"steps": [{"label": "Определи тип уравнения", "detail": "степень / логарифм / дробь / корень"}, {"label": "Найди ОДЗ", "detail": "особенно для логарифмов и корней"}, {"label": "Приведи к простому виду", "detail": "одинаковые основания / определение"}, {"label": "Реши уравнение", "detail": "линейное или квадратное"}, {"label": "Проверь корни по ОДЗ", "detail": "отбрось посторонние"}]}, "caption": "Алгоритм решения уравнений", "placement": "after_section", "priority": "high"}

### Пример 5: annotated_example для примера решения
{"need_visual": true, "visual_type": "annotated_example", "pedagogical_goal": "Проследить каждый шаг решения с визуальными подсказками", "description": "Пошаговое решение с выделением ключевых преобразований", "params": {"problem": "Решите 4^{x+1} = 8", "steps": [{"expression": "4^{x+1} = 8", "annotation": "Запишем уравнение"}, {"expression": "(2^2)^{x+1} = 2^3", "annotation": "4 = 2², 8 = 2³"}, {"expression": "2^{2x+2} = 2^3", "annotation": "Степень степени"}, {"expression": "2x+2 = 3", "annotation": "Основания равны → показатели равны"}, {"expression": "x = 0.5", "annotation": "Решаем линейное уравнение"}]}, "caption": "Решение показательного уравнения 4^{x+1} = 8", "placement": "after_section", "priority": "high"}

## Формат ответа:

Верни ТОЛЬКО валидный JSON (без markdown-обёртки):
{"need_visual": true, "visual_type": "...", "pedagogical_goal": "...", "description": "...", "params": {...}, "caption": "...", "placement": "after_section", "priority": "high/medium/low"}"""


# ---------------------------------------------------------------------------
# Вызовы LLM
# ---------------------------------------------------------------------------

def _call_together(api_key, model, system, user_msg, temperature=0.3, max_tokens=4096):
    """Базовый вызов Together AI API."""
    start = time.time()
    resp = requests.post(
        TOGETHER_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=180,
    )
    elapsed = time.time() - start
    resp.raise_for_status()
    data = resp.json()
    raw = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage", {})
    return {
        "raw": raw,
        "elapsed": round(elapsed, 2),
        "tokens_in": usage.get("prompt_tokens", 0),
        "tokens_out": usage.get("completion_tokens", 0),
    }


def _extract_json_array(text: str) -> Optional[list]:
    """Извлекает JSON-массив из ответа LLM."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# Пост-обработка и валидация
# ---------------------------------------------------------------------------

def validate_and_enrich_params(plan: dict, section_text: str) -> dict:
    """Валидирует и обогащает params конкретными данными из текста."""
    params = plan.get("params", {})
    vtype = plan.get("visual_type", "")

    # Проверка на абстрактные параметры
    params_str = json.dumps(params, ensure_ascii=False)
    has_abstract = any(p in params_str for p in ['"x1"', '"x2"', '"a"', '"b"', '"f(x)"'])

    if has_abstract and vtype == "derivative_sign_chart":
        numbers = re.findall(r'[-+]?\d+\.?\d*', section_text)
        equations = re.findall(r'\$([^$]+)\$', section_text)
        if equations:
            for eq in equations:
                if "f(x)" in eq or "=" in eq:
                    func_match = re.search(r'f\(x\)\s*=\s*(.+)', eq)
                    if func_match:
                        params["function"] = func_match.group(1).strip()
                        break

    if vtype == "function_graph" and "equation" not in params:
        equations = re.findall(r'\$\s*(?:y|f\(x\))\s*=\s*([^$]+)\$', section_text)
        if equations:
            params["equation"] = equations[0].strip()

    plan["params"] = params
    return plan


def deduplicate_plans(plans: list[dict]) -> list[dict]:
    """Убирает дубликаты визуалов одного типа с похожим содержанием."""
    seen = {}
    result = []
    for p in plans:
        if not p["plan"]["need_visual"]:
            result.append(p)
            continue
        vtype = p["plan"]["visual_type"]
        desc_key = p["plan"]["description"][:80]
        key = f"{vtype}:{desc_key}"
        if key in seen:
            prev_pri = seen[key]["plan"]["priority"]
            curr_pri = p["plan"]["priority"]
            priority_rank = {"high": 3, "medium": 2, "low": 1}
            if priority_rank.get(curr_pri, 0) > priority_rank.get(prev_pri, 0):
                idx = result.index(seen[key])
                result[idx] = p
                seen[key] = p
        else:
            seen[key] = p
            result.append(p)
    return result


# ---------------------------------------------------------------------------
# Движок v2
# ---------------------------------------------------------------------------

class VisualPlannerV2:
    """Планировщик визуалов v2 с two-pass подходом."""

    def __init__(self, api_key: str, model: str = "Qwen/Qwen2.5-7B-Instruct-Turbo"):
        self.api_key = api_key
        self.model = model

    def plan_conspect(self, markdown_text: str, temperature: float = 0.3) -> dict:
        sections = split_conspect_into_sections(markdown_text)
        sections = [s for s in sections if len(s["text"].strip()) >= 30]

        total_tokens_in = 0
        total_tokens_out = 0
        total_time = 0

        # ===== PASS 1: глобальный анализ =====
        pass1_result = self._pass1_global_analysis(sections, temperature)
        total_tokens_in += pass1_result["tokens_in"]
        total_tokens_out += pass1_result["tokens_out"]
        total_time += pass1_result["elapsed"]

        section_decisions = {}
        if pass1_result["parsed"]:
            for item in pass1_result["parsed"]:
                sid = item.get("section_id")
                if sid is not None:
                    section_decisions[sid] = item

        # ===== PASS 2: детальное планирование =====
        plans = []
        for section in sections:
            sid = section["id"]
            decision = section_decisions.get(sid, {})
            need_visual = decision.get("need_visual", False)
            visual_type = decision.get("visual_type", "none")

            if need_visual and visual_type != "none":
                detail = self._pass2_detail_plan(section, visual_type, temperature)
                total_tokens_in += detail["tokens_in"]
                total_tokens_out += detail["tokens_out"]
                total_time += detail["elapsed"]

                parsed = detail["parsed"]
                if parsed is None:
                    parsed = {"need_visual": True, "visual_type": visual_type}

                parsed = validate_and_enrich_params(parsed, section["text"])

                plan = VisualPlan(
                    section_id=sid,
                    section_title=section["title"],
                    section_text_preview=section["text"][:200],
                    need_visual=True,
                    visual_type=parsed.get("visual_type", visual_type),
                    pedagogical_goal=parsed.get("pedagogical_goal", ""),
                    description=parsed.get("description", ""),
                    params=parsed.get("params", {}),
                    caption=parsed.get("caption", ""),
                    placement=parsed.get("placement", "after_section"),
                    priority=parsed.get("priority", "high"),
                )
            else:
                plan = VisualPlan(
                    section_id=sid,
                    section_title=section["title"],
                    section_text_preview=section["text"][:200],
                    need_visual=False,
                )

            plans.append({
                "plan": asdict(plan),
                "llm_meta": {
                    "model": self.model,
                    "pass1_decision": decision,
                },
            })

        plans = deduplicate_plans(plans)
        visuals_needed = sum(1 for p in plans if p["plan"]["need_visual"])

        return {
            "model": self.model,
            "version": "v2",
            "total_sections": len(sections),
            "sections_analyzed": len(plans),
            "visuals_planned": visuals_needed,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_time_sec": round(total_time, 2),
            "plans": plans,
        }

    def _pass1_global_analysis(self, sections, temperature):
        """Pass 1: отправить весь конспект, получить решения по секциям."""
        visual_types_str = "\n".join(
            f"- **{k}**: {v}" for k, v in VISUAL_TYPE_DESCRIPTIONS.items() if k != "none"
        )
        system = PASS1_SYSTEM_PROMPT.replace("{visual_types}", visual_types_str)

        sections_text = "\n\n".join(
            f"--- Секция {s['id']}: {s['title']} ---\n{s['text'][:500]}"
            for s in sections
        )
        user_msg = f"Вот конспект ЕГЭ по математике, разбитый на секции:\n\n{sections_text}\n\nОпредели для каждой секции, нужен ли визуал и какого типа. Верни JSON-массив."

        result = _call_together(self.api_key, self.model, system, user_msg, temperature, max_tokens=4096)
        parsed = _extract_json_array(result["raw"])

        return {
            "parsed": parsed,
            "elapsed": result["elapsed"],
            "tokens_in": result["tokens_in"],
            "tokens_out": result["tokens_out"],
            "raw": result["raw"],
        }

    def _pass2_detail_plan(self, section, visual_type, temperature):
        """Pass 2: детальный план для одной секции с известным типом."""
        system = PASS2_SYSTEM_PROMPT.replace("{visual_type}", visual_type)

        user_msg = f"""Создай детальный план визуала типа "{visual_type}" для этой секции.

### Название секции: {section['title']}

### Текст секции:
{section['text']}

Извлеки конкретные данные (числа, формулы, уравнения) из текста. Верни JSON."""

        result = _call_together(self.api_key, self.model, system, user_msg, temperature, max_tokens=2048)
        parsed = _extract_json(result["raw"])

        return {
            "parsed": parsed,
            "elapsed": result["elapsed"],
            "tokens_in": result["tokens_in"],
            "tokens_out": result["tokens_out"],
        }
