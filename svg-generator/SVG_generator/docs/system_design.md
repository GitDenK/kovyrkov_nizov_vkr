# System Design Doc

## Сервис генерации точных SVG-иллюстраций для подготовки к ЕГЭ

**Версия:** 0.1
**Статус:** Draft

---

## 1. Цель

Реализовать backend-сервис, который принимает текст задачи, тему конспекта или структурированный запрос и возвращает **математически корректный SVG**.

Базовый принцип системы:

**входной запрос → LLM → Scene JSON → validation/solve → deterministic renderer → SVG**

---

## 2. Границы системы

### Система отвечает за

* классификацию типа визуализации;
* генерацию структурированного описания сцены;
* валидацию сцены;
* математические вычисления;
* layout;
* рендер в SVG;
* возврат SVG и метаданных.

### Система не отвечает за

* полноценный графический редактор;
* сложную интерактивную геометрию;
* ручную правку SVG пользователем;
* хранение всей учебной логики платформы.

---

## 3. Архитектурный принцип

Система делится на 2 слоя:

### 1. Вероятностный слой

Отвечает за понимание запроса и генерацию структуры:

* LLM
* prompt templates
* structured output

### 2. Детерминированный слой

Отвечает за корректность результата:

* schema validation
* математический solve
* layout
* renderer
* post-validation

Это ключевое решение всей архитектуры.

---

## 4. Основные сущности

### InputRequest

Входной запрос к сервису.

Поля:

* `input_type`: `task_text | topic | scene_json`
* `content`
* `context`
* `options`

### Scene

Структурированное описание сцены.

Поля:

* `scene_type`
* `canvas`
* `style`
* `objects`
* `constraints`
* `annotations`
* `render_options`

### NormalizedScene

Сцена после валидации и раскрытия shorthand-конструкций.

### SolvedScene

Сцена после математических вычислений и подготовки координат.

### RenderResult

Результат рендера.

Поля:

* `svg`
* `warnings`
* `metadata`

---

## 5. Поддерживаемые типы сцен

Для первой версии:

### 1. `function_plot`

* график функции;
* оси;
* сетка;
* точки;
* подписи.

### 2. `geometry`

* точки;
* отрезки;
* прямые;
* лучи;
* треугольники;
* окружности;
* подписи;
* дополнительные построения.

### 3. `diagram`

* блоки;
* стрелки;
* короткие подписи;
* простые формульные вставки.

---

## 6. Компоненты системы

## 6.1 API Layer

Отвечает за HTTP-интерфейс.

Основные endpoint’ы:

* `POST /generate-scene`
* `POST /validate-scene`
* `POST /render-scene`
* `POST /generate-svg`

Для MVP можно оставить один основной endpoint:

* `POST /generate-svg`

---

## 6.2 Orchestrator

Главный управляющий модуль pipeline.

Функции:

* определяет маршрут обработки;
* вызывает LLM;
* запускает validation;
* запускает solver;
* запускает renderer;
* формирует ответ.

---

## 6.3 LLM Adapter

Изолирует работу с моделью.

Функции:

* подготовка prompt;
* structured output;
* retry при schema errors;
* возврат Scene JSON.

Важно: LLM adapter не должен знать о деталях SVG.

---

## 6.4 Scene Schema Layer

Слой моделей данных.

Функции:

* описание DSL;
* Pydantic-модели;
* JSON validation;
* нормализация значений;
* проверка ссылок между объектами.

---

## 6.5 Geometry / Math Engine

Слой математических вычислений.

Функции:

* midpoint;
* intersection;
* projection;
* angle;
* basic symbolic evaluation;
* sampling functions;
* дополнительные построения.

---

## 6.6 Layout Engine

Отвечает за размещение объектов на canvas.

Функции:

* bounding box;
* scaling;
* margins;
* world-to-screen transform;
* размещение подписей;
* авторазмер маркеров.

---

## 6.7 SVG Renderer

Строит итоговый SVG.

Функции:

* рендер слоев;
* рендер геометрических примитивов;
* рендер графиков;
* рендер текста;
* применение theme/style.

---

## 6.8 Validation Layer

Проверяет результат до и после рендера.

Типы проверок:

* schema validation;
* semantic validation;
* render validation.

---

## 7. Полный pipeline

## 7.1 Шаг 1. Прием входа

Сервис принимает:

* текст задачи;
* тему конспекта;
* уже готовый Scene JSON.

## 7.2 Шаг 2. Определение режима

Если вход — `scene_json`, LLM не вызывается.

Если вход — текст:

* определяется `scene_type`;
* строится structured prompt.

## 7.3 Шаг 3. Генерация Scene JSON

