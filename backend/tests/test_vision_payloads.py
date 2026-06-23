from app.providers.schemas import ChatMessage, ImagePart, ModelInfo


def test_chatmessage_defaults_to_no_images():
    m = ChatMessage(role="user", content="oi")
    assert m.images == []


def test_chatmessage_accepts_images():
    m = ChatMessage(role="user", content="veja", images=[ImagePart(base64="QUJD")])
    assert m.images[0].base64 == "QUJD"
    assert m.images[0].media_type == "image/png"


def test_modelinfo_supports_vision_default_false():
    assert ModelInfo(id="x", name="x").supports_vision is False
