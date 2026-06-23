from app.domain.schemas import ModelConfig
from app.runtime.vision_routing import pick_vision_target


def test_vision_config_optional_defaults_none():
    mc = ModelConfig(provider_id="ollama", model="llama3.1:8b")
    assert mc.vision_provider_id is None
    assert mc.vision_model is None


def test_pick_vision_target_prefers_explicit():
    mc = ModelConfig(
        provider_id="ollama",
        model="llama3.1:8b",
        vision_provider_id="ollama",
        vision_model="qwen2.5vl:7b",
    )
    assert pick_vision_target(mc, main_supports_vision=False) == ("ollama", "qwen2.5vl:7b")


def test_pick_vision_target_falls_back_to_main_when_multimodal():
    mc = ModelConfig(provider_id="ollama", model="gemma3:4b")
    assert pick_vision_target(mc, main_supports_vision=True) == ("ollama", "gemma3:4b")


def test_pick_vision_target_returns_none_when_no_vision():
    mc = ModelConfig(provider_id="ollama", model="llama3.1:8b")
    assert pick_vision_target(mc, main_supports_vision=False) is None
