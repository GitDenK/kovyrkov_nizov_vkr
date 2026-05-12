"""
Генерация отчёта-презентации по результатам тестирования планировщика визуалов.
"""

import json
from pathlib import Path
from collections import Counter

RESULTS_DIR = Path(__file__).parent / "results"

with open(RESULTS_DIR / "all_results.json", "r") as f:
    all_results = json.load(f)

MODELS = list(all_results.keys())
TASKS = ["task4", "task6", "task8", "task12"]
TASK_LABELS = {
    "task4": "№4 Классическая вероятность",
    "task6": "№6 Уравнения",
    "task8": "№8 Производная и графики",
    "task12": "№12 Исследование функций",
}
MODEL_SHORT = {m: m.split('/')[-1] for m in MODELS}

report = []
report.append("# Планировщик визуалов для конспектов ЕГЭ")
report.append("")
report.append("## Презентация результатов разработки и тестирования")
report.append("")
report.append("**Дата:** 18 марта 2026")
report.append("**Задача:** Автоматическое планирование визуализаций для персонализированных конспектов ЕГЭ по математике")
report.append("")

# Section 1
report.append("---")
report.append("## 1. Что такое планировщик визуалов?")
report.append("")
report.append("Планировщик визуалов — ключевой компонент пайплайна генерации учебных материалов.")
report.append("")
report.append("**Пайплайн:**")
report.append("```")
report.append("Конспект (текст) → Планировщик визуалов → Scene JSON → Template Retrieval → Renderer (SVG/TikZ) → Готовая инфографика")
report.append("```")
report.append("")
report.append("**Планировщик решает три задачи:**")
report.append("1. **ГДЕ** в тексте нужен визуал (не каждая секция требует иллюстрации)")
report.append("2. **КАКОЙ** тип визуализации подходит (из 13 типов в таксономии)")
report.append("3. **ЧТО** именно должно быть изображено (структурное описание в формате JSON)")
report.append("")

# Section 2
report.append("---")
report.append("## 2. Таксономия типов визуалов (13 типов)")
report.append("")
report.append("| Тип | Описание | Пример применения |")
report.append("|-----|---------|-------------------|")
report.append("| `function_graph` | График математической функции | Парабола y=x²−4 |")
report.append("| `table` | Таблица сравнения/классификации | Типы уравнений |")
report.append("| `step_by_step_diagram` | Пошаговая схема решения | Алгоритм нахождения ОДЗ |")
report.append("| `outcome_tree` | Дерево возможных исходов | Бросок двух монет |")
report.append("| `number_line` | Числовая прямая | Знаки производной |")
report.append("| `coordinate_plane` | Координатная плоскость | Точки пересечения |")
report.append("| `tangent_line_graph` | График с касательной | Наклон = производная |")
report.append("| `derivative_sign_chart` | Схема знаков производной | Возрастание/убывание |")
report.append("| `formula_card` | Карточка с формулой | P = m/n |")
report.append("| `comparison_chart` | Сравнение концепций | «ровно» vs «хотя бы» |")
report.append("| `flowchart` | Блок-схема алгоритма | Выбор метода решения |")
report.append("| `venn_diagram` | Диаграмма Венна | Пересечение событий |")
report.append("| `annotated_example` | Пример с аннотациями | Решение с выделением шагов |")
report.append("")

# Section 3: Quantitative comparison
report.append("---")
report.append("## 3. Сравнение моделей: количественные метрики")
report.append("")
report.append("### 3.1 Детальные результаты по конспектам")
report.append("")
report.append("| Модель | Конспект | Визуалов/Секций | Время, с | Токены (вх+вых) |")
report.append("|--------|---------|:---------------:|:--------:|:---------------:|")

