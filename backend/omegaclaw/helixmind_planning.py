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

from openai import OpenAI

import channels
import providers
from config import config_get_by_key

logger = logging.getLogger(__name__)

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GROQ_OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
_selected_provider = "unknown"
_selected_model = "unknown"

_PLANNING_INSTRUCTION = """You are HelixMind's OmegaClaw research planning agent.
Return exactly one JSON object and nothing else. Build a useful research plan
from the user's question, title, and domain. Do not retrieve literature, invent
papers, invent citations, state evidence as fact, or provide a treatment or
diagnosis. Use exactly these array fields of short strings:
research_objectives, research_questions, search_strategies, key_concepts,
evidence_categories, reasoning_tasks. Keep the plan scoped to a future
literature investigation. Do not include confidence scores or citations.
"""


class Endpoint:
    def __init__(self, label: str, api_key_env: str, base_url: str, model: str) -> None:
        self.label = label
        self.api_key_env = api_key_env
        self.base_url = base_url
        self.model = model


class HelixMindPlanningProvider(providers.LLMProvider):
    def start(self) -> None:
        self.primary = Endpoint(
            "gemini",
            config_get_by_key("helixmind_gemini_api_key_env", "GEMINI_API_KEY"),
            config_get_by_key("helixmind_gemini_base_url", GEMINI_OPENAI_BASE_URL),
            config_get_by_key("helixmind_gemini_model", "gemini-2.5-flash"),
        )
        self.fallback = Endpoint(
            "groq",
            config_get_by_key("helixmind_groq_api_key_env", "GROQ_API_KEY"),
            config_get_by_key("helixmind_groq_base_url", GROQ_OPENAI_BASE_URL),
            config_get_by_key("helixmind_groq_model", "openai/gpt-oss-20b"),
        )
        missing = [endpoint.api_key_env for endpoint in (self.primary, self.fallback) if not os.environ.get(endpoint.api_key_env)]
        if missing:
            raise RuntimeError("HelixMind OmegaClaw planning credentials are missing.")

    def stop(self) -> None:
        return None

    def chat(self, prompt: str, max_tokens: int = 6000, reasoning_mode: str = "medium") -> str:
        global _selected_provider, _selected_model
        failures: list[str] = []
        for endpoint in (self.primary, self.fallback):
            try:
                response = self._request(endpoint, prompt, max_tokens, reasoning_mode)
                plan = self._extract_plan(response)
                if plan is not None:
                    _selected_provider = endpoint.label
                    _selected_model = endpoint.model
                    logger.info("OmegaClaw planning accepted provider=%s model=%s", endpoint.label, endpoint.model)
                    encoded = json.dumps(plan, ensure_ascii=True, separators=(",", ":"))
                    escaped = json.dumps(encoded, ensure_ascii=True)
                    return f"(send {escaped})"
                failures.append(f"{endpoint.label}: invalid plan")
            except Exception as error:
                logger.warning("OmegaClaw planning provider %s failed: %s", endpoint.label, type(error).__name__)
                failures.append(f"{endpoint.label}: {type(error).__name__}")
        logger.error("OmegaClaw planning providers exhausted: %s", "; ".join(failures))
        return "()"

    @staticmethod
    def _request(endpoint: Endpoint, prompt: str, max_tokens: int, reasoning_mode: str) -> str:
        client = OpenAI(api_key=os.environ[endpoint.api_key_env], base_url=endpoint.base_url)
        try:
            response = client.chat.completions.create(
                model=endpoint.model,
                messages=[
                    {"role": "system", "content": _PLANNING_INSTRUCTION},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                reasoning_effort=reasoning_mode,
            )
            return response.choices[0].message.content or ""
        finally:
            client.close()

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
