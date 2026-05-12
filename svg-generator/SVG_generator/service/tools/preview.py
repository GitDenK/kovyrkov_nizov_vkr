"""
Визуальный просмотр всех golden-тестов.

Запуск из папки service/:
    python3 tools/preview.py

Генерирует SVG-файлы в tests/golden/preview/ и открывает HTML-галерею в браузере.
"""

import json
import sys
import webbrowser
from pathlib import Path

# Добавляем корень сервиса в путь импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.orchestrator.orchestrator import render_scene

GOLDEN_DIR = Path(__file__).parent.parent / "tests" / "golden"
OUT_DIR = GOLDEN_DIR / "preview"
OUT_DIR.mkdir(exist_ok=True)

results: list[dict] = []

for json_file in sorted(GOLDEN_DIR.glob("*.json")):
    data = json.loads(json_file.read_text())
    result = render_scene(data)

    svg_file = OUT_DIR / json_file.with_suffix(".svg").name
    if result.svg:
        svg_file.write_text(result.svg)
        status = "ok"
    else:
        status = "error"

    results.append({
        "name": json_file.name,
        "svg": result.svg or "",
        "warnings": result.warnings,
        "status": status,
    })
    marker = "✓" if status == "ok" else "✗"
    print(f"  {marker} {json_file.name}", "  warnings:", result.warnings or "—")

# Генерируем HTML-галерею
rows = ""
for r in results:
    warn_html = ""
    if r["warnings"]:
        warn_html = f'<p class="warn">⚠ {"; ".join(r["warnings"])}</p>'

    svg_block = r["svg"] if r["svg"] else '<p class="err">SVG не сгенерирован</p>'
    rows += f"""
    <div class="card">
        <h3>{r["name"]}</h3>
        <div class="svg-wrap">{svg_block}</div>
        {warn_html}
    </div>
"""

html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>SVG Preview — Golden Tests</title>
<style>
  body {{ font-family: sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
  h1 {{ margin-bottom: 20px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(440px, 1fr)); gap: 20px; }}
  .card {{ background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.12); }}
  .card h3 {{ margin: 0 0 12px; font-size: 14px; color: #555; }}
  .svg-wrap {{ border: 1px solid #e0e0e0; border-radius: 4px; overflow: hidden; background: white; display: flex; justify-content: center; }}
  .svg-wrap svg {{ max-width: 100%; height: auto; display: block; }}
  .warn {{ color: #b45309; font-size: 12px; margin: 8px 0 0; }}
  .err  {{ color: #dc2626; font-size: 13px; margin: 8px 0 0; }}
</style>
</head>
<body>
<h1>SVG Preview — {len(results)} сцен</h1>
<div class="grid">
{rows}
</div>
</body>
</html>"""

html_path = OUT_DIR / "index.html"
html_path.write_text(html)
print(f"\nГалерея: {html_path}")
webbrowser.open(html_path.as_uri())
