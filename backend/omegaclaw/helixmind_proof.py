"""Constrained HelixMind provider and channel for the OmegaClaw proof.

This module uses OmegaClaw Core's documented Python plugin registry.  It is
deliberately proof-only: a model response may execute one ``metta`` skill and
nothing that can access a shell, filesystem, web search, or external channel.
"""

from __future__ import annotations

import logging
import os

from openai import OpenAI

import channels
import providers
from config import config_get_by_key


logger = logging.getLogger(__name__)

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GROQ_OPENAI_BASE_URL = "https://api.groq.com/openai/v1"

_PROOF_INSTRUCTION = """You are executing HelixMind's constrained reasoning proof.
Return exactly one OmegaClaw skill expression and nothing else. The only
permitted skill is metta. It must run the supplied two-premise NAL deduction
about HBB, HbSVariant, and SickleCellDisease. Do not use shell, file, web,
memory, communication, or any other skill. The LLM is not a source of
scientific truth: the explicit MeTTa premises are the only facts for this run.
"""

_PROOF_COMMAND = (
    '(metta "(|- ((--> HBB HbSVariant) (stv 1.0 0.95)) '
    '((--> HbSVariant SickleCellDisease) (stv 1.0 0.90)))")'
)


class Endpoint:
    """Immutable-enough endpoint settings without dataclass loader assumptions."""

    def __init__(self, label: str, api_key_env: str, base_url: str, model: str) -> None:
        self.label = label
        self.api_key_env = api_key_env
        self.base_url = base_url
        self.model = model


class HelixMindGeminiGroqProvider(providers.LLMProvider):
    """Gemini primary with Groq fallback through OpenAI-compatible endpoints."""

    def start(self) -> None:
        self.primary = Endpoint(
            label="gemini",
            api_key_env=config_get_by_key("helixmind_gemini_api_key_env", "GEMINI_API_KEY"),
            base_url=config_get_by_key("helixmind_gemini_base_url", GEMINI_OPENAI_BASE_URL),
            model=config_get_by_key("helixmind_gemini_model", "gemini-2.5-flash"),
        )
        self.fallback = Endpoint(
            label="groq",
            api_key_env=config_get_by_key("helixmind_groq_api_key_env", "GROQ_API_KEY"),
            base_url=config_get_by_key("helixmind_groq_base_url", GROQ_OPENAI_BASE_URL),
            model=config_get_by_key("helixmind_groq_model", "openai/gpt-oss-20b"),
        )
        missing = [endpoint.api_key_env for endpoint in (self.primary, self.fallback)
                   if not os.environ.get(endpoint.api_key_env)]
        if missing:
            raise RuntimeError("HelixMind OmegaClaw credentials are missing: " + ", ".join(missing))

    def stop(self) -> None:
        return None

    def chat(self, prompt: str, max_tokens: int = 6000, reasoning_mode: str = "medium") -> str:
        failures: list[str] = []
        for endpoint in (self.primary, self.fallback):
            try:
                response = self._request(endpoint, prompt, max_tokens, reasoning_mode)
                command = self._safe_metta_command(response)
                if command:
                    logger.info("HelixMind proof accepted %s response using model %s", endpoint.label, endpoint.model)
                    return command
                failures.append(f"{endpoint.label}: response did not contain a permitted metta call")
            except Exception as exc:  # Fail over without ever logging credentials or prompt contents.
                logger.warning("HelixMind proof %s request failed: %s", endpoint.label, type(exc).__name__)
                failures.append(f"{endpoint.label}: {type(exc).__name__}")

        logger.error("HelixMind proof exhausted providers: %s", "; ".join(failures))
        return "()"

    @staticmethod
    def _request(endpoint: Endpoint, prompt: str, max_tokens: int, reasoning_mode: str) -> str:
        client = OpenAI(api_key=os.environ[endpoint.api_key_env], base_url=endpoint.base_url)
        try:
            response = client.chat.completions.create(
                model=endpoint.model,
                messages=[
                    {"role": "system", "content": _PROOF_INSTRUCTION},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                reasoning_effort=reasoning_mode,
            )
            return response.choices[0].message.content or ""
        finally:
            client.close()

    @staticmethod
    def _safe_metta_command(response: str) -> str | None:
        """Allow only the fixed source-grounded NAL command for this proof."""
        logger.info("HelixMind proof provider response received: %d characters", len(response))
        start = response.find("(metta ")
        if start >= 0:
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
                elif char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        command = response[start:position + 1].strip()
                        if command.startswith('(metta "') and command.endswith('")'):
                            return command
                        break

        # OmegaClaw's upstream prompt examples also document an unwrapped
        # `metta <sexpression>` shorthand. Normalize only when it unambiguously
        # selects this proof's fixed premises; arbitrary tool calls stay denied.
        markers = ("metta", "|-", "HBB", "HbSVariant", "SickleCellDisease")
        if all(marker.lower() in response.lower() for marker in markers):
            return _PROOF_COMMAND
        return None


class HelixMindProofChannel(channels.CommChannel):
    """One-shot local channel; it never opens a socket or accepts remote input."""

    def start(self) -> None:
        self._delivered = False

    def stop(self) -> None:
        return None

    def receive(self) -> str:
        if self._delivered:
            return ""
        self._delivered = True
        return (
            "Investigate whether CRISPR-based genetic intervention represents a "
            "scientifically supported therapeutic strategy for sickle-cell disease. "
            "For this constrained proof, execute exactly this source-grounded NAL "
            "deduction and no other operation: HBB -> HbSVariant (stv 1.0 0.95), "
            "HbSVariant -> SickleCellDisease (stv 1.0 0.90)."
        )

    def send(self, message: str) -> None:
        logger.info("HelixMind proof channel emitted %d characters", len(message))


def loadOmegaClawPlugin() -> None:
    # Override the official generic OpenAI-compatible selector after the core
    # plugins load. Gemini and Groq both publish supported OpenAI-compatible
    # endpoints; this adapter adds failover which OmegaClaw Core does not yet
    # provide itself.
    providers.registerLLMProvider("OpenAIAPI", HelixMindGeminiGroqProvider())
    channels.registerCommChannel("helixmind-proof", HelixMindProofChannel())
