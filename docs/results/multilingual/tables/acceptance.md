**Realised risk of the acceptance rule: error rate among *accepted* initial answers, by the model that produced them. Compare with the target risk of risk-controlled systems. Mean ± std over 3 seeds.**

| System | Model | Acceptance rate (%) | Accepted error rate (%) | Accepted / seed |
|---|---:|---:|---:|---:|
| always_large | qwen3-8b | 99.2 ± 0.7 | 19.3 ± 0.7 | 853 ± 6 |
| always_small | qwen3-0.6b | 55.7 ± 4.9 | 43.1 ± 1.0 | 479 ± 42 |
| routeguard_english_trained | qwen3-1.7b | 14.5 ± 25.2 | 22.1 | 45 ± 79 |
| routeguard_english_trained | qwen3-8b | 8.6 ± 7.9 | 31.6 ± 10.3 | 18 ± 19 |
| routeguard_per_language_calibration | qwen3-1.7b | 18.6 ± 17.4 | 21.5 ± 5.3 | 75 ± 74 |
| routeguard_per_language_calibration | qwen3-8b | 45.1 ± 27.0 | 19.4 ± 5.3 | 171 ± 97 |
| routeguard | qwen3-1.7b | 9.9 ± 17.2 | 16.3 | 41 ± 71 |
| routeguard | qwen3-8b | 5.0 ± 4.5 | 28.1 ± 5.3 | 20 ± 19 |
