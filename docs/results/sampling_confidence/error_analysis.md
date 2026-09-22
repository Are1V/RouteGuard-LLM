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
| conf_self_consistency | 430 | 101 | 0 | 65 | 6 | 22 | 168 | 81 | 3 | 18 | 12 | 28 | 0 | 0 |
| conf_semantic_entropy | 430 | 101 | 0 | 65 | 6 | 22 | 168 | 81 | 3 | 18 | 12 | 28 | 0 | 0 |
| routeguard | 430 | 101 | 0 | 65 | 6 | 0 | 304 | 81 | 3 | 18 | 12 | 28 | 0 | 0 |

## Counts per language (all systems)

| Language | incorrect_routing | model_capability_failure | extraction_failure | high_confidence_wrong | low_confidence_correct | verifier_false_pass | verifier_false_fail | escalation_failure | escalation_harm | language_related_failure | retrieval_failure | unsupported_answer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| en | 0 | 111 | 0 | 26 | 273 | 111 | 6 | 18 | 12 | 0 | 0 | 0 |
| fa | 0 | 18 | 12 | 4 | 12 | 24 | 0 | 3 | 3 | 18 | 0 | 0 |
| kk | 0 | 18 | 3 | 6 | 52 | 27 | 0 | 0 | 0 | 18 | 0 | 0 |
| pes_Arab | 0 | 15 | 0 | 2 | 83 | 21 | 0 | 9 | 9 | 9 | 0 | 0 |
| prs_Arab | 0 | 6 | 0 | 0 | 54 | 9 | 0 | 3 | 3 | 3 | 0 | 0 |
| ru | 0 | 27 | 3 | 6 | 166 | 51 | 3 | 21 | 9 | 36 | 0 | 0 |

## Examples (first five per label)

### low_confidence_correct
- `conf_self_consistency` / `arc-ACTAAP_2013_7_16` (en): gold='D', answer='D'
- `conf_self_consistency` / `arc-Mercury_SC_405086` (en): gold='B', answer='B'
- `conf_self_consistency` / `arc-Mercury_7098473` (en): gold='B', answer='B'
- `conf_self_consistency` / `arc-Mercury_400877` (en): gold='C', answer='C'
- `conf_self_consistency` / `arc-Mercury_7159075` (en): gold='B', answer='C'

### model_capability_failure
- `conf_self_consistency` / `arc-Mercury_7016765` (en): gold='A', answer='C'
- `conf_self_consistency` / `arc-MCAS_2016_8_15` (en): gold='C', answer='A'
- `conf_self_consistency` / `belebele-7769f3fe4e-pes_Arab` (pes_Arab): gold='B', answer='C'
- `conf_self_consistency` / `belebele-7eb81bcb23-eng_Latn` (en): gold='C', answer='A'
- `conf_self_consistency` / `belebele-7eb81bcb23-kaz_Cyrl` (kk): gold='C', answer='D'

### verifier_false_pass
- `conf_self_consistency` / `arc-Mercury_7016765` (en): gold='A', answer='C'
- `conf_self_consistency` / `arc-Mercury_7159075` (en): gold='B', answer='C'
- `conf_self_consistency` / `arc-Mercury_SC_400134` (en): gold='D', answer='B'
- `conf_self_consistency` / `belebele-7eb81bcb23-eng_Latn` (en): gold='C', answer='A'
- `conf_self_consistency` / `belebele-7eb81bcb23-kaz_Cyrl` (kk): gold='C', answer='D'

### escalation_harm
- `conf_self_consistency` / `arc-Mercury_7159075` (en): gold='B', answer='C'
- `conf_self_consistency` / `belebele-aa6094d01b-pes_Arab` (pes_Arab): gold='C', answer='B'
- `conf_self_consistency` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `conf_self_consistency` / `gmmlu-fa-high_school_chemistry/test/84` (fa): gold='B', answer='D'
- `conf_self_consistency` / `gmmlu-en-high_school_computer_science/test/40` (en): gold='B', answer='A'

### escalation_failure
- `conf_self_consistency` / `arc-Mercury_7159075` (en): gold='B', answer='C'
- `conf_self_consistency` / `belebele-aa6094d01b-pes_Arab` (pes_Arab): gold='C', answer='B'
- `conf_self_consistency` / `belebele-43c1d735d8-rus_Cyrl` (ru): gold='B', answer='A'
- `conf_self_consistency` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `conf_self_consistency` / `belebele-3092395e67-rus_Cyrl` (ru): gold='C', answer='D'

### high_confidence_wrong
- `conf_self_consistency` / `arc-Mercury_SC_400134` (en): gold='D', answer='B'
- `conf_self_consistency` / `belebele-7eb81bcb23-kaz_Cyrl` (kk): gold='C', answer='D'
- `conf_self_consistency` / `belebele-40aa1fe314-pes_Arab` (pes_Arab): gold='D', answer='A'
- `conf_self_consistency` / `gmmlu-ru-professional_accounting/test/129` (ru): gold='B', answer='C'
- `conf_self_consistency` / `gmmlu-fa-professional_accounting/test/129` (fa): gold='B', answer='C'

### extraction_failure
- `conf_self_consistency` / `belebele-3650c64180-kaz_Cyrl` (kk): gold='A', answer=None
- `conf_self_consistency` / `gmmlu-fa-moral_scenarios/test/839` (fa): gold='A', answer=None
- `conf_self_consistency` / `gmmlu-fa-high_school_biology/test/81` (fa): gold='B', answer=None
- `conf_self_consistency` / `gmmlu-fa-high_school_geography/test/4` (fa): gold='D', answer=None
- `conf_self_consistency` / `gmmlu-fa-high_school_computer_science/test/40` (fa): gold='B', answer=None

### language_related_failure
- `conf_self_consistency` / `belebele-3650c64180-kaz_Cyrl` (kk): gold='A', answer=None
- `conf_self_consistency` / `belebele-7769f3fe4e-pes_Arab` (pes_Arab): gold='B', answer='C'
- `conf_self_consistency` / `belebele-aa6094d01b-pes_Arab` (pes_Arab): gold='C', answer='B'
- `conf_self_consistency` / `belebele-ea8905465a-rus_Cyrl` (ru): gold='B', answer='A'
- `conf_self_consistency` / `belebele-40aa1fe314-kaz_Cyrl` (kk): gold='D', answer='A'

### verifier_false_fail
- `conf_self_consistency` / `gmmlu-en-high_school_computer_science/test/40` (en): gold='B', answer='A'
- `conf_self_consistency` / `mgsm-en-107` (en): gold='3', answer='3'
- `conf_self_consistency` / `mgsm-ru-249` (ru): gold='5600', answer='5600'
- `conf_semantic_entropy` / `gmmlu-en-high_school_computer_science/test/40` (en): gold='B', answer='A'
- `conf_semantic_entropy` / `mgsm-en-107` (en): gold='3', answer='3'
