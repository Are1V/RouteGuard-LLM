#!/usr/bin/env bash
# Submit sharded generation (array job) followed by merge + benchmark (dependency afterok).
#
#   scripts/cluster/submit_slurm.sh experiments/baselines/main.yaml 16
#
# CACHE must be the cache path of the experiment's pipeline config (cache.path), so that the
# benchmark replays the merged generations. Default: .routeguard_cache/hf.sqlite.
set -euo pipefail
CONFIG=${1:?usage: submit_slurm.sh <experiment.yaml> <n_shards>}
SHARDS=${2:?usage: submit_slurm.sh <experiment.yaml> <n_shards>}
SHARD_DIR=${SHARD_DIR:-.routeguard_cache/shards/$(basename "$CONFIG" .yaml)}
CACHE=${CACHE:-.routeguard_cache/hf.sqlite}
mkdir -p logs "$SHARD_DIR"
export CONFIG SHARD_DIR CACHE MODELS=${MODELS:-}
gen=$(sbatch --parsable --array=0-$((SHARDS - 1)) --export=ALL scripts/cluster/slurm_generate.sbatch)
bench=$(sbatch --parsable --dependency=afterok:${gen} --export=ALL scripts/cluster/slurm_benchmark.sbatch)
echo "generation array: ${gen} (${SHARDS} shards) -> benchmark: ${bench}"
