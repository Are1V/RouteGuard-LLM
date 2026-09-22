"""Local inference with Hugging Face Transformers.

Requests are grouped by sampling configuration and generated in left-padded
batches. Token log-probabilities are recorded from the *raw* logits (before temperature or
top-p warping) by a lightweight logits processor that keeps only the top-k per step,
so confidence estimates are not distorted by sampling settings and memory stays small.

PyTorch >= 2.10 may route some ops through JIT-compiled Triton kernels that need a
C toolchain and Python headers at run time. The backend sets
``TORCH_DISABLE_NATIVE_JIT=1`` (unless already set in the environment) before
importing torch, so standard ATen kernels are used: portable and reproducible.
Set ``TORCH_DISABLE_NATIVE_JIT=0`` to opt back in.

Latency: with ``batch_size > 1`` a request's ``latency_s`` is the batch wall time
divided by the batch size (amortised compute time); the unamortised batch time is
kept in ``extra['batch_latency_s']``. Use ``batch_size: 1`` to measure true
per-request latency (see docs/reproducibility.md).
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import time
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from routeguard.models.base import BaseLLM, ModelSpec
from routeguard.types import GenerationOutput, GenerationRequest, Message
from routeguard.utils.imports import require
from routeguard.utils.seeding import derive_seed

logger = logging.getLogger(__name__)


def _disable_native_jit() -> None:
    """Keep PyTorch on standard ATen kernels (see module docstring).

    The flag is read when torch is imported. If torch was already imported without it,
    the JIT-compiled Triton overrides are deregistered through torch's own function; if
    that private function is unavailable (another torch version), a warning is logged.
    """
    if os.environ.get("TORCH_DISABLE_NATIVE_JIT") == "0":
        return  # explicit opt-in to torch's JIT kernels
    already_imported = "torch" in sys.modules
    os.environ.setdefault("TORCH_DISABLE_NATIVE_JIT", "1")
    if not already_imported:
        return
    try:
        triton_utils = importlib.import_module("torch._native.triton_utils")
        triton_utils.deregister_op_overrides()
    except (ImportError, AttributeError) as exc:
        logger.warning(
            "torch was imported before the Hugging Face backend and its JIT kernels could not be "
            "disabled (%s). If generation fails while compiling Triton kernels, set "
            "TORCH_DISABLE_NATIVE_JIT=1 before starting Python.",
            exc,
        )


_RECORD_K = 20


class _TopKRecorder:
    """Logits processor that records the top-k log-probabilities of every decoding step.

    Storing full-vocabulary logits for every step (``output_logits=True``) costs
    ``batch × vocab`` floats per step, several GB per batch for 150k-token vocabularies.
    This keeps only the top-k of the *raw* distribution (it runs before temperature/top-p
    warpers). The chosen token's log-probability is exact whenever the token is in the
    top-k, which always holds for greedy decoding. For a sampled token outside the top-k,
    the k-th value is used as an upper bound, and such tokens are counted in
    ``GenerationOutput.extra['tokens_outside_topk']``.
    """

    def __init__(self, torch: Any, k: int):
        self.torch = torch
        self.k = k
        self.values: list[Any] = []
        self.indices: list[Any] = []

    def __call__(self, _input_ids: Any, scores: Any) -> Any:
        logp = self.torch.log_softmax(scores.float(), dim=-1)
        vals, idx = logp.topk(self.k, dim=-1)
        self.values.append(vals)
        self.indices.append(idx)
        return scores

    def collect(self, seqs: Any) -> tuple[Any, Any, Any]:
        torch = self.torch
        vals = torch.stack(self.values, dim=1)  # [batch, steps, k]
        idx = torch.stack(self.indices, dim=1)
        chosen_ids = seqs[:, : vals.shape[1]].unsqueeze(-1)
        match = idx == chosen_ids
        inside = match.any(dim=-1)
        chosen = torch.where(inside, (vals * match).sum(dim=-1), vals[..., -1])
        return chosen.cpu(), vals.cpu(), (~inside).cpu()


class HuggingFaceLLM(BaseLLM):
    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        _disable_native_jit()
        self.torch = require("torch", "hf", "The Hugging Face backend")
        transformers = require("transformers", "hf", "The Hugging Face backend")
        o = spec.options
        torch = self.torch
        device = o.get("device", "auto")
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        dtype_name = o.get("dtype", "auto")
        if dtype_name == "auto":
            dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
        else:
            dtype = getattr(torch, dtype_name)
        self.batch_size = int(o.get("batch_size", 8))
        self.chat_template_kwargs: dict[str, Any] = dict(o.get("chat_template_kwargs", {}))
        trust = bool(o.get("trust_remote_code", False))
        revision = o.get("revision")

        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            spec.model_id, padding_side="left", trust_remote_code=trust, revision=revision
        )
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = transformers.AutoModelForCausalLM.from_pretrained(
            spec.model_id, dtype=dtype, trust_remote_code=trust, revision=revision
        ).to(device)
        self.model.eval()
        if spec.params_b <= 0:
            spec.params_b = sum(p.numel() for p in self.model.parameters()) / 1e9
        eos = self.model.generation_config.eos_token_id
        self.eos_ids = set(eos if isinstance(eos, list) else [eos]) | {self.tokenizer.eos_token_id}
        self.eos_ids.discard(None)

    def _render(self, messages: list[Message]) -> str:
        if self.tokenizer.chat_template:
            rendered = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, **self.chat_template_kwargs
            )
            return str(rendered)
        return (
            "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages) + "\n\nASSISTANT:"
        )

    def generate(self, request: GenerationRequest) -> GenerationOutput:
        return self.generate_batch([request])[0]

    def generate_batch(self, requests: Sequence[GenerationRequest]) -> list[GenerationOutput]:
        groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        for i, r in enumerate(requests):
            groups[(r.temperature, r.top_p, r.max_new_tokens, r.top_logprobs)].append(i)
        results: list[GenerationOutput | None] = [None] * len(requests)
        for idxs in groups.values():
            # Sort by prompt length inside a group to reduce padding.
            idxs.sort(key=lambda i: sum(len(m["content"]) for m in requests[i].messages))
            for start in range(0, len(idxs), self.batch_size):
                chunk = idxs[start : start + self.batch_size]
                for i, out in zip(chunk, self._run([requests[i] for i in chunk]), strict=True):
                    results[i] = out
        return [r for r in results if r is not None]

    def _run(self, reqs: list[GenerationRequest]) -> list[GenerationOutput]:
        torch = self.torch
        first = reqs[0]
        prompts = [self._render(r.messages) for r in reqs]
        enc = self.tokenizer(prompts, return_tensors="pt", padding=True, add_special_tokens=False)
        enc = {k: v.to(self.device) for k, v in enc.items()}
        sampling = first.temperature > 0
        recorder = _TopKRecorder(torch, k=max(_RECORD_K, first.top_logprobs))
        kwargs: dict[str, Any] = {
            "max_new_tokens": first.max_new_tokens,
            "do_sample": sampling,
            "return_dict_in_generate": True,
            "pad_token_id": self.tokenizer.pad_token_id,
            "logits_processor": [recorder] if any(r.logprobs for r in reqs) else None,
        }
        if sampling:
            kwargs.update(temperature=first.temperature, top_p=first.top_p)
            torch.manual_seed(derive_seed(*[r.seed for r in reqs]))
        else:
            kwargs.update(temperature=None, top_p=None, top_k=None)
        if self.device.startswith("cuda"):
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        with torch.inference_mode():
            out = self.model.generate(**enc, **kwargs)
        if self.device.startswith("cuda"):
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - t0

        prompt_len = enc["input_ids"].shape[1]
        seqs = out.sequences[:, prompt_len:]
        steps = recorder.collect(seqs) if recorder.values else None
        input_lens = enc["attention_mask"].sum(dim=1).tolist()

        outputs = []
        for b, req in enumerate(reqs):
            ids = seqs[b].tolist()
            n = len(ids)
            finish = "length"
            for j, tok in enumerate(ids):
                if tok in self.eos_ids:
                    n, finish = j + 1, "stop"
                    break
            text = self.tokenizer.decode(ids[:n], skip_special_tokens=True)
            if req.stop:
                cut = min((text.find(s) for s in req.stop if s in text), default=-1)
                if cut >= 0:
                    text, finish = text[:cut], "stop"
            token_lps = top_lps = None
            extra: dict[str, Any] = {"batch_latency_s": elapsed, "batch_size": len(reqs)}
            if req.logprobs and steps is not None:
                chosen, tops, outside = steps
                token_lps = [float(chosen[b, t]) for t in range(n)]
                top_lps = [tops[b, t, : req.top_logprobs].tolist() for t in range(n)]
                extra["tokens_outside_topk"] = int(outside[b, :n].sum())
            outputs.append(
                GenerationOutput(
                    text=text.strip(),
                    model=self.spec.name,
                    input_tokens=int(input_lens[b]),
                    output_tokens=n,
                    latency_s=elapsed / len(reqs),
                    token_logprobs=token_lps,
                    top_logprobs=top_lps,
                    finish_reason=finish,
                    extra=extra,
                )
            )
        return outputs

    def resource_stats(self) -> dict[str, Any]:
        """Weight memory of this model and the *process-wide* peak GPU memory.

        CUDA's peak counter covers everything in the process (all loaded models, KV caches,
        activations), so it is reported under a process-level name, not per model.
        """
        weights = sum(p.numel() * p.element_size() for p in self.model.parameters())
        stats: dict[str, Any] = {
            "device": self.device,
            "params_b": round(self.spec.params_b, 3),
            "weights_gb": round(weights / 1e9, 3),
        }
        if self.device.startswith("cuda"):
            peak = self.torch.cuda.max_memory_allocated() / 1e9
            stats["process_peak_gpu_memory_gb"] = round(peak, 3)
        return stats
