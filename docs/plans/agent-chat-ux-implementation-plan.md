# Agent Chat UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the agent/team execution flow into a real multi-turn chat: markdown answers, expandable thinking blocks, inline tool-call chains, raw logs in a side drawer, and a follow-up composer — with the team chat rendered as a conversation with the leader plus a nested member sub-thread.

**Architecture:** Introduce a `Conversation` entity that groups existing `Execution` rows (one execution = one turn). History from prior turns is injected into `PromptBuilder.build_messages()` to give multi-turn memory, reusing the existing execution engine, SSE event stream, approvals, and audit. The frontend adds a chat module that consumes the same SSE per turn and groups events into chat-friendly blocks.

**Tech Stack:** Backend — FastAPI, SQLAlchemy, Alembic, pytest. Frontend — React + TypeScript, react-router, Vite, Vitest, Tailwind, `react-markdown` + `remark-gfm`.

See design spec: `docs/plans/agent-chat-ux-redesign-plan.md`.

---

## File Structure

**Backend (create):**
- `backend/app/db/models.py` (modify) — `ConversationModel`; add `conversation_id` to `ExecutionModel`.
- `backend/app/domain/schemas.py` (modify) — `Conversation*` schemas; add `conversation_id` to execution schemas; `ConversationMessageRequest`.
- `backend/app/domain/enums.py` (modify) — add `MODEL_REASONING_CHUNK` event type (Phase 3).
- `backend/app/db/repositories/registry.py` (modify) — `conversation_repo`.
- `backend/app/api/routers/conversations.py` (create) — conversations router.
- `backend/app/api/routers/__init__.py` (modify) — register router.
- `backend/app/runtime/history.py` (create) — builds prior-turn message history for a conversation.
- `backend/app/runtime/prompt_builder.py` (modify) — accept and inject `history`.
- `backend/app/runtime/agent_runtime.py` (modify) — pass history into PromptBuilder; emit reasoning (Phase 3).
- `backend/app/orchestrator/execution_engine.py` (modify) — load history when running a conversation turn.
- `backend/app/providers/openrouter.py` / `ollama.py` (modify, Phase 3) — surface reasoning deltas.
- `backend/alembic/versions/<rev>_add_conversations.py` (create) — migration.
- `backend/tests/test_conversations.py` (create) — API + history tests.

**Frontend (create):**
- `apps/frontend/src/types/domain.ts` (modify) — `Conversation`, `ConversationTurn`, `ConversationDetail` types.
- `apps/frontend/src/api/conversations.ts` (create) — API client.
- `apps/frontend/src/views/ConversationView.tsx` (create) — chat page.
- `apps/frontend/src/components/chat/ChatThread.tsx` (create) — renders turns.
- `apps/frontend/src/components/chat/AssistantTurn.tsx` (create) — markdown + thinking + tool chain.
- `apps/frontend/src/components/chat/ThinkingBlock.tsx` (create).
- `apps/frontend/src/components/chat/ToolCallChain.tsx` (create).
- `apps/frontend/src/components/chat/LogsDrawer.tsx` (create).
- `apps/frontend/src/components/chat/Markdown.tsx` (create) — sanitized markdown renderer.
- `apps/frontend/src/components/chat/TeamSubThread.tsx` (create, Phase 4).
- `apps/frontend/src/lib/groupEvents.ts` (create) — pure function grouping events → chat blocks.
- `apps/frontend/src/App.tsx` (modify) — routes.
- `apps/frontend/src/views/Agents.tsx` / `Teams.tsx` (modify) — "Chat" buttons.
- Tests under `apps/frontend/src/__tests__/`.

---

## Phase 1 — Backend foundation (conversations + history)

### Task 1: Conversation model + execution link

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/domain/schemas.py`
- Modify: `backend/app/db/repositories/registry.py`

- [ ] **Step 1: Add `ConversationModel` and `conversation_id` column**

In `models.py` add after `ExecutionEventModel`:

```python
class ConversationModel(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True)
    type = Column(String)            # "agent" | "team"
    target_id = Column(String)       # agent id or team id
    title = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

