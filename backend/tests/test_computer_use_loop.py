from app.domain.schemas import ModelConfig
from app.runtime.vision_routing import pick_vision_target
from app.runtime.agent_runtime import build_messages_with_vision


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


def test_only_last_screenshot_kept():
    history = [
        {"role": "user", "content": "faça login"},
        {"role": "assistant", "content": "perceive1", "screenshot_b64": "IMG1"},
        {"role": "assistant", "content": "perceive2", "screenshot_b64": "IMG2"},
    ]
    msgs = build_messages_with_vision(history)
    imgs = [m for m in msgs if m.images]
    assert len(imgs) == 1
    assert imgs[0].images[0].base64 == "IMG2"


def test_no_screenshot_no_images():
    history = [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "olá"},
    ]
    msgs = build_messages_with_vision(history)
    assert all(not m.images for m in msgs)


def test_messages_preserve_content_and_role():
    history = [{"role": "user", "content": "hello"}]
    msgs = build_messages_with_vision(history)
    assert msgs[0].role == "user"
    assert msgs[0].content == "hello"
