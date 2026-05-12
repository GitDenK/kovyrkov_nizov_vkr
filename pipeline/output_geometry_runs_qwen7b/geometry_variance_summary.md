# Variance benchmark of the geometry pipeline

- Model: `Qwen/Qwen2.5-7B-Instruct-Turbo`
- Runs per problem: **3**
- Generated at: 2026-05-08 20:45:39
- Total wall time: 387.7 s

## Per-problem aggregates

### task16_trapezoid

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 15.33 | 0.97 | 14.62 | 16.44 |
| llm_sec | 15.33 | 0.97 | 14.62 | 16.43 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5285.0 | 0.0 | 5285 | 5285 |
| tokens_out | 1614.0 | 86.64 | 1552 | 1713 |
| steps_total | 5.33 | 0.58 | 5 | 6 |
| objects_total | 14.33 | 1.15 | 13 | 15 |
| annotations_total | 6.67 | 2.52 | 4 | 9 |

### task16_rhombus_diagonals

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 16.45 | 9.4 | 10.23 | 27.26 |
| llm_sec | 16.45 | 9.39 | 10.23 | 27.25 |
| llm_calls_total | 1.33 | 0.58 | 1 | 2 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.33 | 0.58 | 0 | 1 |
| tokens_in | 7478.33 | 3809.36 | 5279 | 11877 |
| tokens_out | 1731.0 | 1058.51 | 1098 | 2953 |
| steps_total | 3.67 | 0.58 | 3 | 4 |
| objects_total | 11.0 | 1.73 | 10 | 13 |
| annotations_total | 4.67 | 0.58 | 4 | 5 |

### task14_pyramid_apex_to_face

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 12.48 | 1.71 | 10.83 | 14.23 |
| llm_sec | 12.48 | 1.71 | 10.82 | 14.23 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5264.0 | 0.0 | 5264 | 5264 |
| tokens_out | 1242.33 | 40.22 | 1209 | 1287 |
| steps_total | 4.67 | 0.58 | 4 | 5 |
| objects_total | 14.67 | 0.58 | 14 | 15 |
| annotations_total | 2.67 | 0.58 | 2 | 3 |

### task14_prism_section

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 17.57 | 5.24 | 14.05 | 23.59 |
| llm_sec | 17.56 | 5.24 | 14.04 | 23.58 |
| llm_calls_total | 1.33 | 0.58 | 1 | 2 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.33 | 0.58 | 0 | 1 |
| tokens_in | 7442.67 | 3725.06 | 5292 | 11744 |
| tokens_out | 1879.67 | 611.51 | 1440 | 2578 |
| steps_total | 5.33 | 1.53 | 4 | 7 |
| objects_total | 20.67 | 4.16 | 16 | 24 |
| annotations_total | 3.0 | 2.0 | 1 | 5 |

### task16_triangle_circumscribed

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 8.18 | 1.43 | 7.17 | 9.19 |
| llm_sec | 8.17 | 1.43 | 7.16 | 9.19 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5289.0 | 0.0 | 5289 | 5289 |
| tokens_out | 750.5 | 118.09 | 667 | 834 |
| steps_total | 2.0 | 0.0 | 2 | 2 |
| objects_total | 7.0 | 0.0 | 7 | 7 |
| annotations_total | 3.5 | 2.12 | 2 | 5 |

### task16_parallelogram_diagonals

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 16.54 | 2.54 | 14.49 | 19.39 |
| llm_sec | 16.53 | 2.54 | 14.49 | 19.38 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5273.0 | 0.0 | 5273 | 5273 |
| tokens_out | 1621.0 | 291.79 | 1401 | 1952 |
| steps_total | 4.67 | 1.15 | 4 | 6 |
| objects_total | 13.67 | 2.52 | 11 | 16 |
| annotations_total | 6.33 | 1.53 | 5 | 8 |

### task14_cube_diagonal_section

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 26.17 | 7.73 | 18.44 | 33.91 |
| llm_sec | 26.16 | 7.73 | 18.43 | 33.9 |
| llm_calls_total | 1.67 | 0.58 | 1 | 2 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.67 | 0.58 | 0 | 1 |
| tokens_in | 9770.33 | 3888.0 | 5285 | 12180 |
| tokens_out | 2502.67 | 1066.23 | 1348 | 3450 |
| steps_total | 4.67 | 1.15 | 4 | 6 |
| objects_total | 15.0 | 2.65 | 13 | 18 |
| annotations_total | 2.33 | 1.53 | 1 | 4 |

### task14_pyramid_dihedral_angle

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 15.85 | 2.39 | 13.82 | 18.48 |
| llm_sec | 15.84 | 2.39 | 13.81 | 18.47 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5290.0 | 0.0 | 5290 | 5290 |
| tokens_out | 1604.0 | 136.63 | 1471 | 1744 |
| steps_total | 5.33 | 0.58 | 5 | 6 |
| objects_total | 18.33 | 1.15 | 17 | 19 |
| annotations_total | 3.0 | 1.0 | 2 | 4 |

## Fix-rate (validation triggered LLM retry)

Overall: **0.174** (4/23 cells).

| Problem | cells | fix cells | rate |
|---|---:|---:|---:|
| task16_trapezoid | 3 | 0 | 0.0 |
| task16_rhombus_diagonals | 3 | 1 | 0.333 |
| task14_pyramid_apex_to_face | 3 | 0 | 0.0 |
| task14_prism_section | 3 | 1 | 0.333 |
| task16_triangle_circumscribed | 2 | 0 | 0.0 |
| task16_parallelogram_diagonals | 3 | 0 | 0.0 |
| task14_cube_diagonal_section | 3 | 2 | 0.667 |
| task14_pyramid_dihedral_angle | 3 | 0 | 0.0 |

