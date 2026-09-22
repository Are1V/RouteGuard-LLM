**Accuracy relative to the best cost-matched random mixture of the fixed-model systems (upper concave hull; per seed, then mean ± std). Positive = the system adds value beyond how much compute it spends. Mean ± std over 3 seeds.**

| System | Group | Compute/query (TFLOPs) | Accuracy (%) | Gap vs mixture (pp) |
|---|---:|---:|---:|---:|
| always_large | baseline | 5.682 ± 0.040 | 80.5 ± 0.6 | 0.0 ± 0.0 |
| always_medium | baseline | 1.066 ± 0.007 | 66.6 ± 1.0 | 0.0 ± 0.0 |
| always_small | baseline | 0.309 ± 0.002 | 47.9 ± 0.7 | 0.0 ± 0.0 |
| cascade_a0.25 | baseline | 5.665 ± 1.312 | 78.6 ± 3.1 | -0.4 ± 1.2 |
| cascade_a0.35 | baseline | 1.810 ± 0.192 | 69.4 ± 0.7 | 0.5 ± 0.1 |
| cascade_a0.5 | baseline | 0.782 ± 0.086 | 55.7 ± 3.2 | -3.7 ± 1.3 |
| oracle | oracle | 1.320 ± 0.017 | 86.5 ± 0.2 | 19.1 ± 1.2 |
| routeguard_a0.15 | routeguard | 5.951 ± 0.504 | 80.6 ± 0.9 | 0.5 ± 0.1 |
| routeguard_a0.25 | routeguard | 5.460 ± 0.696 | 79.3 ± 1.5 | 0.1 ± 0.4 |
| routeguard_a0.35 | routeguard | 3.634 ± 0.128 | 74.6 ± 1.1 | 0.3 ± 0.4 |
| routeguard_a0.5 | routeguard | 3.474 ± 0.127 | 73.4 ± 0.5 | -0.4 ± 0.3 |
| routeguard_conditional_a0.15 | routeguard | 6.223 ± 0.080 | 80.9 ± 0.6 | 0.5 ± 0.1 |
| routeguard_conditional_a0.25 | routeguard | 4.535 ± 0.788 | 76.8 ± 2.6 | -0.2 ± 0.6 |
| routeguard_conditional_a0.35 | routeguard | 3.536 ± 0.203 | 74.1 ± 1.5 | 0.2 ± 0.7 |
