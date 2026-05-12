"""
Скрипт запуска экспериментов: тестирование планировщика визуалов
на 4 конспектах ЕГЭ с 3 моделями LLM.
"""

import json
import os
import time
from pathlib import Path

from visual_planner import VisualPlannerEngine, MODELS_TO_COMPARE

API_KEY = os.environ.get("TOGETHER_API_KEY", "")
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

TASK_FILES = ["conspects/task4.md", "conspects/task6.md", "conspects/task8.md", "conspects/task12.md"]


def run_all_experiments(models=None, skip_existing=True):
    all_results = {}
    if models is None:
        models = MODELS_TO_COMPARE

    for model in models:
        model_short = model.split("/")[-1]
        print(f"\n{'#'*70}")
        print(f"# МОДЕЛЬ: {model}")
        print(f"{'#'*70}")

        all_results[model] = {}

        for task_file in TASK_FILES:
            task_name = task_file.replace(".md", "")
            filepath = BASE_DIR / task_file
            out_file = OUTPUT_DIR / f"{model_short}_{task_name}.json"

            if skip_existing and out_file.exists():
                print(f"\n  --- {task_name} --- (cached)")
                with open(out_file, "r") as f:
                    all_results[model][task_name] = json.load(f)
                continue

            print(f"\n  --- {task_name} ---")

            text = filepath.read_text(encoding="utf-8")
            engine = VisualPlannerEngine(api_key=API_KEY, model=model)

            try:
                result = engine.plan_conspect(text, temperature=0.3)
                all_results[model][task_name] = result

                print(f"  Секций: {result['total_sections']}, "
                      f"Визуалов: {result['visuals_planned']}, "
                      f"Время: {result['total_time_sec']}s, "
                      f"Токены: {result['total_tokens_in']}+{result['total_tokens_out']}")

                # Сохраняем промежуточный результат
                out_file = OUTPUT_DIR / f"{model_short}_{task_name}.json"
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"  ОШИБКА: {e}")
                all_results[model][task_name] = {"error": str(e)}

            time.sleep(1)  # rate-limit courtesy

    # Сводный файл
    summary_path = OUTPUT_DIR / "all_results.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n\nВсе результаты сохранены в {summary_path}")

    return all_results


if __name__ == "__main__":
    run_all_experiments()
