import math

from app.schemas import Point, Scene, Segment


def solve(scene: Scene) -> tuple[Scene, list[str]]:
    """Обрабатывает constraints, добавляет вычисленные объекты в scene."""
    warnings: list[str] = []
    new_objs: list = list(scene.objects)

    # Индексы объектов по id (обновляются при добавлении новых)
    pts: dict[str, Point] = {}
    objs: dict = {}
    for obj in new_objs:
        objs[obj.id] = obj
        if obj.type == "point":
            pts[obj.id] = obj

    existing_ids = set(objs.keys())

    def _add(obj) -> None:
        if obj.id not in existing_ids:
            new_objs.append(obj)
            objs[obj.id] = obj
            existing_ids.add(obj.id)
            if obj.type == "point":
                pts[obj.id] = obj

    for c in scene.constraints:
        if c.type == "midpoint":
            seg = objs.get(c.segment)
            if not seg:
                warnings.append(f"Constraint '{c.id}': segment '{c.segment}' not found")
                continue
            p1, p2 = pts.get(seg.from_point), pts.get(seg.to_point)
            if not p1 or not p2:
                warnings.append(f"Constraint '{c.id}': endpoint points not found")
                continue
            _add(Point(id=c.result_id, x=(p1.x + p2.x) / 2, y=(p1.y + p2.y) / 2))

        elif c.type == "median":
            tri = objs.get(c.triangle)
            if not tri:
                warnings.append(f"Constraint '{c.id}': triangle '{c.triangle}' not found")
                continue
            if c.vertex not in tri.vertices:
                warnings.append(f"Constraint '{c.id}': vertex '{c.vertex}' not in triangle")
                continue
            others = [v for v in tri.vertices if v != c.vertex]
            pv = pts.get(c.vertex)
            p1, p2 = pts.get(others[0]), pts.get(others[1])
            if not all([pv, p1, p2]):
                warnings.append(f"Constraint '{c.id}': points not found")
                continue
            mid_id = f"{c.id}_mid"
            seg_id = f"{c.id}_seg"
            _add(Point(id=mid_id, x=(p1.x + p2.x) / 2, y=(p1.y + p2.y) / 2))
            _add(Segment(id=seg_id, from_point=c.vertex, to_point=mid_id))

        elif c.type == "altitude":
            tri = objs.get(c.triangle)
            if not tri:
                warnings.append(f"Constraint '{c.id}': triangle '{c.triangle}' not found")
                continue
            if c.vertex not in tri.vertices:
                warnings.append(f"Constraint '{c.id}': vertex '{c.vertex}' not in triangle")
                continue
            others = [v for v in tri.vertices if v != c.vertex]
            pv = pts.get(c.vertex)
            p1, p2 = pts.get(others[0]), pts.get(others[1])
            if not all([pv, p1, p2]):
                warnings.append(f"Constraint '{c.id}': points not found")
                continue
            # Основание перпендикуляра из pv на отрезок p1-p2
            dx, dy = p2.x - p1.x, p2.y - p1.y
            denom = dx * dx + dy * dy
            if denom == 0:
                warnings.append(f"Constraint '{c.id}': degenerate altitude base")
                continue
            t = ((pv.x - p1.x) * dx + (pv.y - p1.y) * dy) / denom
            foot_id = f"{c.id}_foot"
            seg_id = f"{c.id}_seg"
            _add(Point(id=foot_id, x=p1.x + t * dx, y=p1.y + t * dy))
            _add(Segment(id=seg_id, from_point=c.vertex, to_point=foot_id))

        elif c.type == "bisector":
            tri = objs.get(c.triangle)
            if not tri:
                warnings.append(f"Constraint '{c.id}': triangle '{c.triangle}' not found")
                continue
            if c.vertex not in tri.vertices:
                warnings.append(f"Constraint '{c.id}': vertex '{c.vertex}' not in triangle")
                continue
            others = [v for v in tri.vertices if v != c.vertex]
            pv = pts.get(c.vertex)
            p1, p2 = pts.get(others[0]), pts.get(others[1])
            if not all([pv, p1, p2]):
                warnings.append(f"Constraint '{c.id}': points not found")
                continue
            # Теорема о биссектрисе: D делит p1-p2 в отношении |pv-p1|:|pv-p2|
            d1 = math.dist((pv.x, pv.y), (p1.x, p1.y))
            d2 = math.dist((pv.x, pv.y), (p2.x, p2.y))
            total = d1 + d2
            if total == 0:
                warnings.append(f"Constraint '{c.id}': degenerate bisector")
                continue
            bx = (d2 * p1.x + d1 * p2.x) / total
            by = (d2 * p1.y + d1 * p2.y) / total
            bis_id = f"{c.id}_pt"
            seg_id = f"{c.id}_seg"
            _add(Point(id=bis_id, x=bx, y=by))
            _add(Segment(id=seg_id, from_point=c.vertex, to_point=bis_id))

        # right_angle_marker: пропускается, не добавляет объекты

    return scene.model_copy(update={"objects": new_objs}), warnings
