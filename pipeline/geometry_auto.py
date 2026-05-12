"""
Автоматическая пошаговая визуализация геометрических задач.

LLM анализирует текст задачи+решения и генерирует:
  1. Координаты всех точек (схематичные, для читаемости чертежа)
  2. Последовательность шагов: текст + объекты/аннотации/constraints для каждого кадра
  3. Canvas-параметры

Исполнитель прогоняет план через StepByStepGeo → SVG → HTML.
"""

import json
import math
import os
import re
import sys
import time
import html as html_mod
import contextlib
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.geometry_renderer import StepByStepGeo

TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
OUTPUT_DIR = ROOT / "pipeline" / "output_geometry"

COLORS = ["#2980b9", "#e74c3c", "#27ae60", "#8e44ad", "#e67e22", "#1abc9c"]


# ═══════════════════════════════════════════════════════════════
# Run-level metrics collection (opt-in via _start_metrics)
# ═══════════════════════════════════════════════════════════════

_metrics: dict | None = None


def _start_metrics(model: str, mode: str = "run") -> dict:
    """Initialize metrics state for a single run. Call at the top of run()/run_from_plan()."""
    global _metrics
    _metrics = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": model,
        "mode": mode,
        "wall_t0": time.perf_counter(),
        "llm_calls": [],
        "phases": {},
        "steps": [],
        "totals": {},
    }
    return _metrics


def _metrics_active() -> bool:
    return _metrics is not None


def _record_llm_call(model: str, role: str, tokens_in: int, tokens_out: int,
                     duration_sec: float, success: bool, attempt: int = 1) -> None:
    if not _metrics_active():
        return
    _metrics["llm_calls"].append({
        "model": model,
        "role": role,
        "attempt": attempt,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "duration_sec": round(duration_sec, 3),
        "success": success,
    })


def _record_phase(name: str, duration_sec: float, **extra) -> None:
    if not _metrics_active():
        return
    bucket = _metrics["phases"].setdefault(
        name, {"count": 0, "total_sec": 0.0, "last_sec": 0.0, "extra": []}
    )
    bucket["count"] += 1
    bucket["total_sec"] = round(bucket["total_sec"] + duration_sec, 4)
    bucket["last_sec"] = round(duration_sec, 4)
    if extra:
        bucket["extra"].append(extra)


@contextlib.contextmanager
def _phase(name: str, **extra):
    """Time a code block and record under the given phase name."""
    if not _metrics_active():
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        _record_phase(name, time.perf_counter() - t0, **extra)


def _record_step(idx: int, duration_sec: float, *,
                 n_objects: int, n_annotations: int, n_constraints: int,
                 has_text: bool) -> None:
    if not _metrics_active():
        return
    _metrics["steps"].append({
        "step_idx": idx,
        "duration_sec": round(duration_sec, 4),
        "n_objects": n_objects,
        "n_annotations": n_annotations,
        "n_constraints": n_constraints,
        "has_text": has_text,
    })


def _finalize_metrics() -> dict | None:
    """Compute totals and return the final metrics dict (does not reset state)."""
    if not _metrics_active():
        return None
    llm = _metrics["llm_calls"]
    successful = [c for c in llm if c["success"]]
    total_llm_in = sum(c["tokens_in"] for c in llm)
    total_llm_out = sum(c["tokens_out"] for c in llm)
    total_llm_sec = sum(c["duration_sec"] for c in llm)
    phases_sec = sum(b["total_sec"] for b in _metrics["phases"].values())
    steps_sec = sum(s["duration_sec"] for s in _metrics["steps"])
    wall_total = time.perf_counter() - _metrics["wall_t0"]
    _metrics["totals"] = {
        "wall_sec": round(wall_total, 3),
        "llm_calls": len(llm),
        "llm_calls_successful": len(successful),
        "llm_tokens_in": total_llm_in,
        "llm_tokens_out": total_llm_out,
        "llm_sec": round(total_llm_sec, 3),
        "phases_sec": round(phases_sec, 4),
        "steps_count": len(_metrics["steps"]),
        "steps_sec": round(steps_sec, 4),
    }
    _metrics.pop("wall_t0", None)
    return _metrics


def _reset_metrics() -> None:
    global _metrics
    _metrics = None

# ═══════════════════════════════════════════════════════════════
# 3D oblique projection
# ═══════════════════════════════════════════════════════════════

def _proj_3d(x, y, z):
    """Oblique cabinet projection: x-left/right, y-depth (into page), z-height."""
    return x - y * 0.4, z + y * 0.2


def _is_3d_plan(points_data: dict) -> bool:
    return any("z" in pt for pt in points_data.values())


def _compute_edge_visibility(points_data: dict, faces: list[list[str]]) -> dict[tuple, bool]:
    """Determine which edges are hidden in the oblique projection.

    Robust to face winding direction — auto-orients normals outward using the centroid.

    Args:
        points_data: dict of point_id -> {x, y, z}
        faces: list of faces, each face is a list of point IDs (winding auto-corrected)

    Returns:
        dict mapping (p1_id, p2_id) -> True if edge is HIDDEN.
        Edge keys are sorted tuples for consistency.
    """
    # View direction for cabinet projection: viewer at y=-inf looking along +y
    view_dir = (0.0, 1.0, 0.0)

    def _get_coords(pid):
        pt = points_data.get(pid, {})
        return (pt.get("x", 0), pt.get("y", 0), pt.get("z", 0))

    def _cross(u, v):
        return (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )

    def _dot(u, v):
        return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]

    def _sub(a, b):
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def _scale(v, s):
        return (v[0] * s, v[1] * s, v[2] * s)

    def _add_vec(a, b):
        return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

    def _edge_key(a, b):
        return tuple(sorted((a, b)))

    # Compute centroid of the entire polyhedron
    all_coords = [_get_coords(pid) for pid in points_data]
    n_pts = len(all_coords)
    if n_pts == 0:
        return {}
    centroid = (
        sum(c[0] for c in all_coords) / n_pts,
        sum(c[1] for c in all_coords) / n_pts,
        sum(c[2] for c in all_coords) / n_pts,
    )

    edge_to_faces: dict[tuple, list[bool]] = {}

    for face in faces:
        if len(face) < 3:
            continue
        coords = [_get_coords(pid) for pid in face]
        v1 = _sub(coords[1], coords[0])
        v2 = _sub(coords[2], coords[0])
        normal = _cross(v1, v2)

        # Auto-orient: ensure normal points AWAY from centroid
        face_center = (
            sum(c[0] for c in coords) / len(coords),
            sum(c[1] for c in coords) / len(coords),
            sum(c[2] for c in coords) / len(coords),
        )
        outward = _sub(face_center, centroid)
        if _dot(normal, outward) < 0:
            normal = _scale(normal, -1)

        # Face is FRONT-facing if its outward normal points AGAINST the view direction
        # (toward the viewer). dot(normal, view_dir) < 0 means normal opposes view.
        is_front = _dot(normal, view_dir) < 0

        for i in range(len(face)):
            edge = _edge_key(face[i], face[(i + 1) % len(face)])
            edge_to_faces.setdefault(edge, []).append(is_front)

    # Edge is hidden if NONE of its adjacent faces are front-facing
    hidden_edges = {}
    for edge, face_visibilities in edge_to_faces.items():
        hidden_edges[edge] = not any(face_visibilities)

    return hidden_edges


def _auto_mark_hidden_edges(plan: dict):
    """If the plan has 3D points and 'faces' field, auto-compute edge visibility."""
    points_data = plan.get("points", {})
    faces = plan.get("faces")

    if not _is_3d_plan(points_data) or not faces:
        return

    hidden_edges = _compute_edge_visibility(points_data, faces)
    if not hidden_edges:
        return

    def _edge_key(a, b):
        return tuple(sorted((a, b)))

    modified = 0
    for step in plan.get("steps", []):
        for obj in step.get("objects", []):
            if obj.get("type") != "segment":
                continue
            fp = obj.get("from_point")
            tp = obj.get("to_point")
            if not fp or not tp:
                continue
            key = _edge_key(fp, tp)
            if key in hidden_edges:
                style = obj.setdefault("style", {})
                if hidden_edges[key] and not style.get("hidden"):
                    style["hidden"] = True
                    modified += 1
                elif not hidden_edges[key] and style.get("hidden"):
                    del style["hidden"]
                    modified += 1

    if modified:
        print(f"  [auto-visibility] Modified {modified} edge(s) visibility")


def _compute_canvas_3d(points_data: dict) -> tuple[dict, dict]:
    """Project all 3D points, scale to ~8-unit span, return (canvas, projected)."""
    raw = {}
    for pid, pt in points_data.items():
        px, py = _proj_3d(pt.get("x", 0), pt.get("y", 0), pt.get("z", 0))
        raw[pid] = (px, py)

    xs = [p[0] for p in raw.values()]
    ys = [p[1] for p in raw.values()]

    x_range = max(xs) - min(xs) or 1.0
    y_range = max(ys) - min(ys) or 1.0
    scale = 8.0 / max(x_range, y_range)
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2

    projected = {}
    for pid, (px, py) in raw.items():
        projected[pid] = (
            round((px - cx) * scale + 6, 2),
            round((py - cy) * scale + 4, 2),
        )

    xs2 = [p[0] for p in projected.values()]
    ys2 = [p[1] for p in projected.values()]
    pad_x = (max(xs2) - min(xs2)) * 0.2 + 0.5
    pad_y = (max(ys2) - min(ys2)) * 0.2 + 0.5

    canvas = {
        "width": 560, "height": 440,
        "x_min": round(min(xs2) - pad_x, 2),
        "x_max": round(max(xs2) + pad_x, 2),
        "y_min": round(min(ys2) - pad_y, 2),
        "y_max": round(max(ys2) + pad_y, 2),
    }
    return canvas, projected


