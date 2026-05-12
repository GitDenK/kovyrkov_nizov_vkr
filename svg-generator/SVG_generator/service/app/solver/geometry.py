"""
Sympy-утилиты для геометрических вычислений.
Используются как вспомогательные функции solver.py и будущих constraints.
"""

from sympy.geometry import Line, Point2D


def line_intersection(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> tuple[float, float] | None:
    """
    Находит пересечение двух прямых (p1→p2) и (p3→p4) через sympy.
    Возвращает (x, y) или None если прямые параллельны.
    """
    l1 = Line(Point2D(*p1), Point2D(*p2))
    l2 = Line(Point2D(*p3), Point2D(*p4))
    result = l1.intersection(l2)
    if not result:
        return None
    pt = result[0]
    return float(pt.x), float(pt.y)


def foot_of_perpendicular(
    vertex: tuple[float, float],
    base1: tuple[float, float],
    base2: tuple[float, float],
) -> tuple[float, float]:
    """
    Проекция точки vertex на прямую (base1→base2) через sympy.
    Возвращает координаты основания перпендикуляра.
    """
    line = Line(Point2D(*base1), Point2D(*base2))
    foot = line.perpendicular_segment(Point2D(*vertex)).p2
    return float(foot.x), float(foot.y)