In `ExecutionModel` add:

```python
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
```

- [ ] **Step 2: Add schemas**

In `schemas.py`, add `conversation_id: Optional[str] = None` to `ExecutionBase`. Add near the Execution schemas:

```python
class ConversationBase(BaseModel):
    type: ExecutionType
    target_id: str
    title: str = ""

class ConversationCreate(ConversationBase):
    pass

class ConversationUpdate(BaseModel):
    title: Optional[str] = None

class Conversation(ConversationBase):
    id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ConversationMessageRequest(BaseModel):
    message: str
    approval_mode: ApprovalMode = ApprovalMode.MANUAL
    workspace_ids: List[str] = Field(default_factory=list)
    stream: bool = True

class ConversationTurn(BaseModel):
    execution: Execution
    events: List[ExecutionEvent] = Field(default_factory=list)

class ConversationDetail(BaseModel):
    conversation: Conversation
    turns: List[ConversationTurn] = Field(default_factory=list)
```

- [ ] **Step 3: Register repo** — in `registry.py`:

```python
conversation_repo = BaseRepository[models.ConversationModel, schemas.ConversationCreate, schemas.ConversationUpdate](models.ConversationModel)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py backend/app/domain/schemas.py backend/app/db/repositories/registry.py
git commit -m "feat(conversations): add Conversation model, schemas, repo"
```

### Task 2: Conversations router (create/list/get/message)

**Files:**
- Create: `backend/app/api/routers/conversations.py`
- Modify: `backend/app/api/routers/__init__.py`
- Test: `backend/tests/test_conversations.py`

- [ ] **Step 1: Write failing tests**

```python
def test_create_and_get_conversation(client):
    agent = _make_agent(client)
    r = client.post("/api/conversations", json={"type": "agent", "target_id": agent["id"], "title": "Hi"})
    assert r.status_code == 200
    conv = r.json()
    assert conv["target_id"] == agent["id"]
    g = client.get(f"/api/conversations/{conv['id']}")
    assert g.status_code == 200
    assert g.json()["conversation"]["id"] == conv["id"]
    assert g.json()["turns"] == []

def test_list_conversations_filters_by_target(client):
    agent = _make_agent(client)
    client.post("/api/conversations", json={"type": "agent", "target_id": agent["id"]})
    r = client.get("/api/conversations", params={"target_id": agent["id"]})
    assert r.status_code == 200
    assert len(r.json()) == 1
```

(`_make_agent` creates a provider + agent via existing endpoints — mirror `tests/test_executions.py` helpers.)

- [ ] **Step 2: Run, verify fail** — `pytest tests/test_conversations.py -v` → 404 (router missing).

- [ ] **Step 3: Implement router**