# ═══════════════════════════════════════════════════════════════
# LLM prompt
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = r"""Ты — модуль планирования пошаговых геометрических построений для учебных конспектов ЕГЭ.

Тебе дают задачу с решением. Верни ОДИН JSON (без markdown-обёртки):

{
  "title": "...",
  "canvas": {"width": 560, "height": 380, "x_min": ..., "x_max": ..., "y_min": ..., "y_max": ...},
  "points": {"A": {"x": ..., "y": ..., "label_dx": ..., "label_dy": ...}, ...},
  "steps": [...]
}

## Координаты points
- Схематичные, для читаемости (НЕ обязаны соответствовать длинам).
- label_dx, label_dy — смещение подписи в пикселях (-12..12).
- ВАЖНО: вершины фигуры нумеруются ПОСЛЕДОВАТЕЛЬНО ОБХОДОМ (по/против часовой стрелки).
- Трапеция ABCD с BC∥AD: A и D на НИЖНЕЙ горизонтали (y=0), B и C на ВЕРХНЕЙ (y=5). A.x < D.x, B.x < C.x, B.x > A.x, C.x < D.x.
  КОНКРЕТНЫЙ пример координат: A(1,0), B(3.5,5), C(7.5,5), D(10,0) → AD=9 (низ), BC=4 (верх).
- Треугольник: вершины НЕ на одной прямой. Один из катетов вертикален или горизонтален.
- Вспомогательная точка F при продлении AD: F ПРАВЕЕ D на той же горизонтали. DF=BC.
  Пример: D=(10,0), BC=4, то F=(14,0). AF = AD + DF.

## Типы объектов
- point: {"type":"point","id":"A"} — координаты берутся из points. Стиль: "style":{"fill":"#27ae60","stroke":"#27ae60"}
- segment: {"type":"segment","id":"s_AB","from_point":"A","to_point":"B"} — стиль: "style":{"stroke":"#2980b9","stroke_width":1.8} или {"dash":"dashed"}
  Подписи длин на сторонах: добавь "length_label":"5" для отображения длины по центру отрезка.
- polygon: {"type":"polygon","id":"rect","vertices":["A","B","C","D"]} — произвольный n-угольник. Стиль: "style":{"fill":"rgba(41,128,185,0.08)","stroke":"#2980b9","stroke_width":2}
  Используй для прямоугольников, параллелограммов, ромбов, трапеций, правильных n-угольников.
  Штриховка области: "style":{"fill":"none","hatch":"diagonal","hatch_color":"#2980b9","hatch_opacity":0.3} — типы: "diagonal", "horizontal", "vertical", "cross".
- circle: {"type":"circle","id":"c1","center":"O","radius":2} — окружность
- chord: {"type":"chord","id":"ch1","circle":"c1","from_point":"A","to_point":"B"} — хорда окружности (отрезок между двумя точками на окружности).
- ellipse: {"type":"ellipse","id":"ell","center":"O","rx":3,"ry":1.5,"rotation":0} — эллипс с полуосями rx, ry
- sector: {"type":"sector","id":"sec","center":"O","radius":2,"start_angle":0,"end_angle":90} — закрашенный сектор круга (углы в градусах, против часовой стрелки)
- arc: {"type":"arc","id":"a1","center":"O","radius":2,"start_angle":0,"end_angle":90} — незакрашенная дуга окружности
- cylinder: {"type":"cylinder","id":"cyl","base_center":"O","top_center":"O1","radius":2,"tilt":0.3} — цилиндр (tilt — степень перспективы эллипсов, 0.2..0.4)
- cone: {"type":"cone","id":"cone1","base_center":"O","apex":"S","radius":2,"tilt":0.3} — конус
- sphere: {"type":"sphere","id":"sph1","center":"O","radius":2,"tilt":0.3} — сфера (с экваторным эллипсом)
- cube: {"type":"cube","id":"cube1","origin":"A","size":3} — куб с вершиной в origin и стороной size
- parallelepiped: {"type":"parallelepiped","id":"pp1","origin":"A","a":4,"b":3,"c":2} — параллелепипед с рёбрами a,b,c
- label (ТОЛЬКО в annotations): {"type":"label","id":"lbl_X","text":"BC = 4","anchor":"B","dx":1.0,"dy":0.3,"color":"#333","font_size":12}
  dx/dy — смещение в мировых координатах (0.3..2.0).

## Типы constraints

### Маркеры и декорации (не меняют геометрию, только рисуют)
- right_angle_marker: {"type":"right_angle_marker","id":"ra_1","vertex":"H","ray1":"A","ray2":"C"} — маркер прямого угла. ray1, ray2 — ID точек.
- angle_arc: {"type":"angle_arc","id":"aa_1","vertex":"B","ray1":"A","ray2":"C","radius":20,"color":"#e74c3c","label":"α"} — дуга угла с подписью. radius в пикселях (15-30).
- parallel_lines: {"type":"parallel_lines","id":"par_1","line1":["A","B"],"line2":["C","D"]} — маркер параллельности (стрелочки на линиях).
- equal_segments: {"type":"equal_segments","id":"eq_1","segments":[["A","B"],["C","D"]],"ticks":1} — засечки равных отрезков. ticks=1,2,3 — количество штрихов.

### Построения (solver вычисляет координаты и добавляет объекты)
- midpoint: {"type":"midpoint","id":"mid_AB","segment":"s_AB","result_id":"M"} — середина отрезка s_AB, результат — новая точка M.
- median: {"type":"median","id":"med_A","triangle":"tri_ABC","vertex":"A"} — медиана из вершины A (создаёт середину + отрезок).
- altitude: {"type":"altitude","id":"alt_C","triangle":"tri_ABC","vertex":"C"} — высота из вершины C (создаёт основание + пунктирный отрезок).
- bisector: {"type":"bisector","id":"bis_B","triangle":"tri_ABC","vertex":"B"} — биссектриса из вершины B (создаёт точку на противоположной стороне + отрезок).
- bisector_line: {"type":"bisector_line","id":"bisl_1","vertex":"B","ray1":"A","ray2":"C"} — биссектриса угла для произвольного угла (не обязательно в треугольнике).
- circumscribed_circle: {"type":"circumscribed_circle","id":"cc","triangle":"tri_ABC","center_id":"O"} — описанная окружность треугольника (создаёт центр O + окружность).
- inscribed_circle: {"type":"inscribed_circle","id":"ic","triangle":"tri_ABC","center_id":"I"} — вписанная окружность треугольника (создаёт центр I + окружность).
- midline: {"type":"midline","id":"ml","pairs":[["A","B"],["D","C"]]} — средняя линия: соединяет середины отрезков AB и DC.
- tangent_line: {"type":"tangent_line","id":"tl","circle":"c1","external_point":"P","side":1} — касательная из точки P к окружности c1. side=1 или -1 (верхняя/нижняя).
  Или: {"type":"tangent_line","id":"tl","circle":"c1","touch_point":"T","length":4} — касательная в точке T на окружности.
- cross_section: {"type":"cross_section","id":"cs","vertices":["M","N","P"],"style":{"hatch":"diagonal"}} — сечение (закрашенный многоугольник, опционально со штриховкой).
- perpendicular: {"type":"perpendicular","id":"perp","point":"P","line_point1":"A","line_point2":"B","foot_id":"H"} — перпендикуляр из P на прямую AB.
- intersection: {"type":"intersection","id":"int_1","line1":["A","B"],"line2":["C","D"],"result_id":"P"} — точка пересечения прямых AB и CD (solver вычислит координаты автоматически).

## Правила steps
1. Шаг 1: условие + базовая фигура (все вершины, все стороны, подписи длин).
2. Каждый шаг добавляет ОДНО действие (диагональ, вспомогательная прямая, высота, маркер угла...).
3. Объекты из предыдущих шагов НЕ повторяются.
4. Каждый шаг ОБЯЗАТЕЛЬНО содержит хотя бы 1 объект или 1 аннотацию или 1 constraint.
5. Используй LaTeX: $BC=4$, $$AF^2 = AC^2 + CF^2$$.
6. Используй РАЗНЫЕ цвета: #2980b9, #e74c3c, #27ae60, #8e44ad, #e67e22.
7. Последний шаг: ответ + подпись.
8. Всего 5-7 шагов.
9. Используй constraints для вычисляемой геометрии (altitude, median, perpendicular) — НЕ пытайся вычислить координаты вручную.
10. Для равных отрезков ставь засечки (equal_segments). Для параллельных — маркер (parallel_lines).

## ВАЖНО: визуализация ответа
- Если ответ — длина отрезка (высота, расстояние, медиана): ОБЯЗАТЕЛЬНО НАРИСУЙ этот отрезок как segment или constraint perpendicular/altitude.
  Пример: "Найти высоту" → на последнем шаге добавь constraint perpendicular (или altitude) + подпись значения.
- Если ответ — угол: нарисуй angle_arc с подписью.
- Если ответ — площадь: закрась polygon с hatch.
- НЕ ограничивайся текстовой подписью — итоговая величина ДОЛЖНА быть видна на чертеже как геометрический объект.

## ПОЛНЫЙ ПРИМЕР

Задача: "Прямоугольный треугольник ABC, ∠C=90°, AC=3, BC=4. Найти AB."

{
  "title": "Прямоугольный треугольник 3-4-5",
  "canvas": {"width":560,"height":380,"x_min":-1,"x_max":8,"y_min":-1.5,"y_max":6},
  "points": {
    "A": {"x":0,"y":0,"label_dx":-12,"label_dy":12},
    "B": {"x":4,"y":0,"label_dx":8,"label_dy":12},
    "C": {"x":0,"y":3,"label_dx":-12,"label_dy":-12}
  },
  "steps": [
    {"text":"Дан прямоугольный треугольник $ABC$ с прямым углом при $C$, $AC=3$, $BC=4$.","objects":[{"type":"point","id":"A"},{"type":"point","id":"B"},{"type":"point","id":"C"},{"type":"segment","id":"s_AB","from_point":"A","to_point":"B","style":{"stroke":"#333"}},{"type":"segment","id":"s_AC","from_point":"A","to_point":"C","style":{"stroke":"#2980b9","stroke_width":1.8}},{"type":"segment","id":"s_BC","from_point":"B","to_point":"C","style":{"stroke":"#e74c3c","stroke_width":1.8}}],"annotations":[{"type":"label","id":"lbl_AC","text":"AC = 3","anchor":"A","dx":-0.3,"dy":0.8,"color":"#2980b9","font_size":12},{"type":"label","id":"lbl_BC","text":"BC = 4","anchor":"B","dx":-1.0,"dy":0.8,"color":"#e74c3c","font_size":12}],"constraints":[],"caption":"Треугольник ABC"},
    {"text":"Отметим прямой угол при $C$: $\\angle ACB = 90°$.","objects":[],"annotations":[{"type":"label","id":"lbl_90","text":"90°","anchor":"C","dx":0.3,"dy":-0.5,"color":"#e74c3c","font_size":13}],"constraints":[{"type":"right_angle_marker","id":"ra_C","vertex":"C","ray1":"A","ray2":"B"}],"caption":"∠C = 90°"},
    {"text":"По теореме Пифагора:\n$$AB^2 = AC^2 + BC^2 = 9 + 16 = 25$$\n$$AB = 5$$","objects":[],"annotations":[{"type":"label","id":"lbl_AB","text":"AB = 5","anchor":"A","dx":1.5,"dy":-0.3,"color":"#8e44ad","font_size":14}],"constraints":[],"caption":"Ответ: AB = 5"}
  ]
}

## 3D СТЕРЕОМЕТРИЯ (пирамиды, призмы, параллелепипеды)

Если задача по стереометрии — используй 3D-координаты (добавь ключ "z"):
"A": {"x":0, "y":3.46, "z":0, "label_dx":-12, "label_dy":12}

Правила 3D:
- Основание фигуры в z=0, верхние вершины при z>0.
- ПРАВИЛЬНЫЙ ТРЕУГОЛЬНИК (сторона ≈6): КОНКРЕТНЫЕ координаты:
  A=(0, 3.46, 0), B=(-3, -1.73, 0), C=(3, -1.73, 0). Центр O=(0, 0, 0).
  Середина BC: M=(0, -1.73, 0). ВАЖНО: у A, B, C — РАЗНЫЕ x И y!
- ПРАВИЛЬНЫЙ ШЕСТИУГОЛЬНИК (сторона 1): КОНКРЕТНЫЕ координаты:
  A=(1,0,0), B=(0.5,0.866,0), C=(-0.5,0.866,0), D=(-1,0,0), E=(-0.5,-0.866,0), F=(0.5,-0.866,0).
- Призма высоты h: верхние = нижние, но z=h. Имена: A1, B1, C1,...
- Пирамида: вершина S = (0, 0, h) над центром основания.
- Canvas НЕ указывай для 3D — он вычисляется автоматически.
- Вспомогательные точки (середины, проекции, ноги высот) — задавай с ВЫЧИСЛЕННЫМИ координатами.
  Пример: H — нога перпендикуляра от A на SM. Вычисли координаты H, НЕ ставь H = A!
- FACES (обязательно для 3D): перечисли все грани тела в поле "faces" (массив массивов ID вершин,
  обход вершин ПРОТИВ часовой стрелки при виде СНАРУЖИ тела):
  "faces": [["A","B","C"], ["S","A","B"], ["S","B","C"], ["S","C","A"]]
  Видимость рёбер (скрытые/пунктирные) вычисляется АВТОМАТИЧЕСКИ на основе faces.
  НЕ нужно вручную ставить "hidden":true — система сама определит.

## ПОЛНЫЙ 3D ПРИМЕР

Задача: "Правильная треугольная пирамида SABC, SO=3. Найти SM (S→середина BC)."

{"title":"Пирамида SABC","points":{"A":{"x":0,"y":3.46,"z":0,"label_dx":-12,"label_dy":10},"B":{"x":-3,"y":-1.73,"z":0,"label_dx":-14,"label_dy":8},"C":{"x":3,"y":-1.73,"z":0,"label_dx":10,"label_dy":8},"S":{"x":0,"y":0,"z":3,"label_dx":8,"label_dy":-12},"O":{"x":0,"y":0,"z":0,"label_dx":8,"label_dy":10},"M":{"x":0,"y":-1.73,"z":0,"label_dx":8,"label_dy":12}},"faces":[["A","B","C"],["S","B","A"],["S","C","B"],["S","A","C"]],"steps":[{"text":"Правильная треугольная пирамида $SABC$.","objects":[{"type":"point","id":"A"},{"type":"point","id":"B"},{"type":"point","id":"C"},{"type":"point","id":"S"},{"type":"segment","id":"s_AB","from_point":"A","to_point":"B"},{"type":"segment","id":"s_BC","from_point":"B","to_point":"C"},{"type":"segment","id":"s_CA","from_point":"C","to_point":"A"},{"type":"segment","id":"s_SA","from_point":"S","to_point":"A"},{"type":"segment","id":"s_SB","from_point":"S","to_point":"B"},{"type":"segment","id":"s_SC","from_point":"S","to_point":"C"}],"annotations":[],"constraints":[],"caption":"Пирамида SABC"},{"text":"Высота $SO=3$, $O$ — центр основания.","objects":[{"type":"point","id":"O","style":{"fill":"#e74c3c","stroke":"#e74c3c"}},{"type":"segment","id":"s_SO","from_point":"S","to_point":"O","style":{"stroke":"#e74c3c","dash":"dashed"}}],"annotations":[{"type":"label","id":"lbl_SO","text":"SO=3","anchor":"S","dx":0.4,"dy":-0.4,"color":"#e74c3c","font_size":12}],"constraints":[],"caption":"Высота SO=3"},{"text":"$M$ — середина $BC$. $SM = \\sqrt{SO^2+OM^2}=\\sqrt{9+3}=2\\sqrt{3}$.","objects":[{"type":"point","id":"M","style":{"fill":"#27ae60","stroke":"#27ae60"}},{"type":"segment","id":"s_SM","from_point":"S","to_point":"M","style":{"stroke":"#27ae60","stroke_width":2}}],"annotations":[{"type":"label","id":"lbl_SM","text":"SM=2√3","anchor":"M","dx":0.5,"dy":0.3,"color":"#27ae60","font_size":13}],"constraints":[],"caption":"Ответ: SM=2√3"}]}

Верни ТОЛЬКО JSON.
"""


