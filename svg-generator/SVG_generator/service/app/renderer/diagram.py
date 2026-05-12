from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.schemas import Scene, Style

from .text_engine import ZiaTextEngine

_ENGINE = ZiaTextEngine()

_NODE_H_PADDING = 16.0
_NODE_V_PADDING = 12.0
_LAYER_GAP = 76.0
_NODE_GAP = 42.0
_CANVAS_PADDING = 28.0
_MIN_BOX_WIDTH = 120.0
_MAX_BOX_WIDTH = 300.0
_MIN_TEXT_WIDTH = 120.0
_MAX_TEXT_WIDTH = 360.0
_MIN_FORMULA_WIDTH = 180.0
_MAX_FORMULA_WIDTH = 460.0


@dataclass
class _NodeLayout:
    id: str
    node_type: str
    source: Any
    text: str
    font_size: int
    width: float
    height: float
    lines: list[str]
    line_height: float
    x: float = 0.0
    y: float = 0.0
    layer: int = 0


@dataclass
class _EdgeLayout:
    id: str
    source: Any
    from_id: str
    to_id: str
    points: list[tuple[float, float]]
    label_lines: list[str]
    label_font_size: int
    label_width: float
    label_height: float
    label_bbox: tuple[float, float, float, float] | None
    is_back_edge: bool = False


@dataclass
class _PreparedLayout:
    title: _NodeLayout | None
    nodes: dict[str, _NodeLayout]
    free_texts: list[_NodeLayout]
    edges: list[_EdgeLayout]
    width: float
    height: float


@dataclass
class _EdgeRef:
    source: Any
    from_id: str
    to_id: str


def prepare_diagram_scene(scene: Scene) -> None:
    """
    Подготавливает диаграмму перед рендером.
    В semantic-first режиме canvas вычисляется из layout.
    """
    # Для diagram полностью игнорируем входные размеры холста от LLM.
    scene.canvas.width = 0.0
    scene.canvas.height = 0.0
    scene.canvas.x_min = 0.0
    scene.canvas.y_min = 0.0
    scene.canvas.x_max = 0.0
    scene.canvas.y_max = 0.0


def render_diagram(scene: Scene) -> list[str]:
    """Рендерит diagram сцену с автоматической раскладкой."""
    prepared = _prepare_layout(scene)

    # Холст рассчитывается после layout.
    scene.canvas.width = prepared.width
    scene.canvas.height = prepared.height
    scene.canvas.x_min = 0.0
    scene.canvas.y_min = 0.0
    scene.canvas.x_max = prepared.width
    scene.canvas.y_max = prepared.height

    style = scene.style
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(prepared.width)}" height="{int(prepared.height)}" overflow="hidden">',
        "  <defs>",
        '    <marker id="arrow_axis" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto">',
        '      <path d="M0,0 L8,4 L0,8 Z" fill="#888888"/>',
        "    </marker>",
        f'    <marker id="arrow_obj" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">',
        f'      <path d="M0,0 L8,4 L0,8 Z" fill="{style.stroke_color}"/>',
        "    </marker>",
        "  </defs>",
    ]
    if style.theme == "light":
        lines.append(f'  <rect width="{int(prepared.width)}" height="{int(prepared.height)}" fill="white"/>')

    if prepared.title is not None:
        lines.extend(_render_node_text(prepared.title, style, anchor="middle", bold=True))

    for edge in prepared.edges:
        lines.extend(_render_edge(edge, style, include_label=False))

    for node in prepared.nodes.values():
        lines.extend(_render_node(node, style))

    for edge in prepared.edges:
        lines.extend(_render_edge_label(edge, style))

    for text_node in prepared.free_texts:
        lines.extend(_render_node_text(text_node, style, anchor="middle", bold=False))

    return lines


