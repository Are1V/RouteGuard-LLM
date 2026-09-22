**Failure labels per system (counts; an example can carry several labels).**

| System | Wrong | incorrect_routing | model_capability_failure | extraction_failure | high_confidence_wrong | low_confidence_correct | verifier_false_pass | verifier_false_fail | escalation_failure | escalation_harm | language_related_failure | retrieval_failure | unsupported_answer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| always_large | 504 | 0 | 348 | 68 | 367 | 10 | 373 | 8 | 0 | 0 | 146 | 0 | 0 |
| always_medium | 861 | 461 | 348 | 14 | 727 | 10 | 752 | 1 | 0 | 0 | 239 | 0 | 0 |
| always_small | 1345 | 997 | 348 | 5 | 573 | 418 | 1228 | 0 | 0 | 0 | 280 | 0 | 0 |
| cascade_a0.25 | 551 | 0 | 348 | 0 | 0 | 1235 | 462 | 0 | 203 | 98 | 152 | 0 | 0 |
| cascade_a0.35 | 790 | 0 | 348 | 0 | 0 | 1235 | 742 | 0 | 442 | 148 | 233 | 0 | 0 |
| cascade_a0.5 | 1142 | 691 | 348 | 0 | 851 | 149 | 1099 | 0 | 103 | 20 | 285 | 0 | 0 |
| oracle | 348 | 0 | 348 | 1 | 96 | 424 | 306 | 5 | 0 | 0 | 94 | 0 | 0 |
| routeguard_a0.15 | 500 | 12 | 348 | 46 | 28 | 1712 | 382 | 5 | 61 | 40 | 140 | 0 | 0 |
| routeguard_a0.25 | 533 | 46 | 348 | 46 | 259 | 828 | 417 | 5 | 59 | 37 | 144 | 0 | 0 |
| routeguard_a0.35 | 655 | 169 | 348 | 46 | 492 | 219 | 550 | 5 | 45 | 14 | 176 | 0 | 0 |
| routeguard_a0.5 | 685 | 232 | 348 | 46 | 569 | 26 | 581 | 5 | 12 | 3 | 189 | 0 | 0 |
| routeguard_conditional_a0.15 | 492 | 0 | 348 | 46 | 0 | 1858 | 374 | 5 | 65 | 44 | 138 | 0 | 0 |
| routeguard_conditional_a0.25 | 598 | 127 | 348 | 46 | 212 | 1092 | 486 | 5 | 37 | 21 | 166 | 0 | 0 |
| routeguard_conditional_a0.35 | 667 | 192 | 348 | 46 | 466 | 219 | 563 | 5 | 34 | 11 | 185 | 0 | 0 |
