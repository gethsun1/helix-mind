# OmegaClaw and MeTTa runtime

HelixMind uses the supported OmegaClaw stack below, installed outside the
repository in a private runtime directory so application source and runtime
artifacts remain separate.

| Component | Source | Pinned version | Installation |
| --- | --- | --- | --- |
| OmegaClaw Core | `asi-alliance/OmegaClaw-Core` | `9890bcb8041598fc6a4f1d8e658b8306a204cc87` | `/opt/HelixMind/.runtime/PeTTa/repos/OmegaClaw-Core` |
| PeTTa | `trueagi-io/PeTTa` | `43705f5d9ff8958ffe7f0aa6777fb8477f2401f2` | `/opt/HelixMind/.runtime/PeTTa` |
| SWI-Prolog | `SWI-Prolog/swipl-devel` | `V10.1.12`, `3ac053b9297e46c15fb78a1f1afcd7e6c7eb50f0` | `/opt/HelixMind/.runtime/swi-prolog-10.1.12` |

The Ubuntu SWI-Prolog package was not used because it is version 9.0.4 while
PeTTa requires SWI-Prolog 9.3 or newer. The private build includes Janus
(Python interop) and PCRE2 support.

## Verified scientific proof

`backend/reasoning/hbb_sickle_cell.metta` imports OmegaClaw Core's actual
`lib_nal.metta` and runs the HBB → HbSVariant → SickleCellDisease deduction.
It returns:

```text
(--> HBB SickleCellDisease) (stv 1.0 0.855)
```

Run it with:

```sh
backend/scripts/run_metta_proof.sh
```

The `stv` is an evidence-system truth value, not a clinical probability. Its
two premises are labeled as source facts in the MeTTa program; later literature
ingestion will supply real provenance and evidence rather than hard-coded
premises.

## Constrained provider proof

HelixMind now has a private OmegaClaw Python environment at
`/opt/HelixMind/.runtime/omegaclaw-venv`. It contains the minimal official
OmegaClaw runtime dependencies (`openai 2.38.0`, `chromadb 1.5.9`, and
`py-landlock 0.1.1`) and is separate from the FastAPI virtual environment.

The proof configuration and adapter are versioned in `backend/omegaclaw/`:

| Role | Configuration |
| --- | --- |
| Primary LLM | Google Gemini via its OpenAI-compatible endpoint; model `gemini-3.5-flash`; key name `GEMINI_API_KEY` |
| Fallback LLM | Groq via its OpenAI-compatible endpoint; model `openai/gpt-oss-20b`; key name `GROQ_API_KEY` |
| OmegaClaw provider selector | Core's documented `OpenAIAPI` selector, overridden only in the private HelixMind proof plugin to add ordered failover |
| Channel | One-shot in-process `helixmind-proof`; no listener, socket, or external chat channel |
| Agent capability | Only a fixed, source-grounded `metta` call is accepted; shell, file, web, memory, and communication calls are rejected |

Keys are sourced only from `/etc/helixmind/helixmind.env`; no key is stored in
the repository, private runtime configuration, logs, or documentation.

Run the constrained flagship proof with:

```sh
sudo -u helixmind backend/scripts/run_omegaclaw_flagship_proof.sh
```

Verified result through the real OmegaClaw agent loop and OmegaClaw Core NAL
library:

```text
(((--> HBB SickleCellDisease) (stv 1.0 0.855))
 ((--> SickleCellDisease HBB) (stv 1.0 0.4609164420485175)))
```

The configured Gemini key was verified against the account's models endpoint,
and `gemini-3.5-flash` accepted a direct chat-completions request. The former
`gemini-2.5-flash` configuration returned HTTP 404. The configured Groq fallback
currently returns HTTP 403. The complete OmegaClaw agent proof has not yet
completed: it exceeded its 60-second bound before producing an inference
result, and interrupting Janus/Python caused SWI-Prolog to segfault. Do not
enable the production worker until this end-to-end proof completes and the
fallback/provider behavior is resolved.

Private runtime compatibility changes (the `.runtime/` directory is excluded
from Git) register the HelixMind proof plugin, define the missing `_error`
helper in OmegaClaw Core's channel bridge, use the default prompt instead of a
PeTTa-generated invalid provider-specific path, and avoid loading the large
local embedding model for the OpenAI-embedding proof configuration. These
changes do not alter OmegaClaw reasoning or its provider protocol. Preserve
them when rebuilding the pinned runtime.

## Full agent-loop boundary

The constrained proof starts the real `omegaclaw` loop under a hard Landlock
policy and an in-process channel. It is not yet the production research agent:
the literature-worker integration will expose only the skills required for
planning, retrieval, evidence extraction, and MeTTa updates. No mock planner
or fake OmegaClaw orchestration is substituted for the real agent.