def _prepare_layout(scene: Scene) -> _PreparedLayout:
    title_obj = next((obj for obj in scene.objects if obj.type == "title"), None)
    title = _measure_title(title_obj, scene.style) if title_obj else None

    node_objs = [obj for obj in scene.objects if obj.type in {"box", "formula_block"}]
    nodes = {obj.id: _measure_node(obj, scene.style) for obj in sorted(node_objs, key=lambda o: o.id)}

    free_texts = [
        _measure_free_text(obj, scene.style)
        for obj in sorted((o for o in scene.objects if o.type == "text"), key=lambda o: o.id)
    ]

    arrows = [obj for obj in scene.objects if obj.type == "arrow"]
    edges_def = _normalize_edges(arrows, nodes)
    layers = _assign_layers(nodes, edges_def)
    for node_id, layer in layers.items():
        if node_id in nodes:
            nodes[node_id].layer = layer

    _place_nodes_top_down(nodes, edges_def, title)
    edges = _route_edges(nodes, edges_def, scene.style)
    _place_edge_labels(edges, nodes)
    _place_free_texts(free_texts, nodes, title)
    width, height = _fit_canvas(nodes, edges, title, free_texts)
    _shift_to_canvas(nodes, edges, title, free_texts, width, height)

    return _PreparedLayout(
        title=title,
        nodes=nodes,
        free_texts=free_texts,
        edges=edges,
        width=width,
        height=height,
    )


def _measure_title(obj: Any, style: Style) -> _NodeLayout:
    font_size = style.font_size + 6
    max_width = 520.0
    lines = _ENGINE.wrap_text(obj.text, max_width, font_size)
    line_height = font_size * 1.25
    text_width = max(_ENGINE.measure(line, font_size)[0] for line in lines)
    width = text_width + 8.0
    height = max(24.0, len(lines) * line_height)
    return _NodeLayout(
        id=obj.id,
        node_type="title",
        source=obj,
        text=obj.text,
        font_size=font_size,
        width=width,
        height=height,
        lines=lines,
        line_height=line_height,
    )


def _measure_node(obj: Any, style: Style) -> _NodeLayout:
    if obj.type == "box":
        font_size = style.font_size
        target_width = _pick_target_width(obj.text, font_size, _MIN_BOX_WIDTH, _MAX_BOX_WIDTH)
        lines = _ENGINE.wrap_text(obj.text, target_width - _NODE_H_PADDING * 2, font_size)
        line_height = font_size * 1.3
        content_width = max(_ENGINE.measure(line, font_size)[0] for line in lines)
        width = max(_MIN_BOX_WIDTH, min(_MAX_BOX_WIDTH, content_width + _NODE_H_PADDING * 2))
        height = max(56.0, len(lines) * line_height + _NODE_V_PADDING * 2)
        text = obj.text
    else:
        font_size = obj.font_size if obj.font_size is not None else max(14, style.font_size + 2)
        text = obj.formula.strip()
        if not (text.startswith("$") and text.endswith("$")):
            text = f"${text}$"
        measured_w, measured_h = _ENGINE.measure(text, font_size)
        width = max(_MIN_FORMULA_WIDTH, min(_MAX_FORMULA_WIDTH, measured_w + 24.0))
        line_height = font_size * 1.2
        lines = [text]
        height = max(64.0, measured_h + 24.0)

    return _NodeLayout(
        id=obj.id,
        node_type=obj.type,
        source=obj,
        text=text,
        font_size=font_size,
        width=width,
        height=height,
        lines=lines,
        line_height=line_height,
    )


def _measure_free_text(obj: Any, style: Style) -> _NodeLayout:
    font_size = obj.font_size if obj.font_size is not None else style.font_size
    target_width = _pick_target_width(obj.text, font_size, _MIN_TEXT_WIDTH, _MAX_TEXT_WIDTH)
    lines = _ENGINE.wrap_text(obj.text, target_width, font_size)
    line_height = font_size * 1.28
    width = max(_ENGINE.measure(line, font_size)[0] for line in lines)
    height = max(line_height, len(lines) * line_height)
    return _NodeLayout(
        id=obj.id,
        node_type="text",
        source=obj,
        text=obj.text,
        font_size=font_size,
        width=width,
        height=height,
        lines=lines,
        line_height=line_height,
    )


def _pick_target_width(text: str, font_size: int, min_w: float, max_w: float) -> float:
    raw_w, _ = _ENGINE.measure(text, font_size)
    return max(min_w, min(max_w, raw_w * 0.72 + 20.0))


def _normalize_edges(arrows: list[Any], nodes: dict[str, _NodeLayout]) -> list[_EdgeRef]:
    refs: list[_EdgeRef] = []
    for arrow in sorted(arrows, key=lambda a: a.id):
        if arrow.from_point in nodes and arrow.to_point in nodes:
            refs.append(_EdgeRef(source=arrow, from_id=arrow.from_point, to_id=arrow.to_point))
    return refs


