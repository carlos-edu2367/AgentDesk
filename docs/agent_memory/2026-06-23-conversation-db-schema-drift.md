# Conversation schema drift after computer-use migration

## Context

Opening `/#/conversations/conversation_092f0d6fb4b1423788a507062edef1c8` in the Vite frontend showed `TypeError: Failed to fetch`.

## Finding

The backend at `http://127.0.0.1:8000/api/health` was alive, but `GET /api/conversations/{id}` failed with HTTP 500.

Direct backend reproduction showed SQLite error:

```text
sqlite3.OperationalError: no such column: conversations.computer_use_enabled
```

The local AppData database was stamped at Alembic head `d55191bfff6b`, but `pragma table_info(conversations)` did not include:

- `computer_use_enabled`
- `computer_use_display`

## Local repair applied

The local SQLite database at `C:\Users\Carlos\AppData\Roaming\AgentDesk\database\agentdesk.sqlite` was repaired by adding the missing columns:

```sql
ALTER TABLE conversations ADD COLUMN computer_use_enabled BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE conversations ADD COLUMN computer_use_display INTEGER NOT NULL DEFAULT 0;
```

After repair, the same conversation endpoint returned HTTP 200.

## Secondary observation

That conversation currently has 7 executions and more than 58k execution events. The detail endpoint returned about 18.6 MB in roughly 4.9 seconds, so this chat can still feel heavy even after the schema repair.

