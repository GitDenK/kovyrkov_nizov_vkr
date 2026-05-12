# Milestone 1 — Детерминированный pipeline (без LLM)

**Статус:** выполнен  
**Версия:** 0.2.0

---

## Что реализовано

Добавлен полный pipeline обработки сцены: `validator → solver → renderer`. Новый endpoint `POST /render-scene` принимает готовый `Scene JSON` и возвращает SVG-строку. Все 9 golden-тестов проходят.

---

## Новые файлы и их назначение

### `app/validation/validator.py`

**Зачем:** перед вычислениями нужно убедиться, что все ссылки в constraints указывают на существующие объекты. Если constraint ссылается на несуществующий треугольник или точку — solver упадёт с непонятной ошибкой. Validator перехватывает это заранее и кладёт описание проблемы в `warnings`, не роняя весь запрос с HTTP 500.

**Что делает:**
- Строит множество `object_ids` по всем объектам сцены.
- Для каждого constraint проверяет атрибуты `triangle`, `vertex`, `segment`, `ray1`, `ray2` — если ссылка не найдена, добавляет warning.
- Возвращает `(scene, list[str])` — сцена не изменяется, только собираются предупреждения.

---

### `app/solver/solver.py`

**Зачем:** constraints — это декларативные геометрические правила («проведи медиану», «найди основание высоты»). Сами по себе они не являются объектами сцены — их нужно вычислить и материализовать как конкретные `Point` и `Segment`, чтобы renderer мог их нарисовать.

**Что добавляет в сцену:**

| Constraint | Добавляемые объекты | Алгоритм |
|---|---|---|
| `MidpointConstraint` | `Point` с `id = result_id` | `((x1+x2)/2, (y1+y2)/2)` |
| `MedianConstraint` | `Point` (середина противоположной стороны) + `Segment` (вершина → середина) | midpoint двух оставшихся вершин |
| `AltitudeConstraint` | `Point` (основание высоты) + `Segment` (вершина → основание) | проекция точки на прямую: `t = dot(V−A, B−A) / |B−A|²` |
| `BisectorConstraint` | `Point` (на биссектрисе) + `Segment` (вершина → точка) | теорема о биссектрисе: `D = (|VC|·B + |VB|·C) / (|VB|+|VC|)` |
| `RightAngleMarkerConstraint` | — (пропускается) | визуальный маркер рендерится в будущем |

**Детали реализации:**
- Все вычисления на обычной арифметике Python (`math` модуль), без sympy — геометрия здесь простая и точная в float.
- Поддерживает инкрементальный индекс: добавленные объекты доступны следующим constraints в том же запросе.
- Возвращает новую копию сцены (`model_copy`) — исходный объект не мутируется.

---

### `app/renderer/renderer.py`

**Зачем:** это основная «рисующая» часть системы. Получает сцену со всеми объектами (включая добавленные solver'ом) и генерирует SVG-строку, пригодную для встройки в HTML или отображения в браузере.

**Два режима координат:**

- **Мировые** (`function_plot`, `geometry`): применяется world-to-screen transform с инверсией оси Y:
  ```
  sx = (x − x_min) / (x_max − x_min) × width
  sy = (y_max − y) / (y_max − y_min) × height
  ```
- **Пиксельные** (`diagram`): `Box` и `Arrow` используют координаты напрямую — в диаграммах они задаются в пикселях, ось Y не инвертируется.

**Поддерживаемые объекты:**

| Тип | SVG-элемент | Особенности |
|---|---|---|
| `point` | `<circle r="4">` + `<text>` | label рядом с точкой |
| `segment` | `<line>` | поддержка стилей dash/dotted |
| `triangle` | три `<line>` | по трём парам вершин |
| `circle` | `<circle>` | радиус конвертируется из мировых единиц в пиксели |
| `function_curve` | `<polyline>` | 300 точек, `sympy.lambdify` + `numpy`; NaN-разрывы разбивают кривую на сегменты |
| `label` | `<text>` | смещение `dx/dy` из мировых единиц |
| `box` | `<rect>` + `<text>` | текст по центру, скруглённые углы |
| `arrow` | `<line>` + `<marker>` arrowhead | для Box–Box вычисляются точки выхода с краёв |

**Axes и grid** (только `geometry` / `function_plot`):
- Тонкая сетка (`#e0e0e0`) по целым значениям в диапазоне canvas.
- Оси X и Y (`#888888`) со стрелочными маркерами, отрисовываются только если `0` попадает в диапазон.

---

### `app/orchestrator/orchestrator.py`

**Зачем:** клей, который собирает три шага в одну функцию. Изолирует маршрутизатор от деталей реализации — route знает только `render_scene(data)`.

```python
def render_scene(data: dict) -> RenderResult:
    scene = Scene.model_validate(data)
    scene, val_warnings = validate_and_normalize(scene)
    scene, solve_warnings = solve(scene)
    svg = render(scene)
    return RenderResult(svg=svg, warnings=val_warnings + solve_warnings)
```

Все предупреждения из обоих шагов собираются в `RenderResult.warnings` — ни один из них не бросает исключение при мягких ошибках.

---

### `tests/test_golden.py`

**Зачем:** regression-тесты, которые гарантируют, что pipeline не падает ни на одном из 9 зафиксированных сценариев. При любом изменении кода — `pytest tests/test_golden.py` даёт мгновенную обратную связь.

Параметризован через `pytest.mark.parametrize` по всем `*.json` в `tests/golden/`. Каждый тест проверяет:
- `result.svg is not None`
- строка содержит `<svg` и `</svg>`
- нет необработанных исключений

---

## Изменения в существующих файлах

### `app/api/routes.py`

Добавлен endpoint `POST /render-scene`:

```python
@router.post("/render-scene", response_model=RenderResult)
async def render_scene_endpoint(scene_data: Scene) -> RenderResult:
    return render_scene(scene_data.model_dump())
```

Старый endpoint `POST /generate-svg` (заглушка Milestone 0) сохранён для обратной совместимости.

### `requirements.txt`

Добавлены зависимости: `sympy>=1.12`, `numpy>=1.26`, `pytest>=8.0`.

---

## Структура после выполнения

```
app/
  validation/
    __init__.py
    validator.py       ← новый
  solver/
    __init__.py
    solver.py          ← новый
  renderer/
    __init__.py
    renderer.py        ← новый
  orchestrator/
    __init__.py
    orchestrator.py    ← новый
  api/
    routes.py          ← обновлён
tests/
  __init__.py          ← новый
  test_golden.py       ← новый
  golden/              ← без изменений (9 JSON)
requirements.txt       ← обновлён
```

---

## Критерии готовности — выполнены

- `POST /render-scene` возвращает SVG с `Content-Type: application/json` ✓
- `pytest tests/test_golden.py` — **9/9 тестов зелёные** ✓
- Ошибки (несуществующая ссылка) → warning в `RenderResult.warnings`, не HTTP 500 ✓