def _assign_layers(nodes: dict[str, _NodeLayout], edges: list[_EdgeRef]) -> dict[str, int]:
    if not nodes:
        return {}

    out_edges: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    in_edges: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for edge in edges:
        out_edges[edge.from_id].append(edge.to_id)
        in_edges[edge.to_id].append(edge.from_id)

    # Разбиваем граф на SCC, чтобы стабильно работать с циклами.
    index = 0
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def strongconnect(node_id: str) -> None:
        nonlocal index
        indices[node_id] = index
        low[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)
        for nxt in out_edges[node_id]:
            if nxt not in indices:
                strongconnect(nxt)
                low[node_id] = min(low[node_id], low[nxt])
            elif nxt in on_stack:
                low[node_id] = min(low[node_id], indices[nxt])
        if low[node_id] != indices[node_id]:
            return
        comp: list[str] = []
        while stack:
            candidate = stack.pop()
            on_stack.discard(candidate)
            comp.append(candidate)
            if candidate == node_id:
                break
        components.append(sorted(comp))

    for node_id in sorted(nodes):
        if node_id not in indices:
            strongconnect(node_id)

    comp_by_node: dict[str, int] = {}
    for comp_idx, comp in enumerate(components):
        for node_id in comp:
            comp_by_node[node_id] = comp_idx

    comp_out: dict[int, set[int]] = {idx: set() for idx in range(len(components))}
    comp_in_count: dict[int, int] = {idx: 0 for idx in range(len(components))}
    for edge in edges:
        src = comp_by_node[edge.from_id]
        dst = comp_by_node[edge.to_id]
        if src == dst or dst in comp_out[src]:
            continue
        comp_out[src].add(dst)
        comp_in_count[dst] += 1

    comp_queue = sorted([idx for idx, cnt in comp_in_count.items() if cnt == 0])
    comp_layer = {idx: 0 for idx in range(len(components))}
    while comp_queue:
        comp_idx = comp_queue.pop(0)
        for nxt in sorted(comp_out[comp_idx]):
            comp_layer[nxt] = max(comp_layer[nxt], comp_layer[comp_idx] + 1)
            comp_in_count[nxt] -= 1
            if comp_in_count[nxt] == 0:
                comp_queue.append(nxt)
        comp_queue.sort()

    layers: dict[str, int] = {}
    for comp_idx, comp_nodes in enumerate(components):
        base = comp_layer[comp_idx]
        if len(comp_nodes) == 1:
            layers[comp_nodes[0]] = base
            continue

        comp_set = set(comp_nodes)
        internal_out: dict[str, list[str]] = {node_id: [] for node_id in comp_nodes}
        incoming_from_other = {node_id: 0 for node_id in comp_nodes}
        for edge in edges:
            if edge.from_id in comp_set and edge.to_id in comp_set:
                internal_out[edge.from_id].append(edge.to_id)
            elif edge.to_id in comp_set:
                incoming_from_other[edge.to_id] += 1

        seeds = sorted([node_id for node_id, cnt in incoming_from_other.items() if cnt > 0]) or [sorted(comp_nodes)[0]]
        local_dist: dict[str, int] = {node_id: 0 for node_id in comp_nodes}
        seen: set[str] = set()
        bfs_queue = list(seeds)
        for seed in seeds:
            seen.add(seed)
        while bfs_queue:
            node_id = bfs_queue.pop(0)
            for nxt in sorted(internal_out.get(node_id, [])):
                if nxt not in seen:
                    seen.add(nxt)
                    local_dist[nxt] = local_dist[node_id] + 1
                    bfs_queue.append(nxt)

        for node_id in sorted(comp_nodes):
            layers[node_id] = base + local_dist[node_id]

    isolated = [node_id for node_id in sorted(nodes) if not in_edges[node_id] and not out_edges[node_id]]
    if isolated:
        base = max(layers.values(), default=0) + 1
        for idx, node_id in enumerate(isolated):
            layers[node_id] = base + idx
    return layers


