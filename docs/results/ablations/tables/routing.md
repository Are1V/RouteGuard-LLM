**Routing quality relative to the cost-optimal oracle. Mean ± std over 3 seeds.**

| System | Routing acc. (%) | Unnecessary large-model use (%) | Incorrect small-model routing (%) | Oracle acc. (%) |
|---|---:|---:|---:|---:|
| conf_entropy | 27.1 ± 0.5 | 64.3 ± 1.4 | 10.7 ± 1.3 | 86.5 ± 0.2 |
| conf_min_token_prob | 27.1 ± 0.5 | 64.3 ± 1.4 | 10.7 ± 1.3 | 86.5 ± 0.2 |
| conf_sequence_logprob | 27.1 ± 0.5 | 64.3 ± 1.4 | 10.7 ± 1.3 | 86.5 ± 0.2 |
| heuristic_difficulty | 27.1 ± 0.6 | 64.4 ± 1.8 | 10.7 ± 1.6 | 86.5 ± 0.2 |
| neural_difficulty | 27.2 ± 0.3 | 63.4 ± 1.2 | 11.4 ± 1.4 | 86.5 ± 0.2 |
| no_confidence | 27.1 ± 0.5 | 64.3 ± 1.4 | 10.7 ± 1.3 | 86.5 ± 0.2 |
| no_escalation | 27.1 ± 0.5 | 64.3 ± 1.4 | 10.7 ± 1.3 | 86.5 ± 0.2 |
| no_task_classification | 25.0 ± 2.1 | 68.2 ± 2.7 | 8.8 ± 1.5 | 86.8 ± 0.6 |
| no_verification | 27.1 ± 0.5 | 64.3 ± 1.4 | 10.7 ± 1.3 | 86.5 ± 0.2 |
| oracle_task_labels | 27.5 ± 1.0 | 63.3 ± 0.2 | 11.7 ± 1.5 | 85.9 ± 0.4 |
| routeguard | 27.1 ± 0.5 | 64.3 ± 1.4 | 10.7 ± 1.3 | 86.5 ± 0.2 |
| uncalibrated_fixed_threshold | 27.1 ± 0.5 | 64.3 ± 1.4 | 10.7 ± 1.3 | 86.5 ± 0.2 |