model_totals = {}
for model in MODELS:
    m_short = MODEL_SHORT[model]
    model_totals[model] = {"visuals": 0, "sections": 0, "time": 0, "tokens_in": 0, "tokens_out": 0}
    for task in TASKS:
        r = all_results[model].get(task, {})
        if "error" in r:
            report.append(f"| {m_short} | {TASK_LABELS[task]} | ERROR | - | - |")
            continue
        vis = r["visuals_planned"]
        sec = r["sections_analyzed"]
        t = r["total_time_sec"]
        tok_in = r["total_tokens_in"]
        tok_out = r["total_tokens_out"]

        model_totals[model]["visuals"] += vis
        model_totals[model]["sections"] += sec
        model_totals[model]["time"] += t
        model_totals[model]["tokens_in"] += tok_in
        model_totals[model]["tokens_out"] += tok_out

        report.append(f"| {m_short} | {TASK_LABELS[task]} | {vis}/{sec} | {t:.1f} | {tok_in+tok_out:,} |")

report.append("")
report.append("### 3.2 Итого по моделям (все 4 конспекта)")
report.append("")
report.append("| Модель | Визуалов | Из секций | % покрытия | Время, с | Токены (вх) | Токены (вых) |")
report.append("|--------|:--------:|:---------:|:----------:|:--------:|:-----------:|:------------:|")

for model in MODELS:
    mt = model_totals[model]
    m_short = MODEL_SHORT[model]
    pct = (mt['visuals'] / mt['sections'] * 100) if mt['sections'] > 0 else 0
    report.append(f"| **{m_short}** | {mt['visuals']} | {mt['sections']} | {pct:.0f}% | {mt['time']:.0f} | {mt['tokens_in']:,} | {mt['tokens_out']:,} |")

report.append("")

# Section 4: Visual type distribution
report.append("---")
report.append("## 4. Распределение типов визуалов по моделям")
report.append("")

for model in MODELS:
    m_short = MODEL_SHORT[model]
    report.append(f"### {m_short}")
    report.append("")

    all_types = Counter()
    for task in TASKS:
        r = all_results[model].get(task, {})
        if "error" in r:
            continue
        for p in r["plans"]:
            if p["plan"]["need_visual"]:
                all_types[p["plan"]["visual_type"]] += 1

    total = sum(all_types.values())
    report.append("| Тип визуала | Количество | % |")
    report.append("|------------|:---------:|:--:|")
    for vtype, count in all_types.most_common():
        pct = count / total * 100 if total > 0 else 0
        bar = "█" * int(pct / 5)
        report.append(f"| `{vtype}` | {count} | {pct:.1f}% {bar} |")
    report.append("")

# Section 5: Qualitative examples
report.append("---")
report.append("## 5. Примеры запланированных визуалов (качественный анализ)")
report.append("")


def format_plan(plan_entry, show_params=True):
    lines = []
    p = plan_entry["plan"]
    lines.append(f"**Секция:** {p['section_title']}")
    lines.append(f"- **Тип:** `{p['visual_type']}`")
    lines.append(f"- **Педагогическая цель:** {p['pedagogical_goal']}")
    lines.append(f"- **Описание:** {p['description']}")
    lines.append(f"- **Подпись:** {p['caption']}")
    lines.append(f"- **Приоритет:** {p['priority']}")
    if show_params and p["params"]:
        lines.append(f"- **Параметры (scene JSON):**")
        lines.append("```json")
        lines.append(json.dumps(p["params"], ensure_ascii=False, indent=2))
        lines.append("```")
    return lines


# Examples for Task 4
report.append("### 5.1 №4 Классическая вероятность (Qwen 2.5-7B)")
report.append("")
task4_plans = all_results[MODELS[0]]["task4"]["plans"]
shown = 0
for p in task4_plans:
    if p["plan"]["need_visual"] and p["plan"]["priority"] == "high" and shown < 3:
        report.extend(format_plan(p))
        report.append("")
        shown += 1

# Examples for Task 8
report.append("### 5.2 №8 Производная и графики (Qwen 2.5-7B)")
report.append("")
task8_plans = all_results[MODELS[0]]["task8"]["plans"]
shown = 0
for p in task8_plans:
    if p["plan"]["need_visual"] and shown < 3:
        report.extend(format_plan(p))
        report.append("")
        shown += 1

# Examples for Task 12 - Mistral
report.append("### 5.3 №12 Исследование функций (Mistral Small 24B)")
report.append("")
task12_plans = all_results[MODELS[1]]["task12"]["plans"]
shown = 0
for p in task12_plans:
    if p["plan"]["need_visual"] and p["plan"]["visual_type"] in ["derivative_sign_chart", "function_graph", "step_by_step_diagram"] and shown < 3:
        report.extend(format_plan(p))
        report.append("")
        shown += 1

