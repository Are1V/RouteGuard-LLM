**Failure labels per system (counts; an example can carry several labels).**

| System | Wrong | incorrect_routing | model_capability_failure | extraction_failure | high_confidence_wrong | low_confidence_correct | verifier_false_pass | verifier_false_fail | escalation_failure | escalation_harm | language_related_failure | retrieval_failure | unsupported_answer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| always_large | 504 | 0 | 348 | 68 | 367 | 10 | 373 | 8 | 0 | 0 | 146 | 0 | 0 |
| always_small | 1345 | 997 | 348 | 5 | 573 | 418 | 1228 | 0 | 0 | 0 | 280 | 0 | 0 |
| oracle | 348 | 0 | 348 | 1 | 96 | 424 | 306 | 5 | 0 | 0 | 94 | 0 | 0 |
| routeguard_english_trained | 493 | 19 | 348 | 6 | 39 | 1476 | 395 | 1 | 95 | 61 | 139 | 0 | 0 |
| routeguard_per_language_calibration | 512 | 25 | 348 | 46 | 115 | 1275 | 395 | 5 | 59 | 39 | 146 | 0 | 0 |
| routeguard | 500 | 12 | 348 | 46 | 28 | 1712 | 382 | 5 | 61 | 40 | 140 | 0 | 0 |
