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


def test_default_provider_order_prefers_groq_then_asi_then_gemini(monkeypatch) -> None:
    monkeypatch.delenv("OMEGACLAW_PROVIDER_ORDER", raising=False)
    monkeypatch.delenv("OMEGACLAW_PROVIDER", raising=False)
    router = router_from_environment()
    assert router.order == ["groq", "asi", "gemini"]
    assert router.providers["groq"].base_url == "https://groq-proxy.gethsun09.workers.dev/openai/v1"
    assert router.providers["groq"].chat_model == "openai/gpt-oss-120b"


def test_groq_environment_overrides_worker_url_and_model(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_BASE_URL", "https://worker.example/openai/v1")
    monkeypatch.setenv("GROQ_MODEL", "custom/model")
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-secret")
    router = router_from_environment()
    assert router.providers["groq"].base_url == "https://worker.example/openai/v1"
    assert router.providers["groq"].chat_model == "custom/model"
    assert router.providers["groq"].api_keys == [("GROQ_PRIMARY", "synthetic-secret")]


def test_missing_groq_key_falls_back_to_asi(monkeypatch) -> None:
    from app.inference import InferenceResult
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    router = router_from_environment()

    class ASIWorks:
        def chat(self, *args, **kwargs):
            return InferenceResult("asi", "asi1-mini", "ok", 1)

    router.providers["asi"] = ASIWorks()
    result = router.chat([])
    assert result.provider == "asi"
    assert result.fallback_occurred
    assert result.fallback_reason == "not_configured"


def test_missing_asi_keys_falls_back_to_gemini(monkeypatch) -> None:
    from app.inference import InferenceResult, asi_cloud_from_environment
    for name in ("ASI_CLOUD_API_KEY", "ASI_CLOUD_API_KEY_1", "ASI_CLOUD_API_KEY_2", "ASI_CLOUD_API_KEY_3", "ASI_CLOUD_API_KEY1", "ASI_CLOUD_API_KEY2"):
        monkeypatch.delenv(name, raising=False)
    asi = asi_cloud_from_environment()
    assert asi.api_keys == []

    class GroqDown:
        name = "groq"

        def chat(self, *args, **kwargs):
            raise InferenceError("down", category="provider_server_error", provider="groq", model="configured")

    class GeminiWorks:
        def chat(self, *args, **kwargs):
            return InferenceResult("gemini", "gemini-current", "ok", 1)

    result = InferenceRouter({"groq": GroqDown(), "asi": asi, "gemini": GeminiWorks()}, ["groq", "asi", "gemini"]).chat([])
    assert result.provider == "gemini"
    assert result.fallback_reason == "provider_server_error"


def test_transient_retry_count_is_bounded() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"error": {"type": "temporary"}})

    subject = OpenAICompatibleProvider(name="groq", base_url="https://groq.test/v1", api_keys=[("GROQ_PRIMARY", "fake")],
                                       chat_model="model", embedding_model="unused", retries=2,
                                       client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(InferenceError):
        subject.chat([])
    assert calls == 3


def test_groq_success_uses_expected_model_and_chat_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.groq.test/openai/v1/chat/completions"
        assert json.loads(request.content)["model"] == "openai/gpt-oss-20b"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}], "usage": {"total_tokens": 4}})

    groq = OpenAICompatibleProvider(
        name="groq", base_url="https://api.groq.test/openai/v1", api_keys=[("GROQ_PRIMARY", "never-log-this")],
        chat_model="openai/gpt-oss-20b", embedding_model="unused", retries=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = groq.chat([{"role": "user", "content": "hello"}], json_mode=True)
    assert result.provider == "groq"
    assert result.model == "openai/gpt-oss-20b"
    assert json.loads(result.content) == {"ok": True}
    assert result.usage == {"total_tokens": 4}


def test_groq_403_is_permission_failure_and_does_not_rotate_credentials() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(403, json={"error": {"type": "permissions_error", "message": "Access denied. Please check your network settings."}})

    groq = OpenAICompatibleProvider(
        name="groq", base_url="https://api.groq.test/openai/v1",
        api_keys=[("GROQ_PRIMARY", "secret-value"), ("GROQ_SECONDARY", "other-secret")],
        chat_model="openai/gpt-oss-20b", embedding_model="unused", retries=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(InferenceError) as error:
        groq.chat([{"role": "user", "content": "hello"}])
    assert error.value.category == "permission_failure"
    assert error.value.status_code == 403
    assert calls == 1
    assert "secret-value" not in str(error.value)


def test_groq_429_rotates_credential_slot() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": {"type": "rate_limit_exceeded"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    groq = OpenAICompatibleProvider(
        name="groq", base_url="https://api.groq.test/openai/v1",
        api_keys=[("GROQ_PRIMARY", "secret-one"), ("GROQ_SECONDARY", "secret-two")],
        chat_model="openai/gpt-oss-20b", embedding_model="unused", retries=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = groq.chat([{"role": "user", "content": "hello"}])
    assert result.credential_slot == "GROQ_SECONDARY"
    assert result.content == "ok"
    assert calls == 2


def test_router_falls_back_from_groq_to_asi_and_records_safe_reason() -> None:
    from app.inference import InferenceResult

    class GroqForbidden:
        name = "groq"

        def chat(self, *args, **kwargs):
            raise InferenceError("forbidden", category="permission_failure", provider="groq", model="openai/gpt-oss-20b", status_code=403)

    class ASIWorks:
        name = "asi"

        def chat(self, *args, **kwargs):
            return InferenceResult("asi", "asi1-mini", "ok", 17, usage={"total_tokens": 9})

    result = InferenceRouter({"groq": GroqForbidden(), "asi": ASIWorks()}, ["groq", "asi"]).chat([])
    assert result.provider == "asi"
    assert result.fallback_occurred is True
    assert result.fallback_reason == "permission_failure"
    assert result.latency_ms == 17
    assert result.usage == {"total_tokens": 9}
    assert "secret" not in str(result)


def test_router_falls_back_to_gemini_after_asi_failure() -> None:
    from app.inference import InferenceResult

    class ASIDown:
        name = "asi"

        def chat(self, *args, **kwargs):
            raise InferenceError("down", category="provider_server_error", provider="asi", model="asi1-mini")

    class GeminiWorks:
        name = "gemini"

        def chat(self, *args, **kwargs):
            return InferenceResult("gemini", "gemini-current", "ok", 12)

    result = InferenceRouter({"asi": ASIDown(), "gemini": GeminiWorks()}, ["asi", "gemini"]).chat([])
    assert result.provider == "gemini"
    assert result.fallback_occurred is True
    assert result.fallback_reason == "provider_server_error"


def test_router_reports_all_providers_unavailable() -> None:
    class Down:
        def __init__(self, name: str):
            self.name = name

        def chat(self, *args, **kwargs):
            raise InferenceError("down", category="timeout", provider=self.name, model="configured")

    router = InferenceRouter({name: Down(name) for name in ("groq", "asi", "gemini")}, ["groq", "asi", "gemini"])
    with pytest.raises(InferenceError) as error:
        router.chat([])
    assert error.value.category == "all_providers_failed"
    assert "groq:timeout" in str(error.value)
    assert "asi:timeout" in str(error.value)
    assert "gemini:timeout" in str(error.value)


def test_schema_validation_does_not_rotate_to_another_provider() -> None:
    called = []

    class InvalidPlan:
        name = "asi"

        def chat(self, *args, **kwargs):
            called.append("asi")
            raise InferenceError("schema rejected", category="schema_validation", provider="asi", model="asi1-mini")

    class Backup:
        name = "gemini"

        def chat(self, *args, **kwargs):
            called.append("gemini")

    with pytest.raises(InferenceError) as error:
        InferenceRouter({"asi": InvalidPlan(), "gemini": Backup()}, ["asi", "gemini"]).chat([])
    assert error.value.category == "schema_validation"
    assert called == ["asi"]


def test_asi_environment_loads_four_new_keys_in_order_and_deduplicates(monkeypatch) -> None:
    from app.inference import asi_cloud_from_environment

    for name in ("ASI_CLOUD_API_KEY", "ASI_CLOUD_API_KEY_1", "ASI_CLOUD_API_KEY_2", "ASI_CLOUD_API_KEY_3", "ASI_CLOUD_API_KEY1", "ASI_CLOUD_API_KEY2"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ASI_CLOUD_API_KEY", "same-secret")
    monkeypatch.setenv("ASI_CLOUD_API_KEY_1", "key-one")
    monkeypatch.setenv("ASI_CLOUD_API_KEY_2", "same-secret")
    monkeypatch.setenv("ASI_CLOUD_API_KEY_3", "key-three")
    subject = asi_cloud_from_environment(client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))))
    assert [slot for slot, _ in subject.api_keys] == ["ASI_KEY_0", "ASI_KEY_1", "ASI_KEY_3"]
    assert len({key for _, key in subject.api_keys}) == 3


