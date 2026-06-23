# MCP and Skills desktop UX refactor

## Context

The MCP Servers and Skills views were too dense for desktop configuration workflows. MCP showed the full create form by default, and Skills always showed the import/export JSON panel, making the primary browsing task harder.

## Decisions

- Keep existing API contracts unchanged: `mcpApi.create/update/test` and `skillsApi.create/update/import/export` still receive the same payload shapes.
- Keep the work scoped to the desktop configuration surfaces. No backend source-of-truth logic or authorization behavior moved to the frontend.
- Use progressive disclosure for heavy controls:
  - MCP create/edit form opens only through `Add MCP server` or `Edit`.
  - Skills create/edit form opens only through `New Skill` or `Edit`.
  - Skills JSON import/export opens only through `Import JSON` or `Export`.
- Improve placeholders with concrete local examples, including `python` and `examples/mcp/mock-mcp-server.py`.
- Preserve the existing dark design system classes (`card`, `form-input`, `btn-*`) and avoid introducing a new UI framework.

## Verification notes

- Focused Vitest coverage was updated for collapsed forms, clearer placeholders, and import disclosure behavior.
- Desktop Playwright visual QA used mocked API responses for `/api/mcp`, `/api/skills`, `/api/conversations`, and `/api/health`.