def _place_nodes_top_down(nodes: dict[str, _NodeLayout], edges: list[_EdgeRef], title: _NodeLayout | None) -> None:
    if not nodes:
        return

    by_layer: dict[int, list[_NodeLayout]] = {}
    for node in nodes.values():
        by_layer.setdefault(node.layer, []).append(node)
    for layer_nodes in by_layer.values():
        layer_nodes.sort(key=lambda n: n.id)

    _order_nodes_in_layers(by_layer, edges)

    y_cursor = 96.0
    if title is not None:
        title.x = 0.0
        title.y = 34.0
        y_cursor = title.y + title.height / 2.0 + 38.0

    for layer in sorted(by_layer):
        layer_nodes = by_layer[layer]
        total_w = sum(node.width for node in layer_nodes) + _NODE_GAP * max(0, len(layer_nodes) - 1)
        x_cursor = -total_w / 2.0
        max_h = 0.0
        for node in layer_nodes:
            node.x = x_cursor + node.width / 2.0
            node.y = y_cursor + node.height / 2.0
            x_cursor += node.width + _NODE_GAP
            max_h = max(max_h, node.height)
        y_cursor += max_h + _LAYER_GAP


def _order_nodes_in_layers(by_layer: dict[int, list[_NodeLayout]], edges: list[_EdgeRef]) -> None:
    index_by_id: dict[str, int] = {}
    for layer_nodes in by_layer.values():
        for idx, node in enumerate(layer_nodes):
            index_by_id[node.id] = idx

    incoming: dict[str, list[str]] = {}
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        outgoing.setdefault(edge.from_id, []).append(edge.to_id)
        incoming.setdefault(edge.to_id, []).append(edge.from_id)

    for _ in range(3):
        for layer in sorted(by_layer):
            layer_nodes = by_layer[layer]
            if len(layer_nodes) < 2:
                continue
            weighted: list[tuple[float, str, _NodeLayout]] = []
            for node in layer_nodes:
                neighbours = incoming.get(node.id, []) + outgoing.get(node.id, [])
                positions = [index_by_id[nid] for nid in neighbours if nid in index_by_id]
                bary = (sum(positions) / len(positions)) if positions else float(index_by_id[node.id])
                weighted.append((bary, node.id, node))
            weighted.sort(key=lambda item: (item[0], item[1]))
            by_layer[layer] = [item[2] for item in weighted]
            for idx, node in enumerate(by_layer[layer]):
                index_by_id[node.id] = idx


def _route_edges(nodes: dict[str, _NodeLayout], edges_ref: list[_EdgeRef], style: Style) -> list[_EdgeLayout]:
    edges: list[_EdgeLayout] = []
    all_nodes = list(nodes.values())
    occupied_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    back_idx = 0

    port_totals = _count_ports(nodes, edges_ref)
    port_used: dict[tuple[str, str], int] = {}
    content_min_x = min(node.x - node.width / 2.0 for node in all_nodes) if all_nodes else -100.0
    content_max_x = max(node.x + node.width / 2.0 for node in all_nodes) if all_nodes else 100.0
    content_max_y = max(node.y + node.height / 2.0 for node in all_nodes) if all_nodes else 100.0

    for edge_ref in edges_ref:
        from_node = nodes[edge_ref.from_id]
        to_node = nodes[edge_ref.to_id]
        is_back_edge = to_node.layer < from_node.layer

        start_side, end_side = _pick_port_sides(from_node, to_node, is_back_edge)
        start_slot = port_used.get((from_node.id, start_side), 0)
        end_slot = port_used.get((to_node.id, end_side), 0)
        start_total = port_totals.get((from_node.id, start_side), 1)
        end_total = port_totals.get((to_node.id, end_side), 1)
        port_used[(from_node.id, start_side)] = start_slot + 1
        port_used[(to_node.id, end_side)] = end_slot + 1

        start = _edge_port_with_slot(from_node, start_side, start_slot, start_total)
        end = _edge_port_with_slot(to_node, end_side, end_slot, end_total)

        label_lines: list[str] = []
        label_font = max(8, style.font_size - 2)
        label_width = 0.0
        label_height = 0.0
        if edge_ref.source.label:
            label_lines = _ENGINE.wrap_text(edge_ref.source.label, 180.0, label_font)
            label_width = max(_ENGINE.measure(line, label_font)[0] for line in label_lines) + 6.0
            label_height = len(label_lines) * (label_font * 1.25) + 2.0

        points = _build_edge_path(
            from_node=from_node,
            to_node=to_node,
            start=start,
            end=end,
            is_back_edge=is_back_edge,
            all_nodes=all_nodes,
            occupied_segments=occupied_segments,
            content_min_x=content_min_x,
            content_max_x=content_max_x,
            content_max_y=content_max_y,
            back_index=back_idx,
        )
        if is_back_edge:
            back_idx += 1

        for idx in range(len(points) - 1):
            occupied_segments.append((points[idx], points[idx + 1]))

        edges.append(
            _EdgeLayout(
                id=edge_ref.source.id,
                source=edge_ref.source,
                from_id=edge_ref.from_id,
                to_id=edge_ref.to_id,
                points=points,
                label_lines=label_lines,
                label_font_size=label_font,
                label_width=label_width,
                label_height=label_height,
                label_bbox=None,
                is_back_edge=is_back_edge,
            )
        )

    return edges


