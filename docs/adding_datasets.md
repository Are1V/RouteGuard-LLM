# Adding datasets

## Option 1: a JSONL file (no code)

One item per line, in the schema of `routeguard/benchmarks/schema.py`:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | unique across all datasets of an experiment |
| `question` | yes | the text shown to the model (options and passage go in their own fields) |
| `answer` | yes | gold answer; a string or a list of accepted aliases; an option letter for `choice` |
| `answer_type` | yes | `numeric`, `choice`, `text`, or `code` |
| `category` | yes | task category (see `routeguard/resources/categories.yaml`) |
| `language` | yes | ISO 639-1 code of the query language |
| `language_variant` | no | e.g. `prs_Arab` (Dari) vs `pes_Arab` (Iranian Persian) |
| `choices` | for `choice` | list of option texts (letters A, B, C, ... are added by the prompt) |
| `context` | no | passage the question refers to |
| `public_tests` / `eval_tests` | for `code` | tests shown to the model / tests used for scoring |
| `entry_point`, `solution` | no | required function name; reference solution |
| `parallel_id` | no | shared by translations of the same item (keeps them in one split) |
| `source`, `license` | yes (recommended) | provenance, reported in results |
| `metadata` | no | anything else (e.g. `gold_doc_ids` for retrieval) |

```yaml
data:
  - {loader: jsonl, path: data/my_kazakh_set.jsonl, limit: 200, options: {languages: [kk]}}
```

Items are validated when loaded; an invalid line reports its file and line number.

### Curated multilingual data

`benchmarks/samples/curated_template.jsonl` shows the format for manually written items. It is a
template: every `<...>` field must be replaced. For curated Kazakh, Dari or other items:

1. Write items natively. Do not machine-translate existing benchmarks without disclosure, and
   check the source license if you translate.
2. Record the author and an independent native-speaker reviewer in `metadata`.
3. Prefer answers that can be scored deterministically (numbers, options, short spans).
4. Use `parallel_id` when the same item exists in several languages.
5. Choose and state a license (e.g. CC-BY-4.0).

## Option 2: a loader for a public dataset

```python
from routeguard.benchmarks import Item, register_loader
from routeguard.config import DatasetConfig


def load_my_dataset(cfg: DatasetConfig) -> list[Item]:
    import datasets

    rows = datasets.load_dataset("org/name", split="test", revision="<commit sha>")
    return [
        Item(
            id=f"my-{i}",
            question=r["q"],
            answer=r["a"],
            answer_type="text",
            category="factual_qa",
            language="en",
            source="my_dataset",
            license="CC-BY-4.0",
        )
        for i, r in enumerate(rows)
    ]


register_loader("my_dataset", load_my_dataset)
```

Pin the revision, record the license from the dataset card, convert without leaking gold data
into `question`, and add a unit test with mocked rows (see `tests/unit/test_benchmarks.py`).
Check for overlap with other datasets in the same experiment (see the GSM8K/MGSM note in
`benchmarks.md`).
