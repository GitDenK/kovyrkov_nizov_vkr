# Тестовый запуск Docker-образа

Инструкция описывает минимальную локальную проверку Docker-образа:
сборку контейнера и запуск пайплайна на небольшой выборке данных.

## 1. Сборка образа

Выполните команду из корня проекта:

```bash
docker build -t vkr-pipeline:latest .
```

Проверить, что образ появился локально:

```bash
docker images vkr-pipeline
```

## 2. Запуск одного конспекта

Для полного прогона пайплайна нужен `TOGETHER_API_KEY`.
Передайте ключ через переменную окружения и сохраните результаты в локальную
папку `output-test`:

```bash
docker run --rm \
  -e TOGETHER_API_KEY="$TOGETHER_API_KEY" \
  -v "$PWD/output-test:/app/output" \
  vkr-pipeline:latest \
  conspect conspects/task4.md --output-dir /app/output
```

После завершения результаты будут доступны на хосте:

```bash
ls output-test
```

## 3. Быстрая проверка без API-ключа

Для smoke-test можно переотрисовать уже сохраненный geometry-план. Такой запуск
не обращается к LLM и не требует `TOGETHER_API_KEY`.

Папка `pipeline/output_geometry_runs/` исключена из Docker-образа через
`.dockerignore`, поэтому план нужно примонтировать отдельно:

```bash
docker run --rm \
  -v "$PWD/output-test:/app/output" \
  -v "$PWD/pipeline/output_geometry_runs/run1/task16_trapezoid_plan.json:/app/test-plan.json:ro" \
  vkr-pipeline:latest \
  geometry-replay \
  --plan /app/test-plan.json \
  --output-dir /app/output \
  --animated
```

Если команда завершилась без ошибки, а в `output-test` появились файлы, образ
собран корректно и пайплайн внутри контейнера запускается.
