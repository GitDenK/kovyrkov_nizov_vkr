# Milestone 4 — Quality Loop

**Статус:** выполнен  
**Версия:** 0.5.0

---

## Цель

Сделать разработку управляемой: перевести pipeline на async, построить benchmark-инфраструктуру из 40 кейсов, автоматические SVG-чекеры, ручные инварианты и закрыть топ-баги, найденных при code review.

---

## Что реализовано

### 1. Async pipeline

**Проблема:** роуты были `async def`, но внутри вызывали полностью синхронный `generate_scene` (блокирующий `OpenAI` SDK), что блокировало event loop FastAPI на всё время LLM-запроса.

**Исправления:**

- `app/llm/adapter.py` — `OpenAI` → `AsyncOpenAI`, `_make_client()` → `_make_async_client()`, `generate_scene()` → `async def`. Библиотека `instructor` автоматически переключается в async-режим при получении `AsyncOpenAI`.
- `app/orchestrator/orchestrator.py` — `generate_svg_from_request()` → `async def`, `await generate_scene(...)`, файловая запись `artifact_store.save` обёрнута в `asyncio.to_thread()` чтобы не блокировать event loop.
- `app/api/routes.py` — `return generate_svg_from_request(request)` → `return await generate_svg_from_request(request)`.
- `render_scene()` остаётся синхронным — не делает I/O.
- `validate_and_normalize`, `solve`, `render` — синхронные CPU-функции, остаются синхронными (< 50ms).

**Тесты:**

- `tests/test_e2e.py` переведены на `pytest-asyncio` (`@pytest.mark.asyncio`, `AsyncMock`).
- Добавлены `pytest-asyncio>=0.23` в `requirements.txt` и `pytest.ini` с `asyncio_mode = auto`.

---

### 2. Benchmark-инфраструктура

#### `tests/benchmark/cases.json` — 40 кейсов

| Тип | Количество | Примеры |
|---|---|---|
| `function_plot` | 10 | парабола, синус, экспонента, логарифм, y=1/x, y=|x|, сигмоида |
| `geometry` | 15 | треугольники с медианой/высотой/биссектрисой, окружности, прямоугольник с диагональю, трапеция, теорема Фалеса |
| `diagram` | 10 | схема производной, алгоритм квадратного уравнения, иерархия множеств, метод бисекции |
| edge cases | 5 | y=|x|, сигмоида, острый треугольник, одна точка, одноблочная схема |

#### `tests/benchmark/checkers.py` — 4 автоматические проверки

| Чекер | Что проверяет |
|---|---|
| `check_svg_valid` | SVG является валидным XML (`ET.fromstring`) |
| `check_no_nan` | Нет строки `NaN` в атрибутах координат (regex) |
| `check_within_canvas` | Числовые координаты не выходят за пределы canvas + 20px допуск |
| `check_labels_readable` | Нет двух непустых `<text>`-элементов с одинаковыми `(x, y)` |

Каждый чекер возвращает `CheckResult(ok: bool, message: str)`. Удобная функция `run_all_checks(svg)` запускает все четыре.

**Нюанс:** пустые `<text>`-элементы, генерируемые matplotlib для `FormulaBlock`, фильтруются в `check_labels_readable` — иначе возникают ложные срабатывания.

#### `tests/benchmark/invariants.json` — ручные инварианты для 10 ключевых кейсов

Для кейсов `fp_001`, `fp_002`, `fp_009`, `geo_001`, `geo_002`, `geo_006`, `geo_008`, `dia_001`, `dia_003`, `dia_008` зафиксированы структурные инварианты:

```json
{
  "fp_001": {
    "description": "Парабола y=x²: кривая, оси и числовые подписи",
    "min_polyline_count": 1,
    "has_text": true,
    "min_line_count": 2
  }
}
```

Поддерживаемые инварианты: `min_polyline_count`, `min_line_count`, `min_circle_count`, `min_rect_count`, `has_text`, `has_polyline`.

#### `tests/run_benchmark.py` — CLI runner

```bash
python tests/run_benchmark.py
python tests/run_benchmark.py --cases tests/benchmark/cases.json --out tests/benchmark/results/
```

- Запускает все кейсы **параллельно** через `asyncio.gather` — использует async pipeline.
- Для каждого кейса сохраняет `results/{id}.svg` и `results/{id}.json` (метаданные + результаты чекеров).
- Генерирует Markdown-отчёт `results/report.md` с полной таблицей и разбором провалившихся кейсов.

#### `tests/test_benchmark.py` — pytest-интеграция

