## Measured simulation results

Executed 440 policy runs on 110 synthetic traces. Seeds: [11, 22, 33, 44, 55]. All results below were computed from `runs.json`.

Each cell is a mean across seeds. Intervals in `summary.csv` are two-sided 95% Student t intervals on seed-level statistics; tail percentiles are averaged across runs, not pooled. These intervals describe workload sampling variability, not hardware-model uncertainty. No multiple-comparison correction is applied.

### Main sweep (complete grid)

| Synthetic profile | Rate req/s | Policy | TTFT mean s | TPOT mean s | SLO % | Goodput req/s/GPU | P95 wait s | Jain length SLO |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| humaneval | 2 | edf | 0.026 | 0.014 | 100.0 | 0.685 | 0.013 | 1.000 |
| humaneval | 2 | fcfs | 0.026 | 0.014 | 100.0 | 0.685 | 0.013 | 1.000 |
| humaneval | 2 | sjf | 0.026 | 0.014 | 100.0 | 0.685 | 0.013 | 1.000 |
| humaneval | 2 | smart | 0.026 | 0.014 | 100.0 | 0.685 | 0.013 | 1.000 |
| humaneval | 4 | edf | 0.026 | 0.016 | 100.0 | 1.367 | 0.015 | 1.000 |
| humaneval | 4 | fcfs | 0.026 | 0.016 | 100.0 | 1.367 | 0.015 | 1.000 |
| humaneval | 4 | sjf | 0.026 | 0.016 | 100.0 | 1.367 | 0.015 | 1.000 |
| humaneval | 4 | smart | 0.026 | 0.016 | 100.0 | 1.367 | 0.015 | 1.000 |
| humaneval | 8 | edf | 0.027 | 0.088 | 70.4 | 1.886 | 8.969 | 0.998 |
| humaneval | 8 | fcfs | 0.027 | 0.088 | 70.7 | 1.894 | 6.290 | 0.997 |
| humaneval | 8 | sjf | 0.027 | 0.081 | 89.0 | 2.408 | 28.416 | 0.999 |
| humaneval | 8 | smart | 0.027 | 0.088 | 70.5 | 1.887 | 6.360 | 0.995 |
| humaneval | 16 | edf | 0.028 | 1.005 | 0.9 | 0.047 | 93.112 | 0.578 |
| humaneval | 16 | fcfs | 0.028 | 1.003 | 0.7 | 0.036 | 92.007 | 0.554 |
| humaneval | 16 | sjf | 0.028 | 0.842 | 43.3 | 2.336 | 133.102 | 0.997 |
| humaneval | 16 | smart | 0.028 | 1.003 | 0.7 | 0.036 | 92.008 | 0.554 |
| longbench | 0.5 | edf | 1.086 | 0.015 | 100.0 | 0.166 | 0.265 | 1.000 |
| longbench | 0.5 | fcfs | 1.086 | 0.015 | 100.0 | 0.166 | 0.265 | 1.000 |
| longbench | 0.5 | sjf | 1.086 | 0.015 | 100.0 | 0.166 | 0.265 | 1.000 |
| longbench | 0.5 | smart | 1.086 | 0.015 | 100.0 | 0.166 | 0.265 | 1.000 |
| longbench | 1 | edf | 1.173 | 0.016 | 100.0 | 0.315 | 1.189 | 1.000 |
| longbench | 1 | fcfs | 1.173 | 0.016 | 100.0 | 0.315 | 1.189 | 1.000 |
| longbench | 1 | sjf | 1.171 | 0.016 | 100.0 | 0.315 | 1.208 | 1.000 |
| longbench | 1 | smart | 1.176 | 0.016 | 100.0 | 0.315 | 1.183 | 1.000 |
| longbench | 2 | edf | 6.274 | 0.017 | 73.0 | 0.489 | 13.005 | 0.975 |
| longbench | 2 | fcfs | 6.274 | 0.017 | 73.0 | 0.489 | 13.005 | 0.975 |
| longbench | 2 | sjf | 3.981 | 0.017 | 90.4 | 0.618 | 15.168 | 0.997 |
| longbench | 2 | smart | 6.429 | 0.017 | 73.0 | 0.490 | 13.482 | 0.976 |
| longbench | 3 | edf | 32.503 | 0.018 | 2.3 | 0.023 | 55.579 | 0.353 |
| longbench | 3 | fcfs | 32.503 | 0.018 | 2.3 | 0.023 | 55.579 | 0.353 |
| longbench | 3 | sjf | 15.048 | 0.017 | 73.1 | 0.749 | 75.619 | 0.974 |
| longbench | 3 | smart | 32.583 | 0.018 | 0.9 | 0.009 | 56.112 | 0.200 |
| mixed | 1 | edf | 0.307 | 0.014 | 99.2 | 0.312 | 0.014 | 1.000 |
| mixed | 1 | fcfs | 0.307 | 0.014 | 99.2 | 0.312 | 0.014 | 1.000 |
| mixed | 1 | sjf | 0.307 | 0.014 | 99.2 | 0.312 | 0.014 | 1.000 |
| mixed | 1 | smart | 0.307 | 0.014 | 99.2 | 0.312 | 0.014 | 1.000 |
| mixed | 2 | edf | 0.442 | 0.017 | 96.4 | 0.660 | 0.810 | 0.999 |
| mixed | 2 | fcfs | 0.445 | 0.017 | 96.4 | 0.660 | 0.815 | 0.999 |
| mixed | 2 | sjf | 0.441 | 0.017 | 96.6 | 0.661 | 0.793 | 0.999 |
| mixed | 2 | smart | 0.445 | 0.017 | 96.3 | 0.660 | 0.806 | 0.999 |
| mixed | 3 | edf | 0.622 | 0.020 | 92.3 | 0.951 | 1.597 | 0.996 |
| mixed | 3 | fcfs | 0.679 | 0.020 | 89.6 | 0.922 | 1.840 | 0.994 |
| mixed | 3 | sjf | 0.612 | 0.021 | 92.5 | 0.953 | 1.693 | 0.997 |
| mixed | 3 | smart | 0.658 | 0.020 | 90.4 | 0.931 | 1.813 | 0.995 |
| mixed | 6 | edf | 2.855 | 0.178 | 25.6 | 0.520 | 30.222 | 0.923 |
| mixed | 6 | fcfs | 5.239 | 0.178 | 9.5 | 0.194 | 28.709 | 0.811 |
| mixed | 6 | sjf | 1.563 | 0.132 | 55.3 | 1.143 | 61.711 | 0.941 |
| mixed | 6 | smart | 4.706 | 0.179 | 13.4 | 0.273 | 28.096 | 0.871 |
| sharegpt | 1 | edf | 0.085 | 0.014 | 100.0 | 0.315 | 0.013 | 1.000 |
| sharegpt | 1 | fcfs | 0.085 | 0.014 | 100.0 | 0.315 | 0.013 | 1.000 |
| sharegpt | 1 | sjf | 0.085 | 0.014 | 100.0 | 0.315 | 0.013 | 1.000 |
| sharegpt | 1 | smart | 0.085 | 0.014 | 100.0 | 0.315 | 0.013 | 1.000 |
| sharegpt | 2 | edf | 0.100 | 0.017 | 100.0 | 0.685 | 0.017 | 1.000 |
| sharegpt | 2 | fcfs | 0.100 | 0.017 | 100.0 | 0.685 | 0.017 | 1.000 |
| sharegpt | 2 | sjf | 0.100 | 0.017 | 100.0 | 0.685 | 0.017 | 1.000 |
| sharegpt | 2 | smart | 0.100 | 0.017 | 100.0 | 0.685 | 0.017 | 1.000 |
| sharegpt | 4 | edf | 0.105 | 0.078 | 72.2 | 0.972 | 14.239 | 0.986 |
| sharegpt | 4 | fcfs | 0.105 | 0.077 | 71.7 | 0.964 | 10.692 | 0.992 |
| sharegpt | 4 | sjf | 0.105 | 0.080 | 84.0 | 1.141 | 33.609 | 0.996 |
| sharegpt | 4 | smart | 0.105 | 0.077 | 71.6 | 0.962 | 10.650 | 0.992 |
| sharegpt | 8 | edf | 0.126 | 0.598 | 4.3 | 0.116 | 100.186 | 0.831 |
| sharegpt | 8 | fcfs | 0.126 | 0.600 | 2.7 | 0.073 | 98.623 | 0.889 |
| sharegpt | 8 | sjf | 0.124 | 0.515 | 40.3 | 1.092 | 140.867 | 0.993 |
| sharegpt | 8 | smart | 0.127 | 0.600 | 2.7 | 0.073 | 98.616 | 0.883 |

