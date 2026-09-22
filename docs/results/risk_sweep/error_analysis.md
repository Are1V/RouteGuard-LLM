# Error analysis

Labels are assigned automatically from observable signals and are intended to
guide manual inspection. An example may carry several labels.

## Taxonomy

- **incorrect_routing**: final answer wrong; the routed model was wrong but a stronger model was right, and escalation did not recover
- **model_capability_failure**: no model in the pool answered correctly (reasoning/knowledge limit)
- **extraction_failure**: no answer could be parsed from the final response
- **high_confidence_wrong**: initial answer wrong, its confidence was above the acceptance threshold, and the verifier did not reject it
- **low_confidence_correct**: initial answer correct but flagged as low-confidence (unnecessary escalation)
- **verifier_false_pass**: a verifier accepted a wrong final answer
- **verifier_false_fail**: a verifier rejected a correct initial answer
- **escalation_failure**: escalated, still wrong, although some model in the pool was correct
- **escalation_harm**: initial answer correct, final answer wrong after escalation
- **language_related_failure**: wrong in a non-English language while the English parallel item was answered correctly by the same system and seed
- **retrieval_failure**: retrieval stage ran but no retrieved passage contained the gold answer
- **unsupported_answer**: answer produced after retrieval failed (answer without evidence)

## Counts per system

| System | Records | Wrong | incorrect_routing | model_capability_failure | extraction_failure | high_confidence_wrong | low_confidence_correct | verifier_false_pass | verifier_false_fail | escalation_failure | escalation_harm | language_related_failure | retrieval_failure | unsupported_answer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| always_large | 2580 | 504 | 0 | 348 | 68 | 367 | 10 | 373 | 8 | 0 | 0 | 146 | 0 | 0 |
| always_medium | 2580 | 861 | 461 | 348 | 14 | 727 | 10 | 752 | 1 | 0 | 0 | 239 | 0 | 0 |
| always_small | 2580 | 1345 | 997 | 348 | 5 | 573 | 418 | 1228 | 0 | 0 | 0 | 280 | 0 | 0 |
| cascade_a0.25 | 2580 | 551 | 0 | 348 | 0 | 0 | 1235 | 462 | 0 | 203 | 98 | 152 | 0 | 0 |
| cascade_a0.35 | 2580 | 790 | 0 | 348 | 0 | 0 | 1235 | 742 | 0 | 442 | 148 | 233 | 0 | 0 |
| cascade_a0.5 | 2580 | 1142 | 691 | 348 | 0 | 851 | 149 | 1099 | 0 | 103 | 20 | 285 | 0 | 0 |
| oracle | 2580 | 348 | 0 | 348 | 1 | 96 | 424 | 306 | 5 | 0 | 0 | 94 | 0 | 0 |
| routeguard_a0.15 | 2580 | 500 | 12 | 348 | 46 | 28 | 1712 | 382 | 5 | 61 | 40 | 140 | 0 | 0 |
| routeguard_a0.25 | 2580 | 533 | 46 | 348 | 46 | 259 | 828 | 417 | 5 | 59 | 37 | 144 | 0 | 0 |
| routeguard_a0.35 | 2580 | 655 | 169 | 348 | 46 | 492 | 219 | 550 | 5 | 45 | 14 | 176 | 0 | 0 |
| routeguard_a0.5 | 2580 | 685 | 232 | 348 | 46 | 569 | 26 | 581 | 5 | 12 | 3 | 189 | 0 | 0 |
| routeguard_conditional_a0.15 | 2580 | 492 | 0 | 348 | 46 | 0 | 1858 | 374 | 5 | 65 | 44 | 138 | 0 | 0 |
| routeguard_conditional_a0.25 | 2580 | 598 | 127 | 348 | 46 | 212 | 1092 | 486 | 5 | 37 | 21 | 166 | 0 | 0 |
| routeguard_conditional_a0.35 | 2580 | 667 | 192 | 348 | 46 | 466 | 219 | 563 | 5 | 34 | 11 | 185 | 0 | 0 |

## Counts per language (all systems)

| Language | incorrect_routing | model_capability_failure | extraction_failure | high_confidence_wrong | low_confidence_correct | verifier_false_pass | verifier_false_fail | escalation_failure | escalation_harm | language_related_failure | retrieval_failure | unsupported_answer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| en | 1127 | 2912 | 18 | 2000 | 3911 | 3940 | 16 | 425 | 172 | 0 | 0 | 0 |
| fa | 134 | 322 | 149 | 317 | 404 | 585 | 0 | 100 | 41 | 358 | 0 | 0 |
| kk | 312 | 546 | 165 | 590 | 1163 | 944 | 0 | 119 | 51 | 737 | 0 | 0 |
| pes_Arab | 457 | 210 | 4 | 541 | 1151 | 845 | 0 | 138 | 68 | 405 | 0 | 0 |
| prs_Arab | 127 | 98 | 0 | 157 | 554 | 278 | 0 | 39 | 20 | 163 | 0 | 0 |
| ru | 770 | 784 | 74 | 1035 | 2252 | 1723 | 33 | 240 | 84 | 904 | 0 | 0 |

## Examples (first five per label)