# Section 6: Cross-model comparison
report.append("---")
report.append("## 6. Сравнение моделей на одних и тех же секциях")
report.append("")
report.append("Одна и та же секция конспекта — как её видят разные модели:")
report.append("")


def compare_section_md(task, section_idx, label):
    lines = [f"### {label}", ""]
    lines.append(f"| Модель | Нужен визуал | Тип | Приоритет | Цель |")
    lines.append("|--------|:----------:|-----|:---------:|------|")
    for model in MODELS:
        m_short = MODEL_SHORT[model]
        r = all_results[model].get(task, {})
        if "error" in r:
            lines.append(f"| {m_short} | ERROR | - | - | - |")
            continue
        plans = r["plans"]
        if section_idx >= len(plans):
            lines.append(f"| {m_short} | — | — | — | секция не найдена |")
            continue
        p = plans[section_idx]["plan"]
        if p["need_visual"]:
            lines.append(f"| {m_short} | Да | `{p['visual_type']}` | {p['priority']} | {p['pedagogical_goal'][:80]} |")
        else:
            lines.append(f"| {m_short} | Нет | — | — | — |")
    lines.append("")
    return lines


report.extend(compare_section_md("task4", 3, "Секция «Формула классической вероятности» (task4)"))
report.extend(compare_section_md("task4", 5, "Секция «Пример 1: Бросок двух монет» (task4)"))
report.extend(compare_section_md("task8", 5, "Секция «Тип 1: Найти значение производной» (task8)"))
report.extend(compare_section_md("task12", 8, "Секция «Пример 1: Найти наибольшее значение» (task12)"))

# Section 7: Full plan for one conspect
report.append("---")
report.append("## 7. Полный план визуалов для одного конспекта")
report.append("")
report.append("### Конспект №4 «Классическая вероятность» (Qwen 2.5-7B)")
report.append("")

result = all_results[MODELS[0]]["task4"]
report.append(f"- **Всего секций:** {result['total_sections']}")
report.append(f"- **Проанализировано:** {result['sections_analyzed']}")
report.append(f"- **Визуалов запланировано:** {result['visuals_planned']}")
report.append(f"- **Время:** {result['total_time_sec']}s")
report.append("")
report.append("| # | Секция | Визуал | Тип | Приоритет |")
report.append("|:-:|--------|:------:|-----|:---------:|")

for entry in result["plans"]:
    p = entry["plan"]
    status = "✅" if p["need_visual"] else "—"
    vtype = f"`{p['visual_type']}`" if p["need_visual"] else "—"
    pri = p["priority"] if p["need_visual"] else "—"
    title = p["section_title"][:50]
    report.append(f"| {p['section_id']} | {title} | {status} | {vtype} | {pri} |")

report.append("")

# Section 8: Scene JSON examples
report.append("---")
report.append("## 8. Примеры Scene JSON (готовы для рендерера)")
report.append("")
report.append("Эти JSON-описания напрямую передаются в renderer для генерации SVG-визуалов:")
report.append("")

examples_to_show = [
    ("task4", 0, "outcome_tree"),
    ("task4", 0, "formula_card"),
    ("task8", 0, "tangent_line_graph"),
    ("task12", 0, "derivative_sign_chart"),
    ("task12", 1, "function_graph"),
]

for task, model_idx, target_type in examples_to_show:
    model = MODELS[model_idx]
    m_short = MODEL_SHORT[model]
    r = all_results[model].get(task, {})
    if "error" in r:
        continue
    for p in r["plans"]:
        if p["plan"]["need_visual"] and p["plan"]["visual_type"] == target_type:
            scene = {
                "visual_type": p["plan"]["visual_type"],
                "pedagogical_goal": p["plan"]["pedagogical_goal"],
                "description": p["plan"]["description"],
                "params": p["plan"]["params"],
                "caption": p["plan"]["caption"],
                "placement": p["plan"]["placement"],
            }
            report.append(f"### `{target_type}` — {TASK_LABELS[task]} ({m_short})")
            report.append("```json")
            report.append(json.dumps(scene, ensure_ascii=False, indent=2))
            report.append("```")
            report.append("")
            break