# ═══════════════════════════════════════════════════════════════
# LLM call with retry
# ═══════════════════════════════════════════════════════════════

def _call_llm(api_key: str, model: str, system: str, user: str,
              temperature: float = 0.3, max_tokens: int = 4096,
              retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            resp = requests.post(
                TOGETHER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage", {})
            return {
                "raw": raw,
                "tokens_in": usage.get("prompt_tokens", 0),
                "tokens_out": usage.get("completion_tokens", 0),
            }
        except requests.exceptions.HTTPError as e:
            if attempt < retries - 1 and resp.status_code >= 500:
                wait = 2 ** (attempt + 1)
                print(f"  HTTP error {e}, retry in {wait}s...")
                time.sleep(wait)
            else:
                try:
                    err_body = resp.json()
                except Exception:
                    err_body = resp.text[:300]
                print(f"  HTTP {resp.status_code}: {err_body}")
                raise


def _fix_latex_escapes(text: str) -> str:
    """Fix unescaped LaTeX backslashes that break JSON parsing."""
    latex_cmds = (
        r'\\parallel', r'\\perp', r'\\angle', r'\\triangle', r'\\square',
        r'\\frac', r'\\cdot', r'\\times', r'\\div', r'\\pm', r'\\mp',
        r'\\leq', r'\\geq', r'\\neq', r'\\approx', r'\\sim',
        r'\\sqrt', r'\\sum', r'\\prod', r'\\int', r'\\infty',
        r'\\alpha', r'\\beta', r'\\gamma', r'\\delta', r'\\theta',
        r'\\pi', r'\\sigma', r'\\phi', r'\\psi', r'\\omega',
        r'\\quad', r'\\qquad', r'\\text', r'\\mathrm', r'\\mathbf',
        r'\\left', r'\\right', r'\\big', r'\\Big',
        r'\\overline', r'\\underline', r'\\hat', r'\\vec',
        r'\\boxed', r'\\dfrac', r'\\tfrac',
        r'\\blacksquare', r'\\circ', r'\\bullet',
        # Trigonometric, logarithmic and other named operators commonly
        # produced inside step-by-step solutions.
        r'\\cos', r'\\sin', r'\\tan', r'\\cot', r'\\sec', r'\\csc',
        r'\\arccos', r'\\arcsin', r'\\arctan',
        r'\\log', r'\\ln', r'\\lg', r'\\exp',
        r'\\min', r'\\max', r'\\lim', r'\\inf', r'\\sup',
        r'\\det', r'\\dim', r'\\deg', r'\\bmod',
        r'\\to', r'\\rightarrow', r'\\leftarrow', r'\\Rightarrow',
        r'\\Leftarrow', r'\\Leftrightarrow', r'\\mapsto',
        r'\\lambda', r'\\mu', r'\\nu', r'\\xi', r'\\eta', r'\\zeta',
        r'\\rho', r'\\tau', r'\\chi', r'\\epsilon', r'\\varepsilon',
        r'\\Delta', r'\\Sigma', r'\\Pi', r'\\Omega', r'\\Phi', r'\\Psi',
        r'\\partial', r'\\nabla',
        r'\\cup', r'\\cap', r'\\subset', r'\\supset', r'\\in', r'\\notin',
        r'\\forall', r'\\exists',
    )
    for cmd in latex_cmds:
        single = cmd[1:]  # e.g. \parallel
        double = cmd       # e.g. \\parallel
        text = text.replace(single, double)
    # Fix double-escaping that might result from above
    for cmd in latex_cmds:
        triple = '\\' + cmd  # e.g. \\\parallel
        double = cmd          # e.g. \\parallel
        text = text.replace(triple, double)
    return text


def _sanitize_json_values(text: str) -> str:
    """Fix common LLM JSON errors: invalid values like ![-1,0], NaN, etc."""
    # Replace "key": ![...] with "key": 0
    text = re.sub(r':\s*!\[.*?\]', ': 0', text)
    # Replace "key": NaN/Infinity
    text = re.sub(r':\s*NaN\b', ': 0', text)
    text = re.sub(r':\s*Infinity\b', ': 999', text)
    text = re.sub(r':\s*-Infinity\b', ': -999', text)
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _extract_json(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())

    for attempt_text in [text, _fix_latex_escapes(text),
                         _sanitize_json_values(text),
                         _sanitize_json_values(_fix_latex_escapes(text))]:
        try:
            return json.loads(attempt_text)
        except json.JSONDecodeError:
            pass
        match = re.search(r'\{[\s\S]*\}', attempt_text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    # Try to repair truncated JSON
    for attempt_text in [text, _fix_latex_escapes(text)]:
        match = re.search(r'\{[\s\S]*', attempt_text)
        if match:
            candidate = _try_repair_json(match.group())
            if candidate:
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    pass
    return None


def _try_repair_json(text: str) -> str | None:
    """Attempt to close truncated JSON by balancing brackets."""
    # Remove trailing incomplete key-value pairs
    text = re.sub(r',\s*"[^"]*"?\s*:?\s*"?[^"]*$', '', text)
    text = re.sub(r',\s*\{[^}]*$', '', text)
    text = re.sub(r',\s*\[[^\]]*$', '', text)

    opens = 0
    sq_opens = 0
    for ch in text:
        if ch == '{':
            opens += 1
        elif ch == '}':
            opens -= 1
        elif ch == '[':
            sq_opens += 1
        elif ch == ']':
            sq_opens -= 1

    text += ']' * max(0, sq_opens)
    text += '}' * max(0, opens)
    return text


def _extract_json_array(text: str) -> list | None:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    return None


def _compute_canvas_2d(points_data: dict) -> dict:
    """Compute optimal canvas bounds from 2D point coordinates with padding."""
    if not points_data:
        return {"width": 560, "height": 380,
                "x_min": -1, "x_max": 14, "y_min": -2, "y_max": 8}

    xs = [pt.get("x", 0) for pt in points_data.values()]
    ys = [pt.get("y", 0) for pt in points_data.values()]

    x_min_raw, x_max_raw = min(xs), max(xs)
    y_min_raw, y_max_raw = min(ys), max(ys)

    x_range = x_max_raw - x_min_raw or 1.0
    y_range = y_max_raw - y_min_raw or 1.0

    # Add ~20% padding on each side, minimum 1.0
    pad_x = max(x_range * 0.2, 1.0)
    pad_y = max(y_range * 0.2, 1.0)

    return {
        "width": 560, "height": 380,
        "x_min": round(x_min_raw - pad_x, 1),
        "x_max": round(x_max_raw + pad_x, 1),
        "y_min": round(y_min_raw - pad_y, 1),
        "y_max": round(y_max_raw + pad_y, 1),
    }


def _ensure_canvas_2d(plan: dict):
    """Ensure plan has a reasonable canvas; recompute from points if LLM canvas is bad."""
    points_data = plan.get("points", {})
    llm_canvas = plan.get("canvas")

    if not llm_canvas or not points_data:
        plan["canvas"] = _compute_canvas_2d(points_data)
        return

    # Validate LLM canvas: all points should fit inside with some margin
    xs = [pt.get("x", 0) for pt in points_data.values()]
    ys = [pt.get("y", 0) for pt in points_data.values()]

    x_min_pt, x_max_pt = min(xs), max(xs)
    y_min_pt, y_max_pt = min(ys), max(ys)

    c_xmin = llm_canvas.get("x_min", -1)
    c_xmax = llm_canvas.get("x_max", 14)
    c_ymin = llm_canvas.get("y_min", -2)
    c_ymax = llm_canvas.get("y_max", 8)

    # Check if points are clipped or canvas is way too large
    points_clipped = (x_min_pt < c_xmin or x_max_pt > c_xmax or
                      y_min_pt < c_ymin or y_max_pt > c_ymax)
    x_range = c_xmax - c_xmin
    y_range = c_ymax - c_ymin
    pt_x_range = x_max_pt - x_min_pt or 1
    pt_y_range = y_max_pt - y_min_pt or 1
    canvas_too_large = (x_range > pt_x_range * 5) or (y_range > pt_y_range * 5)

    if points_clipped or canvas_too_large:
        auto_canvas = _compute_canvas_2d(points_data)
        auto_canvas["width"] = llm_canvas.get("width", 560)
        auto_canvas["height"] = llm_canvas.get("height", 380)
        plan["canvas"] = auto_canvas
        print(f"  [auto-canvas] Recomputed: x=[{auto_canvas['x_min']:.1f}..{auto_canvas['x_max']:.1f}] "
              f"y=[{auto_canvas['y_min']:.1f}..{auto_canvas['y_max']:.1f}] "
              f"({'clipped' if points_clipped else 'oversized'})")


# ═══════════════════════════════════════════════════════════════
# Answer-visualization post-condition (soft, advisory)
#
# Checks that the generated plan visualizes the answer to the problem
# as an actual geometric object (segment with length, angle arc, hatched
# polygon, etc.), not as a free-floating caption. The check is heuristic
# and emits warnings only; it does not block the pipeline.
# ═══════════════════════════════════════════════════════════════

# Mapping: regex over the problem text => expected answer type.
# Order is significant: more specific patterns must come before generic ones,
# because the same problem can match multiple types and we want all of them.
_ANSWER_PATTERN_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("height", (
        r"\bнайди(?:те)?\s+высот[уы]",
        r"\bвысот[уаы]\s+(?:трапеции|треугольника|пирамиды|призмы)",
    )),
    ("distance", (
        r"\bнайди(?:те)?\s+расстояни[ея]",
        r"\bрасстояни[ея]\s+от\s+\w+\s+до",
    )),
    ("perimeter", (
        r"\bнайди(?:те)?\s+периметр",
    )),
    ("radius", (
        r"\bнайди(?:те)?\s+радиус",
        r"\bдиаметр\s+(?:окружности|круга)",
    )),
    ("area", (
        r"\bнайди(?:те)?\s+площад[ьи]",
        r"\bплощад[ьи]\s+(?:сечения|треугольника|четырёхугольника|трапеции)",
    )),
    ("volume", (
        r"\bнайди(?:те)?\s+объ[её]м",
    )),
    ("angle", (
        r"\bнайди(?:те)?\s+(?:величину\s+)?(?:двугранн\w+\s+)?угол",
        r"\bдвугранн\w+\s+угол",
    )),
    ("length", (
        r"\bнайди(?:те)?\s+(?:длину|сторону|медиану|апофему|диагональ)",
        r"\bдлин[уы]\s+(?:отрезка|медианы|апофемы|диагонали)",
    )),
    ("proof", (
        r"\bдокажите\b",
        r"\bдоказать\b",
        r"\bдоказательство\b",
    )),
    ("construction", (
        r"\bпострой(?:те)?\b",
    )),
)


def _detect_answer_types(problem_text: str) -> list[str]:
    """Return the list of answer types implied by the problem statement."""
    if not problem_text:
        return []
    text_lower = problem_text.lower()
    detected: list[str] = []
    for ans_type, patterns in _ANSWER_PATTERN_GROUPS:
        for p in patterns:
            if re.search(p, text_lower, flags=re.IGNORECASE | re.UNICODE):
                detected.append(ans_type)
                break
    return detected


def _has_segment_with_length_label(plan: dict) -> bool:
    """True if at least one segment carries a length label, either as the
    segment's own ``length_label`` field or as a textual annotation of the
    form ``X = <number>`` placed alongside any geometric object. Annotations
    are accepted because the LLM often factors length labels into a separate
    annotation block rather than the segment's inline field."""
    for step in plan.get("steps", []) or []:
        for obj in step.get("objects", []) or []:
            if obj.get("type") == "segment" and \
                    str(obj.get("length_label", "")).strip():
                return True
        for ann in step.get("annotations", []) or []:
            if ann.get("type") != "label":
                continue
            text = str(ann.get("text", "") or "")
            if re.search(r"[A-Za-zА-Яа-я]\w*\s*=\s*-?\d", text):
                return True
    return False


def _has_perpendicular_or_right_angle(plan: dict) -> bool:
    for step in plan.get("steps", []) or []:
        for con in step.get("constraints", []) or []:
            if con.get("type") in ("perpendicular", "right_angle_marker"):
                return True
    return False


def _has_angle_marker(plan: dict) -> bool:
    for step in plan.get("steps", []) or []:
        for con in step.get("constraints", []) or []:
            if con.get("type") in ("angle_arc", "right_angle_marker"):
                return True
    return False


def _has_hatched_polygon(plan: dict) -> bool:
    """Detect any polygon with a fill / hatch pattern in style."""
    for step in plan.get("steps", []) or []:
        for obj in step.get("objects", []) or []:
            if obj.get("type") != "polygon":
                continue
            style = obj.get("style", {}) or {}
            if obj.get("hatched") or obj.get("fill"):
                return True
            if any(k in style for k in ("hatch", "hatched", "fill",
                                         "fill_opacity", "pattern")):
                # An empty fill of "none" or "transparent" does not count.
                fill_val = style.get("fill")
                if fill_val and fill_val not in ("none", "transparent"):
                    return True
                if style.get("hatch") or style.get("hatched") or \
                        style.get("pattern"):
                    return True
    return False


def _has_circle(plan: dict) -> bool:
    for step in plan.get("steps", []) or []:
        for obj in step.get("objects", []) or []:
            if obj.get("type") == "circle":
                return True
        for con in step.get("constraints", []) or []:
            if con.get("type") in ("circumscribed_circle",
                                    "inscribed_circle"):
                return True
    return False


_ANSWER_VALUE_RE = re.compile(
    r"(?<![A-Za-zА-Яа-я0-9_])"           # left boundary, not letter/digit
    r"([A-Za-zА-Яа-я][A-Za-zА-Яа-я0-9_]*)"  # variable name (e.g. h, AC, S)
    r"\s*=\s*"
    r"(-?\d+(?:[.,]\d+)?)"               # numeric value, allow comma
)


def _extract_answer_value_from_plan(plan: dict) -> tuple[str, str] | None:
    """Look at the last meaningful step caption / text and try to find
    a pattern like 'h = 2.5' or 'AC = 8'. Return (var_name, value) or None.
    Skip caption strings that are clearly given quantities (anything that
    appears in step 1 captions is treated as given, not as the answer)."""
    steps = plan.get("steps", []) or []
    if not steps:
        return None
    given_values: set[str] = set()
    if len(steps) > 1:
        first_caption = ((steps[0].get("caption", "") or "") + " " +
                         (steps[0].get("text", "") or "")).strip()
        for m in _ANSWER_VALUE_RE.finditer(first_caption):
            given_values.add(m.group(2).replace(",", "."))

    for step in reversed(steps):
        text = ((step.get("caption", "") or "") + " " +
                (step.get("text", "") or "")).strip()
        if not text:
            continue
        # Prefer captions that explicitly say "Ответ".
        ans_match = re.search(r"\bответ[а-яА-Я]*\s*[:=]?\s*([^\n]+)",
                              text, flags=re.IGNORECASE)
        candidates = []
        if ans_match:
            candidates.append(ans_match.group(1))
        candidates.append(text)
        for cand in candidates:
            for m in _ANSWER_VALUE_RE.finditer(cand):
                value = m.group(2).replace(",", ".")
                if value in given_values:
                    continue
                return (m.group(1), value)
    return None


def _plan_has_label_value(plan: dict, value: str) -> bool:
    """True if any segment.length_label or annotation.text contains `value`."""
    norm = value.lstrip("-")
    for step in plan.get("steps", []) or []:
        for obj in step.get("objects", []) or []:
            if obj.get("type") == "segment":
                lbl = str(obj.get("length_label", "") or "")
                if norm and norm in lbl:
                    return True
        for ann in step.get("annotations", []) or []:
            txt = str(ann.get("text", "") or "")
            if norm and norm in txt:
                return True
    return False


def _validate_answer_visualization(plan: dict,
                                   problem_text: str) -> list[str]:
    """Soft post-condition validator. Returns a list of advisory warnings.
    Does not raise; does not modify the plan."""
    if not problem_text:
        return []
    expected = _detect_answer_types(problem_text)
    if not expected:
        return []
    if expected == ["proof"] or expected == ["construction"] or \
            expected == ["proof", "construction"] or \
            expected == ["construction", "proof"]:
        return []

    warnings: list[str] = []
    has_length = _has_segment_with_length_label(plan)
    has_perp = _has_perpendicular_or_right_angle(plan)
    has_angle = _has_angle_marker(plan)
    has_hatch = _has_hatched_polygon(plan)
    has_circle = _has_circle(plan)

    if any(t in expected for t in ("length", "height", "distance",
                                    "radius", "perimeter")) \
            and not has_length:
        warnings.append(
            "answer-vis: problem asks for a length-like quantity, but no "
            "segment with a non-empty length_label was found in the plan"
        )
    if "height" in expected and not has_perp:
        warnings.append(
            "answer-vis: problem asks for a height, but no perpendicular "
            "or right_angle_marker was found in the plan"
        )
    if "distance" in expected and not has_perp:
        warnings.append(
            "answer-vis: problem asks for a distance, but no perpendicular "
            "or right_angle_marker was found in the plan"
        )
    if "angle" in expected and not has_angle:
        warnings.append(
            "answer-vis: problem asks for an angle, but no angle_arc or "
            "right_angle_marker was found in the plan"
        )
    if "area" in expected and not has_hatch:
        warnings.append(
            "answer-vis: problem asks for an area, but no hatched/filled "
            "polygon was found in the plan"
        )
    if "radius" in expected and not has_circle:
        warnings.append(
            "answer-vis: problem asks for a radius, but no circle was "
            "found in the plan"
        )

    # If we managed to extract an answer value (e.g. h = 2.5 from the last
    # step caption), check it actually appears as a label somewhere.
    extracted = _extract_answer_value_from_plan(plan)
    if extracted is not None:
        var_name, value = extracted
        # Only emit this warning when a length-like answer is expected.
        if any(t in expected for t in ("length", "height", "distance",
                                        "radius", "perimeter")) and \
                not _plan_has_label_value(plan, value):
            warnings.append(
                f"answer-vis: solution claims {var_name} = {value} but no "
                f"segment label or annotation contains this value"
            )

    return warnings


# ═══════════════════════════════════════════════════════════════
# Planner: problem text → step-by-step JSON plan
# ═══════════════════════════════════════════════════════════════

def plan_geometry_steps(problem_text: str, api_key: str = None,
                        model: str = DEFAULT_MODEL,
                        max_retries: int = 2,
                        enforce_answer_vis: bool = True,
                        max_answer_vis_retries: int = 1) -> dict:
    """Planning with validation + retry: LLM generates plan, validator finds errors,
    errors are sent back for correction (up to max_retries times).

    If `enforce_answer_vis` is True, additionally runs the answer-visualization
    post-condition validator and, if it emits warnings, asks the LLM to revise
    the plan up to `max_answer_vis_retries` times. The fix is accepted only if
    the new plan still passes the structural validator and produces strictly
    fewer answer-vis warnings than the previous one; otherwise the previous
    plan is kept.
    """
    api_key = api_key or os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        raise RuntimeError("TOGETHER_API_KEY not set")

    user_msg = f"""Вот геометрическая задача с решением. Сгенерируй полный JSON-план пошаговой визуализации.

{problem_text}

ПОДСКАЗКИ:
- ПЛАНИМЕТРИЯ (2D): основания фигуры горизонтальны на РАЗНОЙ высоте. Если BC и AD — основания трапеции, то B и C вверху (y=5), A и D внизу (y=0).
- СТЕРЕОМЕТРИЯ (3D): используй 3D-координаты (x, y, z). Основание в z=0. НЕ указывай canvas. Скрытые рёбра: "hidden":true.
  ВАЖНО: вершины основания должны иметь РАЗНЫЕ x И y, НЕ лежать на одной прямой!
  Правильный треугольник: A=(0,3.46,0), B=(-3,-1.73,0), C=(3,-1.73,0).
  Вспомогательные точки (H, M, O и т.д.) — ВЫЧИСЛИ координаты, не копируй из других точек!

Верни ТОЛЬКО JSON (без текста до/после)."""

    plan = _request_and_parse_plan(api_key, model, SYSTEM_PROMPT, user_msg,
                                   role="plan")

    plan.setdefault("title", "Геометрическая задача")
    if not _is_3d_plan(plan.get("points", {})):
        with _phase("ensure_canvas_2d"):
            _ensure_canvas_2d(plan)
    with _phase("postprocess_plan"):
        _postprocess_plan(plan)
    with _phase("validate_plan"):
        warnings = _validate_plan(plan)
    _record_phase("validation_round", 0.0,
                  round_idx=0, warnings=len(warnings))

    # Retry loop: send validation errors back to LLM for correction
    for retry in range(max_retries):
        if not warnings:
            break
        print(f"[geometry_auto] Retry {retry + 1}/{max_retries}: "
              f"{len(warnings)} validation issues found, requesting fix...")

        fix_msg = _build_fix_request(plan, warnings)
        try:
            plan = _request_and_parse_plan(api_key, model, SYSTEM_PROMPT, fix_msg,
                                           role="fix")
            plan.setdefault("title", "Геометрическая задача")
            if not _is_3d_plan(plan.get("points", {})):
                with _phase("ensure_canvas_2d"):
                    _ensure_canvas_2d(plan)
            with _phase("postprocess_plan"):
                _postprocess_plan(plan)
            with _phase("validate_plan"):
                warnings = _validate_plan(plan)
            _record_phase("validation_round", 0.0,
                          round_idx=retry + 1, warnings=len(warnings))
        except (ValueError, AssertionError) as e:
            print(f"  Retry {retry + 1} failed: {e}. Keeping previous plan.")
            break

    if warnings:
        print(f"[geometry_auto] Final plan has {len(warnings)} warnings (proceeding anyway)")
    else:
        print(f"[geometry_auto] Plan validated successfully")

    expected_types = _detect_answer_types(problem_text)
    with _phase("validate_answer_vis"):
        answer_warnings = _validate_answer_visualization(plan, problem_text)
    _record_phase("answer_vis_check", 0.0,
                  round_idx=0,
                  warnings=len(answer_warnings),
                  expected_types=expected_types)
    if answer_warnings:
        print(f"[geometry_auto] Answer-vis post-condition: "
              f"{len(answer_warnings)} issue(s) detected")
        for w in answer_warnings:
            print(f"  - {w}")

    if enforce_answer_vis and answer_warnings and expected_types:
        prev_warnings = list(answer_warnings)
        prev_plan = plan
        for av_retry in range(max_answer_vis_retries):
            print(f"[geometry_auto] Answer-vis retry "
                  f"{av_retry + 1}/{max_answer_vis_retries}: "
                  f"{len(prev_warnings)} pedagogical issue(s), "
                  f"requesting fix...")
            fix_msg = _build_answer_vis_fix_request(
                prev_plan, problem_text, prev_warnings, expected_types
            )
            try:
                candidate = _request_and_parse_plan(
                    api_key, model, SYSTEM_PROMPT, fix_msg, role="fix"
                )
            except (ValueError, AssertionError) as e:
                print(f"  Answer-vis retry {av_retry + 1} failed to parse: {e}."
                      f" Keeping previous plan.")
                _record_phase("answer_vis_fix_round", 0.0,
                              round_idx=av_retry + 1,
                              accepted=False,
                              reason="parse_error")
                break

            candidate.setdefault("title", "Геометрическая задача")
            if not _is_3d_plan(candidate.get("points", {})):
                with _phase("ensure_canvas_2d"):
                    _ensure_canvas_2d(candidate)
            with _phase("postprocess_plan"):
                _postprocess_plan(candidate)
            with _phase("validate_plan"):
                cand_warnings = _validate_plan(candidate)
            with _phase("validate_answer_vis"):
                cand_answer_warnings = _validate_answer_visualization(
                    candidate, problem_text
                )

            cand_n = len(cand_answer_warnings)
            prev_n = len(prev_warnings)
            structural_ok = not cand_warnings
            improved = cand_n < prev_n
            accepted = structural_ok and improved
            reason = (
                "accepted_improvement" if accepted
                else "structural_regression" if not structural_ok
                else "no_improvement"
            )
            _record_phase("answer_vis_fix_round", 0.0,
                          round_idx=av_retry + 1,
                          accepted=accepted,
                          prev_warnings=prev_n,
                          new_warnings=cand_n,
                          structural_warnings=len(cand_warnings),
                          reason=reason)
            if accepted:
                print(f"  Accepted: answer-vis warnings {prev_n} -> {cand_n}")
                prev_plan = candidate
                prev_warnings = cand_answer_warnings
                if cand_n == 0:
                    break
            else:
                print(f"  Rejected ({reason}); answer-vis "
                      f"{prev_n} -> {cand_n}, struct={len(cand_warnings)}.")
                break

        plan = prev_plan
        answer_warnings = prev_warnings
        _record_phase("answer_vis_check", 0.0,
                      round_idx=99,  # final
                      warnings=len(answer_warnings),
                      expected_types=expected_types)

    return plan


def _request_and_parse_plan(api_key: str, model: str,
                            system: str, user_msg: str,
                            role: str = "plan") -> dict:
    """Call LLM and parse the response into a plan dict."""
    print(f"[geometry_auto] Planning ({model})...")
    n_prior = sum(1 for c in (_metrics["llm_calls"] if _metrics_active() else [])
                  if c.get("role") == role)
    t0 = time.perf_counter()
    success = False
    result = None
    try:
        result = _call_llm(api_key, model, system, user_msg,
                           temperature=0.2, max_tokens=8192)
        success = True
    finally:
        elapsed = time.perf_counter() - t0
        _record_llm_call(
            model=model, role=role,
            tokens_in=(result or {}).get("tokens_in", 0),
            tokens_out=(result or {}).get("tokens_out", 0),
            duration_sec=elapsed, success=success,
            attempt=n_prior + 1,
        )
    print(f"  Done in {elapsed:.1f}s ({result['tokens_in']}+{result['tokens_out']} tok)")

    raw = result["raw"]
    print(f"  Raw length: {len(raw)} chars")
    with _phase("extract_json", chars=len(raw)):
        plan = _extract_json(raw)
    if not plan or "points" not in plan or "steps" not in plan:
        debug_path = OUTPUT_DIR / "debug_raw.txt"
        debug_path.write_text(raw, encoding="utf-8")
        print(f"  Full raw saved to: {debug_path}")
        raise ValueError("LLM returned invalid plan (no points or steps)")
    return plan


def _build_fix_request(plan: dict, warnings: list[str]) -> str:
    """Build a message asking LLM to fix the plan based on validation errors."""
    plan_json = json.dumps(plan, ensure_ascii=False, indent=2)
    warnings_text = "\n".join(f"  - {w}" for w in warnings)

    return f"""Ты сгенерировал план, но в нём обнаружены ошибки валидации:

{warnings_text}

Исходный план (с ошибками):
```json
{plan_json}
```

ИСПРАВЬ план:
1. Каждая точка, используемая в objects/constraints, ДОЛЖНА быть определена в "points" с координатами.
2. Если constraint ссылается на точку — эта точка должна существовать.
3. Все вершины polygon ДОЛЖНЫ быть в "points".
4. Для constraints типа altitude/median/bisector — triangle должен быть определён как объект.

Верни ИСПРАВЛЕННЫЙ полный JSON (без текста до/после)."""


def _build_answer_vis_fix_request(plan: dict, problem_text: str,
                                  answer_warnings: list[str],
                                  expected_types: list[str]) -> str:
    """Build a message asking the LLM to fix the plan so that the problem's
    answer is visually represented (height shown as a perpendicular segment,
    distance as a labelled segment, area as a hatched polygon, etc.).
    """
    plan_json = json.dumps(plan, ensure_ascii=False, indent=2)
    warnings_text = "\n".join(f"  - {w}" for w in answer_warnings)
    types_text = ", ".join(expected_types) if expected_types else "—"

    hints: list[str] = []
    if "height" in expected_types or "distance" in expected_types:
        hints.append(
            "Высота / расстояние от точки до прямой или плоскости должны "
            "быть показаны как ОТДЕЛЬНЫЙ ОТРЕЗОК с constraint "
            "perpendicular (или altitude в треугольнике) и подписью длины "
            "(length_label) либо аннотацией вида 'h = <число>'."
        )
    if "area" in expected_types:
        hints.append(
            "Искомая площадь должна быть выделена штриховкой (hatched=true) "
            "у соответствующего полигона; готовая числовая величина — "
            "подписана аннотацией 'S = <число>'."
        )
    if "angle" in expected_types:
        hints.append(
            "Искомый угол должен быть отмечен дугой (constraint angle с "
            "label) и сопровождён аннотацией со значением, либо явно "
            "обозначен как двугранный/линейный."
        )
    if "perimeter" in expected_types or "length" in expected_types:
        hints.append(
            "Искомая длина / периметр должны иметь подпись на ребре "
            "(length_label) или аннотацию 'P = <число>' / '<имя> = <число>'."
        )
    if "radius" in expected_types:
        hints.append(
            "Радиус должен быть показан отрезком из центра окружности и "
            "иметь подпись длины."
        )
    if "volume" in expected_types:
        hints.append(
            "Объём чаще всего невозможно показать геометрически, но "
            "соответствующее тело должно быть визуализировано (как 3D-фигура "
            "или сечение), а число — приведено в аннотации."
        )
    hints_text = "\n".join(f"  * {h}" for h in hints) or "  * —"

    return f"""Ты сгенерировал план, но визуализация не показывает ответ задачи.

Условие задачи:
{problem_text}

Ожидаемые типы ответа (по разбору формулировки): {types_text}.

Найденные пробелы:
{warnings_text}

Что нужно учесть:
{hints_text}

Текущий план:
```json
{plan_json}
```

ИСПРАВЬ план так, чтобы ответ задачи был ВИДЕН геометрически (а не только в подписях шагов). Сохрани все корректно работающие точки/объекты/шаги, добавь недостающие конструкции и подписи. Не удаляй уже существующие правильные элементы.

Верни ИСПРАВЛЕННЫЙ полный JSON (без текста до/после)."""


def _auto_create_point(plan: dict, pid: str, segment: dict, key: str,
                       point_ids: set):
    """Create a missing point by projecting from the other endpoint."""
    other_key = "to_point" if key == "from_point" else "from_point"
    other_pid = segment.get(other_key)
    other_pt = plan["points"].get(other_pid) if other_pid else None
    if not other_pt:
        return

    new_pt = {
        "x": other_pt["x"],
        "y": 0 if other_pt["y"] != 0 else other_pt["y"] - 2,
        "label_dx": 8, "label_dy": 12,
    }
    if "z" in other_pt:
        new_pt["z"] = 0
    plan["points"][pid] = new_pt
    point_ids.add(pid)
    z_info = f", {new_pt['z']}" if "z" in new_pt else ""
    print(f"  AUTO-CREATED point '{pid}' at ({new_pt['x']}, {new_pt['y']}{z_info})")


_SEG_LABEL_PATTERN = re.compile(
    r"^\s*([A-Za-z]{1,3})\s*=\s*(.+?)\s*$"
)

# Single-letter "derived quantity" markers handled by
# ``_attach_derived_quantity_labels``: height (h, H), radius (r, R),
# distance (d, D), Cyrillic 'высота', etc.
_DERIVED_HEIGHT = {"h", "H", "высота"}
_DERIVED_RADIUS = {"r", "R", "радиус"}
_DERIVED_DISTANCE = {"d", "D", "ρ", "расстояние"}


def _promote_segment_labels(plan: dict) -> None:
    """Move LLM-style ``annotation`` text of the form ``XY = <value>`` onto the
    matching segment as a proper ``length_label``.

    The renderer places ``length_label`` exactly at the midpoint of the
    segment with a perpendicular offset, so transferring such annotations
    fixes the common defect where labels float far from the segment they
    describe. If the corresponding segment is missing entirely (a frequent
    LLM oversight, e.g. unrendered diagonals of an auxiliary parallelogram),
    a thin dashed helper segment is synthesised so the label has a real
    geometric carrier instead of floating in empty space.

    Heuristic:
      * For each step, walk its annotations.
      * If the annotation text matches ``XY = <value>`` and there is a
        segment in the current step (or any earlier step) with endpoints
        {X, Y} in either order, set ``segment.length_label = <value>``
        and drop the annotation. Existing non-empty ``length_label`` is
        never overwritten.
      * If no such segment is found but both points X and Y are defined in
        ``plan["points"]``, synthesise a dashed helper segment in the
        current step and attach the label to it.
      * Single-letter annotations like ``h = 60/13`` are left untouched
        here because they refer to derived quantities, not specific
        segments.
    """
    point_ids = set(plan.get("points", {}).keys())
    seen_segments: list[dict] = []
    helper_counter = 0
    for step in plan.get("steps", []):
        for obj in step.get("objects", []):
            if obj.get("type") == "segment":
                seen_segments.append(obj)

        new_anns: list[dict] = []
        for ann in step.get("annotations", []):
            if ann.get("type") != "label":
                new_anns.append(ann)
                continue
            text = str(ann.get("text", ""))
            m = _SEG_LABEL_PATTERN.match(text)
            if not m:
                new_anns.append(ann)
                continue
            head, tail = m.group(1), m.group(2).strip()
            if len(head) != 2 or not head.isalpha():
                new_anns.append(ann)
                continue
            a, b = head[0], head[1]
            target = None
            for seg in seen_segments:
                fp, tp = seg.get("from_point"), seg.get("to_point")
                if {fp, tp} == {a, b}:
                    target = seg
                    break
            if target is None:
                if a in point_ids and b in point_ids:
                    helper_counter += 1
                    target = {
                        "type": "segment",
                        "id": f"s_helper_{a}{b}_{helper_counter}",
                        "from_point": a,
                        "to_point": b,
                        "style": {
                            "stroke": ann.get("color", "#666666"),
                            "stroke_width": 1.2,
                            "dash": "dashed",
                        },
                    }
                    step.setdefault("objects", []).append(target)
                    seen_segments.append(target)
                else:
                    new_anns.append(ann)
                    continue
            if str(target.get("length_label", "")).strip():
                new_anns.append(ann)
                continue
            # Keep the FULL annotation text ("BC = 4", not just "4") so a
            # student can cross-check labels with the LLM's claim and spot
            # mistakes such as wrong vertex naming or swapped lengths.
            target["length_label"] = text.strip()
            if ann.get("color"):
                target.setdefault("label_color", ann.get("color"))
            if ann.get("font_size"):
                target.setdefault("label_font_size", ann.get("font_size"))
        step["annotations"] = new_anns


def _find_perpendicular_segment(plan: dict, exclude_ids: set) -> dict | None:
    """Locate a segment in the plan that is geometrically perpendicular to
    another segment (i.e. a height/distance candidate).

    Returns the segment dict, or ``None`` if no candidate exists.
    """
    points = plan.get("points", {})
    all_segments: list[dict] = []
    for step in plan.get("steps", []):
        for obj in step.get("objects", []):
            if obj.get("type") == "segment" and obj.get("id") not in exclude_ids:
                all_segments.append(obj)

    def vec(seg):
        p1 = points.get(seg.get("from_point"))
        p2 = points.get(seg.get("to_point"))
        if not p1 or not p2:
            return None
        return (p2["x"] - p1["x"], p2["y"] - p1["y"])

    for s1 in all_segments:
        v1 = vec(s1)
        if not v1:
            continue
        len1 = math.hypot(*v1)
        if len1 < 1e-6:
            continue
        for s2 in all_segments:
            if s2 is s1:
                continue
            v2 = vec(s2)
            if not v2:
                continue
            len2 = math.hypot(*v2)
            if len2 < 1e-6:
                continue
            dot = v1[0] * v2[0] + v1[1] * v2[1]
            if abs(dot) / (len1 * len2) < 0.05:  # ≈ perpendicular
                return s1
    return None


def _find_parallel_pair(plan: dict) -> tuple[dict, dict] | None:
    """Find two distinct, non-collinear, parallel segments in the plan.

    Returns ``(s_top, s_bottom)`` such that ``s_top`` is the shorter side
    (it is more pedagogically natural to drop a height *from* its vertex
    *onto* the opposite — longer — side). Returns ``None`` if no parallel
    pair is available.
    """
    points = plan.get("points", {})
    all_segments: list[dict] = []
    for step in plan.get("steps", []):
        for obj in step.get("objects", []):
            if obj.get("type") == "segment":
                all_segments.append(obj)

    def vec(seg):
        p1 = points.get(seg.get("from_point"))
        p2 = points.get(seg.get("to_point"))
        if not p1 or not p2:
            return None
        return (p2["x"] - p1["x"], p2["y"] - p1["y"], p1, p2)

    pairs: list[tuple[dict, dict, float, float]] = []
    for i, s1 in enumerate(all_segments):
        d1 = vec(s1)
        if not d1:
            continue
        v1x, v1y, p1a, p1b = d1
        len1 = math.hypot(v1x, v1y)
        if len1 < 1e-6:
            continue
        for s2 in all_segments[i + 1:]:
            d2 = vec(s2)
            if not d2:
                continue
            v2x, v2y, p2a, p2b = d2
            len2 = math.hypot(v2x, v2y)
            if len2 < 1e-6:
                continue
            cross = v1x * v2y - v1y * v2x
            if abs(cross) / (len1 * len2) > 0.05:
                continue
            offset = abs(
                (p2a["x"] - p1a["x"]) * v1y
                - (p2a["y"] - p1a["y"]) * v1x
            ) / len1
            if offset < 1e-6:
                continue  # collinear, not a real pair of parallel sides
            pairs.append((s1, s2, len1, len2))

    if not pairs:
        return None
    pairs.sort(key=lambda t: -max(t[2], t[3]))
    s1, s2, len1, len2 = pairs[0]
    if len1 <= len2:
        return s1, s2
    return s2, s1


def _attach_derived_quantity_labels(plan: dict) -> None:
    """Attach ``h = …``, ``H = …``, ``r = …`` style annotations to a real
    geometric carrier: an existing perpendicular/radius segment if one is
    available, otherwise a synthesised dashed altitude between a pair of
    parallel sides found in the plan. The label format ``<X> = <V>`` is
    preserved so that the picture remains self-explanatory.

    Heuristic order:
      1. Already-promoted segment labels are skipped.
      2. For ``h``/``H``/``высота`` we first look for a segment that is
         geometrically perpendicular to another; if found, attach the
         label there.
      3. If no such segment exists but the plan contains two parallel
         sides, drop a perpendicular from the closest vertex of the
         shorter side onto the longer side, register the foot point in
         ``plan["points"]`` and add a dashed segment carrying the label.
      4. If neither succeeds, the annotation is left in place.
    """
    points = plan.get("points", {})
    if not points:
        return

    used_carriers: set = set()
    foot_counter = 0

    for step in plan.get("steps", []):
        new_anns: list[dict] = []
        for ann in step.get("annotations", []):
            if ann.get("type") != "label":
                new_anns.append(ann)
                continue
            text = str(ann.get("text", ""))
            m = _SEG_LABEL_PATTERN.match(text)
            if not m:
                new_anns.append(ann)
                continue
            head = m.group(1)
            if not (head in _DERIVED_HEIGHT or head in _DERIVED_RADIUS
                    or head in _DERIVED_DISTANCE):
                new_anns.append(ann)
                continue

            carrier = _find_perpendicular_segment(plan, used_carriers)
            if carrier is None and (head in _DERIVED_HEIGHT
                                    or head in _DERIVED_DISTANCE):
                pair = _find_parallel_pair(plan)
                if pair is None:
                    new_anns.append(ann)
                    continue
                s_top, s_bottom = pair
                a_id = s_top.get("from_point")
                a_pt = points.get(a_id)
                lp1 = points.get(s_bottom.get("from_point"))
                lp2 = points.get(s_bottom.get("to_point"))
                if not (a_pt and lp1 and lp2):
                    new_anns.append(ann)
                    continue
                dx = lp2["x"] - lp1["x"]
                dy = lp2["y"] - lp1["y"]
                denom = dx * dx + dy * dy
                if denom < 1e-12:
                    new_anns.append(ann)
                    continue
                t = ((a_pt["x"] - lp1["x"]) * dx
                     + (a_pt["y"] - lp1["y"]) * dy) / denom
                if not (-0.05 <= t <= 1.05):
                    # foot lands outside the segment — try the other apex
                    a_id = s_top.get("to_point")
                    a_pt = points.get(a_id)
                    if not a_pt:
                        new_anns.append(ann)
                        continue
                    t = ((a_pt["x"] - lp1["x"]) * dx
                         + (a_pt["y"] - lp1["y"]) * dy) / denom
                if not (-0.05 <= t <= 1.05):
                    new_anns.append(ann)
                    continue
                foot_x = lp1["x"] + t * dx
                foot_y = lp1["y"] + t * dy
                foot_counter += 1
                foot_id = f"H_{a_id}_{foot_counter}"
                while foot_id in points:
                    foot_counter += 1
                    foot_id = f"H_{a_id}_{foot_counter}"
                points[foot_id] = {
                    "x": foot_x, "y": foot_y,
                    "label_dx": 8, "label_dy": 14,
                }
                # Register the foot as an explicit, label-less point so
                # that its technical id does not show up on the canvas.
                step.setdefault("objects", []).append({
                    "type": "point",
                    "id": foot_id,
                    "label": "",
                })
                carrier = {
                    "type": "segment",
                    "id": f"s_alt_{a_id}{foot_id}",
                    "from_point": a_id,
                    "to_point": foot_id,
                    "style": {
                        "stroke": ann.get("color", "#27ae60"),
                        "stroke_width": 1.6,
                        "dash": "dashed",
                    },
                    "label_offset": 18,
                    "label_offset_dir": "auto",
                }
                step.setdefault("objects", []).append(carrier)
                step.setdefault("constraints", []).append({
                    "type": "right_angle_marker",
                    "id": f"ra_{foot_id}",
                    "vertex": foot_id,
                    "ray1": a_id,
                    "ray2": s_bottom.get("from_point"),
                })

            if carrier is None:
                new_anns.append(ann)
                continue
            if str(carrier.get("length_label", "")).strip():
                new_anns.append(ann)
                continue
            carrier["length_label"] = text
            if ann.get("color"):
                carrier.setdefault("label_color", ann.get("color"))
            if ann.get("font_size"):
                carrier.setdefault("label_font_size", ann.get("font_size"))
            used_carriers.add(carrier.get("id"))
        step["annotations"] = new_anns


def _postprocess_plan(plan: dict):
    """Fix common LLM mistakes in the plan."""
    point_ids = set(plan.get("points", {}).keys())

    for step in plan.get("steps", []):
        step.setdefault("constraints", [])
        step.setdefault("annotations", [])
        step.setdefault("objects", [])

        CONSTRAINT_TYPES = {
            "right_angle_marker", "angle_arc", "midpoint", "median",
            "altitude", "bisector", "bisector_line", "circumscribed_circle",
            "inscribed_circle", "midline", "tangent_line", "cross_section",
            "perpendicular", "parallel_lines", "equal_segments",
        }

        new_objects = []
        for obj in step["objects"]:
            if obj.get("type") in CONSTRAINT_TYPES:
                step["constraints"].append(obj)
            elif obj.get("type") == "label":
                step["annotations"].append(obj)
            else:
                new_objects.append(obj)
        step["objects"] = new_objects

        # Also check annotations for misplaced constraints
        new_annotations = []
        for ann in step["annotations"]:
            if ann.get("type") in CONSTRAINT_TYPES:
                step["constraints"].append(ann)
            else:
                new_annotations.append(ann)
        step["annotations"] = new_annotations

        # Fix right_angle_marker ray references: must be point ids
        for c in step["constraints"]:
            if c.get("type") == "right_angle_marker":
                for key in ("ray1", "ray2"):
                    val = c.get(key)
                    if val and val not in point_ids:
                        c[key] = None

    # Auto-create missing points referenced in segments
    for step in plan["steps"]:
        for obj in step["objects"]:
            if obj.get("type") == "segment":
                for key in ("from_point", "to_point"):
                    pid = obj.get(key)
                    if pid and pid not in point_ids:
                        _auto_create_point(plan, pid, obj, key, point_ids)

    # Remove consecutive text-only steps that produce no visual
    # by merging their text with the next step that has visuals
    merged_steps = []
    pending_text = ""
    for step in plan["steps"]:
        has_visual = (step.get("objects") or step.get("annotations")
                      or step.get("constraints"))
        if has_visual:
            if pending_text:
                step["text"] = pending_text + "\n\n" + step.get("text", "")
                pending_text = ""
            merged_steps.append(step)
        else:
            pending_text += ("\n\n" if pending_text else "") + step.get("text", "")

    if pending_text and merged_steps:
        merged_steps[-1]["text"] += "\n\n" + pending_text
    elif pending_text and not merged_steps:
        merged_steps.append({"text": pending_text, "objects": [], "annotations": [],
                             "constraints": [], "caption": ""})
    plan["steps"] = merged_steps

    _promote_segment_labels(plan)
    _attach_derived_quantity_labels(plan)


def _validate_plan(plan: dict) -> list[str]:
    """Basic sanity checks on the plan. Returns list of warnings."""
    assert "points" in plan, "Plan missing 'points'"
    assert "steps" in plan, "Plan missing 'steps'"
    assert len(plan["steps"]) >= 2, "Plan has fewer than 2 steps"

    warnings = []
    point_ids = set(plan["points"].keys())
    for i, step in enumerate(plan["steps"]):
        for obj in step.get("objects", []):
            if obj["type"] == "point" and obj["id"] not in point_ids:
                msg = f"step {i} references unknown point '{obj['id']}'"
                warnings.append(msg)
                print(f"  WARNING: {msg}")
            if obj["type"] == "segment":
                for key in ("from_point", "to_point"):
                    pid = obj.get(key)
                    if pid and pid not in point_ids:
                        msg = (f"step {i} segment '{obj['id']}' "
                               f"references unknown point '{pid}'")
                        warnings.append(msg)
                        print(f"  WARNING: {msg}")
            if obj["type"] == "polygon":
                for vid in obj.get("vertices", []):
                    if vid not in point_ids:
                        msg = f"step {i} polygon '{obj['id']}' references unknown point '{vid}'"
                        warnings.append(msg)
                        print(f"  WARNING: {msg}")
        for con in step.get("constraints", []):
            for key in ("vertex", "ray1", "ray2", "point", "line_point1",
                        "line_point2", "foot_id", "external_point", "touch_point"):
                pid = con.get(key)
                if pid and pid not in point_ids:
                    msg = (f"step {i} constraint '{con.get('id','')}' "
                           f"references unknown point '{pid}' in field '{key}'")
                    warnings.append(msg)
                    print(f"  WARNING: {msg}")
    return warnings


# ═══════════════════════════════════════════════════════════════
# Executor: JSON plan → StepByStepGeo → blocks (text + SVG)
# ═══════════════════════════════════════════════════════════════

def execute_plan(plan: dict) -> list[dict]:
    """Execute a step-by-step plan and return interleaved text/visual blocks."""
    points_data = plan.get("points", {})
    is_3d = _is_3d_plan(points_data)

    if is_3d:
        with _phase("auto_mark_hidden_edges",
                    n_points=len(points_data),
                    n_faces=len(plan.get("faces") or [])):
            _auto_mark_hidden_edges(plan)
        with _phase("compute_canvas_3d", n_points=len(points_data)):
            canvas, projected = _compute_canvas_3d(points_data)
        print(f"  3D plan detected ({len(points_data)} points), auto-canvas: "
              f"x=[{canvas['x_min']:.1f}..{canvas['x_max']:.1f}] "
              f"y=[{canvas['y_min']:.1f}..{canvas['y_max']:.1f}]")
    else:
        canvas = plan.get("canvas", {
            "width": 560, "height": 380,
            "x_min": -1, "x_max": 14, "y_min": -2, "y_max": 8
        })
        projected = None

    style = {
        "theme": "light", "stroke_color": "#333333", "fill_color": "none",
        "font_size": 13, "font_family": "sans-serif",
    }

    geo = StepByStepGeo(canvas, style)
    blocks = []

    for step_idx, step in enumerate(plan["steps"]):
        step_t0 = time.perf_counter()
        text = step.get("text", "")
        if text.strip():
            blocks.append({"type": "text", "content": text})

        n_objects = len(step.get("objects") or [])
        n_annotations = len(step.get("annotations") or [])
        n_constraints = len(step.get("constraints") or [])
        has_visual_content = bool(n_objects or n_annotations or n_constraints)

        if not has_visual_content:
            _record_step(step_idx, time.perf_counter() - step_t0,
                         n_objects=0, n_annotations=0, n_constraints=0,
                         has_text=bool(text.strip()))
            continue

        referenced_points = set()
        for obj in step.get("objects", []):
            if obj.get("type") == "segment":
                for key in ("from_point", "to_point"):
                    pid = obj.get(key)
                    if pid and pid in points_data:
                        referenced_points.add(pid)
        for obj in step.get("objects", []):
            if obj.get("type") == "point":
                referenced_points.discard(obj["id"])
        for pid in referenced_points:
            pt_obj = {"type": "point", "id": pid}
            built = _build_object(pt_obj, points_data, projected)
            if built:
                geo.add_object(built)

        for obj in step.get("objects", []):
            built = _build_object(obj, points_data, projected)
            if built:
                geo.add_object(built)

        for ann in step.get("annotations", []):
            geo.add_annotation(ann)

        for con in step.get("constraints", []):
            geo.add_constraint(con)

        geo.snapshot()
        blocks.append({
            "type": "visual",
            "svg": geo.steps[-1]["svg"],
            "caption": step.get("caption", ""),
        })
        _record_step(step_idx, time.perf_counter() - step_t0,
                     n_objects=n_objects,
                     n_annotations=n_annotations,
                     n_constraints=n_constraints,
                     has_text=bool(text.strip()))

    return blocks


def _build_object(obj: dict, points_data: dict,
                   projected: dict | None = None) -> dict | None:
    """Enrich object with coordinates from points_data.
    If projected is set, use pre-computed 2D positions (3D mode)."""
    obj = dict(obj)
    if obj["type"] == "point":
        pid = obj["id"]
        pt = points_data.get(pid)
        if not pt:
            print(f"  WARNING: point '{pid}' not in points_data, skipping")
            return None
        if projected and pid in projected:
            obj["x"], obj["y"] = projected[pid]
        else:
            obj["x"] = pt["x"]
            obj["y"] = pt["y"]
        label = re.sub(r'(?<=[A-Za-z])1$', '₁', pid) if projected else pid
        obj.setdefault("label", label)
        if "label_dx" in pt:
            obj["label_dx"] = pt["label_dx"]
        if "label_dy" in pt:
            obj["label_dy"] = pt["label_dy"]
    if obj["type"] == "segment":
        style = obj.get("style", {})
        if style.get("hidden"):
            style = dict(style)
            style["dash"] = "dashed"
            style.setdefault("stroke", "#aaa")
            del style["hidden"]
            obj["style"] = style
    return obj


# ═══════════════════════════════════════════════════════════════
# HTML generation (reused/improved from task16_demo)
# ═══════════════════════════════════════════════════════════════

def render_md(text):
    lines = text.strip().split("\n")
    result = []
    for line in lines:
        s = line.strip()
        if s == "---":
            result.append('<hr style="border:none;border-top:1px solid #ddd;margin:24px 0;"/>')
        elif s.startswith("## "):
            result.append(f'<h2>{_fmt(s[3:])}</h2>')
        elif s.startswith("### "):
            result.append(f'<h3>{_fmt(s[4:])}</h3>')
        elif s.startswith("$$") and s.endswith("$$"):
            result.append(f'<div class="formula">{s}</div>')
        elif s.startswith("- "):
            result.append(f'<div style="padding-left:16px;">• {_fmt(s[2:])}</div>')
        elif s == "":
            result.append("<br/>")
        else:
            result.append(f'<p>{_fmt(s)}</p>')
    return "\n".join(result)


def _fmt(s):
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = s.replace("\\square", "\\(\\blacksquare\\)")
    return s


def generate_html_animated(blocks, title="Геометрическая задача", source_url=""):
    """Generate an animated HTML where steps appear progressively with navigation."""
    # Group blocks into steps: each step = text + visual pair
    steps = []
    current_text = ""
    for block in blocks:
        if block["type"] == "text":
            current_text += ("\n\n" if current_text else "") + block["content"]
        elif block["type"] == "visual":
            steps.append({
                "text": current_text,
                "svg": block["svg"],
                "caption": block.get("caption", ""),
            })
            current_text = ""
    if current_text and steps:
        steps[-1]["text"] += "\n\n" + current_text

    n_steps = len(steps)
    esc = html_mod.escape

    source_line = ""
    if source_url:
        source_line = (f'<p style="margin-top:6px;">'
                       f'<a href="{esc(source_url)}">Источник задачи</a></p>')

    # Build step HTML blocks
    step_divs = []
    for i, step in enumerate(steps):
        text_html = render_md(step["text"]) if step["text"].strip() else ""
        step_divs.append(f"""
<div class="step" id="step-{i}" style="display:{'block' if i == 0 else 'none'}">
  <div class="step-header">Шаг {i + 1} из {n_steps}</div>
  <div class="text-block">{text_html}</div>
  <div class="visual-block">
    <div class="visual-frame">{step['svg']}</div>
    <div class="visual-caption">{esc(step['caption'])}</div>
  </div>
</div>""")

    steps_html = "\n".join(step_divs)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>{esc(title)}</title>
<script>
MathJax = {{
  tex: {{ inlineMath: [['$','$']], displayMath: [['$$','$$']] }},
  svg: {{ fontCache: 'global' }}
}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Georgia','PT Serif',serif; background:#faf9f6; color:#2c2c2c; line-height:1.85; }}
  .page-header {{ background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%); padding:36px 20px; text-align:center; color:white; }}
  .page-header h1 {{ font-size:24px; margin-bottom:6px; font-family:sans-serif; }}
  .page-header p {{ opacity:0.8; font-size:13px; font-family:sans-serif; }}
  .page-header a {{ color:#81d4fa; text-decoration:none; }}
  .conspect {{ max-width:740px; margin:0 auto; padding:32px 28px 60px; }}
  .step {{ animation: fadeIn 0.4s ease; }}
  @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(12px); }} to {{ opacity:1; transform:translateY(0); }} }}
  .step-header {{ font-family:-apple-system,sans-serif; font-size:12px; color:#999; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:12px; }}
  .text-block {{ margin:14px 0; font-size:16.5px; }}
  .text-block p {{ margin:5px 0; }}
  .text-block h2 {{ font-size:21px; color:#2c3e50; font-family:sans-serif; }}
  .text-block h3 {{ font-size:18px; color:#34495e; font-family:sans-serif; }}
  .text-block strong {{ color:#2c3e50; }}
  .formula {{ background:#f7f9fc; padding:14px 20px; border-radius:8px; margin:12px 0; text-align:center; border-left:3px solid #2980b9; }}
  .visual-block {{ margin:22px 0; text-align:center; }}
  .visual-frame {{ display:inline-block; background:white; border:1px solid #e0e0e0; border-radius:10px; padding:14px 18px; box-shadow:0 2px 10px rgba(0,0,0,0.06); }}
  .visual-frame svg {{ max-width:100%; height:auto; }}
  .visual-caption {{ font-family:-apple-system,sans-serif; font-size:13px; color:#777; margin-top:8px; font-style:italic; }}
  .nav {{ display:flex; justify-content:center; gap:12px; margin:28px 0; }}
  .nav button {{ font-family:-apple-system,sans-serif; font-size:14px; padding:10px 24px; border:1px solid #ddd; border-radius:8px; background:white; cursor:pointer; transition:all 0.2s; }}
  .nav button:hover:not(:disabled) {{ background:#2980b9; color:white; border-color:#2980b9; }}
  .nav button:disabled {{ opacity:0.4; cursor:default; }}
  .progress {{ display:flex; justify-content:center; gap:6px; margin:16px 0; }}
  .progress .dot {{ width:10px; height:10px; border-radius:50%; background:#ddd; transition:background 0.3s; }}
  .progress .dot.active {{ background:#2980b9; }}
  .footer {{ text-align:center; padding:30px 20px; color:#aaa; font-size:11px; font-family:sans-serif; border-top:1px solid #eee; }}
</style>
</head>
<body>
<div class="page-header">
  <h1>{esc(title)}</h1>
  <p>Пошаговое построение — переключайте шаги кнопками или клавишами ←→</p>
  {source_line}
</div>
<div class="conspect">
  <div class="progress" id="progress">
    {''.join(f'<div class="dot{" active" if i == 0 else ""}" id="dot-{i}"></div>' for i in range(n_steps))}
  </div>
  {steps_html}
  <div class="nav">
    <button id="btn-prev" onclick="navigate(-1)" disabled>← Назад</button>
    <button id="btn-next" onclick="navigate(1)">Далее →</button>
  </div>
</div>
<div class="footer">
  Автоматическая генерация: LLM-планировщик → StepByStepGeo → Solver → SVG Renderer |
  {n_steps} пошаговых построений
</div>
<script>
let current = 0;
const total = {n_steps};
function navigate(dir) {{
  document.getElementById('step-' + current).style.display = 'none';
  document.getElementById('dot-' + current).classList.remove('active');
  current = Math.max(0, Math.min(total - 1, current + dir));
  const el = document.getElementById('step-' + current);
  el.style.display = 'block';
  el.style.animation = 'none';
  el.offsetHeight;
  el.style.animation = 'fadeIn 0.4s ease';
  document.getElementById('dot-' + current).classList.add('active');
  document.getElementById('btn-prev').disabled = (current === 0);
  document.getElementById('btn-next').disabled = (current === total - 1);
}}
document.addEventListener('keydown', function(e) {{
  if (e.key === 'ArrowRight' || e.key === ' ') navigate(1);
  if (e.key === 'ArrowLeft') navigate(-1);
}});
</script>
</body></html>"""


def generate_html(blocks, title="Геометрическая задача", source_url=""):
    n_visuals = sum(1 for b in blocks if b["type"] == "visual")
    esc = html_mod.escape

    source_line = ""
    if source_url:
        source_line = (f'<p style="margin-top:6px;">'
                       f'<a href="{esc(source_url)}">Источник задачи</a></p>')

    parts = [f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>{esc(title)}</title>
<script>
MathJax = {{
  tex: {{ inlineMath: [['$','$']], displayMath: [['$$','$$']] }},
  svg: {{ fontCache: 'global' }}
}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Georgia','PT Serif',serif; background:#faf9f6; color:#2c2c2c; line-height:1.85; }}
  .page-header {{ background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%); padding:36px 20px; text-align:center; color:white; }}
  .page-header h1 {{ font-size:24px; margin-bottom:6px; font-family:sans-serif; }}
  .page-header p {{ opacity:0.8; font-size:13px; font-family:sans-serif; }}
  .page-header a {{ color:#81d4fa; text-decoration:none; }}
  .conspect {{ max-width:740px; margin:0 auto; padding:32px 28px 60px; }}
  .text-block {{ margin:14px 0; font-size:16.5px; }}
  .text-block p {{ margin:5px 0; }}
  .text-block h2 {{ font-size:21px; color:#2c3e50; font-family:sans-serif; }}
  .text-block h3 {{ font-size:18px; color:#34495e; font-family:sans-serif; }}
  .text-block strong {{ color:#2c3e50; }}
  .formula {{ background:#f7f9fc; padding:14px 20px; border-radius:8px; margin:12px 0; text-align:center; border-left:3px solid #2980b9; }}
  .visual-block {{ margin:22px 0; text-align:center; }}
  .visual-frame {{ display:inline-block; background:white; border:1px solid #e0e0e0; border-radius:10px; padding:14px 18px; box-shadow:0 2px 10px rgba(0,0,0,0.06); }}
  .visual-frame svg {{ max-width:100%; height:auto; }}
  .visual-caption {{ font-family:-apple-system,sans-serif; font-size:13px; color:#777; margin-top:8px; font-style:italic; }}
  .footer {{ text-align:center; padding:30px 20px; color:#aaa; font-size:11px; font-family:sans-serif; border-top:1px solid #eee; }}
</style>
</head>
<body>
<div class="page-header">
  <h1>{esc(title)}</h1>
  <p>Пошаговое решение с автоматически сгенерированными построениями (LLM → SVG)</p>
  {source_line}
</div>
<div class="conspect">
"""]

    for block in blocks:
        if block["type"] == "text":
            parts.append(f'<div class="text-block">{render_md(block["content"])}</div>')
        elif block["type"] == "visual":
            cap = block.get("caption", "")
            parts.append(f"""
<div class="visual-block">
  <div class="visual-frame">{block['svg']}</div>
  <div class="visual-caption">{esc(cap)}</div>
</div>""")

    parts.append(f"""
</div>
<div class="footer">
  Автоматическая генерация: LLM-планировщик → StepByStepGeo → Solver → SVG Renderer |
  {n_visuals} пошаговых построений
</div>
</body></html>""")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════

def run(problem_text: str, output_name: str = "auto_geometry",
        title: str = "Геометрическая задача", source_url: str = "",
        api_key: str = None, model: str = DEFAULT_MODEL,
        save_plan: bool = True, animated: bool = False,
        save_metrics: bool = True,
        enforce_answer_vis: bool = True,
        max_answer_vis_retries: int = 1) -> Path:
    """Full pipeline: problem text → LLM plan → SVG → HTML.

    If `enforce_answer_vis` is True (default), the planner runs the
    answer-visualization post-condition validator and may issue up to
    `max_answer_vis_retries` extra LLM fix-requests when pedagogical
    defects are detected. Set to False to bypass the post-condition
    enforcement (useful for "before/after" benchmarks).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _start_metrics(model=model, mode="run")

    try:
        plan = plan_geometry_steps(
            problem_text, api_key=api_key, model=model,
            enforce_answer_vis=enforce_answer_vis,
            max_answer_vis_retries=max_answer_vis_retries,
        )

        if save_plan:
            plan_path = OUTPUT_DIR / f"{output_name}_plan.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            print(f"[geometry_auto] Plan saved: {plan_path}")

        with _phase("execute_plan",
                    n_points=len(plan.get("points", {})),
                    n_steps=len(plan.get("steps", [])),
                    is_3d=_is_3d_plan(plan.get("points", {}))):
            blocks = execute_plan(plan)

        with _phase("html_render", animated=animated):
            if animated:
                html = generate_html_animated(blocks, title=title,
                                              source_url=source_url)
            else:
                html = generate_html(blocks, title=title, source_url=source_url)

        out_path = OUTPUT_DIR / f"{output_name}.html"
        out_path.write_text(html, encoding="utf-8")

        n_text = sum(1 for b in blocks if b["type"] == "text")
        n_vis = sum(1 for b in blocks if b["type"] == "visual")
        print(f"[geometry_auto] Report: {out_path}")
        print(f"[geometry_auto] {n_text} text blocks, {n_vis} visuals"
              f"{' (animated)' if animated else ''}")

        if save_metrics:
            metrics = _finalize_metrics()
            if metrics is not None:
                metrics_path = OUTPUT_DIR / f"{output_name}_metrics.json"
                metrics_path.write_text(
                    json.dumps(metrics, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                tot = metrics["totals"]
                print(f"[geometry_auto] Metrics: wall={tot['wall_sec']}s, "
                      f"LLM={tot['llm_sec']}s ({tot['llm_calls']} calls, "
                      f"{tot['llm_tokens_in']}+{tot['llm_tokens_out']} tok), "
                      f"steps={tot['steps_sec']}s ({tot['steps_count']})")
                print(f"[geometry_auto] Metrics saved: {metrics_path}")
        return out_path
    finally:
        _reset_metrics()


# ═══════════════════════════════════════════════════════════════

TASK16_PROBLEM = """Задание 16 Профильного ЕГЭ по математике. Планиметрия. Задача 1.

Основания трапеции равны 4 и 9, а её диагонали равны 5 и 12.

а) Докажите, что диагонали трапеции перпендикулярны.
б) Найдите высоту трапеции.

Решение:

В условии есть тонкий намёк. Вспомним пифагорову тройку: 5, 12, 13.
Как бы нам построить треугольник с такими же длинами сторон?

Пусть BC = 4, AD = 9, AC = 12, BD = 5.

а) Проведём CF ∥ BD. BCFD — параллелограмм, значит, DF = BC = 4, CF = BD = 5.

Треугольник ACF со сторонами AC = 12, CF = 5, AF = 9 + 4 = 13 прямоугольный
(так как AF² = AC² + CF², то есть 169 = 144 + 25).

Значит, AC и BD перпендикулярны, что и требовалось доказать.

б) Высота трапеции равна высоте треугольника ACF. Обозначим эту высоту h.

S_ACF = (1/2) · AF · h = (1/2) · AC · CF

13h = 12 · 5

h = 60/13.
"""


def run_from_plan(plan_path: str, output_name: str = "auto_geometry",
                  title: str = "Геометрическая задача",
                  source_url: str = "", animated: bool = False,
                  save_metrics: bool = True) -> Path:
    """Run from a previously saved plan JSON (no LLM needed)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _start_metrics(model="(plan-replay)", mode="run_from_plan")
    try:
        raw_text = Path(plan_path).read_text(encoding="utf-8")
        with _phase("extract_json", chars=len(raw_text)):
            try:
                plan = json.loads(raw_text)
            except json.JSONDecodeError:
                plan = _extract_json(raw_text)
                if not plan:
                    raise ValueError(f"Could not parse plan from {plan_path}")
        with _phase("postprocess_plan"):
            _postprocess_plan(plan)
        with _phase("validate_plan"):
            warnings = _validate_plan(plan)
        _record_phase("validation_round", 0.0, round_idx=0,
                      warnings=len(warnings) if warnings else 0)

        with _phase("execute_plan",
                    n_points=len(plan.get("points", {})),
                    n_steps=len(plan.get("steps", [])),
                    is_3d=_is_3d_plan(plan.get("points", {}))):
            blocks = execute_plan(plan)

        with _phase("html_render", animated=animated):
            if animated:
                html = generate_html_animated(blocks, title=title,
                                              source_url=source_url)
            else:
                html = generate_html(blocks, title=title, source_url=source_url)

        out_path = OUTPUT_DIR / f"{output_name}.html"
        out_path.write_text(html, encoding="utf-8")
        n_vis = sum(1 for b in blocks if b["type"] == "visual")
        print(f"[geometry_auto] Report from plan: {out_path} ({n_vis} visuals)")

        if save_metrics:
            metrics = _finalize_metrics()
            if metrics is not None:
                metrics_path = OUTPUT_DIR / f"{output_name}_metrics.json"
                metrics_path.write_text(
                    json.dumps(metrics, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"[geometry_auto] Metrics saved: {metrics_path}")
        return out_path
    finally:
        _reset_metrics()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Auto geometry step-by-step")
    parser.add_argument("--problem-file", type=str, default=None,
                        help="Path to .txt file with problem+solution")
    parser.add_argument("--plan-file", type=str, default=None,
                        help="Path to saved plan JSON (skip LLM)")
    parser.add_argument("--output", type=str, default="auto_task16")
    parser.add_argument("--title", type=str, default="Задание 16 ЕГЭ — Планиметрия")
    parser.add_argument("--source-url", type=str, default="")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--api-key", type=str, default=None,
                        help="Together AI API key (or set TOGETHER_API_KEY env)")
    parser.add_argument("--animated", action="store_true",
                        help="Generate animated step-by-step HTML with navigation")
    args = parser.parse_args()

    if args.api_key:
        os.environ["TOGETHER_API_KEY"] = args.api_key

    if args.plan_file:
        run_from_plan(
            plan_path=args.plan_file,
            output_name=args.output,
            title=args.title,
            source_url=args.source_url,
            animated=args.animated,
        )
    else:
        if args.problem_file:
            text = Path(args.problem_file).read_text(encoding="utf-8")
        else:
            text = TASK16_PROBLEM

        run(
            problem_text=text,
            output_name=args.output,
            title=args.title,
            source_url=args.source_url,
            model=args.model,
            animated=args.animated,
        )
