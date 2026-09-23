from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_flagship_proof_keeps_provider_and_reasoning_configuration_explicit() -> None:
    config = (PROJECT_ROOT / "backend/omegaclaw/proof.yaml").read_text()
    provider = (PROJECT_ROOT / "backend/omegaclaw/helixmind_proof.py").read_text()

    assert "helixmind_gemini_model: gemini-3.5-flash" in config
    assert "helixmind_groq_model: openai/gpt-oss-20b" in config
    assert 'providers.registerLLMProvider("OpenAIAPI", HelixMindGeminiGroqProvider())' in provider
    assert "_PROOF_COMMAND" in provider
    assert "(shell whoami)" not in provider
