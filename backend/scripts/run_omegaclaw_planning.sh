#!/usr/bin/env sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
petta_root="${HELIXMIND_PETTA_ROOT:-$project_root/.runtime/PeTTa}"
swi_bin="${HELIXMIND_SWI_BIN:-$project_root/.runtime/swi-prolog-10.1.12/bin}"
omega_venv="${HELIXMIND_OMEGACLAW_VENV:-$project_root/.runtime/omegaclaw-venv}"
config_path="$project_root/backend/omegaclaw/planning.yaml"
run_path="$project_root/backend/omegaclaw/run_planning.metta"

if [ ! -x "$swi_bin/swipl" ] || [ ! -f "$petta_root/run.sh" ] || [ ! -x "$omega_venv/bin/python" ]; then
  echo "HelixMind's private OmegaClaw runtime is unavailable." >&2
  exit 1
fi

set -a
. /etc/helixmind/helixmind.env
set +a
: "${GEMINI_API_KEY:?GEMINI_API_KEY must be configured}"
: "${GROQ_API_KEY:?GROQ_API_KEY must be configured}"

request_payload=$(cat)
request_dir=$(mktemp -d /tmp/helixmind-omegaclaw-planning.XXXXXX)
trap 'rm -rf "$request_dir"' EXIT INT TERM
chmod 700 "$request_dir"
export HELIXMIND_PLANNING_REQUEST="$request_payload"
export HELIXMIND_OMEGACLAW_MODE=planning
export PYTHONNOUSERSITE=1
export CHROMA_DB_PATH="$request_dir/chroma"
mkdir -p "$CHROMA_DB_PATH"
omega_core="$petta_root/repos/OmegaClaw-Core"
export PYTHONPATH="$omega_venv/lib/python3.12/site-packages:$omega_core:$omega_core/src:$omega_core/providers:$omega_core/profile${PYTHONPATH:+:$PYTHONPATH}"

cd "$petta_root"
PATH="$swi_bin:$PATH" timeout --signal=TERM 900 sh run.sh "$run_path" "config=$config_path" "memoryDirectory=$request_dir"
