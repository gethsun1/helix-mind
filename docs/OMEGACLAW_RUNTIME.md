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

## Full agent-loop boundary

OmegaClaw's full `omegaclaw` loop requires an LLM provider key and activates
its configured communication, web, shell, and file skills. HelixMind does not
start that loop until a dedicated provider configuration and restrictive
runtime policy are in place. This is intentional: no mock planner or fake
OmegaClaw orchestration is substituted for the real agent.
