#!/usr/bin/env bash
# The same sharded workflow on one machine with several GPUs (no scheduler needed).
#
#   scripts/cluster/local_multi_gpu.sh experiments/baselines/main.yaml 4
set -euo pipefail
CONFIG=${1:?usage: local_multi_gpu.sh <experiment.yaml> <n_gpus>}
N=${2:?usage: local_multi_gpu.sh <experiment.yaml> <n_gpus>}
SHARD_DIR=${SHARD_DIR:-.routeguard_cache/shards/$(basename "$CONFIG" .yaml)}
CACHE=${CACHE:-.routeguard_cache/hf.sqlite}
mkdir -p "$SHARD_DIR" logs
for i in $(seq 0 $((N - 1))); do
  CUDA_VISIBLE_DEVICES=$i routeguard generate --config "$CONFIG" --shard "$i/$N" \
    --cache "$SHARD_DIR/shard_$i.sqlite" > "logs/generate_$i.log" 2>&1 &
done
wait
routeguard cache-merge "$SHARD_DIR"/shard_*.sqlite --out "$CACHE"
routeguard benchmark --config "$CONFIG"
