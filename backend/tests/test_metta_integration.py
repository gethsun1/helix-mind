import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_omegaclaw_nal_derives_hbb_sickle_cell_relationship() -> None:
    """Exercise the installed OmegaClaw Core NAL engine through PeTTa."""
    runner = PROJECT_ROOT / "backend/scripts/run_metta_proof.sh"
    private_runtime = PROJECT_ROOT / ".runtime/swi-prolog-10.1.12/bin/swipl"
    if not private_runtime.exists():
        pytest.skip("HelixMind's private OmegaClaw runtime is not installed in this checkout.")

    result = subprocess.run(
        [str(runner)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
        env=os.environ.copy(),
    )

    assert "(--> HBB SickleCellDisease) (stv 1.0 0.855)" in result.stdout
