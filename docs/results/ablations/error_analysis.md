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
| conf_entropy | 2580 | 503 | 15 | 348 | 46 | 28 | 1729 | 385 | 5 | 61 | 40 | 140 | 0 | 0 |
| conf_min_token_prob | 2580 | 492 | 0 | 348 | 46 | 0 | 1858 | 373 | 5 | 65 | 44 | 138 | 0 | 0 |
| conf_sequence_logprob | 2580 | 499 | 11 | 348 | 46 | 32 | 1708 | 381 | 5 | 61 | 40 | 140 | 0 | 0 |
| heuristic_difficulty | 2580 | 499 | 12 | 348 | 45 | 28 | 1717 | 382 | 5 | 62 | 41 | 139 | 0 | 0 |
| neural_difficulty | 2580 | 502 | 14 | 348 | 45 | 31 | 1693 | 385 | 5 | 63 | 43 | 139 | 0 | 0 |
| no_confidence | 2580 | 702 | 257 | 348 | 46 | 0 | 0 | 601 | 5 | 4 | 0 | 185 | 0 | 0 |
| no_escalation | 2580 | 722 | 277 | 348 | 48 | 535 | 81 | 599 | 5 | 0 | 0 | 185 | 0 | 0 |
| no_task_classification | 2580 | 485 | 2 | 341 | 6 | 50 | 1706 | 433 | 2 | 74 | 49 | 152 | 0 | 0 |
| no_verification | 2580 | 503 | 14 | 348 | 46 | 36 | 1712 | 0 | 0 | 62 | 40 | 140 | 0 | 0 |
| oracle_task_labels | 2580 | 500 | 0 | 365 | 31 | 12 | 1779 | 408 | 6 | 78 | 52 | 146 | 0 | 0 |
| routeguard | 2580 | 500 | 12 | 348 | 46 | 28 | 1712 | 382 | 5 | 61 | 40 | 140 | 0 | 0 |
| uncalibrated_fixed_threshold | 2580 | 648 | 192 | 348 | 46 | 459 | 217 | 542 | 5 | 21 | 8 | 175 | 0 | 0 |

## Counts per language (all systems)

| Language | incorrect_routing | model_capability_failure | extraction_failure | high_confidence_wrong | low_confidence_correct | verifier_false_pass | verifier_false_fail | escalation_failure | escalation_harm | language_related_failure | retrieval_failure | unsupported_answer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| en | 379 | 2493 | 13 | 685 | 6234 | 2542 | 10 | 210 | 150 | 0 | 0 | 0 |
| fa | 23 | 287 | 175 | 64 | 611 | 392 | 0 | 82 | 44 | 325 | 0 | 0 |
| kk | 34 | 458 | 224 | 94 | 2100 | 464 | 0 | 41 | 21 | 528 | 0 | 0 |
| pes_Arab | 135 | 183 | 1 | 145 | 2139 | 425 | 2 | 101 | 64 | 239 | 0 | 0 |
| prs_Arab | 25 | 86 | 0 | 29 | 953 | 150 | 0 | 45 | 27 | 87 | 0 | 0 |
| ru | 210 | 679 | 84 | 222 | 3875 | 898 | 41 | 133 | 91 | 640 | 0 | 0 |

## Examples (first five per label)

### low_confidence_correct
- `conf_entropy` / `arc-MCAS_2005_8_6` (en): gold='A', answer='A'
- `conf_entropy` / `arc-Mercury_415086` (en): gold='D', answer='D'
- `conf_entropy` / `arc-Mercury_403234` (en): gold='B', answer='B'
- `conf_entropy` / `arc-Mercury_7106593` (en): gold='D', answer='D'
- `conf_entropy` / `arc-Mercury_7014333` (en): gold='A', answer='A'

### verifier_false_pass
- `conf_entropy` / `arc-Mercury_7011323` (en): gold='A', answer='B'
- `conf_entropy` / `arc-Mercury_7016765` (en): gold='A', answer='C'
- `conf_entropy` / `belebele-5c64dbb6a7-kaz_Cyrl` (kk): gold='A', answer='B'
- `conf_entropy` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `conf_entropy` / `belebele-f67e6d5b5d-rus_Cyrl` (ru): gold='C', answer='B'

