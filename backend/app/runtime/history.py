from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.db.repositories.registry import execution_repo

# How many prior completed turns to replay into the prompt. Keeps context bounded.
MAX_HISTORY_TURNS = 10


def build_conversation_history(
    db: Session,
    conversation_id: Optional[str],
    exclude_execution_id: str,
) -> List[Dict[str, str]]:
    """Return prior turns of a conversation as alternating user/assistant messages.

    Only completed turns (those with a stored result) are included, excluding the
    current execution. Capped at MAX_HISTORY_TURNS most-recent turns.
    """
    if not conversation_id:
        return []

    rows = (
        db.query(execution_repo.model)
        .filter(
            execution_repo.model.conversation_id == conversation_id,
            execution_repo.model.id != exclude_execution_id,
        )
        .order_by(execution_repo.model.created_at.asc())
        .all()
    )
    rows = [r for r in rows if r.result]
    rows = rows[-MAX_HISTORY_TURNS:]

    history: List[Dict[str, str]] = []
    for r in rows:
        history.append({"role": "user", "content": r.user_input or ""})
        history.append({"role": "assistant", "content": r.result or ""})
    return history
