# Milestone 2 — MVP renderer: все 3 типа сцен

**Статус:** выполнен  
**Версия:** 0.3.0

---

## Что реализовано

Renderer доведён до состояния полезного MVP: добавлены числовые подписи осей для `function_plot`, рендер маркера прямого угла для `geometry`, новые типы объектов `Text`, `Title`, `FormulaBlock` для `diagram`. Монолитный `renderer.py` разбит на три специализированных под-модуля. Golden-тесты расширены до 5 на каждый тип (15 + 1 = 16 тестов, все зелёные).

---

## Новые файлы и их назначение

### `app/renderer/function_plot.py`

**Зачем:** вынесен весь рендер `function_plot`-сцен в отдельный модуль.

**Что добавлено:**

- **Числовые подписи осей** (`_render_axis_labels`) — для каждого целого значения в диапазоне canvas рисует tick-риску и подпись. Ноль подписывается отдельно в начале координат.
- **Авто-margins** (`_add_margins`) — перед рендером расширяет диапазон мировых координат на 5% по каждому краю. Работает на локальной копии `Canvas`, исходный объект сцены не мутируется.

### `app/renderer/geometry.py`

**Зачем:** вынесен весь рендер `geometry`-сцен.

**Что добавлено:**

- **`_render_right_angle_marker`** — рисует маленький квадрат 10×10px у вершины между двумя лучами. Алгоритм: вычисляет единичные векторы от вершины к обеим точкам лучей в экранных координатах, строит четыре вершины квадрата.
- **Обработка `RightAngleMarkerConstraint`** — renderer напрямую обходит `scene.constraints` и рисует маркеры. Solver по-прежнему пропускает этот тип (маркер — визуальный, не вычислительный).

### `app/renderer/diagram.py`

**Зачем:** вынесен рендер `diagram`-сцен, добавлены три новых типа объектов.

**Что добавлено:**

| Тип | SVG-элемент | Особенности |
|-----|-------------|-------------|
| `Text` | `<text>` | Позиция x/y в пикселях, опциональный `font_size` |
| `Title` | `<text font-weight="bold">` | `font_size + 6` от глобального стиля, выровнен по умолчанию |
| `FormulaBlock` | `<g transform="translate(...)">` | matplotlib.mathtext → SVG paths, встраивается в нужное место |

#### Детали реализации `FormulaBlock`

1. Создаётся фигура `plt.figure` с размерами из полей `width`/`height` (в дюймах при dpi=72).
2. Текст формулы добавляется через `ax.text(0.5, 0.5, formula, ...)` — mathtext-синтаксис matplotlib.
3. Фигура сохраняется в `io.StringIO` формата SVG.
4. Из SVG-строки через `xml.etree.ElementTree` извлекаются все дочерние элементы внутри `<svg>`.
5. Извлечённые элементы оборачиваются в `<g transform="translate(x, y)">` для позиционирования.
6. Fallback при ошибке парсинга: рендерится формула как обычный `<text>`.

**Ограничения matplotlib.mathtext:**
- Нет поддержки матриц (`\begin{matrix}`) и выровненных уравнений (`\align`, `\cases`)
- Поддерживает: `\frac`, `\sqrt`, `\sum`, `\int`, степени/индексы, греческие буквы, `\lim`, `\infty`
- При необходимости матриц и полного LaTeX — заменить на MathJax в Milestone 4+

### `app/renderer/renderer.py` (рефактор)

Стал тонким dispatcher'ом: общие утилиты (`_sx`, `_sy`, `_render_axes_grid`) + `render(scene)` с dispatch по `scene_type`. Все объекты-рендеры делегированы в под-модули.

### `app/solver/geometry.py` (новый)

Sympy-утилиты для геометрических вычислений:

| Функция | Что делает |
|---------|------------|
| `line_intersection(p1, p2, p3, p4)` | Пересечение двух прямых через `sympy.geometry.Line` |
| `foot_of_perpendicular(vertex, base1, base2)` | Проекция точки на прямую через sympy |

Solver.py продолжает использовать текущие вычисления (float-арифметика, корректна). `geometry.py` — утилитарный модуль для расширений и новых типов constraints.

---

## Изменения в существующих файлах

### `app/schemas/objects.py`

Добавлены три новых класса:

```python
class Text(BaseModel):
    type: Literal["text"] = "text"
    id: str
    text: str
    x: float
    y: float
    font_size: Optional[int] = None
    style: Optional[ObjectStyle] = None

class Title(BaseModel):
    type: Literal["title"] = "title"
    id: str
    text: str
    x: float
    y: float
    style: Optional[ObjectStyle] = None

class FormulaBlock(BaseModel):
    type: Literal["formula_block"] = "formula_block"
    id: str
    formula: str
    x: float
    y: float
    width: float
    height: float
    font_size: Optional[int] = None
    style: Optional[ObjectStyle] = None
```

Включены в дискриминированный union `SceneObject`.

### `app/schemas/__init__.py`

Добавлены экспорты `Text`, `Title`, `FormulaBlock`.

### `requirements.txt`

Добавлена зависимость: `matplotlib>=3.8`.

---

## Новые golden-тесты (6 файлов)

| Файл | scene_type | Что тестирует |
|------|-----------|--------------|
| `geometry_4.json` | geometry | Прямоугольный треугольник + `right_angle_marker` у вершины A |
| `geometry_5.json` | geometry | `bisector` из вершины A + `right_angle_marker` |
| `function_plot_4.json` | function_plot | Широкий диапазон [−10, 10] — axis labels по всем делениям |
| `function_plot_5.json` | function_plot | Кубическая кривая y=x³−3x с точками экстремума и корнями |
| `diagram_4.json` | diagram | `Title` + `Box` + `Arrow` + `Text` в одной сцене |
| `diagram_5.json` | diagram | `FormulaBlock` с формулой предела производной |

---

## Структура после выполнения

```
app/
  schemas/
    objects.py         ← добавлены Text, Title, FormulaBlock
    __init__.py        ← обновлён
  renderer/
    renderer.py        ← рефакторинг: dispatcher + shared utils
    function_plot.py   ← новый
    geometry.py        ← новый
    diagram.py         ← новый
  solver/
    geometry.py        ← новый (sympy-утилиты)
tests/
  golden/
    geometry_4.json    ← новый
    geometry_5.json    ← новый
    function_plot_4.json ← новый
    function_plot_5.json ← новый
    diagram_4.json     ← новый
    diagram_5.json     ← новый
requirements.txt       ← добавлен matplotlib>=3.8
```

---

## Критерии готовности — выполнены

- `pytest tests/test_golden.py` — **16/16 тестов зелёные** ✓
- `function_plot`: числовые подписи на осях, tick-риски, авто-margins ✓
- `geometry`: `right_angle_marker` рендерится корректно ✓
- `diagram`: `Text`, `Title`, `FormulaBlock` поддерживаются ✓
- `FormulaBlock` рендерится через `matplotlib.mathtext` → SVG paths ✓
- Renderer разбит на под-модули согласно плану ✓
- 5+ golden-тестов на каждый тип сцен ✓