### Priority policy versus FCFS

Differences below are paired by seed and trace. Positive SLO difference favors Smart; positive waiting-time difference means Smart has worse tail waiting. These are descriptive comparisons over the entire main grid, not a selected best case.

| Synthetic profile | Rate req/s | SLO difference percentage points (95% halfwidth) | P95 wait difference s (95% halfwidth) |
|---|---:|---:|---:|
| humaneval | 2 | +0.000 +/- 0.000 | +0.000 +/- 0.000 |
| humaneval | 4 | +0.000 +/- 0.000 | -0.000 +/- 0.000 |
| humaneval | 8 | -0.268 +/- 0.933 | +0.070 +/- 0.175 |
| humaneval | 16 | +0.000 +/- 0.000 | +0.001 +/- 0.014 |
| longbench | 0.5 | +0.000 +/- 0.000 | +0.000 +/- 0.000 |
| longbench | 1 | +0.000 +/- 0.000 | -0.006 +/- 0.017 |
| longbench | 2 | +0.064 +/- 1.735 | +0.477 +/- 0.499 |
| longbench | 3 | -1.382 +/- 2.582 | +0.533 +/- 2.753 |
| mixed | 1 | +0.000 +/- 0.000 | +0.000 +/- 0.000 |
| mixed | 2 | -0.125 +/- 0.347 | -0.009 +/- 0.020 |
| mixed | 3 | +0.831 +/- 0.897 | -0.026 +/- 0.191 |
| mixed | 6 | +3.899 +/- 3.239 | -0.613 +/- 0.989 |
| sharegpt | 1 | +0.000 +/- 0.000 | +0.000 +/- 0.000 |
| sharegpt | 2 | +0.000 +/- 0.000 | +0.000 +/- 0.000 |
| sharegpt | 4 | -0.106 +/- 1.062 | -0.042 +/- 0.116 |
| sharegpt | 8 | +0.004 +/- 0.146 | -0.008 +/- 0.047 |