def _place_edge_labels(edges: list[_EdgeLayout], nodes: dict[str, _NodeLayout]) -> None:
    node_rects = [_node_rect(node) for node in nodes.values()]
    placed_rects: list[tuple[float, float, float, float]] = []

    for edge in edges:
        if not edge.label_lines:
            edge.label_bbox = None
            continue
        candidates = _build_label_candidates(edge.points, edge.label_width, edge.label_height)
        if not candidates:
            mx, my = _polyline_midpoint(edge.points)
            candidates = [(mx - edge.label_width / 2.0, my - edge.label_height / 2.0, edge.label_width, edge.label_height)]

        best_rect = min(
            candidates,
            key=lambda rect: _score_label_rect(rect, node_rects, placed_rects, edge.points),
        )
        edge.label_bbox = best_rect
        placed_rects.append(best_rect)


def _count_ports(nodes: dict[str, _NodeLayout], edges: list[_EdgeRef]) -> dict[tuple[str, str], int]:
    totals: dict[tuple[str, str], int] = {}
    for edge in edges:
        from_node = nodes[edge.from_id]
        to_node = nodes[edge.to_id]
        is_back_edge = to_node.layer < from_node.layer
        start_side, end_side = _pick_port_sides(from_node, to_node, is_back_edge)
        totals[(from_node.id, start_side)] = totals.get((from_node.id, start_side), 0) + 1
        totals[(to_node.id, end_side)] = totals.get((to_node.id, end_side), 0) + 1
    return totals


def _pick_port_sides(from_node: _NodeLayout, to_node: _NodeLayout, is_back_edge: bool) -> tuple[str, str]:
    if is_back_edge:
        side = "left" if to_node.x <= from_node.x else "right"
        return ("bottom", side)
    dx = to_node.x - from_node.x
    dy = to_node.y - from_node.y
    if abs(dx) >= abs(dy):
        return ("right", "left") if dx >= 0 else ("left", "right")
    return ("bottom", "top") if dy >= 0 else ("top", "bottom")


def _edge_port_with_slot(node: _NodeLayout, side: str, slot: int, total: int) -> tuple[float, float]:
    offset = 0.0
    if total > 1:
        span = (node.height - 16.0) if side in {"left", "right"} else (node.width - 16.0)
        step = span / max(1, total - 1)
        offset = -span / 2.0 + step * slot
    if side == "left":
        return (node.x - node.width / 2.0, node.y + offset)
    if side == "right":
        return (node.x + node.width / 2.0, node.y + offset)
    if side == "top":
        return (node.x + offset, node.y - node.height / 2.0)
    return (node.x + offset, node.y + node.height / 2.0)


def _build_edge_path(
    from_node: _NodeLayout,
    to_node: _NodeLayout,
    start: tuple[float, float],
    end: tuple[float, float],
    is_back_edge: bool,
    all_nodes: list[_NodeLayout],
    occupied_segments: list[tuple[tuple[float, float], tuple[float, float]]],
    content_min_x: float,
    content_max_x: float,
    content_max_y: float,
    back_index: int,
) -> list[tuple[float, float]]:
    obstacles = [node for node in all_nodes if node.id not in {from_node.id, to_node.id}]

    candidates: list[list[tuple[float, float]]]
    if is_back_edge:
        side = "left" if to_node.x <= from_node.x else "right"
        lane_gap = 30.0 + back_index * 18.0
        lane_x = (content_min_x - lane_gap) if side == "left" else (content_max_x + lane_gap)
        clearance_y = max(content_max_y + 16.0, start[1] + 26.0 + back_index * 8.0)
        candidates = [
            [start, (start[0], clearance_y), (lane_x, clearance_y), (lane_x, end[1]), end],
            [start, (lane_x, start[1]), (lane_x, end[1]), end],
        ]
    else:
        if abs(start[0] - end[0]) <= 1e-3 or abs(start[1] - end[1]) <= 1e-3:
            candidates = [[start, end]]
        else:
            candidates = []
            candidates.extend([
                [start, (end[0], start[1]), end],
                [start, (start[0], end[1]), end],
            ])

    cleaned = [_cleanup_path(path) for path in candidates]
    scored = sorted(
        cleaned,
        key=lambda path: _score_path(path, obstacles, occupied_segments),
    )
    return scored[0] if scored else cleaned[0]