LLM возвращает JSON по схеме.

## 7.4 Шаг 4. Валидация Scene JSON

Проверяются:

* типы;
* обязательные поля;
* ссылки;
* корректность enum;
* базовые ограничения.

Если ошибка не критична:

* выполняется auto-fix.

Если критична:

* retry к LLM.

## 7.5 Шаг 5. Нормализация

Сцена приводится к внутреннему формату:

* разворачиваются shorthand-конструкции;
* проставляются defaults;
* разрешаются ссылки;
* формулы переводятся в внутренние объекты.

## 7.6 Шаг 6. Solve

Выполняются вычисления:

* координаты производных объектов;
* midpoint;
* пересечения;
* кривые графиков;
* ключевые точки графиков;
* дополнительные линии.

## 7.7 Шаг 7. Layout

Сцена масштабируется и размещается на canvas.

## 7.8 Шаг 8. Render

Строится SVG.

## 7.9 Шаг 9. Post-validation

Проверяются:

* валидность SVG;
* отсутствие пустых объектов;
* отсутствие NaN;
* попадание элементов в canvas.

## 7.10 Шаг 10. Ответ

Сервис возвращает:

* SVG;
* scene JSON;
* warnings;
* metadata.

---

## 8. Внутренний контракт Scene DSL

## 8.1 Основные требования

DSL должен:

* быть независимым от SVG;
* описывать смысл сцены;
* быть удобным для генерации моделью;
* быть удобным для проверки кодом.

## 8.2 Принцип описания

LLM должна задавать:

* логические объекты;
* отношения;
* учебные акценты;

а не:

* ручные экранные координаты.

### Хорошо

* “медиана из A”
* “подписать точку M”
* “отметить прямой угол при H”

### Плохо

* “линия из (123, 221) в (417, 202)”

---

## 9. Ключевые проектные решения

### Решение 1. Scene-first, not SVG-first

Основной контракт системы — Scene JSON, а не SVG.

### Решение 2. Renderer полностью детерминирован

SVG строится только backend-кодом.

### Решение 3. Layout не зависит от LLM

LLM не управляет экранным размещением.

### Решение 4. Поддержка scene_json как входа

Это важно для тестов, дебага и дальнейшей интеграции.

### Решение 5. Ограниченный MVP

Сначала поддерживаются только 3 типа сцен.

---

## 10. Основные интерфейсы модулей

## 10.1 LLM Adapter

```python
generate_scene(input_text: str, scene_type: str) -> Scene
```

## 10.2 Validator

```python
validate_scene(scene: dict) -> ValidationResult
```

## 10.3 Normalizer

```python
normalize_scene(scene: Scene) -> NormalizedScene
```

## 10.4 Solver

```python
solve_scene(scene: NormalizedScene) -> SolvedScene
```

## 10.5 Renderer

```python
render_svg(scene: SolvedScene) -> RenderResult
```

## 10.6 Orchestrator

```python
generate_svg(request: InputRequest) -> RenderResult
```

---

## 11. Ошибки и fallback

Система должна различать:

### 1. Schema errors

Пример:

* отсутствует обязательное поле;
* неверный enum;
* неизвестный reference.

Действие:

* auto-fix или retry.

### 2. Semantic errors

Пример:

* медиана указана к несуществующей стороне;
* точка пересечения не существует.

Действие:

* controlled failure.

### 3. Render errors

Пример:

* NaN coordinates;
* пустой bbox;
* текст за пределами canvas.

Действие:

* логирование и controlled failure.

---

## 12. Хранение артефактов

Для каждого запроса желательно сохранять:

* входной запрос;
* scene_type;
* raw model output;
* validated scene;
* normalized scene;
* solved scene;
* final svg;
* warnings;
* renderer version.

Это поможет:

* в дебаге;
* в тестировании;
* в сборе кейсов для улучшения.

---

## 13. Структура репозитория

```text
service/
  app/
    api/
    orchestrator/
    llm/
    schemas/
    normalizer/
    solver/
    layout/
    renderer/
    validation/
    storage/
    utils/
  tests/
    unit/
    integration/
    golden/
  docs/
    PRD.md
    system-design.md
    scene-schema.md
    prompt-spec.md
    validation-spec.md
```

---

## 14. План разработки

Это главный раздел документа.

## Этап 1. Зафиксировать контракты

Сначала нужно описать систему на уровне данных.

### Сделать

1. определить список поддерживаемых `scene_type`;
2. описать минимальный Scene DSL;
3. описать Pydantic-модели;
4. описать JSON examples;
5. зафиксировать формат ответа API.

### Результат

Есть единый контракт, вокруг которого строится вся разработка.

