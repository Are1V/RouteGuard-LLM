**Quality, reliability and cost of all systems (test split). Mean ± std over 3 seeds.**

| System | Group | Accuracy (%) | Macro-acc. lang. (%) | Compute/query (TFLOPs) | Latency mean (s) | Escalation rate (%) |
|---|---:|---:|---:|---:|---:|---:|
| always_large | baseline | 80.5 ± 0.6 | 79.3 ± 0.8 | 5.682 ± 0.040 | 2.757 ± 0.003 | 0.0 ± 0.0 |
| always_medium | baseline | 66.6 ± 1.0 | 67.0 ± 0.4 | 1.066 ± 0.007 | 0.919 ± 0.011 | 0.0 ± 0.0 |
| always_small | baseline | 47.9 ± 0.7 | 47.9 ± 1.1 | 0.309 ± 0.002 | 0.448 ± 0.016 | 0.0 ± 0.0 |
| cascade | baseline | 80.9 ± 1.6 | 81.7 ± 1.1 | 6.526 ± 0.897 | 3.843 ± 0.490 | 100.0 ± 0.0 |
| difficulty_threshold | baseline | 62.1 ± 0.3 | 57.9 ± 0.9 | 1.639 ± 0.053 | 1.104 ± 0.020 | 0.0 ± 0.0 |
| learned_router | baseline | 52.8 ± 0.7 | 53.3 ± 1.1 | 0.741 ± 0.080 | 0.642 ± 0.059 | 0.0 ± 0.0 |
| oracle | oracle | 86.5 ± 0.2 | 88.2 ± 0.6 | 1.320 ± 0.017 | 0.916 ± 0.034 | 0.0 ± 0.0 |
| random | baseline | 64.0 ± 0.1 | 63.2 ± 0.5 | 2.300 ± 0.075 | 1.372 ± 0.005 | 0.0 ± 0.0 |
| routeguard | routeguard | 80.6 ± 0.9 | 80.0 ± 0.9 | 5.951 ± 0.504 | 3.134 ± 0.300 | 50.9 ± 7.7 |
| rule_based | baseline | 61.7 ± 0.6 | 64.6 ± 1.1 | 1.596 ± 0.057 | 1.017 ± 0.025 | 0.0 ± 0.0 |
