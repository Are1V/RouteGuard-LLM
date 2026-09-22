**Accuracy relative to the best cost-matched random mixture of the fixed-model systems (upper concave hull; per seed, then mean ± std). Positive = the system adds value beyond how much compute it spends. Mean ± std over 3 seeds.**

| System | Group | Compute/query (TFLOPs) | Accuracy (%) | Gap vs mixture (pp) |
|---|---:|---:|---:|---:|
| always_large | baseline | 5.682 ± 0.040 | 80.5 ± 0.6 | 0.0 ± 0.0 |
| always_medium | baseline | 1.066 ± 0.007 | 66.6 ± 1.0 | 0.0 ± 0.0 |
| always_small | baseline | 0.309 ± 0.002 | 47.9 ± 0.7 | 0.0 ± 0.0 |
| cascade | baseline | 6.526 ± 0.897 | 80.9 ± 1.6 | 0.7 ± 0.9 |
| difficulty_threshold | baseline | 1.639 ± 0.053 | 62.1 ± 0.3 | -6.3 ± 0.7 |
| learned_router | baseline | 0.741 ± 0.080 | 52.8 ± 0.7 | -5.8 ± 2.0 |
| oracle | oracle | 1.320 ± 0.017 | 86.5 ± 0.2 | 19.1 ± 1.2 |
| random | baseline | 2.300 ± 0.075 | 64.0 ± 0.1 | -6.3 ± 0.4 |
| routeguard | routeguard | 5.951 ± 0.504 | 80.6 ± 0.9 | 0.5 ± 0.1 |
| rule_based | baseline | 1.596 ± 0.057 | 61.7 ± 0.6 | -6.5 ± 1.4 |
