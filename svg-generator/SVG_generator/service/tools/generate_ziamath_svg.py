#!/usr/bin/env python3
from pathlib import Path

import ziamath


def main() -> None:
    svg = ziamath.Text("f(x) \\text{ непрерывна в } x_0 \\iff \\begin{cases} 1.\\, f(x_0) \\text{ определена} \\\\ 2.\\, \\exists \\lim_{x \\to x_0} f(x) \\\\ 3.\\, \\lim_{x \\to x_0} f(x) = f(x_0) \\end{cases}").svg()
    output_path = Path("formula.svg")
    output_path.write_text(svg, encoding="utf-8")

    print(f"SVG сохранен в: {output_path.resolve()}")


if __name__ == "__main__":
    main()
