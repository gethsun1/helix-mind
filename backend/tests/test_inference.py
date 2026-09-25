import httpx
import json
import pytest

from app.inference import InferenceError, InferenceRouter, OpenAICompatibleProvider, router_from_environment


def provider(handler, keys=("k1", "k2", "k3")):
    return OpenAICompatibleProvider(
        name="asi",
        base_url="https://asi.test/v1",
        api_keys=[(f"ASI_{index + 1}", key) for index, key in enumerate(keys)],
        chat_model="asi1-mini",
        embedding_model="BAAI/bge-base-en-v1.5",
        retries=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_asi_chat_rotates_only_on_auth_failure_and_never_exposes_key() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        if len(seen) == 1:
            return httpx.Response(401, json={"error": {"type": "invalid_api_key"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    result = provider(handler).chat([{"role": "user", "content": "hello"}])
    assert result.content == "ok"
    assert result.credential_slot == "ASI_2"
    assert len(seen) == 2
    assert "k1" not in str(result)


def test_asi_embedding_returns_provider_model_and_provenance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        assert json.loads(request.content)["model"] == "BAAI/bge-base-en-v1.5"
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})

    result = provider(handler, keys=("k1",)).embeddings(["source text"])
    assert result.provider == "asi"
    assert result.model == "BAAI/bge-base-en-v1.5"
    assert result.vectors == [[0.1, 0.2]]
    assert result.provenance["input_count"] == 1


def test_router_falls_back_after_provider_failure() -> None:
    class Failed:
        name = "asi"

        def chat(self, *args, **kwargs):
            raise InferenceError("down", category="provider_server_error", provider="asi", model="asi1-mini")

    class Working:
        name = "groq"

        def chat(self, *args, **kwargs):
            from app.inference import InferenceResult
            return InferenceResult("groq", "openai/gpt-oss-20b", "fallback", 1)

    result = InferenceRouter({"asi": Failed(), "groq": Working()}, ["asi", "groq"]).chat([])
    assert result.content == "fallback"
    assert result.fallback_occurred is True


def test_invalid_request_does_not_rotate_credentials() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": {"type": "invalid_request_error"}})

    with pytest.raises(InferenceError) as error:
        provider(handler).chat([{"role": "user", "content": "hello"}])
    assert error.value.category == "invalid_request"
    assert calls == 1


def test_default_provider_order_tries_asi_then_gemini_without_groq(monkeypatch) -> None:
    monkeypatch.delenv("OMEGACLAW_PROVIDER_ORDER", raising=False)
    monkeypatch.delenv("OMEGACLAW_PROVIDER", raising=False)
    router = router_from_environment()
    assert router.order == ["asi", "gemini"]