```python
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.domain import schemas
from app.db.repositories.registry import conversation_repo, execution_repo, execution_event_repo
from app.domain.utils import generate_id, sanitize_for_output
from app.domain.enums import ExecutionType, ExecutionStatus
from app.orchestrator.execution_engine import execution_engine
from app.orchestrator.team_engine import team_execution_engine

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.post("", response_model=schemas.Conversation)
def create_conversation(obj_in: schemas.ConversationCreate, db: Session = Depends(get_db)):
    return conversation_repo.create(db, obj_in=obj_in, id=generate_id("conversation"))

@router.get("", response_model=List[schemas.Conversation])
def list_conversations(type: Optional[str] = None, target_id: Optional[str] = None,
                       limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    q = db.query(conversation_repo.model)
    if type:
        q = q.filter(conversation_repo.model.type == type)
    if target_id:
        q = q.filter(conversation_repo.model.target_id == target_id)
    return q.order_by(conversation_repo.model.updated_at.desc()).limit(limit).all()

@router.get("/{id}", response_model=schemas.ConversationDetail)
def get_conversation(id: str, db: Session = Depends(get_db)):
    conv = conversation_repo.get(db, id=id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    executions = db.query(execution_repo.model).filter(
        execution_repo.model.conversation_id == id
    ).order_by(execution_repo.model.created_at.asc()).all()
    turns = []
    for ex in executions:
        events = db.query(execution_event_repo.model).filter(
            execution_event_repo.model.execution_id == ex.id
        ).order_by(execution_event_repo.model.created_at.asc()).all()
        event_views = [
            schemas.ExecutionEvent(**{
                **schemas.ExecutionEvent.model_validate(e).model_dump(),
                "content": sanitize_for_output(e.content or {}),
            }) for e in events
        ]
        turns.append(schemas.ConversationTurn(
            execution=schemas.Execution.model_validate(ex), events=event_views))
    return schemas.ConversationDetail(
        conversation=schemas.Conversation.model_validate(conv), turns=turns)

@router.post("/{id}/messages")
def post_message(id: str, req: schemas.ConversationMessageRequest,
                 background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    conv = conversation_repo.get(db, id=id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    new_id = generate_id("execution")
    execution_in = schemas.ExecutionCreate(
        type=ExecutionType(conv.type), target_id=conv.target_id,
        user_input=req.message, status=ExecutionStatus.PENDING,
        approval_mode=req.approval_mode, workspace_ids=req.workspace_ids,
        conversation_id=id,
    )
    execution_repo.create(db, obj_in=execution_in, id=new_id)
    conversation_repo.update(db, db_obj=conv, obj_in=schemas.ConversationUpdate(
        title=conv.title or req.message[:60]))
    if conv.type == "team":
        background_tasks.add_task(team_execution_engine.run_team_execution, new_id, conv.target_id, req.stream)
    else:
        background_tasks.add_task(execution_engine.run_agent_execution, new_id, conv.target_id, req.stream)
    return {"execution_id": new_id, "conversation_id": id, "status": "running"}
```

Register in `__init__.py` alongside other routers (follow the existing include pattern).

- [ ] **Step 4: Run, verify pass** — `pytest tests/test_conversations.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routers/conversations.py backend/app/api/routers/__init__.py backend/tests/test_conversations.py
git commit -m "feat(conversations): add conversations router with message dispatch"
```

### Task 3: History injection into the prompt

**Files:**
- Create: `backend/app/runtime/history.py`
- Modify: `backend/app/runtime/prompt_builder.py`
- Modify: `backend/app/runtime/agent_runtime.py`
- Modify: `backend/app/orchestrator/execution_engine.py`
- Test: `backend/tests/test_conversations.py` (add)

- [ ] **Step 1: Failing test for history builder**

```python
def test_build_history_returns_prior_turns(client):
    # Two completed executions in the same conversation become user/assistant pairs
    from app.runtime.history import build_conversation_history
    from app.db.database import SessionLocal
    db = SessionLocal()
    # ... insert conversation + 1 completed execution with result ...
    history = build_conversation_history(db, conversation_id, exclude_execution_id=current_id)
    assert history[0] == {"role": "user", "content": "first message"}
    assert history[1]["role"] == "assistant"
```

- [ ] **Step 2: Implement `history.py`**

```python
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.db.repositories.registry import execution_repo

MAX_HISTORY_TURNS = 10

def build_conversation_history(db: Session, conversation_id: Optional[str],
                               exclude_execution_id: str) -> List[Dict[str, str]]:
    if not conversation_id:
        return []
    rows = db.query(execution_repo.model).filter(
        execution_repo.model.conversation_id == conversation_id,
        execution_repo.model.id != exclude_execution_id,
    ).order_by(execution_repo.model.created_at.asc()).all()
    rows = [r for r in rows if r.result]  # completed turns only
    rows = rows[-MAX_HISTORY_TURNS:]
    history: List[Dict[str, str]] = []
    for r in rows:
        history.append({"role": "user", "content": r.user_input or ""})
        history.append({"role": "assistant", "content": r.result or ""})
    return history
```

- [ ] **Step 3: Inject history in `PromptBuilder`**

Add `history: List[Dict[str, str]] = None` param to `__init__` (store `self.history = history or []`). In `build_messages`:

```python
def build_messages(self) -> List[Dict[str, str]]:
    messages = []
    sys_prompt = self.build_system_prompt()
    if sys_prompt:
        messages.append({"role": "system", "content": sys_prompt})
    messages.extend(self.history)
    messages.append({"role": "user", "content": self._get_user_request()})
    return messages
```

- [ ] **Step 4: Pass history from runtime** — in `agent_runtime.py` where `PromptBuilder(...)` is constructed (around line 204), compute history and pass it:

```python
from app.runtime.history import build_conversation_history
history = build_conversation_history(self.db, getattr(execution, "conversation_id", None), execution.id) if self.db else []
builder = PromptBuilder(agent, execution, available_tools,
                        skills_context=skills_context, memory_context=memory_context,
                        operational_context=runtime_options.get("operational_context", ""),
                        history=history)
```

- [ ] **Step 5: Run tests** — `pytest tests/test_conversations.py -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/runtime/history.py backend/app/runtime/prompt_builder.py backend/app/runtime/agent_runtime.py backend/tests/test_conversations.py
git commit -m "feat(conversations): inject prior-turn history into prompt"
```

### Task 4: Alembic migration

**Files:**
- Create: `backend/alembic/versions/<rev>_add_conversations.py`

- [ ] **Step 1: Generate revision** — `cd backend && python -m alembic revision -m "add conversations"` (or hand-write using the latest `down_revision`, found via `python -m alembic heads`).

- [ ] **Step 2: Implement up/down**

```python
def upgrade():
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("type", sa.String()),
        sa.Column("target_id", sa.String()),
        sa.Column("title", sa.String()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    with op.batch_alter_table("executions") as batch:
        batch.add_column(sa.Column("conversation_id", sa.String(), nullable=True))

def downgrade():
    with op.batch_alter_table("executions") as batch:
        batch.drop_column("conversation_id")
    op.drop_table("conversations")
```

- [ ] **Step 3: Apply** — `python -m alembic upgrade head`. Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(conversations): alembic migration for conversations table"
```

---

## Phase 2 — Frontend chat (single agent)

### Task 5: Markdown dependency + renderer

**Files:**
- Modify: `apps/frontend/package.json`
- Create: `apps/frontend/src/components/chat/Markdown.tsx`
- Test: `apps/frontend/src/__tests__/Markdown.test.tsx`

- [ ] **Step 1: Install** — `cd apps/frontend && npm install react-markdown remark-gfm`.
- [ ] **Step 2: Failing test** — render `# Hi` and assert an `<h1>` with "Hi".
- [ ] **Step 3: Implement** — small wrapper around `react-markdown` with `remark-gfm`, Tailwind prose classes, links open in new tab.
- [ ] **Step 4: Run** — `npm test -- Markdown` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(chat): markdown renderer"`.

### Task 6: Event grouping utility

**Files:**
- Create: `apps/frontend/src/lib/groupEvents.ts`
- Test: `apps/frontend/src/__tests__/groupEvents.test.ts`

- [ ] **Step 1: Failing test** — given an array of events (model_chunk deltas, tool_call_requested/executed/result, agent_completed), assert it returns `{ answer, thinking, toolCalls[] }` with tool calls grouped by tool and joined answer text.
- [ ] **Step 2: Implement** pure function `groupTurnEvents(events): TurnView`. Join `model_chunk` deltas; collect `model_reasoning_chunk` into thinking; fold `tool_*` events into `ToolCallView[]` keyed by step/tool with `args`, `result`, `status`; final answer from `agent_completed`/`execution.result` else streamed text.
- [ ] **Step 3: Run** — `npm test -- groupEvents` → PASS.
- [ ] **Step 4: Commit.**

### Task 7: Chat components (ThinkingBlock, ToolCallChain, AssistantTurn, ChatThread)

**Files:** create the five components under `src/components/chat/`. Tests for `AssistantTurn` (renders markdown answer, expandable thinking hidden by default, tool chain) and `ChatThread` (alternating user/assistant turns).

