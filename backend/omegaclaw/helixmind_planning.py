"""OmegaClaw planning adapter for the Phase 3B investigation worker.

The worker invokes the installed OmegaClaw loop through this plugin. The LLM
may only return a structured research plan; no literature, citation, or
scientific conclusion is accepted at this phase.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import channels
import providers
from app.inference import InferenceError, router_from_environment
from config import config_get_by_key

logger = logging.getLogger(__name__)

_selected_provider = "unknown"
_selected_model = "unknown"

_PLANNING_INSTRUCTION = """You are HelixMind's OmegaClaw research planning agent.
Return exactly one JSON object and nothing else. Build a useful research plan
from the user's question, title, and domain. Do not retrieve literature, invent
papers, invent citations, state evidence as fact, or provide a treatment or
diagnosis. Use exactly these array fields of short strings:
research_objectives, research_questions, search_strategies, key_concepts,
evidence_categories, reasoning_tasks. Keep the plan scoped to a future
literature investigation. Search only PubMed and Europe PMC. Do not include
confidence scores or citations.
"""


class HelixMindPlanningProvider(providers.LLMProvider):
    def start(self) -> None:
        """Load OmegaClaw's provider policy into the shared HelixMind router."""
        mappings = {
            "helixmind_gemini_base_url": "GEMINI_BASE_URL",
            "helixmind_gemini_model": "GEMINI_MODEL",
            "helixmind_groq_base_url": "GROQ_BASE_URL",
            "helixmind_groq_model": "GROQ_MODEL",
            "helixmind_asi_base_url": "ASI_CLOUD_BASE_URL",
            "helixmind_asi_model": "ASI_CLOUD_CHAT_MODEL",
            "omegaclaw_provider": "OMEGACLAW_PROVIDER",
            "omegaclaw_provider_order": "OMEGACLAW_PROVIDER_ORDER",
            "omegaclaw_model": "OMEGACLAW_MODEL",
        }
        for config_key, env_key in mappings.items():
            value = config_get_by_key(config_key, "")
            if value and not os.environ.get(env_key):
                os.environ[env_key] = str(value)
        self.router = router_from_environment()

    def stop(self) -> None:
        return None

    def chat(self, prompt: str, max_tokens: int = 6000, reasoning_mode: str = "medium") -> str:
        global _selected_provider, _selected_model
        try:
            response = self.router.chat(
                [
                    {"role": "system", "content": _PLANNING_INSTRUCTION},
                    # OmegaClaw's harness prompt contains tool instructions that
                    # conflict with this JSON planning contract. The channel
                    # request is the authoritative, bounded user input.
                    {"role": "user", "content": os.environ.get("HELIXMIND_PLANNING_REQUEST", "")},
                ],
                workload="omegaclaw_planning",
                max_tokens=max_tokens,
                reasoning_effort=reasoning_mode,
                json_mode=True,
            )
            plan = self._extract_plan(response.content)
            if plan is None:
                logger.warning("OmegaClaw planning providers returned no valid structured plan")
                return "()"
            _selected_provider = response.provider
            _selected_model = response.model
            logger.info("OmegaClaw planning accepted provider=%s model=%s fallback=%s", response.provider, response.model, response.fallback_occurred)
            # Deliver through OmegaClaw's selected communication channel. A
            # textual `(send ...)` return is only parsed as a loop command and
            # does not reliably invoke the Python channel callback.
            channels.commChannelSend(json.dumps(plan, ensure_ascii=True, separators=(",", ":")))
            return "()"
        except InferenceError as error:
            logger.error("OmegaClaw planning providers exhausted category=%s", error.category)
            return "()"

    @staticmethod
    def _extract_plan(response: str) -> dict[str, Any] | None:
        start = response.find("{")
        if start < 0:
            return None
        depth = 0
        quoted = False
        escaped = False
        for position, char in enumerate(response[start:], start=start):
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
                continue
            if char == '"':
                quoted = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        candidate = json.loads(response[start : position + 1])
                    except json.JSONDecodeError:
                        return None
                    required = (
                        "research_objectives",
                        "research_questions",
                        "search_strategies",
                        "key_concepts",
                        "evidence_categories",
                        "reasoning_tasks",
                    )
                    if not isinstance(candidate, dict) or any(not isinstance(candidate.get(key), list) for key in required):
                        return None
                    if any(not isinstance(item, str) or not item.strip() for key in required for item in candidate[key]):
                        return None
                    return {key: candidate[key][:12] for key in required}
        return None


class HelixMindPlanningChannel(channels.CommChannel):
    def start(self) -> None:
        self._request = os.environ.get("HELIXMIND_PLANNING_REQUEST", "")
        self._delivered = False

    def stop(self) -> None:
        return None

    def receive(self) -> str:
        if self._delivered:
            return ""
        self._delivered = True
        return self._request

    def send(self, message: str) -> None:
        try:
            plan = json.loads(message)
        except json.JSONDecodeError:
            return
        print(
            "HELIXMIND_PLAN_JSON:" + json.dumps(
                {"plan": plan, "provider": _selected_provider, "model": _selected_model},
                ensure_ascii=True,
                separators=(",", ":"),
            ),
            flush=True,
        )


def loadOmegaClawPlugin() -> None:
    if os.environ.get("HELIXMIND_OMEGACLAW_MODE") != "planning":
        return
    providers.registerLLMProvider("OpenAIAPI", HelixMindPlanningProvider())
    channels.registerCommChannel("helixmind-planning", HelixMindPlanningChannel())
