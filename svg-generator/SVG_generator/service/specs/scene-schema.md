# Scene DSL — Описание контракта данных

Документ описывает формат `scene_json` — основной контракт SVG-генератора.

---

## Принципы DSL

- LLM описывает **смысл** сцены, а не экранные координаты.
- Объекты ссылаются друг на друга через `id`.
- Для `function_plot` и `geometry` координаты задаются в **мировой системе** (world coordinates).
- Для `diagram` LLM задаёт только смысловые объекты и связи; геометрию вычисляет renderer.
- `scene_type` обязателен и передаётся вызывающей системой — сервис не занимается классификацией.

**Хорошо:**
```json
{ "type": "altitude", "triangle": "tri_ABC", "vertex": "C" }
```

**Плохо:**
```json
{ "type": "segment", "from": [120, 340], "to": [400, 200] }
```

---

## Верхний уровень — Scene

```json
{
  "scene_type": "geometry",
  "canvas": { ... },
  "style": { ... },
  "objects": [ ... ],
  "constraints": [ ... ],
  "annotations": [ ... ]
}
```

| Поле          | Тип                    | Обязательное | Описание                              |
|---------------|------------------------|:------------:|---------------------------------------|
| `scene_type`  | `string` (enum)        | да           | `function_plot`, `geometry`, `diagram` |
| `canvas`      | `Canvas`               | нет          | Размер холста и диапазон координат     |
| `style`       | `Style`                | нет          | Глобальный стиль                       |
| `objects`     | `SceneObject[]`        | да           | Основные объекты сцены                 |
| `constraints` | `Constraint[]`         | нет          | Дополнительные построения              |
| `annotations` | `Label[]`              | нет          | Текстовые аннотации                    |

---

## Canvas

```json
{
  "width": 400,
  "height": 400,
  "x_min": -5,
  "x_max": 5,
  "y_min": -5,
  "y_max": 5
}
```

| Поле     | Тип     | Умолч. | Описание                        |
|----------|---------|:------:|---------------------------------|
| `width`  | `float` | 400    | Ширина SVG в пикселях           |
| `height` | `float` | 400    | Высота SVG в пикселях           |
| `x_min`  | `float` | -5     | Левая граница мировых координат |
| `x_max`  | `float` | 5      | Правая граница                  |
| `y_min`  | `float` | -5     | Нижняя граница                  |
| `y_max`  | `float` | 5      | Верхняя граница                 |

---

## Style

```json
{
  "theme": "light",
  "stroke_color": "#333333",
  "fill_color": "none",
  "font_size": 12,
  "font_family": "sans-serif"
}
```

---

## ObjectStyle

Локальное переопределение стиля для отдельного объекта.

```json
{
  "stroke": "#e74c3c",
  "fill": "none",
  "stroke_width": 2,
  "dash": "dashed"
}
```

`dash`: `"solid"` | `"dashed"` | `"dotted"`

---

## Объекты сцены (SceneObject)

Тип объекта задаётся полем `type`. Все объекты имеют обязательное поле `id`.

### Point

```json
{
  "type": "point",
  "id": "A",
  "x": 1.0,
  "y": 2.0,
  "label": "A",
  "style": null
}
```

### Segment

Ссылается на `id` двух точек.

```json
{
  "type": "segment",
  "id": "seg_AB",
  "from_point": "A",
  "to_point": "B",
  "style": null
}
```

> `Line` и `Ray` в MVP не поддерживаются. Бесконечная прямая или луч описываются длинным `Segment` с точками за пределами canvas — renderer обрезает по viewBox.

### Circle

```json
{
  "type": "circle",
  "id": "circ_1",
  "center": "O",
  "radius": 3.0,
  "style": null
}
```

### Triangle

```json
{
  "type": "triangle",
  "id": "tri_ABC",
  "vertices": ["A", "B", "C"],
  "style": null
}
```

`vertices` — ровно 3 элемента, каждый — `id` объекта `Point`.

### FunctionCurve

```json
{
  "type": "function_curve",
  "id": "parabola",
  "expression": "x**2 - 2*x + 1",
  "x_min": -3,
  "x_max": 5,
  "style": null
}
```

`expression` — Python-выражение от `x` (совместимо с `math` и `sympy`). Если `x_min`/`x_max` не указаны, используются границы canvas.

### Label

```json
{
  "type": "label",
  "id": "lbl_A",
  "text": "A",
  "anchor": "A",
  "dx": 0.2,
  "dy": 0.2,
  "style": null
}
```

`anchor` — `id` объекта `Point`. `dx`/`dy` — смещение в мировых единицах.

### Box

Используется только в `diagram`.

```json
{
  "type": "box",
  "id": "box_func",
  "text": "f(x)",
  "style": null
}
```

Координаты и размеры для `box` не задаются: layout выполняется автоматически.

### Arrow

Используется только в `diagram`.

```json
{
  "type": "arrow",
  "id": "arr_1",
  "from_point": "box_func",
  "to_point": "box_deriv",
  "label": "дифференцирование",
  "style": null
}
```

`from_point` и `to_point` — `id` объектов `Box` или `Point`.

### Text