### Почему это первым

Без этого невозможно:

* писать prompts;
* писать validator;
* писать renderer;
* писать тесты.

---

## Этап 2. Реализовать deterministic pipeline без LLM

Сначала сервис должен уметь работать на вручную заданном `scene_json`.

### Сделать

1. endpoint `render-scene-json`;
2. schema validation;
3. normalizer;
4. базовый solver;
5. базовый svg renderer;
6. post-validation;
7. golden tests на фиксированных JSON.

### Результат

Можно руками подать сцену и получить SVG.

### Почему это вторым

Это позволяет проверить ядро системы без нестабильности LLM.

---

## Этап 3. Сделать MVP renderer для 3 типов сцен

Нужно довести рендер до практически полезного состояния.

### Сначала реализовать

#### 3.1 Function plot

* axes
* grid
* function curve
* highlight point
* labels

#### 3.2 Geometry

* point
* segment
* line
* triangle
* circle
* label
* median
* altitude
* bisector
* right angle marker

#### 3.3 Diagram

* box
* arrow
* text
* title
* mini formula block

### Результат

Появляется первый полезный продуктовый функционал.

### Почему в таком порядке

* графики проще и быстрее валидировать;
* геометрия дает основную ценность для ЕГЭ;
* diagram нужен для конспектов, но его можно делать после базовой математики.

---

## Этап 4. Добавить LLM только после готовности ядра

На этом этапе подключается генерация Scene JSON из текста.

### Сделать

1. classifier или lightweight route selection;
2. prompt templates для каждого `scene_type`;
3. structured output generation;
4. retry policy;
5. сохранение raw output;
6. интеграционные тесты “text → scene → svg”.

### Результат

Сервис начинает работать end-to-end.

### Почему не раньше

Если подключить LLM слишком рано, будет непонятно, где ошибка:

* в prompt;
* в схеме;
* в solver;
* в renderer.

---

## Этап 5. Ввести quality loop

После появления e2e нужна системная проверка качества.

### Сделать

1. benchmark set из 30–50 кейсов;
2. acceptance checks;
3. ручную разметку expected invariants;
4. сбор типовых ошибок;
5. приоритизацию багов.

### Результат

Разработка становится управляемой.

---

## Этап 6. Интеграция в основной сервис

Только после этого сервис подключается к продукту.

### Сделать

1. единый API endpoint;
2. логирование;
3. таймауты;
4. кэширование;
5. feature flag;
6. fallback response.

### Результат

Можно безопасно включать фичу на части сценариев.

---

## 15. Приоритеты разработки по неделям

## Неделя 1

* Scene DSL
* Pydantic schema
* API contract
* примеры scene JSON

## Неделя 2

* validation
* normalizer
* базовый renderer
* function_plot MVP

## Неделя 3

* geometry renderer
* дополнительные построения
* layout engine
* golden tests

## Неделя 4

* diagram renderer
* LLM adapter
* structured prompts
* e2e pipeline

## Неделя 5

* benchmark
* retries
* post-validation
* bugfix cycle

## Неделя 6

* интеграция в основной сервис
* логирование
* кэширование
* документация

---

## 16. Что делать в самой первой реализации

Если нужен самый практичный старт, то порядок должен быть таким:

### Шаг 1

Написать `scene-schema.md`

### Шаг 2

Реализовать Pydantic-модели

### Шаг 3

Реализовать `render-scene-json`

### Шаг 4

Сделать renderer только для:

* point
* segment
* label
* axis
* grid
* function curve

### Шаг 5

Добавить:

* triangle
* circle
* median
* altitude
* bisector

### Шаг 6

Подключить LLM к генерации JSON

Это лучший порядок, потому что каждый следующий шаг опирается на уже проверенную основу.

---

## 17. Критерий готовности системы

Система считается готовой к первой продуктовой интеграции, если:

* она принимает `scene_json` и стабильно рендерит SVG;
* она поддерживает 3 базовых типа сцен;
* она проходит golden tests;
* LLM может сгенерировать scene JSON хотя бы для типовых задач;
* ошибки не приводят к некорректому SVG без явного сигнала.

---

## 18. Краткий итог

Главная идея дизайна:

* сначала строится **контракт сцены**;
* затем создается **детерминированное ядро**;
* только потом подключается **LLM**;
* затем добавляются **тесты, benchmark и интеграция**.

Правильная очередность разработки:

**Scene DSL → validator → renderer по scene_json → solve/layout → поддержка 3 типов сцен → LLM adapter → quality loop → product integration**

Именно в таком порядке сервис проще всего довести до рабочего состояния без хаоса и без смешивания ошибок разных уровней.
