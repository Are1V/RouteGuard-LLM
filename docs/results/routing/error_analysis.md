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
| cost_aware_t0.5 | 2580 | 1015 | 622 | 348 | 20 | 661 | 226 | 911 | 2 | 0 | 0 | 236 | 0 | 0 |
| cost_aware_t0.7 | 2580 | 722 | 277 | 348 | 48 | 535 | 81 | 599 | 5 | 0 | 0 | 185 | 0 | 0 |
| cost_aware_t0.85 | 2580 | 582 | 106 | 348 | 61 | 444 | 12 | 455 | 9 | 0 | 0 | 158 | 0 | 0 |
| learned_router | 2580 | 1218 | 853 | 348 | 11 | 671 | 363 | 1106 | 0 | 0 | 0 | 293 | 0 | 0 |
| oracle | 2580 | 348 | 0 | 348 | 1 | 96 | 424 | 306 | 5 | 0 | 0 | 94 | 0 | 0 |
| quality_cost_l0.05 | 2580 | 556 | 72 | 348 | 58 | 410 | 10 | 427 | 9 | 0 | 0 | 142 | 0 | 0 |
| quality_cost_l0.2 | 2580 | 761 | 337 | 348 | 24 | 607 | 20 | 651 | 3 | 0 | 0 | 193 | 0 | 0 |
| quality_cost_l0.5 | 2580 | 903 | 517 | 348 | 8 | 697 | 49 | 799 | 1 | 0 | 0 | 261 | 0 | 0 |
| random | 2580 | 929 | 506 | 348 | 26 | 579 | 137 | 814 | 2 | 0 | 0 | 284 | 0 | 0 |
| rule_based | 2580 | 987 | 594 | 348 | 21 | 624 | 113 | 910 | 9 | 0 | 0 | 211 | 0 | 0 |
| threshold_heuristic | 2580 | 979 | 590 | 348 | 17 | 540 | 180 | 902 | 9 | 0 | 0 | 259 | 0 | 0 |
| threshold_learned | 2580 | 1168 | 798 | 348 | 7 | 689 | 325 | 1065 | 0 | 0 | 0 | 267 | 0 | 0 |
| threshold_llm_judge | 2580 | 861 | 461 | 348 | 14 | 727 | 10 | 752 | 1 | 0 | 0 | 239 | 0 | 0 |
| threshold_neural | 2580 | 1174 | 795 | 348 | 18 | 666 | 346 | 1057 | 0 | 0 | 0 | 273 | 0 | 0 |

## Counts per language (all systems)

| Language | incorrect_routing | model_capability_failure | extraction_failure | high_confidence_wrong | low_confidence_correct | verifier_false_pass | verifier_false_fail | escalation_failure | escalation_harm | language_related_failure | retrieval_failure | unsupported_answer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| en | 3231 | 3536 | 50 | 3961 | 1174 | 5747 | 36 | 0 | 0 | 0 | 0 | 0 |
| fa | 358 | 391 | 150 | 715 | 159 | 852 | 0 | 0 | 0 | 464 | 0 | 0 |
| kk | 972 | 663 | 114 | 1416 | 302 | 1694 | 0 | 0 | 0 | 1041 | 0 | 0 |
| pes_Arab | 1125 | 255 | 15 | 1059 | 282 | 1441 | 0 | 0 | 0 | 700 | 0 | 0 |
| prs_Arab | 353 | 119 | 0 | 294 | 179 | 503 | 0 | 0 | 0 | 274 | 0 | 0 |
| ru | 1947 | 952 | 92 | 2168 | 638 | 2870 | 28 | 0 | 0 | 1281 | 0 | 0 |

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
