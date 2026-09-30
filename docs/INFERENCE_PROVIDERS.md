# HelixMind inference providers

HelixMind uses one provider contract for OmegaClaw language calls and future
embedding consumers. The provider layer is separate from scientific evidence:
LLM output is orchestration or structured extraction input, never authoritative
literature evidence, and MeTTa/NAL remains the symbolic reasoning substrate.

## Providers and routing

The shared backend adapter supports OpenAI-compatible chat and embedding
requests, model discovery, bounded retries, error categories, latency, usage,
fallback metadata, and safe diagnostics.

Provider routing is configurable. The default order is Groq, ASI Cloud, then
Gemini. Groq chat uses the OpenAI-compatible Cloudflare Worker transport; its
model catalogue is not required for a configured chat completion. The router
falls through to the next provider after bounded retries for transient errors
and on rate-limit, permission, authentication, or missing-configuration
failures. Invalid requests do not trigger provider fan-out.

```text
OMEGACLAW_PROVIDER_ORDER=groq,asi,gemini
GROQ_API_BASE_URL=https://groq-proxy.gethsun09.workers.dev/openai/v1
GROQ_API_KEY=<server-side secret>
GROQ_MODEL=openai/gpt-oss-120b
```

Set `OMEGACLAW_PROVIDER_ORDER` to override the order. The legacy
`OMEGACLAW_PROVIDER` setting, when present, moves that provider to the front.
The Worker is an external infrastructure dependency; its deployment and
credentials are managed outside this repository. Keep credentials in the
server environment only. Provider/model metadata records the provider that
actually returned the completion.

## ASI Cloud configuration

Keep all credentials in `/etc/helixmind/helixmind.env`; never commit or expose
them through the frontend:

```text
ASI_CLOUD_BASE_URL=https://llm.c.singularitynet.io/v1
ASI_CLOUD_API_KEY=<server-side secret>
ASI_CLOUD_API_KEY_1=<server-side secret>
ASI_CLOUD_API_KEY_2=<server-side secret>
ASI_CLOUD_API_KEY_3=<server-side secret>
ASI_CLOUD_CHAT_MODEL=asi1-mini
ASI_CLOUD_EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
ASI_CLOUD_TIMEOUT_SECONDS=30
ASI_CLOUD_RETRIES=2
```

The unsuffixed ASI key and optional `_1`, `_2`, and `_3` keys form one ordered
provider pool. Empty entries are ignored and duplicate secret values are
deduplicated. Historical `ASI_CLOUD_API_KEY1` and `ASI_CLOUD_API_KEY2`
spellings remain accepted during migration. Credentials rotate only for
authentication or rate-limit failures; invalid requests and missing models fail
without needless credential rotation. Timeouts, network failures,
and provider 5xx responses use bounded exponential retry. The adapter never
logs authorization headers or secret values.

The verified gateway catalogue includes `asi1-mini`,
`openai/gpt-oss-20b`, `openai/gpt-oss-120b`,
`BAAI/bge-base-en-v1.5`, and `WhereIsAI/UAE-Large-V1`. Availability is still
checked through `/v1/models` because provider catalogues can change.

## Embeddings

The ASI embedding adapter currently defaults to `BAAI/bge-base-en-v1.5`. It
returns vectors with provider/model, credential-slot, latency, and input-count
metadata for future retrieval consumers. The current Phase 3E reasoning path
does not use embeddings, add a vector database, or replace the canonical
PostgreSQL provenance graph.

## Diagnostics and testing

The protected admin diagnostics response reports only configured provider
names, selected models, model availability, reachability, and error category.
It does not return credentials or authorization headers. Development tests use
transport-level fakes for rotation and fallback; production verification must
also record real `/models`, chat, and embedding results without recording
secret material.

The private OmegaClaw adapter now calls the shared HelixMind router. It still
validates planning JSON and the constrained proof-specific MeTTa command, so
provider integration does not turn symbolic reasoning into LLM-generated
scientific conclusions.
