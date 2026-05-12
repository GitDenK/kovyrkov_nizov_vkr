# Variance benchmark of the geometry pipeline

- Model: `meta-llama/Llama-3.3-70B-Instruct-Turbo`
- Runs per problem: **3**
- Generated at: 2026-05-08 21:21:40
- Total wall time: 501.4 s

## Per-problem aggregates

### task14_pyramid_apex_to_face

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 58.44 | 9.42 | 48.59 | 67.37 |
| llm_sec | 58.43 | 9.42 | 48.59 | 67.36 |
| llm_calls_total | 2.0 | 0.0 | 2 | 2 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 1.0 | 0.0 | 1 | 1 |
| tokens_in | 11234.0 | 136.84 | 11154 | 11392 |
| tokens_out | 2140.0 | 261.63 | 1982 | 2442 |
| steps_total | 2.33 | 0.58 | 2 | 3 |
| objects_total | 11.33 | 0.58 | 11 | 12 |
| annotations_total | 3.33 | 0.58 | 3 | 4 |

### task14_pyramid_dihedral_angle

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 79.28 | 45.72 | 29.82 | 120.0 |
| llm_sec | 79.27 | 45.72 | 29.81 | 119.99 |
| llm_calls_total | 1.67 | 0.58 | 1 | 2 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.67 | 0.58 | 0 | 1 |
| tokens_in | 9626.33 | 3937.73 | 5083 | 12054 |
| tokens_out | 2781.0 | 1055.85 | 1592 | 3609 |
| steps_total | 5.33 | 0.58 | 5 | 6 |
| objects_total | 18.67 | 1.53 | 17 | 20 |
| annotations_total | 4.0 | 1.0 | 3 | 5 |

### task16_rhombus_diagonals

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| wall_sec | 29.41 | 27.68 | 12.4 | 61.34 |
| llm_sec | 29.4 | 27.68 | 12.39 | 61.34 |
| llm_calls_total | 1.0 | 0.0 | 1 | 1 |
| llm_calls_plan | 1.0 | 0.0 | 1 | 1 |
| llm_calls_fix | 0.0 | 0.0 | 0 | 0 |
| tokens_in | 5068.0 | 0.0 | 5068 | 5068 |
| tokens_out | 1571.67 | 228.18 | 1394 | 1829 |
| steps_total | 5.0 | 2.65 | 3 | 8 |
| objects_total | 14.67 | 0.58 | 14 | 15 |
| annotations_total | 5.33 | 2.52 | 3 | 8 |

## Fix-rate (validation triggered LLM retry)

Overall: **0.556** (5/9 cells).

| Problem | cells | fix cells | rate |
|---|---:|---:|---:|
| task14_pyramid_apex_to_face | 3 | 3 | 1.0 |
| task14_pyramid_dihedral_angle | 3 | 2 | 0.667 |
| task16_rhombus_diagonals | 3 | 0 | 0.0 |

## Answer-vis warning rate (post-condition validator)

Overall: **0.0** (0/9 cells flagged).

| Problem | cells | flagged | rate |
|---|---:|---:|---:|
| task14_pyramid_apex_to_face | 3 | 0 | 0.0 |
| task14_pyramid_dihedral_angle | 3 | 0 | 0.0 |
| task16_rhombus_diagonals | 3 | 0 | 0.0 |

