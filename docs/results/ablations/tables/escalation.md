**Escalation behaviour (systems that escalate). Mean ± std over 3 seeds.**

| System | Escalation rate (%) | Precision (%) | Recall (%) | Initial errors corrected (%) | Initially-correct broken (%) | Escalation cost share (%) |
|---|---:|---:|---:|---:|---:|---:|
| conf_entropy | 50.8 ± 7.9 | 29.6 ± 1.0 | 53.5 ± 6.6 | 35.8 ± 5.5 | 2.1 ± 0.9 | 43.8 ± 5.3 |
| conf_min_token_prob | 55.5 ± 4.3 | 28.5 ± 1.2 | 56.4 ± 3.2 | 37.9 ± 2.9 | 2.4 ± 0.7 | 46.8 ± 3.3 |
| conf_sequence_logprob | 51.1 ± 7.4 | 29.9 ± 1.5 | 54.4 ± 5.3 | 36.4 ± 4.6 | 2.1 ± 0.9 | 44.0 ± 5.1 |
| heuristic_difficulty | 50.5 ± 7.8 | 29.8 ± 2.1 | 53.8 ± 5.8 | 36.1 ± 5.3 | 2.2 ± 0.9 | 43.5 ± 5.4 |
| neural_difficulty | 53.0 ± 7.4 | 29.8 ± 1.1 | 55.2 ± 6.6 | 37.6 ± 5.5 | 2.3 ± 0.8 | 45.6 ± 4.6 |
| no_confidence | 1.6 ± 0.8 | 100.0 ± 0.0 | 5.6 ± 2.5 | 2.7 ± 1.6 | 0.0 ± 0.0 | 2.9 ± 1.2 |
| no_task_classification | 50.5 ± 4.3 | 27.4 ± 1.5 | 54.2 ± 6.3 | 33.9 ± 5.5 | 2.5 ± 0.6 | 42.2 ± 4.0 |
| no_verification | 50.7 ± 8.0 | 29.7 ± 1.2 | 53.7 ± 6.3 | 35.8 ± 5.5 | 2.1 ± 0.9 | 43.6 ± 5.6 |
| oracle_task_labels | 63.5 ± 4.8 | 26.6 ± 1.3 | 58.5 ± 5.1 | 39.9 ± 4.0 | 2.8 ± 0.7 | 52.8 ± 4.1 |
| routeguard | 50.9 ± 7.7 | 30.0 ± 1.6 | 54.2 ± 5.5 | 36.2 ± 4.8 | 2.1 ± 0.9 | 43.8 ± 5.3 |
| uncalibrated_fixed_threshold | 13.2 ± 1.1 | 44.0 ± 5.7 | 20.7 ± 3.0 | 11.3 ± 2.7 | 0.4 ± 0.2 | 15.2 ± 1.9 |
