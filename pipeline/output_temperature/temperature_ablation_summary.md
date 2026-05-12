# Temperature ablation on task4

- Conspect: `conspects/task4.md`
- Model: `Qwen/Qwen2.5-7B-Instruct-Turbo`
- Runs per temperature: **3**
- Temperatures: [0.0, 0.3, 0.7]
- Generated at: 2026-05-08 20:52:38
- Total wall time: 392.7 s

## Per-temperature aggregates

### T = 0.0

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| total_sections | 20.0 | 0.0 | 20 | 20 |
| sections_analyzed | 20.0 | 0.0 | 20 | 20 |
| visuals_planned | 6.0 | 0.0 | 6 | 6 |
| total_tokens_in | 13700.0 | 0.0 | 13700 | 13700 |
| total_tokens_out | 2797.0 | 65.48 | 2741 | 2869 |
| total_time_sec | 34.76 | 2.23 | 32.94 | 37.24 |

### T = 0.3

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| total_sections | 20.0 | 0.0 | 20 | 20 |
| sections_analyzed | 19.67 | 0.58 | 19 | 20 |
| visuals_planned | 9.33 | 0.58 | 9 | 10 |
| total_tokens_in | 19493.67 | 947.89 | 18400 | 20078 |
| total_tokens_out | 3558.0 | 118.73 | 3421 | 3631 |
| total_time_sec | 50.23 | 14.74 | 39.55 | 67.05 |

### T = 0.7

| Metric | mean | stdev | min | max |
|---|---:|---:|---:|---:|
| total_sections | 20.0 | 0.0 | 20 | 20 |
| sections_analyzed | 20.0 | 0.0 | 20 | 20 |
| visuals_planned | 8.33 | 3.06 | 5 | 11 |
| total_tokens_in | 17411.33 | 4970.31 | 12028 | 21826 |
| total_tokens_out | 3275.67 | 654.77 | 2632 | 3941 |
| total_time_sec | 45.9 | 14.84 | 29.18 | 57.52 |

## Distinct outputs per temperature

| T | distinct visuals_planned | values |
|---|---:|---|
| 0.0 | 1 | 6, 6, 6 |
| 0.3 | 2 | 9, 10, 9 |
| 0.7 | 3 | 9, 11, 5 |