Across 16 tested conditions, Smart's mean SLO attainment exceeds FCFS in 4, falls below it in 4, and ties in 8. Paired mean differences range from -1.382 to +3.899 percentage points. This does not establish universal superiority or novelty.

### Interpretation of measured tradeoffs

At mixed rate 3 req/s, mean joint SLO attainment is 89.58% (FCFS), 90.41% (Smart), 92.50% (SJF), and 92.33% (EDF). Mean run P95 queue wait is 1.840 s (FCFS), 1.813 s (Smart), 1.693 s (SJF), and 1.597 s (EDF). Aggregate attainment and tail waiting therefore need to be assessed together; a higher successful-request rate alone does not establish better fairness.

At mixed rate 6 req/s, mean joint SLO attainment is 9.55% (FCFS), 13.45% (Smart), 55.30% (SJF), and 25.64% (EDF). Mean run P95 queue wait is 28.709 s (FCFS), 28.096 s (Smart), 61.711 s (SJF), and 30.222 s (EDF). Aggregate attainment and tail waiting therefore need to be assessed together; a higher successful-request rate alone does not establish better fairness.

Removing both aging mechanisms changes mean mixed-rate-3 Smart attainment from 90.41% to 90.14% (-0.264 percentage points). This is one operating point, so it does not establish a general effect or a statistically reliable component benefit.

Removing the duration term changes mean mixed-rate-3 Smart attainment from 90.41% to 91.52% (+1.111 percentage points). This is one operating point, so it does not establish a general effect or a statistically reliable component benefit.


### Ablations at the configured mixed-workload rate

Every ablation includes all four policies and identical traces within that condition. The table shows Smart only; full comparison data are retained in the summary and run files.

| Condition | SLO % | P95 wait s | Jain profile SLO | Jain length SLO |
|---|---:|---:|---:|---:|
| bursty_arrivals | 87.3 | 2.470 | 0.980 | 0.992 |
| no_aging | 90.1 | 1.834 | 0.988 | 0.995 |
| no_duration | 91.5 | 1.709 | 0.989 | 0.996 |
| noisy_estimates | 90.6 | 1.789 | 0.988 | 0.996 |
| profile_prior_only | 90.7 | 1.781 | 0.987 | 0.995 |
| slow_transfer | 87.9 | 1.810 | 0.992 | 0.998 |

### Conservative tested-grid capacity diagnostic

For each workload/policy, select the largest offered rate for which **every seed** attains at least 90% joint SLO success. Report offered rate divided by provisioned GPUs. This finite, fully drained simulation is not a steady-state capacity measurement, and this diagnostic is distinct from the cohort successful-request goodput above. 'None' means no tested rate qualified, not zero capacity.

| Synthetic profile | Policy | Highest qualified tested rate req/s | Offered rate/GPU |
|---|---|---:|---:|
| humaneval | edf | 4 | 1.333 |
| humaneval | fcfs | 4 | 1.333 |
| humaneval | sjf | 4 | 1.333 |
| humaneval | smart | 4 | 1.333 |
| longbench | edf | 1 | 0.333 |
| longbench | fcfs | 1 | 0.333 |
| longbench | sjf | 1 | 0.333 |
| longbench | smart | 1 | 0.333 |
| mixed | edf | 2 | 0.667 |
| mixed | fcfs | 2 | 0.667 |
| mixed | sjf | 2 | 0.667 |
| mixed | smart | 2 | 0.667 |
| sharegpt | edf | 2 | 0.667 |
| sharegpt | fcfs | 2 | 0.667 |
| sharegpt | sjf | 2 | 0.667 |
| sharegpt | smart | 2 | 0.667 |

The saved request logs include all warmup and measurement arrivals, failures, single-token cases, first-token timestamps, decode admission, and final completion. Use `python scripts/audit_results.py` to independently recompute the scalar metrics.