- [ ] Steps: failing test → implement → run → commit per component (TDD). `ThinkingBlock`/`ToolCallChain`/tool cards are `<details>`-style expandable; reuse existing color conventions from `ExecutionDetail.tsx`.

### Task 8: LogsDrawer

**Files:** `src/components/chat/LogsDrawer.tsx` — collapsible right panel reusing the raw event timeline + audit + export from `ExecutionDetail.tsx`. Test: toggles open/closed; renders events.

### Task 9: ConversationView + API client + routing

**Files:**
- Create: `src/api/conversations.ts`, `src/views/ConversationView.tsx`
- Modify: `src/types/domain.ts`, `src/App.tsx`, `src/views/Agents.tsx`

- [ ] **Step 1:** Add types (`Conversation`, `ConversationTurn`, `ConversationDetail`) and `conversationsApi` (`create`, `list`, `get`, `sendMessage`).
- [ ] **Step 2:** `ConversationView` — on mount, GET conversation detail; render `ChatThread`; composer posts to `/messages`, then opens SSE for the returned `execution_id` via `useExecutionEvents`; on SSE close, refetch detail and append turn. `LogsDrawer` bound to the active turn's events.
- [ ] **Step 3:** Routes: `conversations/:id` → `ConversationView`. New-conversation entry: `Agents.tsx` "Run" → "Chat" creates a conversation (`type:"agent"`) then navigates to `conversations/:id`.
- [ ] **Step 4:** Vitest for ConversationView (mock api): submitting a message calls `sendMessage` and renders the user bubble.
- [ ] **Step 5: Commit.**

---

## Phase 3 — Reasoning capture (real thinking)

### Task 10: `model_reasoning_chunk` event + provider support

**Files:**
- Modify: `backend/app/domain/enums.py` (add `MODEL_REASONING_CHUNK = "model_reasoning_chunk"`), `apps/frontend/src/types/domain.ts` (mirror).
- Modify: `backend/app/providers/schemas.py` — add `reasoning_delta: str = ""` to the stream chunk schema.
- Modify: `backend/app/providers/openrouter.py` (parse `choices[].delta.reasoning`) and `ollama.py` (parse `message.thinking` when present).
- Modify: `backend/app/runtime/agent_runtime.py` — in the stream loop, when `chunk.reasoning_delta`, emit `MODEL_REASONING_CHUNK` (do not add to `final_text`).
- Modify: `apps/frontend/src/lib/groupEvents.ts` + `ThinkingBlock` to consume reasoning.

- [ ] TDD: backend test that a fake provider emitting reasoning deltas produces `model_reasoning_chunk` events; frontend test that grouping routes reasoning into `thinking`. Implement → run → commit.

---

## Phase 4 — Team sub-thread

### Task 11: TeamSubThread rendering

**Files:**
- Create: `apps/frontend/src/components/chat/TeamSubThread.tsx`
- Modify: `src/lib/groupEvents.ts` (group `leader_*` / `member_*` / `subagent_*` events per member), `AssistantTurn.tsx` (render sub-thread when team events present), `src/views/Teams.tsx` ("Chat" button → create `type:"team"` conversation → `conversations/:id`).

- [ ] TDD: grouping test producing per-member contributions with avatar/color; component test rendering nested member cards, collapsed by default. Implement → run → commit.

---

## Testing summary

- Backend: `cd backend && pytest tests/test_conversations.py -v` (and full suite `pytest`).
- Frontend: `cd apps/frontend && npm test`.
- Manual/preview: start backend + `npm run dev`, create an agent, open Chat, send two messages, confirm the second reflects memory of the first; toggle Logs drawer; expand a tool call and thinking block.

## Notes / risks

- `conversation_id` is nullable; legacy one-shot executions and the existing `RunAgent`/`ExecutionDetail` views keep working unchanged.
- History is capped at `MAX_HISTORY_TURNS` (10) completed turns; revisit with token budgeting if needed.
- Reasoning is best-effort: when a model/provider emits no reasoning, the thinking block shows only intermediate steps.
