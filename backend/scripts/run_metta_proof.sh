#!/usr/bin/env sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
petta_root="${HELIXMIND_PETTA_ROOT:-$project_root/.runtime/PeTTa}"
swi_bin="${HELIXMIND_SWI_BIN:-$project_root/.runtime/swi-prolog-10.1.12/bin}"

if [ ! -x "$swi_bin/swipl" ] || [ ! -f "$petta_root/run.sh" ]; then
  echo "HelixMind's private OmegaClaw/PeTTa runtime is unavailable." >&2
  exit 1
fi

cd "$petta_root"
PATH="$swi_bin:$PATH" sh run.sh "$project_root/backend/reasoning/hbb_sickle_cell.metta"
