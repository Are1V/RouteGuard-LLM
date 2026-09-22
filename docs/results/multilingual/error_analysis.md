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
| always_small | 2580 | 1345 | 997 | 348 | 5 | 573 | 418 | 1228 | 0 | 0 | 0 | 280 | 0 | 0 |
| oracle | 2580 | 348 | 0 | 348 | 1 | 96 | 424 | 306 | 5 | 0 | 0 | 94 | 0 | 0 |
| routeguard_english_trained | 2580 | 493 | 19 | 348 | 6 | 39 | 1476 | 395 | 1 | 95 | 61 | 139 | 0 | 0 |
| routeguard_per_language_calibration | 2580 | 512 | 25 | 348 | 46 | 115 | 1275 | 395 | 5 | 59 | 39 | 146 | 0 | 0 |
| routeguard | 2580 | 500 | 12 | 348 | 46 | 28 | 1712 | 382 | 5 | 61 | 40 | 140 | 0 | 0 |

## Counts per language (all systems)

| Language | incorrect_routing | model_capability_failure | extraction_failure | high_confidence_wrong | low_confidence_correct | verifier_false_pass | verifier_false_fail | escalation_failure | escalation_harm | language_related_failure | retrieval_failure | unsupported_answer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| en | 434 | 1248 | 12 | 518 | 2214 | 1508 | 11 | 65 | 45 | 0 | 0 | 0 |
| fa | 55 | 138 | 59 | 97 | 240 | 229 | 0 | 27 | 15 | 146 | 0 | 0 |
| kk | 116 | 234 | 65 | 187 | 630 | 348 | 0 | 27 | 15 | 280 | 0 | 0 |
| pes_Arab | 144 | 90 | 3 | 125 | 642 | 282 | 0 | 33 | 24 | 126 | 0 | 0 |
| prs_Arab | 45 | 42 | 0 | 31 | 318 | 107 | 0 | 15 | 10 | 58 | 0 | 0 |
| ru | 259 | 336 | 33 | 260 | 1271 | 605 | 13 | 48 | 31 | 335 | 0 | 0 |

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
- `always_small` / `arc-MCAS_2005_8_6` (en): gold='A', answer='B'
- `always_small` / `arc-Mercury_7106593` (en): gold='D', answer='B'
- `always_small` / `arc-MCAS_2003_8_7` (en): gold='A', answer='D'
- `always_small` / `arc-MCAS_1999_8_16` (en): gold='D', answer='B'
- `always_small` / `arc-Mercury_7011323` (en): gold='A', answer='B'

### escalation_failure
- `routeguard_english_trained` / `belebele-5c64dbb6a7-kaz_Cyrl` (kk): gold='A', answer='B'
- `routeguard_english_trained` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `routeguard_english_trained` / `belebele-f68c2e0e26-kaz_Cyrl` (kk): gold='D', answer='A'
- `routeguard_english_trained` / `belebele-f67e6d5b5d-rus_Cyrl` (ru): gold='C', answer='B'
- `routeguard_english_trained` / `belebele-40aa1fe314-kaz_Cyrl` (kk): gold='D', answer='A'

### escalation_harm
- `routeguard_english_trained` / `belebele-f68c2e0e26-kaz_Cyrl` (kk): gold='D', answer='A'
- `routeguard_english_trained` / `belebele-f67e6d5b5d-rus_Cyrl` (ru): gold='C', answer='B'
- `routeguard_english_trained` / `belebele-40aa1fe314-kaz_Cyrl` (kk): gold='D', answer='A'
- `routeguard_english_trained` / `belebele-45af0224db-kaz_Cyrl` (kk): gold='C', answer='A'
- `routeguard_english_trained` / `belebele-1edeee7bc9-kaz_Cyrl` (kk): gold='B', answer='C'
