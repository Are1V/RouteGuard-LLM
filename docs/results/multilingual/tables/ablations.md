**Ablations relative to routeguard. Mean ± std over 3 seeds.**

| System | Accuracy (%) | Δ acc. vs ref. (pp) | 95% CI (pp) | Compute/query (TFLOPs) | Escalation rate (%) |
|---|---:|---:|---:|---:|---:|
| routeguard | 80.6 ± 0.9 | 0.0 | – | 5.951 ± 0.504 | 50.9 ± 7.7 |
| routeguard_english_trained | 80.9 ± 1.6 | +0.3 | [-0.2, +0.7] | 6.250 ± 0.754 | 71.9 ± 8.3 |
| routeguard_per_language_calibration | 80.2 ± 0.7 | -0.5 | [-0.8, -0.2] | 5.715 ± 0.538 | 47.1 ± 6.8 |
