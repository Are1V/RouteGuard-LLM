# Multilingual evaluation

RouteGuard treats **language as an axis orthogonal to the task**. "Multilingual QA" is the
language axis crossed with the task axis, not a separate category. Every metric can therefore be
broken down by language (`by_language` in `metrics.json`) and by task (`by_category`).

## Languages and data

| Language | Code | Script | Data in the core suite | Notes |
|---|---|---|---|---|
| English | `en` | Latin | all seven datasets | reference language for paired comparisons |
| Kazakh | `kk` | Cyrillic | Belebele, SIB-200 | lower-resource; no public Kazakh math/knowledge set with a clear license was found |
| Russian | `ru` | Cyrillic | Belebele, SIB-200, Global-MMLU, MGSM | |
| Persian (Iranian) | `fa` / `pes_Arab` | Arabic | Belebele, SIB-200 | |
| Persian (variety unspecified) | `fa` | Arabic | Global-MMLU | the dataset labels it `fa` without a variety, so it is reported as `fa` |
| Dari | `fa` / `prs_Arab` | Arabic | SIB-200 | Belebele on the Hub has `pes_Arab` but no `prs_Arab`, so Dari coverage is currently classification only |

Gaps are reported, not filled. We did not machine-translate benchmarks or write synthetic
evaluation data. For additional Kazakh or Dari data, use the curated format in
`adding_datasets.md` (`benchmarks/samples/curated_template.jsonl`), with a native-speaker author
and reviewer.

## Language identification

`analysis/language.py` identifies the script, then disambiguates within the script using letters
distinctive for a language (Kazakh `ә ғ қ ң ө ұ ү һ і`, Persian `پ چ ژ گ`) plus short stopword
lists. It is transparent by design, so identification errors are measurable
(`language_id_accuracy` per language). The language of a query is detected from the question
*and* its passage: an English instruction over a Dari passage is a Dari query.

It does **not** separate Dari from Iranian Persian; both are `fa`. The dataset variant is kept in
`language_variant`, and all per-language results use the variant, so Dari and Iranian Persian are
reported separately.

Add a language:

```python
from routeguard.analysis import LanguageProfile, register_language

register_language(
    LanguageProfile("uz", "Uzbek (Cyrillic)", "Cyrillic", "ўқғҳ", frozenset({"ва", "бу", "учун"}))
)
```

## Text normalisation

`utils/text.py` folds Arabic/Persian letter variants (`ي→ی`, `ك→ک`), maps Persian and
Arabic-Indic digits to ASCII, treats ZWNJ as a word boundary, and strips diacritics *except*
Cyrillic `й`/`ё`, which are separate letters in Russian and Kazakh. Without this, exact-match
scoring silently penalises Persian-script answers and every cross-language comparison is biased.

## Prompts

Instructions are in English for every query language; the question, passage and options stay in
their original language. This keeps the prompt constant, so differences are attributable to the
query language. Models sometimes answer in the query language (`Ответ: 19`, `پاسخ: ۱۹`), and the
answer extractor accepts localised answer markers and digits.

## Research questions and where they are measured

| Question | Experiment | Output |
|---|---|---|
| Does model selection change by language? | `multilingual`, `main` | `model_selection_distribution` per language (records: `routed_model` × `language_variant`) |
| Does confidence calibration differ by language? | `main` | `language_reliability` table (AUROC by language), per-language reliability diagrams |
| Do routing errors increase for low-resource languages? | `main` | `incorrect_small_model_rate` by language; `language_related_failure` counts |
| Does an English-trained router transfer? | `multilingual` | `routeguard_english_trained` vs `routeguard` |
| Does per-language calibration help? | `multilingual` | `routeguard_per_language_calibration` |
| Does retrieval quality change by language? | `rag/belebele_rag.yaml` | recall@k, MRR, accuracy given hit/miss per language |
| Are Dari and Iranian Persian handled equally? | `main` (SIB-200) | per-variant accuracy and calibration (`prs_Arab` vs `pes_Arab`) |
