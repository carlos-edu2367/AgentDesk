from app.providers.schemas import ChatMessage, ImagePart, ModelInfo
from app.providers.ollama import _msg_to_ollama
from app.providers.openrouter import _msg_to_openrouter


def test_chatmessage_defaults_to_no_images():
    m = ChatMessage(role="user", content="oi")
    assert m.images == []


def test_chatmessage_accepts_images():
    m = ChatMessage(role="user", content="veja", images=[ImagePart(base64="QUJD")])
    assert m.images[0].base64 == "QUJD"
    assert m.images[0].media_type == "image/png"


def test_modelinfo_supports_vision_default_false():
    assert ModelInfo(id="x", name="x").supports_vision is False


def test_ollama_text_only_is_unchanged():
    m = ChatMessage(role="user", content="oi")
    assert _msg_to_ollama(m) == {"role": "user", "content": "oi"}


def test_openrouter_text_only_is_string_content():
    m = ChatMessage(role="user", content="oi")
    assert _msg_to_openrouter(m) == {"role": "user", "content": "oi"}


def test_openrouter_images_become_content_parts():
    m = ChatMessage(role="user", content="veja", images=[ImagePart(base64="QUJD")])
    out = _msg_to_openrouter(m)
    assert out["content"][0] == {"type": "text", "text": "veja"}
    assert out["content"][1]["type"] == "image_url"
    assert out["content"][1]["image_url"]["url"] == "data:image/png;base64,QUJD"


def test_ollama_includes_images_base64_array():
    m = ChatMessage(role="user", content="veja", images=[ImagePart(base64="QUJD")])
    out = _msg_to_ollama(m)
    assert out["images"] == ["QUJD"]
    assert out["content"] == "veja"
