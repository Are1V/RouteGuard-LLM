#!/bin/bash
# Stage 1: one array task per shard generates its share of all (model, item) requests.
# Submit through scripts/cluster/submit_slurm.sh, which sets CONFIG, SHARD_DIR and the array size.
#SBATCH --job-name=rg-generate
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x_%A_%a.out
# Latency is measured on the node that generates. Pin one GPU type (e.g. --constraint=a100)
# if you want latency comparisons to be meaningful across shards.
set -euo pipefail
: "${CONFIG:?set CONFIG}" "${SHARD_DIR:?set SHARD_DIR}"
mkdir -p "$SHARD_DIR"
# Load your cluster's modules / activate the environment here, e.g.:
#   module load cuda/12.4 && source .venv/bin/activate
routeguard generate --config "$CONFIG" --shard auto \
  --cache "$SHARD_DIR/shard_${SLURM_ARRAY_TASK_ID}.sqlite" ${MODELS:+--models $MODELS}
