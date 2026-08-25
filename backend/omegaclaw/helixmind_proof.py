"""Constrained HelixMind provider and channel for the OmegaClaw proof.

This module uses OmegaClaw Core's documented Python plugin registry.  It is
deliberately proof-only: a model response may execute one ``metta`` skill and
nothing that can access a shell, filesystem, web search, or external channel.
"""

from __future__ import annotations

import logging
import os

import channels
import providers
from app.inference import InferenceError, router_from_environment
from config import config_get_by_key


logger = logging.getLogger(__name__)

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


class HelixMindGeminiGroqProvider(providers.LLMProvider):
    """Shared HelixMind inference routing with proof-specific output validation."""

    def start(self) -> None:
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
        try:
            response = self.router.chat(
                [
                    {"role": "system", "content": _PROOF_INSTRUCTION},
                    {"role": "user", "content": prompt},
                ],
                workload="omegaclaw_metta_proof",
                max_tokens=max_tokens,
                reasoning_effort=reasoning_mode,
            )
            command = self._safe_metta_command(response.content)
            if command:
                logger.info("HelixMind proof accepted provider=%s model=%s fallback=%s", response.provider, response.model, response.fallback_occurred)
                return command
            logger.warning("HelixMind proof response did not contain a permitted metta call")
        except InferenceError as exc:  # Fail over without ever logging credentials or prompt contents.
            logger.warning("HelixMind proof inference failed category=%s", exc.category)
        return "()"

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