def _cleanup_path(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for px, py in points:
        if not out or math.hypot(px - out[-1][0], py - out[-1][1]) > 1e-3:
            out.append((px, py))
    return out


def _score_path(
    points: list[tuple[float, float]],
    obstacles: list[_NodeLayout],
    occupied_segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> tuple[int, int, int, float]:
    node_hits = 0
    edge_hits = 0
    length = 0.0
    for idx in range(len(points) - 1):
        p1 = points[idx]
        p2 = points[idx + 1]
        length += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        for node in obstacles:
            if _segment_hits_node(p1, p2, node, padding=6.0):
                node_hits += 1
        # Пересечения с другими рёбрами штрафуем слабо, чтобы не уводить трассы в огромные обходы.
        for seg1, seg2 in occupied_segments:
            if _segments_intersect(p1, p2, seg1, seg2):
                edge_hits += 1
    bends = max(0, len(points) - 2)
    return (node_hits, edge_hits // 3, bends, length)


def _segment_hits_node(
    p1: tuple[float, float],
    p2: tuple[float, float],
    node: _NodeLayout,
    padding: float,
) -> bool:
    x1 = node.x - node.width / 2.0 - padding
    x2 = node.x + node.width / 2.0 + padding
    y1 = node.y - node.height / 2.0 - padding
    y2 = node.y + node.height / 2.0 + padding

    if abs(p1[0] - p2[0]) < 1e-3:
        x = p1[0]
        if x < x1 or x > x2:
            return False
        seg_y1, seg_y2 = sorted((p1[1], p2[1]))
        return not (seg_y2 < y1 or seg_y1 > y2)
    if abs(p1[1] - p2[1]) < 1e-3:
        y = p1[1]
        if y < y1 or y > y2:
            return False
        seg_x1, seg_x2 = sorted((p1[0], p2[0]))
        return not (seg_x2 < x1 or seg_x1 > x2)
    return False


def _segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    a_vertical = abs(a1[0] - a2[0]) < 1e-3
    b_vertical = abs(b1[0] - b2[0]) < 1e-3
    if a_vertical == b_vertical:
        return False
    if a_vertical:
        vx = a1[0]
        hy = b1[1]
        ay1, ay2 = sorted((a1[1], a2[1]))
        bx1, bx2 = sorted((b1[0], b2[0]))
    else:
        vx = b1[0]
        hy = a1[1]
        ay1, ay2 = sorted((b1[1], b2[1]))
        bx1, bx2 = sorted((a1[0], a2[0]))
    return (bx1 < vx < bx2) and (ay1 < hy < ay2)


def _build_label_candidates(
    points: list[tuple[float, float]],
    label_width: float,
    label_height: float,
) -> list[tuple[float, float, float, float]]:
    candidates: list[tuple[float, float, float, float]] = []
    for idx in range(len(points) - 1):
        x1, y1 = points[idx]
        x2, y2 = points[idx + 1]
        seg_len = math.hypot(x2 - x1, y2 - y1)
        if seg_len < max(label_width, label_height) + 12.0:
            continue
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0
        if abs(y2 - y1) <= abs(x2 - x1):
            candidates.append((mx - label_width / 2.0, my - label_height - 6.0, label_width, label_height))
            candidates.append((mx - label_width / 2.0, my + 6.0, label_width, label_height))
        else:
            candidates.append((mx + 8.0, my - label_height / 2.0, label_width, label_height))
            candidates.append((mx - label_width - 8.0, my - label_height / 2.0, label_width, label_height))
    return candidates


def _score_label_rect(
    rect: tuple[float, float, float, float],
    node_rects: list[tuple[float, float, float, float]],
    placed_rects: list[tuple[float, float, float, float]],
    points: list[tuple[float, float]],
) -> tuple[int, int, float]:
    overlap_nodes = sum(1 for node_rect in node_rects if _rects_intersect(rect, node_rect))
    overlap_labels = sum(1 for placed in placed_rects if _rects_intersect(rect, placed))
    center_x = rect[0] + rect[2] / 2.0
    center_y = rect[1] + rect[3] / 2.0
    anchor_x, anchor_y = _polyline_midpoint(points)
    distance = math.hypot(center_x - anchor_x, center_y - anchor_y)
    return (overlap_nodes, overlap_labels, distance)


def _node_rect(node: _NodeLayout) -> tuple[float, float, float, float]:
    return (node.x - node.width / 2.0, node.y - node.height / 2.0, node.width, node.height)


def _rects_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])


def _polyline_midpoint(points: list[tuple[float, float]]) -> tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    if len(points) == 1:
        return points[0]
    lengths: list[float] = []
    total = 0.0
    for idx in range(len(points) - 1):
        x1, y1 = points[idx]
        x2, y2 = points[idx + 1]
        seg_len = math.hypot(x2 - x1, y2 - y1)
        lengths.append(seg_len)
        total += seg_len
    target = total / 2.0
    walked = 0.0
    for idx, seg_len in enumerate(lengths):
        if walked + seg_len >= target and seg_len > 1e-6:
            x1, y1 = points[idx]
            x2, y2 = points[idx + 1]
            ratio = (target - walked) / seg_len
            return (x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio)
        walked += seg_len
    return points[-1]


def _place_free_texts(free_texts: list[_NodeLayout], nodes: dict[str, _NodeLayout], title: _NodeLayout | None) -> None:
    if not free_texts:
        return
    lowest = 80.0
    if nodes:
        lowest = max(lowest, max(node.y + node.height / 2.0 for node in nodes.values()) + 48.0)
    elif title is not None:
        lowest = title.y + title.height / 2.0 + 40.0

    x_cursor = 0.0
    for text_node in free_texts:
        text_node.x = x_cursor
        text_node.y = lowest + text_node.height / 2.0
        lowest += text_node.height + 22.0


def _fit_canvas(
    nodes: dict[str, _NodeLayout],
    edges: list[_EdgeLayout],
    title: _NodeLayout | None,
    free_texts: list[_NodeLayout],
) -> tuple[float, float]:
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    def include_rect(x: float, y: float, w: float, h: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)

    if title is not None:
        include_rect(title.x - title.width / 2.0, title.y - title.height / 2.0, title.width, title.height)
    for node in nodes.values():
        include_rect(node.x - node.width / 2.0, node.y - node.height / 2.0, node.width, node.height)
    for text_node in free_texts:
        include_rect(text_node.x - text_node.width / 2.0, text_node.y - text_node.height / 2.0, text_node.width, text_node.height)
    for edge in edges:
        for px, py in edge.points:
            include_rect(px, py, 1.0, 1.0)
        if edge.label_bbox is not None:
            include_rect(*edge.label_bbox)

    if not math.isfinite(min_x):
        return 400.0, 320.0

    width = (max_x - min_x) + _CANVAS_PADDING * 2
    height = (max_y - min_y) + _CANVAS_PADDING * 2

    # Соотношение стремится к 1:1, но без агрессивного увеличения.
    long_side = max(width, height)
    short_side = min(width, height)
    target_short = max(short_side, long_side * 0.9)
    if width < height:
        width = target_short
    else:
        height = target_short

    return max(300.0, width), max(260.0, height)


def _shift_to_canvas(
    nodes: dict[str, _NodeLayout],
    edges: list[_EdgeLayout],
    title: _NodeLayout | None,
    free_texts: list[_NodeLayout],
    canvas_width: float,
    canvas_height: float,
) -> None:
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    def include_rect(x: float, y: float, w: float, h: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)

    if title is not None:
        include_rect(title.x - title.width / 2.0, title.y - title.height / 2.0, title.width, title.height)
    for node in nodes.values():
        include_rect(node.x - node.width / 2.0, node.y - node.height / 2.0, node.width, node.height)
    for text_node in free_texts:
        include_rect(text_node.x - text_node.width / 2.0, text_node.y - text_node.height / 2.0, text_node.width, text_node.height)
    for edge in edges:
        for px, py in edge.points:
            include_rect(px, py, 1.0, 1.0)
        if edge.label_bbox is not None:
            include_rect(*edge.label_bbox)

    if not math.isfinite(min_x):
        return

    content_width = max_x - min_x
    content_height = max_y - min_y
    shift_x = (canvas_width - content_width) / 2.0 - min_x
    shift_y = (canvas_height - content_height) / 2.0 - min_y

    if title is not None:
        title.x += shift_x
        title.y += shift_y
    for node in nodes.values():
        node.x += shift_x
        node.y += shift_y
    for text_node in free_texts:
        text_node.x += shift_x
        text_node.y += shift_y
    for edge in edges:
        edge.points = [(px + shift_x, py + shift_y) for px, py in edge.points]
        if edge.label_bbox is not None:
            lx, ly, lw, lh = edge.label_bbox
            edge.label_bbox = (lx + shift_x, ly + shift_y, lw, lh)


def _render_node(node: _NodeLayout, style: Style) -> list[str]:
    stroke = node.source.style.stroke if (node.source.style and node.source.style.stroke) else style.stroke_color
    fill = node.source.style.fill if (node.source.style and node.source.style.fill) else style.fill_color
    stroke_w = node.source.style.stroke_width if (node.source.style and node.source.style.stroke_width is not None) else 1.5
    x = node.x - node.width / 2.0
    y = node.y - node.height / 2.0

    lines = [
        f'  <rect x="{x:.1f}" y="{y:.1f}" width="{node.width:.1f}" height="{node.height:.1f}" '
        f'stroke="{stroke}" fill="{fill}" stroke-width="{stroke_w}" rx="6"/>'
    ]
    lines.extend(_render_node_text(node, style, anchor="middle", bold=False))
    return lines


def _render_node_text(node: _NodeLayout, style: Style, anchor: str, bold: bool) -> list[str]:
    fill = node.source.style.stroke if (node.source.style and node.source.style.stroke) else style.stroke_color
    text_lines = node.lines
    total_height = len(text_lines) * node.line_height
    start_y = node.y - total_height / 2.0 + node.line_height / 2.0
    out: list[str] = []
    for idx, line in enumerate(text_lines):
        render_lines, _ = _ENGINE.render_line(
            text=line,
            x=node.x,
            y=start_y + idx * node.line_height,
            font_size=node.font_size,
            fill=fill,
            text_anchor=anchor,
        )
        out.extend(render_lines)
    if bold:
        # Ziamath не всегда учитывает SVG font-weight; заголовок выделяем лёгкой линией.
        underline_y = node.y + node.height / 2.0 + 4.0
        out.append(
            f'  <line x1="{(node.x - node.width / 2.0):.1f}" y1="{underline_y:.1f}" '
            f'x2="{(node.x + node.width / 2.0):.1f}" y2="{underline_y:.1f}" stroke="{fill}" stroke-width="1"/>'
        )
    return out


def _render_edge(edge: _EdgeLayout, style: Style, include_label: bool) -> list[str]:
    stroke = edge.source.style.stroke if (edge.source.style and edge.source.style.stroke) else style.stroke_color
    stroke_w = edge.source.style.stroke_width if (edge.source.style and edge.source.style.stroke_width is not None) else 1.5
    out: list[str] = []
    if len(edge.points) == 2:
        (x1, y1), (x2, y2) = edge.points
        out.append(
            f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{stroke_w}" marker-end="url(#arrow_obj)"/>'
        )
    else:
        points_attr = " ".join(f"{px:.1f},{py:.1f}" for px, py in edge.points)
        out.append(
            f'  <polyline points="{points_attr}" fill="none" stroke="{stroke}" '
            f'stroke-width="{stroke_w}" marker-end="url(#arrow_obj)"/>'
        )

    if include_label and edge.label_bbox is not None and edge.label_lines:
        out.extend(_render_edge_label(edge, style))
    return out


def _render_edge_label(edge: _EdgeLayout, style: Style) -> list[str]:
    if edge.label_bbox is None or not edge.label_lines:
        return []
    out: list[str] = []
    if style.theme == "light":
        label_bg = "white"
    else:
        label_bg = "#111111"
    lx, ly, lw, lh = edge.label_bbox
    out.append(f'  <rect x="{lx:.1f}" y="{ly:.1f}" width="{lw:.1f}" height="{lh:.1f}" fill="{label_bg}" stroke="none"/>')
    line_h = edge.label_font_size * 1.25
    text_y = ly + line_h / 2.0 + 1.0
    for line in edge.label_lines:
        text_lines, _ = _ENGINE.render_line(
            text=line,
            x=lx + lw / 2.0,
            y=text_y,
            font_size=edge.label_font_size,
            fill=style.stroke_color,
            text_anchor="middle",
        )
        out.extend(text_lines)
        text_y += line_h
    return out
