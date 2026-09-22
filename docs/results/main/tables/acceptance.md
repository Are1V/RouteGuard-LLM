**Realised risk of the acceptance rule: error rate among *accepted* initial answers, by the model that produced them. Compare with the target risk of risk-controlled systems. Mean ± std over 3 seeds.**

| System | Model | Acceptance rate (%) | Accepted error rate (%) | Accepted / seed |
|---|---:|---:|---:|---:|
| always_large | qwen3-8b | 99.2 ± 0.7 | 19.3 ± 0.7 | 853 ± 6 |
| always_medium | qwen3-1.7b | 98.6 ± 0.5 | 32.8 ± 1.1 | 848 ± 5 |
| always_small | qwen3-0.6b | 55.7 ± 4.9 | 43.1 ± 1.0 | 479 ± 42 |
| difficulty_threshold | qwen3-0.6b | 51.6 ± 5.7 | 31.8 ± 0.8 | 193 ± 22 |
| difficulty_threshold | qwen3-1.7b | 99.7 ± 0.3 | 30.8 ± 1.3 | 356 ± 4 |
| difficulty_threshold | qwen3-8b | 99.5 ± 0.8 | 25.8 ± 2.1 | 129 ± 5 |
| learned_router | qwen3-0.6b | 58.1 ± 7.1 | 39.4 ± 2.9 | 391 ± 52 |
| learned_router | qwen3-1.7b | 99.5 ± 0.9 | 40.1 ± 8.2 | 97 ± 27 |
| learned_router | qwen3-8b | 99.2 ± 0.7 | 58.2 ± 7.1 | 90 ± 15 |
| random | qwen3-0.6b | 55.9 ± 3.2 | 43.3 ± 2.6 | 163 ± 16 |
| random | qwen3-1.7b | 99.0 ± 0.3 | 34.3 ± 2.2 | 283 ± 9 |
| random | qwen3-8b | 99.3 ± 0.7 | 19.3 ± 0.9 | 281 ± 2 |
| routeguard | qwen3-1.7b | 9.9 ± 17.2 | 16.3 | 41 ± 71 |
| routeguard | qwen3-8b | 5.0 ± 4.5 | 28.1 ± 5.3 | 20 ± 19 |
| rule_based | qwen3-0.6b | 64.2 ± 5.2 | 39.3 ± 1.8 | 236 ± 20 |
| rule_based | qwen3-1.7b | 99.2 ± 0.7 | 29.5 ± 1.1 | 361 ± 4 |
| rule_based | qwen3-8b | 99.5 ± 0.9 | 25.1 ± 2.4 | 128 ± 6 |
