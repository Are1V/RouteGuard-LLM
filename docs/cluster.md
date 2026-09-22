# Running on clusters

Almost all GPU time in a RouteGuard experiment is the *initial* answer of every pool model for
every item. For the core suite that is 3 models × 2,150 items, shared by every system and seed.
Those requests are independent, so they are generated in parallel shards. Evaluation then
replays them from the generation cache.

```
┌──────────── stage 1: N GPU jobs (array) ─────────────┐   ┌── stage 2: 1 job ─────────────┐
│ routeguard generate --shard i/N --cache shard_i.sqlite │ → │ routeguard cache-merge ...     │
└────────────────────────────────────────────────────────┘   │ routeguard benchmark --config  │
                                                              └────────────────────────────────┘
```

- **Shards are disjoint and balanced.** The unique requests of all systems are planned
  deterministically, keyed by the same cache key the benchmark uses, sorted, and dealt
  round-robin. Any job can compute any shard.
- **One SQLite file per job.** SQLite on a network file system is not safe for concurrent
  writers, so shards never share a database. `cache-merge` combines them.
- **Stage 2 needs little GPU.** Every initial answer is a cache hit. The GPU is used only for
  what depends on earlier results: escalation stages whose prompts were not pre-generated,
  sampling-based confidence, and LLM judges.
- Systems with a *learned* task classifier are skipped by the planner (their prompts depend on
  a fitted component) and generate their remaining requests in stage 2.

## SLURM

```bash
scripts/cluster/submit_slurm.sh experiments/baselines/main.yaml 16
```

This submits `slurm_generate.sbatch` as a 16-task array (`--shard auto` reads
`SLURM_ARRAY_TASK_ID`/`SLURM_ARRAY_TASK_COUNT`), then `slurm_benchmark.sbatch` with
`--dependency=afterok`. Edit the `#SBATCH` lines (partition, GPU type, time) and the
environment-activation line for your cluster. Environment variables:

| Variable | Meaning | Default |
|---|---|---|
| `SHARD_DIR` | where shard caches are written (shared file system) | `.routeguard_cache/shards/<experiment>` |
| `CACHE` | merged cache; **must equal `cache.path` of the experiment's pipeline** | `.routeguard_cache/hf.sqlite` |
| `MODELS` | only generate these pool models (space-separated) | all |

## One machine, several GPUs

```bash
scripts/cluster/local_multi_gpu.sh experiments/baselines/main.yaml 4
```

This runs one shard per GPU (`CUDA_VISIBLE_DEVICES=i`), then merges and runs the benchmark.

## Other schedulers

The two stages are plain commands, so any scheduler (PBS, LSF, Kubernetes jobs, Ray) can run
them. Give job *i* of *N* `routeguard generate --config X --shard i/N --cache <unique file>`, run
`routeguard cache-merge <files> --out <cache.path>` once they finish, then
`routeguard benchmark --config X`.

## Validity notes

- **Latency** is measured on the node that generated a request (amortised over its batch).
  Mixing GPU types across shards makes latency comparisons between systems meaningless.
  Constrain the array to one GPU type (e.g. `--constraint`), or compare systems on compute
  (TFLOPs) and tokens, which do not depend on the node.
- **Numerics.** Greedy bf16 outputs can differ in rare low-probability ties between GPU types.
  Every request is generated exactly once and then replayed, so all systems see identical outputs
  within an experiment. Record the GPU types used; each generation keeps its measured latency and
  batch information in the cache.
- The sharded workflow is covered by `tests/integration/test_sharding.py`, which checks
  disjointness, completeness of the merge, and that the replayed benchmark hits the cache for
  every initial answer.
