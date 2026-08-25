"""Shared, secret-safe inference providers for HelixMind and OmegaClaw.

The database remains the source of truth for research evidence. This module
only supplies bounded language/embedding calls and safe operational metadata.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

import httpx

logger = logging.getLogger(__name__)


class InferenceError(RuntimeError):
    def __init__(self, message: str, *, category: str, provider: str, model: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.provider = provider
        self.model = model
        self.status_code = status_code


@dataclass(frozen=True)
class InferenceResult:
    provider: str
    model: str
    content: str
    latency_ms: int
    request_id: str | None = None
    credential_slot: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    fallback_occurred: bool = False


@dataclass(frozen=True)
class EmbeddingResult:
    provider: str
    model: str
    vectors: list[list[float]]
    latency_ms: int
    request_id: str | None = None
    credential_slot: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


class InferenceProvider(Protocol):
    name: str

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None, max_tokens: int = 1200,
             reasoning_effort: str | None = None, json_mode: bool = False) -> InferenceResult: ...

    def embeddings(self, inputs: list[str], *, model: str | None = None) -> EmbeddingResult: ...

    def discover_models(self) -> list[str]: ...


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        value = response.json()
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _error_category(status_code: int | None, error: Exception | None = None) -> str:
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.NetworkError):
        return "connection_failure"
    if status_code in (401, 403):
        return "authentication_failure"
    if status_code == 404:
        return "model_unavailable"
    if status_code == 429:
        return "rate_limit"
    if status_code is not None and 400 <= status_code < 500:
        return "invalid_request"
    if status_code is not None and status_code >= 500:
        return "provider_server_error"
    return "provider_failure"


class OpenAICompatibleProvider:
    """OpenAI-compatible provider with bounded retry and safe metadata."""

    def __init__(self, *, name: str, base_url: str, api_keys: list[tuple[str, str]], chat_model: str,
                 embedding_model: str, timeout_seconds: float = 30.0, retries: int = 2,
                 client: httpx.Client | None = None) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_keys = [(slot, key) for slot, key in api_keys if key]
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.timeout_seconds = timeout_seconds
        self.retries = max(0, min(retries, 3))
        self.client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def discover_models(self) -> list[str]:
        response = self._request("GET", "/models", allow_credential_rotation=True)
        payload = _safe_json(response)
        return sorted(str(item["id"]) for item in payload.get("data", []) if isinstance(item, dict) and item.get("id"))

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None, max_tokens: int = 1200,
             reasoning_effort: str | None = None, json_mode: bool = False) -> InferenceResult:
        selected_model = model or self.chat_model
        body: dict[str, Any] = {"model": selected_model, "messages": messages, "max_tokens": max_tokens}
        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        response, slot = self._request_with_slot("POST", "/chat/completions", body, allow_credential_rotation=True)
        payload = _safe_json(response)
        choices = payload.get("choices") or []
        content = ""
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            content = message.get("content") or ""
        if not isinstance(content, str) or not content.strip():
            raise InferenceError("Provider returned no completion content.", category="empty_response", provider=self.name, model=selected_model, status_code=response.status_code)
        latency_ms = int((time.perf_counter() - started) * 1000)
        result = InferenceResult(self.name, selected_model, content, latency_ms, response.headers.get("x-request-id"), slot, payload.get("usage") or {})
        logger.info("inference provider=%s model=%s credential_slot=%s success=true latency_ms=%s", self.name, selected_model, slot, latency_ms)
        return result

    def embeddings(self, inputs: list[str], *, model: str | None = None) -> EmbeddingResult:
        selected_model = model or self.embedding_model
        if not inputs or any(not isinstance(value, str) or not value.strip() for value in inputs):
            raise InferenceError("Embedding input must contain non-empty strings.", category="invalid_request", provider=self.name, model=selected_model)
        started = time.perf_counter()
        response, slot = self._request_with_slot("POST", "/embeddings", {"model": selected_model, "input": inputs}, allow_credential_rotation=True)
        payload = _safe_json(response)
        rows = payload.get("data") or []
        vectors = [row.get("embedding") for row in rows if isinstance(row, dict) and isinstance(row.get("embedding"), list)]
        if len(vectors) != len(inputs):
            raise InferenceError("Provider returned incomplete embeddings.", category="invalid_response", provider=self.name, model=selected_model, status_code=response.status_code)
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info("inference provider=%s model=%s credential_slot=%s operation=embedding success=true latency_ms=%s", self.name, selected_model, slot, latency_ms)
        return EmbeddingResult(self.name, selected_model, vectors, latency_ms, response.headers.get("x-request-id"), slot, {"input_count": len(inputs)})

    def _request(self, method: str, path: str, body: Mapping[str, Any] | None = None, *, allow_credential_rotation: bool) -> httpx.Response:
        response, _ = self._request_with_slot(method, path, body, allow_credential_rotation=allow_credential_rotation)
        return response

    def _request_with_slot(self, method: str, path: str, body: Mapping[str, Any] | None, *, allow_credential_rotation: bool) -> tuple[httpx.Response, str]:
        if not self.api_keys:
            raise InferenceError("Provider credentials are not configured.", category="not_configured", provider=self.name, model=self.chat_model)
        failures: list[str] = []
        for slot_index, (slot, key) in enumerate(self.api_keys):
            attempts = 0
            while attempts <= self.retries:
                attempts += 1
                try:
                    response = self.client.request(method, f"{self.base_url}{path}", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body, timeout=self.timeout_seconds)
                except (httpx.TimeoutException, httpx.NetworkError) as error:
                    category = _error_category(None, error)
                    failures.append(f"{slot}:{category}")
                    if attempts <= self.retries:
                        time.sleep(min(0.25 * (2 ** (attempts - 1)), 2.0))
                        continue
                    break
                category = _error_category(response.status_code)
                if response.is_success:
                    return response, slot
                failures.append(f"{slot}:{category}:{response.status_code}")
                rotate = allow_credential_rotation and category in {"authentication_failure", "rate_limit"}
                transient = category in {"timeout", "connection_failure", "provider_server_error"}
                if rotate and slot_index + 1 < len(self.api_keys):
                    break
                if transient and attempts <= self.retries:
                    time.sleep(min(0.25 * (2 ** (attempts - 1)), 2.0))
                    continue
                if category in {"invalid_request", "model_unavailable"} or not rotate:
                    detail = _safe_json(response).get("error")
                    safe_detail = detail.get("type") if isinstance(detail, dict) else category
                    raise InferenceError(f"{self.name} request failed: {safe_detail}", category=category, provider=self.name, model=self.chat_model, status_code=response.status_code)
                break
        logger.warning("inference provider=%s exhausted credential slots failures=%s", self.name, ",".join(failures))
        category = "rate_limit" if any(":rate_limit" in item for item in failures) else "authentication_failure" if any(":authentication_failure" in item for item in failures) else "provider_failure"
        raise InferenceError(f"{self.name} credentials/providers exhausted.", category=category, provider=self.name, model=self.chat_model)


class InferenceRouter:
    """Configured provider order with explicit workload routing and fallback."""

    def __init__(self, providers: Mapping[str, InferenceProvider], order: list[str]) -> None:
        self.providers = dict(providers)
        self.order = [name for name in order if name in self.providers]

    def chat(self, messages: list[dict[str, str]], *, workload: str = "general", model: str | None = None,
             max_tokens: int = 1200, reasoning_effort: str | None = None, json_mode: bool = False) -> InferenceResult:
        failures: list[str] = []
        for index, name in enumerate(self.order):
            provider = self.providers[name]
            try:
                result = provider.chat(messages, model=model, max_tokens=max_tokens, reasoning_effort=reasoning_effort, json_mode=json_mode)
                return InferenceResult(result.provider, result.model, result.content, result.latency_ms, result.request_id, result.credential_slot, result.usage, fallback_occurred=index > 0)
            except InferenceError as error:
                failures.append(f"{name}:{error.category}")
                logger.warning("inference fallback workload=%s provider=%s category=%s", workload, name, error.category)
        raise InferenceError(f"All configured inference providers failed: {','.join(failures)}", category="all_providers_failed", provider="router", model=model or "configured")


def asi_cloud_from_environment(*, client: httpx.Client | None = None) -> OpenAICompatibleProvider:
    keys = [("ASI_PRIMARY", os.getenv("ASI_CLOUD_API_KEY", "")), ("ASI_SECONDARY", os.getenv("ASI_CLOUD_API_KEY1", "")), ("ASI_TERTIARY", os.getenv("ASI_CLOUD_API_KEY2", ""))]
    return OpenAICompatibleProvider(
        name="asi",
        base_url=os.getenv("ASI_CLOUD_BASE_URL", "https://llm.c.singularitynet.io/v1"),
        api_keys=keys,
        chat_model=os.getenv("ASI_CLOUD_CHAT_MODEL", os.getenv("OMEGACLAW_MODEL", "asi1-mini")),
        embedding_model=os.getenv("ASI_CLOUD_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5"),
        timeout_seconds=float(os.getenv("ASI_CLOUD_TIMEOUT_SECONDS", "30")),
        retries=int(os.getenv("ASI_CLOUD_RETRIES", "2")),
        client=client,
    )


def _compatible_from_environment(name: str, *, key_env: str, base_env: str, model_env: str, default_base: str,
                                  default_model: str, client: httpx.Client | None = None) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        name=name,
        base_url=os.getenv(base_env, default_base),
        api_keys=[(f"{name.upper()}_PRIMARY", os.getenv(key_env, ""))],
        chat_model=os.getenv(model_env, default_model),
        embedding_model=os.getenv("ASI_CLOUD_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5"),
        timeout_seconds=float(os.getenv("ASI_CLOUD_TIMEOUT_SECONDS", "30")),
        retries=int(os.getenv("ASI_CLOUD_RETRIES", "2")),
        client=client,
    )


def router_from_environment(*, client: httpx.Client | None = None) -> InferenceRouter:
    asi = asi_cloud_from_environment(client=client)
    providers: dict[str, InferenceProvider] = {
        "asi": asi,
        "groq": _compatible_from_environment("groq", key_env="GROQ_API_KEY", base_env="GROQ_BASE_URL", model_env="GROQ_MODEL", default_base="https://api.groq.com/openai/v1", default_model="openai/gpt-oss-20b", client=client),
        "gemini": _compatible_from_environment("gemini", key_env="GEMINI_API_KEY", base_env="GEMINI_BASE_URL", model_env="GEMINI_MODEL", default_base="https://generativelanguage.googleapis.com/v1beta/openai/", default_model="gemini-2.5-flash", client=client),
    }
    order = [item.strip().lower() for item in os.getenv("OMEGACLAW_PROVIDER_ORDER", "gemini,groq").split(",") if item.strip()]
    if os.getenv("OMEGACLAW_PROVIDER", "").strip().lower() == "asi":
        order = ["asi", "groq", "gemini"]
    return InferenceRouter(providers, order)