Произвольный смысловой текст. Используется только в `diagram`.

```json
{
  "type": "text",
  "id": "note_1",
  "text": "Геометрический смысл: наклон касательной",
  "font_size": 12,
  "style": null
}
```

| Поле        | Тип      | Обязательное | Описание                                 |
|-------------|----------|:------------:|------------------------------------------|
| `text`      | `string` | да           | Содержание подписи                       |
| `font_size` | `int?`   | нет          | Размер шрифта; по умолчанию — из `Style` |

### Title

Заголовок диаграммы — крупный полужирный текст. Используется только в `diagram`.

```json
{
  "type": "title",
  "id": "page_title",
  "text": "Производная функции",
  "style": null
}
```

Размер шрифта = `Style.font_size + 6`, начертание `bold`.

### FormulaBlock

Формульный блок. Формула задаётся в LaTeX-подобном формате для `Ziamath`. Используется только в `diagram`.

```json
{
  "type": "formula_block",
  "id": "formula_1",
  "formula": "$f'(x) = \\lim_{\\Delta x \\to 0} \\frac{f(x + \\Delta x) - f(x)}{\\Delta x}$",
  "font_size": 16,
  "style": null
}
```

| Поле        | Тип      | Обязательное | Описание                                        |
|-------------|----------|:------------:|-------------------------------------------------|
| `formula`   | `string` | да           | Строка формулы (LaTeX-подмножество для Ziamath) |
| `font_size` | `int?`   | нет          | Размер шрифта формулы; по умолчанию — из `Style` |

**Поддерживаемые конструкции:** базовые дроби, степени/индексы, корни, греческие буквы, текстовые вставки.
Если формула не поддерживается движком, renderer возвращает предупреждение в `warnings`.

---

## Constraints — дополнительные построения

Constraints описывают **смысловые** построения. Solver вычисляет координаты автоматически.

### MedianConstraint

```json
{
  "type": "median",
  "id": "med_A",
  "triangle": "tri_ABC",
  "vertex": "A"
}
```

### AltitudeConstraint

```json
{
  "type": "altitude",
  "id": "alt_C",
  "triangle": "tri_ABC",
  "vertex": "C"
}
```

### BisectorConstraint

```json
{
  "type": "bisector",
  "id": "bis_B",
  "triangle": "tri_ABC",
  "vertex": "B"
}
```

### MidpointConstraint

```json
{
  "type": "midpoint",
  "id": "mid_PQ",
  "segment": "seg_PQ",
  "result_id": "M"
}
```

`result_id` — `id` новой точки-середины, которую создаст solver.

### RightAngleMarkerConstraint

Рисует маркер прямого угла (маленький квадрат) у вершины. Не создаёт объектов — только визуальный элемент.

```json
{
  "type": "right_angle_marker",
  "id": "ram_A",
  "vertex": "A",
  "ray1": "B",
  "ray2": "C"
}
```

`vertex`, `ray1`, `ray2` — `id` объектов `Point`. `ray1` и `ray2` задают два луча из вершины (направление на точку).

---

## InputRequest

```json
{
  "scene_type": "geometry",
  "content": "Треугольник ABC с высотой из вершины C",
  "context": "Задача ЕГЭ по планиметрии",
  "options": null
}
```

| Поле         | Тип             | Обязательное | Описание                   |
|--------------|-----------------|:------------:|----------------------------|
| `scene_type` | `string` (enum) | да           | Тип сцены                  |
| `content`    | `string`        | да           | Текст задачи или темы      |
| `context`    | `string`        | нет          | Дополнительный контекст    |
| `options`    | `object`        | нет          | Дополнительные параметры   |

---

## RenderResult

```json
{
  "svg": "<svg ...>...</svg>",
  "warnings": [],
  "metadata": { "scene_type": "geometry" }
}
```

| Поле       | Тип        | Описание                              |
|------------|------------|---------------------------------------|
| `svg`      | `string?`  | Итоговый SVG или `null` при ошибке    |
| `warnings` | `string[]` | Нефатальные предупреждения            |
| `metadata` | `object`   | Метаданные (scene_type, версия и др.) |

---

## Правила ссылок

- `Segment.from_point` и `Segment.to_point` — должны быть `id` объекта `Point` в том же `objects`.
- `Circle.center` — `id` объекта `Point`.
- `Triangle.vertices` — ровно 3 `id` объектов `Point`.
- `Label.anchor` — `id` объекта `Point`.
- Все поля `triangle`, `segment`, `vertex` в Constraints — `id` объектов соответствующих типов.
- Ссылки разрешаются validator'ом; нарушение → ошибка валидации.

---

## Типичные ошибки

| Ошибка                                  | Причина                                    |
|-----------------------------------------|--------------------------------------------|
| `from_point` указывает на несуществующий id | Точка не объявлена в `objects`         |
| `vertices` содержит менее 3 элементов   | `Triangle` требует ровно 3 вершины         |
| `expression` содержит синтаксическую ошибку | Solver не сможет вычислить кривую      |
| `radius` ≤ 0                            | Некорректная окружность                    |
| `x_min` ≥ `x_max` в Canvas             | Инвертированный диапазон координат         |
