# Milestone 3 — LLM Adapter и end-to-end pipeline

**Статус:** выполнен  
**Версия:** 0.4.0

---

## Цель

Подключить LLM к существующему детерминированному pipeline: `POST /generate-svg` теперь принимает произвольный текст задачи и возвращает SVG без ручного составления `scene_json`.

---

## Что реализовано

### `app/llm/config.py` — конфигурация через pydantic-settings

Все параметры LLM вынесены в `Settings`, читаемый из `.env` или переменных окружения:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Ключ OpenRouter (обязательный при вызове) |
| `LLM_MODEL` | `deepseek/deepseek-v3.2` | Любая модель OpenRouter, меняется без смены кода |
| `LLM_MAX_TOKENS` | `1200` | Лимит ответа (scene JSON редко превышает 800 токенов) |
| `LLM_TEMPERATURE` | `0.0` | 0 — детерминированный вывод, 0.7–1.0 — разнообразнее |
| `LLM_TIMEOUT` | `60.0` | Таймаут запроса в секундах |
| `LLM_INSTRUCTOR_MODE` | `JSON` | Режим instructor (`JSON`, `JSON_SCHEMA`, `TOOLS`) |
| `SAVE_ARTIFACTS` | `true` | Сохранять артефакты в файлы |
| `ARTIFACTS_DIR` | `artifacts` | Путь к папке артефактов |

Ключ API никогда не попадает в код — только через `.env` (который в `.gitignore`).

---

### `app/llm/adapter.py` — вызов LLM

Использует библиотеку `instructor` поверх OpenAI SDK для structured output. Возвращает `GenerateResult` — датакласс со всеми данными для логирования:

```python
@dataclass
class GenerateResult:
    scene: Scene              # распарсенная Pydantic-модель
    request_messages: list    # системный промпт + запрос пользователя
    response_raw: str         # сырой текст ответа модели
    usage: dict               # токены: prompt / completion / total
```

**Ключевые решения:**

- `instructor.from_openai(raw, mode=Mode.JSON)` — `Mode.JSON` единственный корректный режим для OpenAI-совместимого API; `Mode.MD_JSON` не поддерживается `from_openai` (обнаружено в процессе).
- `create_with_completion()` вместо `create()` — возвращает и распарсенный объект, и сырой `ChatCompletion`. Позволяет сохранить токены и raw-ответ без дополнительных вызовов API.
- `max_retries=2` — instructor автоматически делает retry при `ValidationError`, добавляя описание ошибки в историю. Отдельный retry-цикл не нужен.
- Ключ проверяется при создании клиента — сервер запускается без `OPENROUTER_API_KEY`, ошибка возникает только при вызове.

---

### `app/llm/prompts/` — системные промпты

По одному файлу на тип сцены (`function_plot.txt`, `geometry.txt`, `diagram.txt`). Каждый промпт:

- Формулирует роль (~1 строка)
- Запрещает экранные координаты — только мировые или пиксельные по правилам DSL
- Перечисляет допустимые типы объектов и их обязательные поля
- Содержит 1 компактный пример JSON для ориентира

Размер каждого промпта ~150–200 токенов — минимум для корректного вывода.

---

### `app/llm/artifact_store.py` — хранилище артефактов

Изолированный модуль с единственной функцией `save(artifact: dict)`. Сохранение включается флагом `SAVE_ARTIFACTS=true` в `.env`; при `false` — не делает ничего.

При каждом запросе создаются два файла:

```
artifacts/
  2026-03-24T22-00-35_geometry.json   ← полный лог (без SVG)
  2026-03-24T22-00-35_geometry.svg    ← SVG отдельно, открывается в браузере
```

Содержимое JSON-артефакта:
- `input` — запрос пользователя (`InputRequest`)
- `llm_request.messages` — сообщения, отправленные в модель (system + user)
- `llm_response_raw` — сырой текст ответа до Pydantic-парсинга
- `llm_usage` — токены: prompt / completion / total
- `scene_json` — распарсенная сцена
- `render_warnings` — предупреждения из validator и solver

Для смены хранилища (файлы → БД → S3) — менять только этот модуль.

---

### `app/orchestrator/orchestrator.py` — LLM-ветка и логирование

Добавлена функция `generate_svg_from_request(request: InputRequest) → RenderResult`:

1. Вызывает `generate_scene` → `GenerateResult`
2. Раздельно прогоняет `validate_and_normalize` и `solve` (для логирования каждого шага)
3. Рендерит SVG
4. Сохраняет артефакт

