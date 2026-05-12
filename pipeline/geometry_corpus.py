"""Small reference corpus of geometry problems for variance benchmarking.

The corpus is intentionally small (4 problems) and stable so that repeated runs
on the same model produce comparable metrics. Each entry contains:

- slug: short identifier used in output filenames;
- title: human-readable problem title (used in HTML output);
- domain: one of {"planimetry", "stereometry"};
- problem_text: full natural-language problem statement (RU).

Adding new problems: append a tuple to PROBLEMS.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeometryProblem:
    slug: str
    title: str
    domain: str
    problem_text: str


PROBLEMS: tuple[GeometryProblem, ...] = (
    GeometryProblem(
        slug="task16_trapezoid",
        title="Трапеция с перпендикулярными диагоналями",
        domain="planimetry",
        problem_text=(
            "В трапеции ABCD основания BC = 4 и AD = 9, "
            "диагонали AC = 12 и BD = 5. "
            "а) Докажите, что диагонали трапеции перпендикулярны. "
            "б) Найдите высоту трапеции."
        ),
    ),
    GeometryProblem(
        slug="task16_rhombus_diagonals",
        title="Ромб с известными диагоналями",
        domain="planimetry",
        problem_text=(
            "В ромбе ABCD диагонали AC и BD пересекаются в точке O, "
            "AC = 16, BD = 12. На стороне AB взята точка M такая, что AM = 5. "
            "Найдите расстояние от точки M до диагонали BD."
        ),
    ),
    GeometryProblem(
        slug="task14_pyramid_apex_to_face",
        title="Расстояние от вершины пирамиды до боковой грани",
        domain="stereometry",
        problem_text=(
            "В правильной треугольной пирамиде SABC сторона основания AB = 6, "
            "боковое ребро SA = 5. "
            "Найдите расстояние от вершины A до плоскости SBC."
        ),
    ),
    GeometryProblem(
        slug="task14_prism_section",
        title="Сечение правильной треугольной призмы",
        domain="stereometry",
        problem_text=(
            "В правильной треугольной призме ABCA1B1C1 со стороной основания, "
            "равной 6, и высотой, равной 4, "
            "точка M --- середина ребра CC1. "
            "Найдите площадь сечения призмы плоскостью, проходящей через "
            "точки A, B и M."
        ),
    ),
    GeometryProblem(
        slug="task16_triangle_circumscribed",
        title="Треугольник с описанной окружностью",
        domain="planimetry",
        problem_text=(
            "В треугольнике ABC угол A равен 60 градусам, сторона BC = 6. "
            "Около треугольника описана окружность с центром O. "
            "а) Найдите радиус окружности. "
            "б) Изобразите треугольник, описанную окружность и центр O."
        ),
    ),
    GeometryProblem(
        slug="task16_parallelogram_diagonals",
        title="Параллелограмм с заданным углом между диагоналями",
        domain="planimetry",
        problem_text=(
            "В параллелограмме ABCD стороны AB = 5 и AD = 8, "
            "угол между диагоналями равен 60 градусам. "
            "Диагонали пересекаются в точке O. "
            "Найдите длину диагонали AC."
        ),
    ),
    GeometryProblem(
        slug="task14_cube_diagonal_section",
        title="Сечение куба, проходящее через диагональ грани",
        domain="stereometry",
        problem_text=(
            "В кубе ABCDA1B1C1D1 с ребром, равным 4, "
            "точка M --- середина ребра CC1. "
            "Постройте сечение куба плоскостью, проходящей через "
            "точки A, M и вершину D1, и найдите его площадь."
        ),
    ),
    GeometryProblem(
        slug="task14_pyramid_dihedral_angle",
        title="Двугранный угол в правильной четырёхугольной пирамиде",
        domain="stereometry",
        problem_text=(
            "В правильной четырёхугольной пирамиде SABCD со стороной "
            "основания AB = 6 и высотой SO = 4 "
            "(где O --- центр основания) "
            "найдите двугранный угол при ребре основания AB. "
            "Постройте линейный угол этого двугранного угла."
        ),
    ),
)


def by_slug(slug: str) -> GeometryProblem:
    for p in PROBLEMS:
        if p.slug == slug:
            return p
    raise KeyError(f"Unknown problem slug: {slug}")
