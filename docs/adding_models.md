# Adding models and backends

## Use any model with an existing backend

Models are ordered **weakest/cheapest first**. The pool can have any number of models.

```yaml
models:
  - name: small                      # name used by routers and in results
    backend: huggingface             # huggingface | openai_compatible | simulated
    model_id: Qwen/Qwen3-1.7B
    params_b: 1.721                  # used for compute estimates and cost-aware routing
    price_input_per_1k: 0.0          # optional USD prices (API models)
    price_output_per_1k: 0.0
    max_new_tokens: 512
    options:
      revision: <commit sha>         # pin for reproducibility
      batch_size: 32
      device: auto                   # cuda / cpu / auto
      dtype: auto                    # bfloat16 on GPU, float32 on CPU
      chat_template_kwargs: {enable_thinking: false}
      trust_remote_code: false
```

Set `params_b` (or prices) explicitly. Cost-aware routers need relative costs before any model is
loaded. The pool logs a warning if the configured order is not monotone in estimated cost.

### vLLM, llama.cpp, Ollama, hosted APIs

All speak the OpenAI chat-completions protocol:

```yaml
  - name: large
    backend: openai_compatible
    model_id: Qwen/Qwen3-8B
    params_b: 8.191
    options:
      base_url: http://localhost:8000/v1       # vllm serve / llama-server / ollama (/v1)
      api_key_env: ROUTEGUARD_API_KEY          # name of an environment variable, never the key
      timeout_s: 120
      max_retries: 4
      extra_body: {chat_template_kwargs: {enable_thinking: false}}
```

Validated end to end with vLLM 0.29 serving Qwen3-0.6B (`vllm serve Qwen/Qwen3-0.6B
--max-logprobs 20`): generation, token accounting, server-side log-probabilities for
token-probability confidence, and seeded sampling for self-consistency. Notes from that setup:

- Send one warm-up request before measuring latency. The first request after start-up includes
  kernel and graph initialisation (33 s in our test, 2 s afterwards).
- vLLM JIT-compiles kernels, so it needs a C compiler, `ninja` on `PATH`, and the Python headers.
  Without root, `apt-get download libpython3.12-dev` + `dpkg-deb -x` and pointing
  `C_INCLUDE_PATH` at the extracted `usr/include/python3.12` works. `--enforce-eager` avoids
  `torch.compile` but not the Triton kernels.

Log-probability confidence methods need `logprobs` support (vLLM and llama.cpp support it;
Ollama's OpenAI endpoint may not). Otherwise use `self_consistency` or `semantic_entropy`.
Config validation rejects `api_key`, `token`, `secret` or `password` fields in model options.

## Write a new backend

```python
from routeguard.models import BaseLLM, ModelSpec, register_backend
from routeguard.types import GenerationOutput, GenerationRequest


class MyBackend(BaseLLM):
    def __init__(self, spec: ModelSpec):
        super().__init__(spec)
        ...  # read spec.options; import heavy deps lazily

    def generate(self, request: GenerationRequest) -> GenerationOutput:
        ...  # measure latency; return tokens and logprobs if available
        return GenerationOutput(
            text=...,
            model=self.spec.name,
            input_tokens=...,
            output_tokens=...,
            latency_s=...,
            token_logprobs=...,
            top_logprobs=...,
        )


register_backend("my_backend", lambda: MyBackend)  # a function returning the class
```

Rules:

- Never read `request.metadata["reference"]`; it is gold data for the simulator only. Leave
  `requires_reference = False`.
- Override `generate_batch` if the backend can batch.
- Override the `spec_identity(spec)` classmethod if settings that change outputs are not in
  `spec.options`, so the generation cache does not mix outputs. Cache lookups use it without
  instantiating the backend, so cached replays never load weights.
- Implement `resource_stats()` if you can report memory.
- Raise `routeguard.utils.MissingDependencyError` (via `require(...)`) for optional dependencies.
