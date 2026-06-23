from app.db.models import ConversationModel
from app.runtime.capability_gate import resolve_computer_use


def test_conversation_has_computer_use_flags():
    c = ConversationModel()
    assert hasattr(c, "computer_use_enabled")
    assert hasattr(c, "computer_use_display")


def test_computer_use_requires_flag_and_grant():
    assert resolve_computer_use(agent_has=True, chat_enabled=True) is True
    assert resolve_computer_use(agent_has=True, chat_enabled=False) is False
    assert resolve_computer_use(agent_has=False, chat_enabled=True) is False
    assert resolve_computer_use(agent_has=False, chat_enabled=False) is False
