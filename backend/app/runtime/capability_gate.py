"""
Capability gating helpers: decide whether a capability is active
given the agent's grants and the per-conversation flags.
"""


def resolve_computer_use(agent_has: bool, chat_enabled: bool) -> bool:
    """computer_use is active only when both agent has the capability AND the
    conversation has computer_use_enabled=True."""
    return bool(agent_has and chat_enabled)
