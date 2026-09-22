#!/usr/bin/env bash
# Reproduce every experiment reported in the README, in order.
# Requirements: pip install -e ".[hf,data]" and one GPU with >= 24 GB memory.
# All experiments share one generation cache (.routeguard_cache/hf.sqlite): the first run
# generates, later runs mostly replay cached generations.
set -euo pipefail

routeguard benchmark --config experiments/baselines/main.yaml
routeguard benchmark --config experiments/ablations/routeguard_ablations.yaml
routeguard benchmark --config experiments/multilingual/multilingual_routing.yaml
routeguard benchmark --config experiments/routing/router_comparison.yaml
routeguard benchmark --config experiments/routing/risk_sweep.yaml
routeguard benchmark --config experiments/ablations/sampling_confidence.yaml
routeguard rag-eval --config experiments/rag/belebele_rag.yaml
routeguard tool-eval --config experiments/tools/tool_use_hf.yaml

echo "All runs written to results/runs/"