### model_capability_failure
- `conf_entropy` / `arc-Mercury_7016765` (en): gold='A', answer='C'
- `conf_entropy` / `belebele-0aa83ddbb8-kaz_Cyrl` (kk): gold='C', answer=None
- `conf_entropy` / `belebele-09db09c4f8-kaz_Cyrl` (kk): gold='C', answer='A'
- `conf_entropy` / `belebele-fd3e6be09d-eng_Latn` (en): gold='B', answer='D'
- `conf_entropy` / `belebele-fd3e6be09d-kaz_Cyrl` (kk): gold='B', answer='D'

### language_related_failure
- `conf_entropy` / `belebele-5c64dbb6a7-kaz_Cyrl` (kk): gold='A', answer='B'
- `conf_entropy` / `belebele-0aa83ddbb8-kaz_Cyrl` (kk): gold='C', answer=None
- `conf_entropy` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `conf_entropy` / `belebele-f68c2e0e26-kaz_Cyrl` (kk): gold='D', answer=None
- `conf_entropy` / `belebele-f67e6d5b5d-rus_Cyrl` (ru): gold='C', answer='B'

### extraction_failure
- `conf_entropy` / `belebele-0aa83ddbb8-kaz_Cyrl` (kk): gold='C', answer=None
- `conf_entropy` / `belebele-f68c2e0e26-kaz_Cyrl` (kk): gold='D', answer=None
- `conf_entropy` / `belebele-e9087829b2-kaz_Cyrl` (kk): gold='C', answer=None
- `conf_entropy` / `belebele-7701cce634-kaz_Cyrl` (kk): gold='B', answer=None
- `conf_entropy` / `belebele-11f8a22d8d-kaz_Cyrl` (kk): gold='D', answer=None

### escalation_harm
- `conf_entropy` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `conf_entropy` / `belebele-f67e6d5b5d-rus_Cyrl` (ru): gold='C', answer='B'
- `conf_entropy` / `belebele-7dc0de21ba-pes_Arab` (pes_Arab): gold='B', answer='C'
- `conf_entropy` / `belebele-8c6053af00-rus_Cyrl` (ru): gold='D', answer='C'
- `conf_entropy` / `belebele-e362c53641-eng_Latn` (en): gold='C', answer='D'

### escalation_failure
- `conf_entropy` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `conf_entropy` / `belebele-f67e6d5b5d-rus_Cyrl` (ru): gold='C', answer='B'
- `conf_entropy` / `belebele-7dc0de21ba-pes_Arab` (pes_Arab): gold='B', answer='C'
- `conf_entropy` / `belebele-8c6053af00-rus_Cyrl` (ru): gold='D', answer='C'
- `conf_entropy` / `belebele-e362c53641-eng_Latn` (en): gold='C', answer='D'

### verifier_false_fail
- `conf_entropy` / `mgsm-ru-249` (ru): gold='5600', answer='5600'
- `conf_entropy` / `mgsm-en-115` (en): gold='90', answer='90'
- `conf_entropy` / `mgsm-ru-205` (ru): gold='98', answer='98'
- `conf_entropy` / `mgsm-ru-249` (ru): gold='5600', answer='5600'
- `conf_entropy` / `mgsm-ru-249` (ru): gold='5600', answer='5600'

### high_confidence_wrong
- `conf_entropy` / `nq-550` (en): gold=['an instant messaging client'], answer='One of the first instant messaging programs.'
- `conf_entropy` / `nq-1708` (en): gold=['2012'], answer='2020.'
- `conf_entropy` / `nq-3106` (en): gold=['Ceramic art', 'Ceramic'], answer='Pottery.'
- `conf_entropy` / `nq-871` (en): gold=['Chennamaneni Vidyasagar Rao'], answer='Eknath Shinde'
- `conf_entropy` / `nq-2319` (en): gold=['the following day'], answer='Monday Night Raw is not available on Hulu.'

### incorrect_routing
- `conf_entropy` / `arc-MCAS_2014_5_15` (en): gold='D', answer='B'
- `conf_entropy` / `belebele-aadf621d20-pes_Arab` (pes_Arab): gold='B', answer='C'
- `conf_entropy` / `belebele-0aa83ddbb8-pes_Arab` (pes_Arab): gold='C', answer='B'
- `conf_entropy` / `belebele-b9d85af5e1-eng_Latn` (en): gold='C', answer='A'
- `conf_entropy` / `belebele-07de2ab0e2-eng_Latn` (en): gold='C', answer='B'
