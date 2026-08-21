#!/usr/bin/env sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
petta_root="${HELIXMIND_PETTA_ROOT:-$project_root/.runtime/PeTTa}"
swi_bin="${HELIXMIND_SWI_BIN:-$project_root/.runtime/swi-prolog-10.1.12/bin}"
omega_venv="${HELIXMIND_OMEGACLAW_VENV:-$project_root/.runtime/omegaclaw-venv}"
config_path="$project_root/backend/omegaclaw/proof.yaml"
run_path="$project_root/backend/omegaclaw/run_flagship_proof.metta"

if [ ! -x "$swi_bin/swipl" ] || [ ! -f "$petta_root/run.sh" ] || [ ! -x "$omega_venv/bin/python" ]; then
  echo "HelixMind's private OmegaClaw runtime is unavailable." >&2
  exit 1
fi

# The file is root-owned and group-readable only by the HelixMind service user.
# Do not echo the environment or enable shell tracing in this script.
set -a
. /etc/helixmind/helixmind.env
set +a

: "${GEMINI_API_KEY:?GEMINI_API_KEY must be configured}"
: "${GROQ_API_KEY:?GROQ_API_KEY must be configured}"

proof_dir=/tmp/helixmind-omegaclaw-proof
mkdir -p "$proof_dir"
mkdir -p "$proof_dir/chroma"
chmod 700 "$proof_dir"
export CHROMA_DB_PATH="$proof_dir/chroma"
export PYTHONNOUSERSITE=1
omega_core="$petta_root/repos/OmegaClaw-Core"
export PYTHONPATH="$omega_venv/lib/python3.12/site-packages:$omega_core:$omega_core/src:$omega_core/providers:$omega_core/profile${PYTHONPATH:+:$PYTHONPATH}"

cd "$petta_root"
PATH="$swi_bin:$PATH" timeout --signal=TERM 20 sh run.sh "$run_path" "config=$config_path"