### high_confidence_wrong
- `always_large` / `arc-Mercury_7011323` (en): gold='A', answer='B'
- `always_large` / `arc-Mercury_7016765` (en): gold='A', answer='C'
- `always_large` / `belebele-5c64dbb6a7-kaz_Cyrl` (kk): gold='A', answer='B'
- `always_large` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `always_large` / `belebele-f67e6d5b5d-rus_Cyrl` (ru): gold='C', answer='B'

### verifier_false_pass
- `always_large` / `arc-Mercury_7011323` (en): gold='A', answer='B'
- `always_large` / `arc-Mercury_7016765` (en): gold='A', answer='C'
- `always_large` / `belebele-5c64dbb6a7-kaz_Cyrl` (kk): gold='A', answer='B'
- `always_large` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `always_large` / `belebele-f67e6d5b5d-rus_Cyrl` (ru): gold='C', answer='B'

### model_capability_failure
- `always_large` / `arc-Mercury_7016765` (en): gold='A', answer='C'
- `always_large` / `belebele-0aa83ddbb8-kaz_Cyrl` (kk): gold='C', answer=None
- `always_large` / `belebele-09db09c4f8-kaz_Cyrl` (kk): gold='C', answer='A'
- `always_large` / `belebele-fd3e6be09d-eng_Latn` (en): gold='B', answer='D'
- `always_large` / `belebele-fd3e6be09d-kaz_Cyrl` (kk): gold='B', answer='D'

### language_related_failure
- `always_large` / `belebele-5c64dbb6a7-kaz_Cyrl` (kk): gold='A', answer='B'
- `always_large` / `belebele-0aa83ddbb8-kaz_Cyrl` (kk): gold='C', answer=None
- `always_large` / `belebele-994e614b9f-kaz_Cyrl` (kk): gold='C', answer=None
- `always_large` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `always_large` / `belebele-f68c2e0e26-kaz_Cyrl` (kk): gold='D', answer=None

### extraction_failure
- `always_large` / `belebele-0aa83ddbb8-kaz_Cyrl` (kk): gold='C', answer=None
- `always_large` / `belebele-994e614b9f-kaz_Cyrl` (kk): gold='C', answer=None
- `always_large` / `belebele-f68c2e0e26-kaz_Cyrl` (kk): gold='D', answer=None
- `always_large` / `belebele-e9087829b2-kaz_Cyrl` (kk): gold='C', answer=None
- `always_large` / `belebele-7701cce634-kaz_Cyrl` (kk): gold='B', answer=None

### verifier_false_fail
- `always_large` / `gmmlu-en-econometrics/test/111` (en): gold='B', answer='B'
- `always_large` / `mgsm-ru-249` (ru): gold='5600', answer='5600'
- `always_large` / `mgsm-en-115` (en): gold='90', answer='90'
- `always_large` / `mgsm-en-107` (en): gold='3', answer='3'
- `always_large` / `mgsm-ru-205` (ru): gold='98', answer='98'

### low_confidence_correct
- `always_large` / `gmmlu-fa-philosophy/test/289` (fa): gold='A', answer='A'
- `always_large` / `sib200-1200-kaz_Cyrl` (kk): gold='D', answer='D'
- `always_large` / `sib200-779-kaz_Cyrl` (kk): gold='A', answer='A'
- `always_large` / `sib200-953-eng_Latn` (en): gold='B', answer='B'
- `always_large` / `sib200-1853-eng_Latn` (en): gold='D', answer='D'

### incorrect_routing
- `always_medium` / `arc-Mercury_SC_407070` (en): gold='B', answer='D'
- `always_medium` / `arc-Mercury_7027720` (en): gold='B', answer='D'
- `always_medium` / `arc-Mercury_7263638` (en): gold='B', answer='D'
- `always_medium` / `arc-MCAS_2014_5_15` (en): gold='D', answer='B'
- `always_medium` / `belebele-07de2ab0e2-eng_Latn` (en): gold='C', answer='B'

### escalation_failure
- `cascade_a0.25` / `arc-Mercury_7011323` (en): gold='A', answer='B'
- `cascade_a0.25` / `belebele-5c64dbb6a7-kaz_Cyrl` (kk): gold='A', answer='B'
- `cascade_a0.25` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `cascade_a0.25` / `belebele-f68c2e0e26-kaz_Cyrl` (kk): gold='D', answer='A'
- `cascade_a0.25` / `belebele-f67e6d5b5d-rus_Cyrl` (ru): gold='C', answer='B'

### escalation_harm
- `cascade_a0.25` / `belebele-f68c2e0e26-kaz_Cyrl` (kk): gold='D', answer='A'
- `cascade_a0.25` / `belebele-f67e6d5b5d-rus_Cyrl` (ru): gold='C', answer='B'
- `cascade_a0.25` / `belebele-40aa1fe314-kaz_Cyrl` (kk): gold='D', answer='A'
- `cascade_a0.25` / `belebele-45af0224db-kaz_Cyrl` (kk): gold='C', answer='A'
- `cascade_a0.25` / `belebele-1edeee7bc9-kaz_Cyrl` (kk): gold='B', answer='C'