| Режим | Команда | Что делает |
|---|---|---|
| По умолчанию | `pytest tests/test_benchmark.py` | Прогоняет 4 чекера на 15 golden SVG-файлах |
| С флагом | `pytest tests/test_benchmark.py --benchmark` | Чекеры + инварианты на сохранённых результатах из `results/` |
| С флагом | `pytest tests/test_benchmark.py --integration` | Запускает кейсы с реальным LLM на лету |

`conftest.py` дополнен флагом `--benchmark` и маркером `benchmark`.

---

### 3. Bugfix по code review

#### Bugfix 1: `_render_circle` — окружности превращались в эллипсы

**Проблема:** радиус вычислялся только через масштаб оси X: `r_px = obj.radius * c.width / (c.x_max - c.x_min)`. При несимметричном canvas (разные пиксели на единицу по X и Y) окружность рендерилась эллипсом.

**Исправление** в `app/renderer/geometry.py`:

```python
# было
r_px = obj.radius * c.width / (c.x_max - c.x_min)

# стало
scale_x = c.width / (c.x_max - c.x_min)
scale_y = c.height / (c.y_max - c.y_min)
r_px = obj.radius * min(scale_x, scale_y)
```

#### Bugfix 2: объекты выходили за пределы canvas

**Проблема:** объекты с координатами за пределами мирового canvas рендерились поверх белого фона и выходили за границы SVG.

**Исправление** в `app/renderer/renderer.py` и `app/renderer/function_plot.py` — добавлен атрибут `overflow="hidden"` на корневой элемент `<svg>`. Браузеры обрезают всё содержимое по viewport:

```html
<svg ... overflow="hidden">
```

Вариант с `<clipPath>` не использован: `function_plot` применяет `_add_margins`, изменяя размеры canvas уже внутри рендерера — `clipPath` из общего header имел бы неверные размеры.

---

## Структура после выполнения

```
app/
  llm/
    adapter.py         — generate_scene теперь async (AsyncOpenAI + instructor)
    artifact_store.py  — save(); вызывается через asyncio.to_thread
  orchestrator/
    orchestrator.py    — generate_svg_from_request — async def
  api/
    routes.py          — await generate_svg_from_request(request)
  renderer/
    renderer.py        — overflow="hidden" на <svg>
    function_plot.py   — overflow="hidden" на <svg> (после _add_margins)
    geometry.py        — _render_circle использует min(scale_x, scale_y)
tests/
  benchmark/
    cases.json         — 40 кейсов (10 fp + 15 geo + 10 dia + 5 edge)
    checkers.py        — 4 SVG-проверки + run_all_checks()
    invariants.json    — ручные инварианты для 10 ключевых кейсов
    results/           — создаётся при запуске run_benchmark.py
  run_benchmark.py     — CLI: asyncio.gather по всем кейсам + Markdown-отчёт
  test_benchmark.py    — pytest: golden SVG quality + --benchmark режим
  conftest.py          — флаги --integration и --benchmark
pytest.ini             — asyncio_mode = auto
requirements.txt       — добавлен pytest-asyncio>=0.23
```

---

## Новые зависимости

```
pytest-asyncio>=0.23
```

---

## Результаты тестирования

```
pytest tests/
```

| Тест | Результат |
|---|---|
| `test_golden.py` (16 кейсов) | 16/16 ✓ |
| `test_e2e.py` mock (6 кейсов) | 6/6 ✓ |
| `test_benchmark.py` golden quality (15 SVG) | 15/15 ✓ |
| integration / benchmark | skipped (требуют флагов) |

**Итого: 37 passed, 11 skipped**

---

## Отклонения от плана

| Пункт плана | Фактически |
|---|---|
| `<clipPath id="canvas_clip">` | Заменён на `overflow="hidden"` — clipPath не работает с `_add_margins` в `function_plot` |
| 16 golden SVG в `test_benchmark.py` | 15 файлов (5 diagram + 5 function_plot + 5 geometry в `golden/preview/`) |

---

## Критерии готовности — выполнены

- Async pipeline: event loop FastAPI не блокируется во время LLM-запроса ✓
- 40 кейсов описаны в `cases.json` ✓
- 4 автоматических SVG-чекера реализованы и проходят на golden SVG ✓
- Ручные инварианты для 10 ключевых кейсов зафиксированы ✓
- `run_benchmark.py` готов к запуску с реальным LLM ✓
- Bugfix окружности: `min(scale_x, scale_y)` ✓
- Bugfix canvas overflow: `overflow="hidden"` ✓
- `pytest tests/` — **37 passed, 0 failed** ✓
