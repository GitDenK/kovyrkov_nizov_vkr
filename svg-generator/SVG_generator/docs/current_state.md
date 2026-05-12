# Текущее состояние проекта

**Версия:** 0.5.0  
**Выполнен:** Milestone 0, Milestone 1, Milestone 2, Milestone 3, Milestone 4

---

## Что работает

- **`POST /generate-svg`** — принимает текст задачи и `scene_type`, вызывает LLM async, возвращает SVG. End-to-end pipeline.
- **`POST /render-scene`** — принимает готовый `Scene JSON`, возвращает SVG без LLM. Детерминированный pipeline.
- **Async pipeline** — `generate_scene` и `generate_svg_from_request` асинхронны (`AsyncOpenAI` + `asyncio.to_thread` для файловых операций); event loop FastAPI не блокируется.
- **Structured output** через `instructor` + OpenRouter: LLM возвращает валидный `Scene` JSON.
- **Retry**: при ValidationError instructor автоматически повторяет запрос (до 2 раз).
- **Артефакты**: каждый запрос сохраняет `.json` (запрос+ответ модели+scene+warnings) и `.svg` (для просмотра в браузере).
- **Логирование шагов** pipeline в консоль: время каждого этапа, токены, warnings.
- **Benchmark-инфраструктура**: 40 кейсов, 4 SVG-чекера, ручные инварианты для 10 кейсов, CLI-runner с параллельным запуском и Markdown-отчётом.
- **37/37 тестов зелёные** (`pytest tests/`); integration и benchmark — только с соответствующими флагами.

---

## Поддерживаемые типы сцен

### function_plot
- Оси, сетка, числовые подписи делений (tick-риски + цифры)
- Авто-margins 5% по всем краям
- График функции (300 точек, разрывы при NaN), подписи точек

### geometry
- Точки, отрезки, треугольники, окружности, метки
- Маркер прямого угла (`RightAngleMarkerConstraint`)
- Solver: медиана, высота, биссектриса, середина отрезка
- Окружности рендерятся корректно при несимметричном canvas (исправлен bugfix M4)

### diagram
- `Box`, `Arrow`, `Text`, `Title`, `FormulaBlock`
- `FormulaBlock` рендерится через `matplotlib.mathtext` → SVG paths
- Ограничение mathtext: нет матриц и `\align`; поддерживает `\frac`, `\sqrt`, греческие буквы

---

## Структура сервиса

```
app/
  schemas/         — Pydantic-модели Scene DSL
  validation/      — проверка ссылок между объектами
  solver/
    solver.py      — вычисление constraints
    geometry.py    — sympy-утилиты
  renderer/
    renderer.py    — dispatcher + overflow="hidden" на <svg>
    function_plot.py — overflow="hidden" после _add_margins
    geometry.py    — _render_circle: min(scale_x, scale_y)
    diagram.py
  llm/
    config.py      — pydantic-settings (все LLM-параметры через .env)
    adapter.py     — async generate_scene → GenerateResult (AsyncOpenAI)
    artifact_store.py — save(); вызывается через asyncio.to_thread
    prompts/
      function_plot.txt
      geometry.txt
      diagram.txt
  orchestrator/    — async generate_svg_from_request; логирование шагов
  api/routes.py    — FastAPI endpoints (await generate_svg_from_request)
tests/
  golden/          — 15 тестовых JSON-сцен (5 на тип)
  test_golden.py   — regression-тесты
  conftest.py      — флаги --integration, --benchmark
  test_e2e.py      — 6 async мок + 10 интеграционных тестов
  test_benchmark.py — quality-тесты: golden SVG + --benchmark режим
  run_benchmark.py — CLI: параллельный запуск 40 кейсов + Markdown-отчёт
  benchmark/
    cases.json     — 40 кейсов (10 fp + 15 geo + 10 dia + 5 edge)
    checkers.py    — 4 SVG-чекера + run_all_checks()
    invariants.json — ручные инварианты для 10 ключевых кейсов
    results/       — создаётся при запуске run_benchmark.py
artifacts/         — создаётся при первом запросе (в .gitignore)
.venv/             — Python 3.12
pytest.ini         — asyncio_mode = auto
pyrightconfig.json
```

---

## Конфигурация через `.env`

| Переменная | По умолчанию | Описание |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Ключ OpenRouter |
| `LLM_MODEL` | `deepseek/deepseek-v3.2` | Модель, меняется без смены кода |
| `LLM_MAX_TOKENS` | `1200` | Лимит токенов ответа |
| `LLM_TEMPERATURE` | `0.0` | 0 — детерминировано |
| `LLM_TIMEOUT` | `60.0` | Таймаут запроса (сек) |
| `LLM_INSTRUCTOR_MODE` | `JSON` | Режим instructor |
| `SAVE_ARTIFACTS` | `true` | Сохранение артефактов |

---

## Запуск

```bash
source .venv/bin/activate
uvicorn app.main:app --reload  # dev-сервер

pytest tests/                       # без LLM (37 тестов)
pytest tests/ --integration         # + реальные LLM-вызовы (тратят токены)
pytest tests/ --benchmark           # + проверка сохранённых результатов

python tests/run_benchmark.py       # полный benchmark: 40 кейсов параллельно
```

---

## Что не реализовано

- Кэширование по хэшу запроса — Milestone 5.
- Feature flag, production-логирование — Milestone 5.
- `FormulaBlock` с матрицами и `\align` (ограничение matplotlib.mathtext).
- Экспорт PNG/PDF.
- Запуск реального benchmark с LLM и отчёт о типовых ошибках (требует `OPENROUTER_API_KEY`).

## Следующий шаг

**Milestone 5** — Продуктовая интеграция: единый `/generate-svg` с чистым API-контрактом, таймаут, fallback response, feature flag, кэширование, документация API.
