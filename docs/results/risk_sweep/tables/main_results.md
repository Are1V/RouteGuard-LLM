**Quality, reliability and cost of all systems (test split). Mean ± std over 3 seeds.**

| System | Group | Accuracy (%) | Macro-acc. lang. (%) | Compute/query (TFLOPs) | Latency mean (s) | Escalation rate (%) |
|---|---:|---:|---:|---:|---:|---:|
| always_large | baseline | 80.5 ± 0.6 | 79.3 ± 0.8 | 5.682 ± 0.040 | 2.757 ± 0.003 | 0.0 ± 0.0 |
| always_medium | baseline | 66.6 ± 1.0 | 67.0 ± 0.4 | 1.066 ± 0.007 | 0.919 ± 0.011 | 0.0 ± 0.0 |
| always_small | baseline | 47.9 ± 0.7 | 47.9 ± 1.1 | 0.309 ± 0.002 | 0.448 ± 0.016 | 0.0 ± 0.0 |
| cascade_a0.25 | baseline | 78.6 ± 3.1 | 80.0 ± 1.1 | 5.665 ± 1.312 | 3.393 ± 0.710 | 100.0 ± 0.0 |
| cascade_a0.35 | baseline | 69.4 ± 0.7 | 69.5 ± 1.0 | 1.810 ± 0.192 | 1.573 ± 0.059 | 100.0 ± 0.0 |
| cascade_a0.5 | baseline | 55.7 ± 3.2 | 54.5 ± 3.7 | 0.782 ± 0.086 | 0.768 ± 0.076 | 24.9 ± 10.7 |
| oracle | oracle | 86.5 ± 0.2 | 88.2 ± 0.6 | 1.320 ± 0.017 | 0.916 ± 0.034 | 0.0 ± 0.0 |
| routeguard_a0.15 | routeguard | 80.6 ± 0.9 | 80.0 ± 0.9 | 5.951 ± 0.504 | 3.134 ± 0.300 | 50.9 ± 7.7 |
| routeguard_a0.25 | routeguard | 79.3 ± 1.5 | 79.2 ± 0.8 | 5.460 ± 0.696 | 2.849 ± 0.402 | 43.4 ± 8.4 |
| routeguard_a0.35 | routeguard | 74.6 ± 1.1 | 74.2 ± 0.5 | 3.634 ± 0.128 | 1.869 ± 0.101 | 14.2 ± 3.9 |
| routeguard_a0.5 | routeguard | 73.4 ± 0.5 | 73.2 ± 0.9 | 3.474 ± 0.127 | 1.763 ± 0.091 | 3.8 ± 1.7 |
| routeguard_conditional_a0.15 | routeguard | 80.9 ± 0.6 | 80.2 ± 0.8 | 6.223 ± 0.080 | 3.287 ± 0.049 | 55.5 ± 4.3 |
| routeguard_conditional_a0.25 | routeguard | 76.8 ± 2.6 | 76.8 ± 2.7 | 4.535 ± 0.788 | 2.328 ± 0.395 | 24.0 ± 13.3 |
| routeguard_conditional_a0.35 | routeguard | 74.1 ± 1.5 | 73.9 ± 0.2 | 3.536 ± 0.203 | 1.814 ± 0.156 | 9.8 ± 5.4 |
