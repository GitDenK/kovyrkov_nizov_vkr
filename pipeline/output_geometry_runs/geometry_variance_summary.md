# Variance benchmark of the geometry pipeline

- Model: `meta-llama/Llama-3.3-70B-Instruct-Turbo`
- Runs per problem: **3**
- Generated at: 2026-05-08 21:11:04
- Total wall time: 0.0 s

## Per-problem aggregates

### task16_trapezoid

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 13.34 | 8.75 | 6.59 | 23.23 |
| llm_sec | 13.33 | 8.75 | 6.58 | 23.22 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5075.0 | 0.0 | 5075 | 5075 |
| tokens_out | 1099.33 | 237.15 | 928 | 1370 |
| steps_total | 3.67 | 1.15 | 3 | 5 |
| objects_total | 12.67 | 1.15 | 12 | 14 |
| annotations_total | 2.67 | 2.08 | 1 | 5 |

### task16_rhombus_diagonals

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 11.12 | 3.79 | 6.76 | 13.61 |
| llm_sec | 11.12 | 3.79 | 6.76 | 13.6 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5068.0 | 0.0 | 5068 | 5068 |
| tokens_out | 1274.33 | 57.81 | 1208 | 1314 |
| steps_total | 3.67 | 0.58 | 3 | 4 |
| objects_total | 14.0 | 0.0 | 14 | 14 |
| annotations_total | 4.0 | 0.0 | 4 | 4 |

### task14_pyramid_apex_to_face

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 16.14 | 12.97 | 5.7 | 30.65 |
| llm_sec | 16.14 | 12.96 | 5.7 | 30.65 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5058.0 | 0.0 | 5058 | 5058 |
| tokens_out | 942.0 | 110.01 | 876 | 1069 |
| steps_total | 2.33 | 0.58 | 2 | 3 |
| objects_total | 11.33 | 0.58 | 11 | 12 |
| annotations_total | 3.33 | 0.58 | 3 | 4 |

### task14_prism_section

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 15.77 | 8.28 | 10.92 | 25.33 |
| llm_sec | 15.77 | 8.28 | 10.92 | 25.33 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5082.0 | 0.0 | 5082 | 5082 |
| tokens_out | 1378.67 | 37.17 | 1336 | 1404 |
| steps_total | 4.33 | 0.58 | 4 | 5 |
| objects_total | 20.0 | 1.73 | 18 | 21 |
| annotations_total | 2.0 | 1.73 | 1 | 4 |

### task16_triangle_circumscribed

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 10.65 | 2.02 | 8.69 | 12.72 |
| llm_sec | 10.65 | 2.02 | 8.68 | 12.72 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5080.0 | 0.0 | 5080 | 5080 |
| tokens_out | 960.67 | 125.32 | 816 | 1036 |
| steps_total | 3.0 | 0.0 | 3 | 3 |
| objects_total | 8.0 | 0.0 | 8 | 8 |
| annotations_total | 5.0 | 1.73 | 3 | 6 |

### task16_parallelogram_diagonals

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 16.77 | 3.39 | 14.24 | 20.62 |
| llm_sec | 16.76 | 3.39 | 14.23 | 20.61 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5066.0 | 0.0 | 5066 | 5066 |
| tokens_out | 1890.67 | 362.09 | 1480 | 2164 |
| steps_total | 4.0 | 0.0 | 4 | 4 |
| objects_total | 12.33 | 1.53 | 11 | 14 |
| annotations_total | 5.67 | 3.21 | 2 | 8 |

### task14_cube_diagonal_section

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 23.28 | 9.7 | 17.23 | 34.46 |
| llm_sec | 23.27 | 9.7 | 17.23 | 34.46 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5073.0 | 0.0 | 5073 | 5073 |
| tokens_out | 1576.67 | 104.51 | 1456 | 1638 |
| steps_total | 4.0 | 0.0 | 4 | 4 |
| objects_total | 26.0 | 2.0 | 24 | 28 |
| annotations_total | 3.0 | 0.0 | 3 | 3 |

### task14_pyramid_dihedral_angle

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 15.07 | 6.32 | 10.94 | 22.34 |
| llm_sec | 15.06 | 6.32 | 10.93 | 22.34 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5083.0 | 0.0 | 5083 | 5083 |
| tokens_out | 1523.33 | 139.17 | 1414 | 1680 |
| steps_total | 4.67 | 0.58 | 4 | 5 |
| objects_total | 19.0 | 1.73 | 18 | 21 |
| annotations_total | 3.33 | 1.15 | 2 | 4 |

## Fix-rate (validation triggered LLM retry)

Overall: **0.0** (0/24 cells).

| Problem | cells | fix cells | rate |
|---|---:|---:|---:|
| task16_trapezoid | 3 | 0 | 0.0 |
| task16_rhombus_diagonals | 3 | 0 | 0.0 |
| task14_pyramid_apex_to_face | 3 | 0 | 0.0 |
| task14_prism_section | 3 | 0 | 0.0 |
| task16_triangle_circumscribed | 3 | 0 | 0.0 |
| task16_parallelogram_diagonals | 3 | 0 | 0.0 |
| task14_cube_diagonal_section | 3 | 0 | 0.0 |
| task14_pyramid_dihedral_angle | 3 | 0 | 0.0 |

## Answer-vis warning rate (post-condition validator)

Overall: **0.208** (5/24 cells flagged).

| Problem | cells | flagged | rate |
|---|---:|---:|---:|
| task16_trapezoid | 3 | 0 | 0.0 |
| task16_rhombus_diagonals | 3 | 1 | 0.333 |
| task14_pyramid_apex_to_face | 3 | 3 | 1.0 |
| task14_prism_section | 3 | 0 | 0.0 |
| task16_triangle_circumscribed | 3 | 0 | 0.0 |
| task16_parallelogram_diagonals | 3 | 0 | 0.0 |
| task14_cube_diagonal_section | 3 | 0 | 0.0 |
| task14_pyramid_dihedral_angle | 3 | 1 | 0.333 |

