"""
Decide which provider/model to use for vision-carrying turns.
"""
from typing import Optional, Tuple


def pick_vision_target(
    model_config,
    main_supports_vision: bool,
) -> Optional[Tuple[str, str]]:
    """
    Returns (provider_id, model) for the turn that carries a screenshot image.

    Priority:
    1. Explicit vision_provider_id / vision_model on the agent's ModelConfig.
    2. Main model, if it supports vision (supports_vision=True from the provider).
    3. None → caller degrades gracefully (sends only UIA text, no image).
    """
    if model_config.vision_provider_id and model_config.vision_model:
        return (model_config.vision_provider_id, model_config.vision_model)
    if main_supports_vision:
        return (model_config.provider_id, model_config.model)
    return None
