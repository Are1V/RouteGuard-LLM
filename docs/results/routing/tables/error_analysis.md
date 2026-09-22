**Failure labels per system (counts; an example can carry several labels).**

| System | Wrong | incorrect_routing | model_capability_failure | extraction_failure | high_confidence_wrong | low_confidence_correct | verifier_false_pass | verifier_false_fail | escalation_failure | escalation_harm | language_related_failure | retrieval_failure | unsupported_answer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| always_large | 504 | 0 | 348 | 68 | 367 | 10 | 373 | 8 | 0 | 0 | 146 | 0 | 0 |
| always_medium | 861 | 461 | 348 | 14 | 727 | 10 | 752 | 1 | 0 | 0 | 239 | 0 | 0 |
| always_small | 1345 | 997 | 348 | 5 | 573 | 418 | 1228 | 0 | 0 | 0 | 280 | 0 | 0 |
| cost_aware_t0.5 | 1015 | 622 | 348 | 20 | 661 | 226 | 911 | 2 | 0 | 0 | 236 | 0 | 0 |
| cost_aware_t0.7 | 722 | 277 | 348 | 48 | 535 | 81 | 599 | 5 | 0 | 0 | 185 | 0 | 0 |
| cost_aware_t0.85 | 582 | 106 | 348 | 61 | 444 | 12 | 455 | 9 | 0 | 0 | 158 | 0 | 0 |
| learned_router | 1218 | 853 | 348 | 11 | 671 | 363 | 1106 | 0 | 0 | 0 | 293 | 0 | 0 |
| oracle | 348 | 0 | 348 | 1 | 96 | 424 | 306 | 5 | 0 | 0 | 94 | 0 | 0 |
| quality_cost_l0.05 | 556 | 72 | 348 | 58 | 410 | 10 | 427 | 9 | 0 | 0 | 142 | 0 | 0 |
| quality_cost_l0.2 | 761 | 337 | 348 | 24 | 607 | 20 | 651 | 3 | 0 | 0 | 193 | 0 | 0 |
| quality_cost_l0.5 | 903 | 517 | 348 | 8 | 697 | 49 | 799 | 1 | 0 | 0 | 261 | 0 | 0 |
| random | 929 | 506 | 348 | 26 | 579 | 137 | 814 | 2 | 0 | 0 | 284 | 0 | 0 |
| rule_based | 987 | 594 | 348 | 21 | 624 | 113 | 910 | 9 | 0 | 0 | 211 | 0 | 0 |
| threshold_heuristic | 979 | 590 | 348 | 17 | 540 | 180 | 902 | 9 | 0 | 0 | 259 | 0 | 0 |
| threshold_learned | 1168 | 798 | 348 | 7 | 689 | 325 | 1065 | 0 | 0 | 0 | 267 | 0 | 0 |
| threshold_llm_judge | 861 | 461 | 348 | 14 | 727 | 10 | 752 | 1 | 0 | 0 | 239 | 0 | 0 |
| threshold_neural | 1174 | 795 | 348 | 18 | 666 | 346 | 1057 | 0 | 0 | 0 | 273 | 0 | 0 |