Функция `render_scene` (детерминированный pipeline без LLM) — без изменений.

**Логирование каждого шага** — в консоль сервера при каждом запросе:

```
22:00:35 [INFO] ▶ pipeline start | scene_type=geometry | content='Треугольник ABC...'
22:00:35 [INFO]   → LLM request | model=deepseek/deepseek-v3.2 | mode=JSON
22:00:52 [INFO]   LLM done | 17.3s | tokens: 312 prompt + 187 completion = 499 total
22:00:52 [INFO]   validate | 0.001s | warnings: 0
22:00:52 [INFO]   solve    | 0.003s | warnings: 0
22:00:52 [INFO]   render   | 0.012s | svg_ok=True | svg_len=2341
22:00:52 [INFO] ◀ pipeline done | total=17.3s | warnings=0
```

---

### `app/api/routes.py` — обновлённый `/generate-svg`

Endpoint теперь вызывает `generate_svg_from_request`. Добавлена обработка таймаута:
- `RuntimeError` (нет ключа) → HTTP 503
- `APITimeoutError` → HTTP 504 с понятным сообщением

---

### `tests/conftest.py` + `tests/test_e2e.py`

**Мок-тесты** (6 кейсов, всегда запускаются):
- Патчат `generate_scene` и `save` в исходных модулях
- Подставляют заранее написанный `GenerateResult` с корректным `Scene`
- Проверяют весь pipeline от orchestrator до валидного SVG без LLM

**Интеграционные тесты** (10 кейсов, только с `--integration`):
- Реальные LLM-вызовы через OpenRouter
- 3–4 кейса на каждый тип сцены
- Пропускаются через `pytest.skip` при обычном `pytest`

```bash
pytest tests/             # только мок-тесты — токены не тратятся
pytest tests/ --integration  # + реальные LLM-вызовы
```

---

## Виртуальное окружение

Создано `.venv/` с Python 3.12 (`/opt/homebrew/bin/python3.12`).  
Python 3.12 устраняет необходимость в `eval_type_backport` — `instructor` использует синтаксис `str | Path` (Python 3.10+).

Добавлен `pyrightconfig.json` для автоматического подхвата интерпретатора в Cursor/Pylance.

---

## Новые зависимости

```
openai>=1.0.0
instructor>=1.0.0
pydantic-settings>=2.0.0
```

---

## Структура после выполнения

```
app/
  llm/
    __init__.py
    config.py          — pydantic-settings (все LLM-параметры)
    adapter.py         — generate_scene → GenerateResult
    artifact_store.py  — save(); управляется SAVE_ARTIFACTS
    prompts/
      function_plot.txt
      geometry.txt
      diagram.txt
  orchestrator/
    orchestrator.py    — добавлена generate_svg_from_request + логирование
  api/
    routes.py          — /generate-svg работает end-to-end; обработка таймаута
  main.py              — настройка logging.basicConfig
tests/
  conftest.py          — флаг --integration
  test_e2e.py          — 6 мок + 10 интеграционных тестов
artifacts/             — создаётся при первом запросе (в .gitignore)
.venv/                 — Python 3.12 (в .gitignore)
pyrightconfig.json
requirements.txt       — добавлены openai, instructor, pydantic-settings
```

---

## Отклонения от плана

| Пункт плана | Фактически |
|---|---|
| `Mode.MD_JSON` | Заменён на `Mode.JSON` — `MD_JSON` не поддерживается `from_openai` |
| `generate_scene` возвращает `Scene` | Возвращает `GenerateResult` — нужны токены и raw-ответ для артефактов |
| SVG только в JSON-артефакте | SVG сохраняется отдельным файлом для просмотра в браузере |
| Не было в плане | `llm_temperature=0.0` — детерминированный вывод |
| Не было в плане | `llm_timeout=60s` + HTTP 504 при превышении |
| Не было в плане | Подробное логирование каждого шага pipeline |

---

## Критерии готовности — выполнены

- `POST /generate-svg` работает end-to-end: текст → LLM → scene → SVG ✓
- `pytest tests/` — **22/22 зелёных**, 10 skipped (интеграционные) ✓
- Ключ API не хранится в коде — только через `.env` ✓
- Смена модели — одна строка в `.env` ✓
- Retry при schema-ошибках — через `instructor` (max_retries=2) ✓
- Артефакты логируют полный след: запрос, ответ модели, scene, svg ✓
- Интеграционные тесты не запускаются при обычном `pytest` ✓
