# Variance benchmark of the geometry pipeline

- Model: `meta-llama/Llama-3.3-70B-Instruct-Turbo`
- Runs per problem: **3**
- Generated at: 2026-05-08 20:37:44
- Total wall time: 50.3 s

## Per-problem aggregates

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

## Fix-rate (validation triggered LLM retry)

Overall: **0.0** (0/3 cells).

| Problem | cells | fix cells | rate |
|---|---:|---:|---:|
| task16_parallelogram_diagonals | 3 | 0 | 0.0 |

