from __future__ import annotations

import json
import logging
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class OmegaClawPlanningError(RuntimeError):
    def __init__(self, message: str, category: str = "SYSTEM_ERROR") -> None:
        super().__init__(message)
        self.category = category


def run_research_planning(*, title: str, research_question: str, domain: str) -> dict[str, Any]:
    """Run the installed OmegaClaw planning agent and return its validated plan."""
    project_root = Path(__file__).resolve().parents[2]
    runner = project_root / "backend/scripts/run_omegaclaw_planning.sh"
    if not runner.is_file():
        raise OmegaClawPlanningError("OmegaClaw planning runner is unavailable.")

    payload = {"title": title, "research_question": research_question, "domain": domain}
    process: subprocess.Popen[str] | None = None
    output_tail: list[str] = []
    marker: str | None = None
    timed_out = False
    try:
        process = subprocess.Popen(
            [str(runner)],
            cwd=project_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=os.environ.copy(),
            start_new_session=True,
        )
        assert process.stdin is not None
        process.stdin.write(json.dumps(payload))
        process.stdin.close()
        assert process.stdout is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + get_settings().omegaclaw_timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            ready = selector.select(timeout=min(remaining, 1.0))
            if not ready:
                if process.poll() is not None:
                    break
                continue
            line = process.stdout.readline()
            if not line:
                break
            if len(output_tail) >= 20:
                output_tail.pop(0)
            output_tail.append(line.rstrip())
            if "HELIXMIND_PLAN_JSON:" in line:
                marker = line[line.index("HELIXMIND_PLAN_JSON:") :].strip()
                break
        selector.close()
    except OSError as error:
        raise OmegaClawPlanningError("OmegaClaw planning could not be started.") from error
    finally:
        if process is not None and (marker is not None or timed_out or process.poll() is None):
            _stop_process_group(process)

    if timed_out:
        raise OmegaClawPlanningError("OmegaClaw planning timed out.", "OMEGACLAW_TIMEOUT")
    if marker is None and (process is None or process.returncode not in (0, -signal.SIGTERM, 128 + signal.SIGTERM)):
        logger.error("OmegaClaw planning exited without a plan; output_tail=%s", output_tail[-3:])
        raise OmegaClawPlanningError("OmegaClaw planning failed to produce a research plan.", "EXTERNAL_PROVIDER_ERROR")

    if marker is None:
        logger.error("OmegaClaw planning completed without a plan marker")
        raise OmegaClawPlanningError("OmegaClaw planning returned no structured plan.")
    try:
        envelope = json.loads(marker.removeprefix("HELIXMIND_PLAN_JSON:"))
        plan = envelope["plan"]
        provider = envelope.get("provider")
        model = envelope.get("model")
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise OmegaClawPlanningError("OmegaClaw returned an invalid structured plan.") from error

    required = (
        "research_objectives",
        "research_questions",
        "search_strategies",
        "key_concepts",
        "evidence_categories",
        "reasoning_tasks",
    )
    if not isinstance(plan, dict) or any(not isinstance(plan.get(key), list) for key in required):
        raise OmegaClawPlanningError("OmegaClaw returned an incomplete research plan.")
    if any(not isinstance(item, str) or not item.strip() for key in required for item in plan[key]):
        raise OmegaClawPlanningError("OmegaClaw returned an unsafe research plan.")

    plan["phase"] = "planning"
    plan["source_note"] = "No scientific literature has been retrieved in Phase 3B."
    plan["_metadata"] = {
        "orchestrator": "OmegaClaw",
        "provider": provider if isinstance(provider, str) else "unknown",
        "model": model if isinstance(model, str) else "unknown",
    }
    return plan


def _stop_process_group(process: subprocess.Popen[str]) -> None:
    """Stop OmegaClaw after its one-shot channel emits the structured plan."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
