from app.db.models import ConversationModel


def test_conversation_has_computer_use_flags():
    c = ConversationModel()
    assert hasattr(c, "computer_use_enabled")
    assert hasattr(c, "computer_use_display")