# Section 9: Conclusions
report.append("---")
report.append("## 9. Выводы и рекомендации")
report.append("")
report.append("### 9.1 Планировщик работает")
report.append("")
report.append("Все три модели успешно анализируют конспекты ЕГЭ и генерируют структурированные планы визуалов:")
report.append("- JSON-парсинг: **~100% успех** у всех моделей")
report.append("- Типы визуалов: **контекстно адекватны** тематике каждого конспекта")
report.append("- Params: содержат **конкретные уравнения, точки, шаги** — готовы для рендерера")
report.append("")

report.append("### 9.2 Сравнение моделей")
report.append("")
report.append("| Критерий | Qwen 2.5-7B | Mistral Small 24B | Gemma 3n-E4B |")
report.append("|----------|:-----------:|:-----------------:|:------------:|")

for model in MODELS:
    mt = model_totals[model]
    pct = (mt['visuals'] / mt['sections'] * 100) if mt['sections'] > 0 else 0

qwen_mt = model_totals[MODELS[0]]
mistral_mt = model_totals[MODELS[1]]
gemma_mt = model_totals[MODELS[2]]

q_pct = qwen_mt['visuals'] / qwen_mt['sections'] * 100
m_pct = mistral_mt['visuals'] / mistral_mt['sections'] * 100
g_pct = gemma_mt['visuals'] / gemma_mt['sections'] * 100

report.append(f"| Визуалов/секций | {qwen_mt['visuals']}/{qwen_mt['sections']} ({q_pct:.0f}%) | {mistral_mt['visuals']}/{mistral_mt['sections']} ({m_pct:.0f}%) | {gemma_mt['visuals']}/{gemma_mt['sections']} ({g_pct:.0f}%) |")
report.append(f"| Общее время | {qwen_mt['time']:.0f}s | {mistral_mt['time']:.0f}s | {gemma_mt['time']:.0f}s |")
report.append(f"| Токены (вх) | {qwen_mt['tokens_in']:,} | {mistral_mt['tokens_in']:,} | {gemma_mt['tokens_in']:,} |")
report.append(f"| Токены (вых) | {qwen_mt['tokens_out']:,} | {mistral_mt['tokens_out']:,} | {gemma_mt['tokens_out']:,} |")
report.append(f"| Разнообразие типов | Среднее | **Высокое** | Среднее |")
report.append(f"| Избыточность | Низкая | Высокая | Средняя |")
report.append("")

report.append("### 9.3 Рекомендация по модели")
report.append("")
report.append("**Qwen 2.5-7B-Instruct-Turbo** — лучший выбор для продакшена:")
report.append("- Генерирует адекватное количество визуалов (не перегружает конспект)")
report.append("- Корректно определяет типы визуалов по контексту")
report.append("- Даёт содержательные params с конкретными данными")
report.append("- Самый быстрый и экономичный по токенам")
report.append("- Хорошо следует инструкциям по формату JSON")
report.append("")
report.append("**Mistral Small 24B** — вариант для более богатого визуального покрытия:")
report.append("- Генерирует больше визуалов с бо́льшим разнообразием типов")
report.append("- Полезен, если стоит задача максимального визуального покрытия")
report.append("- Может потребовать пост-фильтрации для удаления избыточных визуалов")
report.append("")

report.append("### 9.4 Следующие шаги")
report.append("")
report.append("1. **SVG-рендерер** — реализовать рендерер для каждого типа визуала из таксономии")
report.append("2. **Библиотека шаблонов** — создать template retrieval с параметризованными SVG/TikZ")
report.append("3. **Персонализация** — связать уровень ученика со сложностью визуала (подробные/краткие)")
report.append("4. **Интеграция** — встроить планировщик в пайплайн генерации конспектов")
report.append("5. **A/B тестирование** — проверить эффективность визуалов с реальными учениками")
report.append("")

# Write report
output = "\n".join(report)
output_path = Path(__file__).parent / "REPORT.md"
output_path.write_text(output, encoding="utf-8")
print(f"Отчёт сохранён: {output_path}")
print(f"Размер: {len(output):,} символов")
