#!/bin/bash
# Stage 2: merge the shard caches, then run the full benchmark protocol. All initial answers are
# cache hits; the GPU is only needed for the remaining escalation/sampling requests.
#SBATCH --job-name=rg-benchmark
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=logs/%x_%j.out
set -euo pipefail
: "${CONFIG:?set CONFIG}" "${SHARD_DIR:?set SHARD_DIR}" "${CACHE:?set CACHE}"
routeguard cache-merge "$SHARD_DIR"/shard_*.sqlite --out "$CACHE"
routeguard benchmark --config "$CONFIG"