def test_asi_environment_supports_historical_key_aliases(monkeypatch) -> None:
    from app.inference import asi_cloud_from_environment

    for name in ("ASI_CLOUD_API_KEY", "ASI_CLOUD_API_KEY_1", "ASI_CLOUD_API_KEY_2", "ASI_CLOUD_API_KEY_3", "ASI_CLOUD_API_KEY1", "ASI_CLOUD_API_KEY2"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ASI_CLOUD_API_KEY", "primary")
    monkeypatch.setenv("ASI_CLOUD_API_KEY1", "secondary")
    monkeypatch.setenv("ASI_CLOUD_API_KEY2", "tertiary")
    subject = asi_cloud_from_environment(client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))))
    assert [slot for slot, _ in subject.api_keys] == ["ASI_KEY_0", "ASI_KEY_1", "ASI_KEY_2"]


def test_asi_rate_limit_rotates_through_three_distinct_slots_without_secret_leak(caplog) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["authorization"])
        if len(calls) < 3:
            return httpx.Response(429, json={"error": {"type": "rate_limit_exceeded"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    keys = [("ASI_KEY_0", "synthetic-secret-a"), ("ASI_KEY_1", "synthetic-secret-b"), ("ASI_KEY_2", "synthetic-secret-c")]
    subject = OpenAICompatibleProvider(name="asi", base_url="https://asi.test/v1", api_keys=keys, chat_model="asi1-mini", embedding_model="unused", retries=0, client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = subject.chat([{"role": "user", "content": "hello"}])
    assert result.credential_slot == "ASI_KEY_2"
    assert len(calls) == 3
    assert "synthetic-secret" not in caplog.text
    assert "Bearer" not in caplog.text


def test_asi_all_rate_limited_returns_safe_rate_limit_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"type": "rate_limit_exceeded"}})

    subject = OpenAICompatibleProvider(name="asi", base_url="https://asi.test/v1", api_keys=[("slot-a", "secret-a"), ("slot-b", "secret-b")], chat_model="asi1-mini", embedding_model="unused", retries=0, client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(InferenceError) as error:
        subject.chat([{"role": "user", "content": "hello"}])
    assert error.value.category == "rate_limit"
    assert error.value.status_code == 429
    assert "secret-a" not in str(error.value)
    assert "secret-b" not in str(error.value)
