# AgentDesk — Base Skills Catalog (Design)

**Date:** 2026-06-22
**Status:** Approved (design), pending implementation plan
**Related specs:** [07-skills-plugins.md](../../specs/07-skills-plugins.md), [00-agentdesk-master-spec.md](../../specs/00-agentdesk-master-spec.md)

---

## 1. Goal

Ship a curated set of **base (builtin) skills** with AgentDesk so a fresh install
has immediately useful, opinionated behaviors that users can attach to agents and
teams. Users can still create/import their own skills; the base set is the floor,
not a ceiling.

A skill in AgentDesk is **prompt-only** (no executable code). Its `prompt` is
injected into the agent context as `[ACTIVE SKILL: <name> | <id>]\n<prompt>` by
`SkillService.format_skills_for_prompt`.

---

## 2. Constraints (from the runtime)

`backend/app/skills/service.py` enforces hard limits that shape every base skill:

- `max_skills_per_prompt = 10` — at most 10 active skills injected per prompt.
- `max_skill_chars_per_item = 1200` — **each skill prompt must be ≤ 1200 chars** or it
  is truncated with `[truncated]`.
- `max_total_skill_chars = 6000` — combined budget across active skills.

Implication: the catalog may hold more than 10 skills (a user just can't *activate*
more than 10 on one agent at once), but **every base skill prompt must stay ≤ 1200
chars** and be self-contained.

Language: **English** content. Style: **each prompt mixes process discipline +
output template** (how to work AND the shape of the result).

---

## 3. Skill content pattern

Every base skill `prompt` follows one compact shape for consistency and to stay in
budget:

```
When to use: <trigger>.
Process: <3-6 ordered imperative steps — the discipline>.
Output: <the exact sections/structure the agent must produce>.
Rules: <2-4 guardrails / anti-patterns to avoid>.
```

- `description` carries the trigger phrase (also used for relevance/listing).
- `tags` enable filtering in the Skills UI.
- `examples` holds 1 short `{input, behavior}` sample per skill.
- `version` starts at `0.1.0`.

---

## 4. Delivery & loading mechanism

**Approach A — bundled seed + idempotent upsert on startup (chosen).**

1. Base skills ship as read-only JSON under `backend/resources/skills/base/*.skill.json`
   (bundled into the packaged app; the spec's `skills/installed/` lane). User-created
   skills remain conceptually in `custom/`.
2. Add an `origin` column to `SkillModel`: `origin = Column(String, default="custom")`,
   values `"builtin" | "custom"`. Alembic migration required.
3. On backend startup, a `seed_base_skills()` routine upserts each bundled skill into
   the DB **keyed by `id` + `version`**:
   - Missing → insert with `origin="builtin"`.
   - Present, same version → no-op.
   - Present, older version → update prompt/description/tags/examples/version,
     preserve associations.
   - Never touch rows with `origin="custom"`.
4. Seeding is idempotent and audit-logged (`skill_seeded`). It runs after migrations,
   before serving requests.

**UI/behavior notes:**
- Builtin skills are labeled "Builtin" and shown read-only in the editor; users
  **clone-to-edit** (creates a `custom` copy with a new id) rather than mutating the
  original. Deleting a builtin is allowed (soft-delete) but it re-seeds on next start
  unless we also persist a "dismissed builtins" list — out of scope for v1; v1 simply
  re-seeds missing builtins.
- Associations (agent/team) work identically for builtin and custom skills.

**Rejected — Approach B (a "Core Skills" plugin):** plugins carry a manual-enable /
"potentially dangerous" UX meant for tool-bearing packages; overkill for tool-less
prompt snippets and adds activation friction.

---

## 5. Catalog — 17 skills, 4 families

IDs are stable kebab-case. Each prompt below is the literal `prompt` field (≤ 1200
chars).

### 5.1 Engineering / Dev

**`dev-tdd` — Test-Driven Development**
- tags: `["engineering","testing","tdd"]`
- description: "Use when implementing a feature or bugfix, before writing implementation code."
- prompt:
```
When to use: implementing any feature or bugfix.
Process: 1) Restate the desired behavior as one concrete example. 2) Write a single failing test for that behavior; run it and confirm it fails for the right reason. 3) Write the minimum code to make it pass. 4) Run the test; confirm green. 5) Refactor with tests staying green. 6) Repeat per behavior, smallest slice first.
Output: for each cycle show the test first, then the implementation, then the run result (red→green). End with a short list of behaviors still untested.
Rules: never write implementation before a failing test exists. One behavior per test. Do not weaken a test to make it pass. If you can't write the test, the requirement is unclear — ask.
```

**`dev-debugging` — Systematic Debugging**
- tags: `["engineering","debugging"]`
- description: "Use on any bug, test failure, or unexpected behavior, before proposing a fix."
- prompt:
```
When to use: any bug, failure, or behavior that diverges from expectation.
Process: 1) Reproduce reliably; capture exact inputs, environment, and the precise error. 2) State expected vs actual. 3) Isolate: narrow to the smallest failing case; bisect code/commits/inputs. 4) Form one hypothesis about the root cause and a cheap way to test it. 5) Confirm the cause before changing code. 6) Fix, then re-run the reproduction to verify. 7) Add a regression test.
Output: Reproduction, Expected vs Actual, Root cause (evidence), Fix, Verification.
Rules: no fix before a confirmed reproduction and root cause. Change one variable at a time. Report what you actually observed, not what you assume. If you can't reproduce, say so.
```

**`dev-code-review` — Code Review**
- tags: `["engineering","review","quality"]`
- description: "Use when reviewing a diff or PR before merge."
- prompt:
```
When to use: reviewing a change or PR before merge.
Process: 1) Understand the intent and scope of the change. 2) Read the diff for correctness first, then security, then performance, then readability/tests. 3) Check edge cases, error handling, and missing tests. 4) Separate must-fix from nice-to-have.
Output: a list of findings grouped by severity — Blocker, Major, Minor, Nit. Each finding: file:line, what's wrong, why it matters, and a concrete suggested fix. End with an overall verdict (approve / request changes) and one-line summary.
Rules: be specific and cite file:line. Justify every blocker. Do not rubber-stamp; do not invent issues to seem thorough. Praise notably good choices briefly. Flag, never silently assume, security-sensitive code (auth, input handling, secrets).
```

**`dev-planning` — Technical Planning**
- tags: `["engineering","planning"]`
- description: "Use before implementing a multi-step technical task."
- prompt:
```
When to use: before implementing a non-trivial technical task.
Process: 1) Restate the goal and acceptance criteria. 2) Explore the relevant existing code/structure. 3) Break the work into small ordered steps that each leave the system working. 4) For each step name the files touched and the test that proves it. 5) Surface risks, unknowns, and decisions that need input.
Output: Goal, Assumptions, Ordered steps (each with files + verification), Risks/Unknowns, Open questions.
Rules: prefer the smallest change that satisfies the goal (YAGNI). Follow existing patterns over inventing new ones. Each step must be independently verifiable. Call out anything ambiguous instead of guessing.
```

**`dev-architecture-adr` — Architecture Decision Record**
- tags: `["engineering","architecture","adr"]`
- description: "Use when making or documenting a design decision with trade-offs."
- prompt:
```
When to use: choosing between technical options or recording a design decision.
Process: 1) State the decision to be made and what's forcing it now. 2) Capture constraints and requirements. 3) Lay out 2-3 viable options. 4) For each, give honest pros/cons against the constraints. 5) Pick one and explain why. 6) Note the consequences, including what becomes harder.
Output: an ADR with sections — Context, Decision drivers, Options considered (with trade-offs), Decision, Consequences (positive and negative), Status.
Rules: present at least two real options; do not strawman alternatives. Tie the choice to the stated constraints. Record what you're giving up, not just what you gain. Keep it decision-focused, not a tutorial.
```

### 5.2 Design / UX

**`design-critique` — Design Critique**
- tags: `["design","ux","review"]`
- description: "Use when reviewing a mockup or screen for usability and visual quality."
- prompt:
```
When to use: reviewing a design, mockup, or screen.
Process: 1) Identify the screen's primary goal and user. 2) Evaluate visual hierarchy — does the eye land on what matters? 3) Check usability: clarity of actions, feedback, error/empty states. 4) Check consistency with the rest of the product (spacing, type, components). 5) Separate objective issues from taste.
Output: Strengths (brief), then Issues ranked by impact (High/Med/Low) — each with what's wrong, why it hurts the user, and a concrete suggestion. End with the single highest-impact change.
Rules: critique the design, not the designer. Tie every issue to a user or goal, not personal preference. Be specific ("the CTA competes with the secondary link") not vague ("feels off"). Acknowledge constraints you can see.
```

**`design-ux-copy` — UX Copy**
- tags: `["design","ux-writing","content"]`
- description: "Use when writing or reviewing microcopy: buttons, errors, empty states, CTAs."
- prompt:
```
When to use: writing or reviewing interface copy — buttons, errors, empty states, labels, CTAs.
Process: 1) Identify the moment and the user's emotional state. 2) Lead with the most useful information. 3) Use plain language, active voice, and the product's voice. 4) For errors: say what happened, why if useful, and the next action. 5) Keep it as short as clarity allows.
Output: the recommended copy, plus 1-2 alternates where tone could vary, and a one-line rationale. For reviews: before → after with the reason.
Rules: no jargon, no blame ("you entered..."), no dead ends — always offer a next step. Match length to the UI slot. Be specific over clever. Keep terminology consistent across states.
```

**`design-accessibility` — Accessibility Review (WCAG AA)**
- tags: `["design","accessibility","wcag"]`
- description: "Use to audit a design or page against WCAG 2.1 AA."
- prompt:
```
When to use: auditing a design or page for accessibility.
Process: check against WCAG 2.1 AA — 1) Color contrast (text ≥ 4.5:1, large ≥ 3:1, UI/graphics ≥ 3:1). 2) Keyboard: every action reachable and operable, visible focus, logical order. 3) Targets ≥ 24px (prefer 44px touch). 4) Screen reader: labels, alt text, roles, headings, form associations. 5) Don't rely on color alone; respect motion/contrast preferences.
Output: findings by severity (Critical/Serious/Minor) — each with the criterion, where it fails, and the fix. End with a pass/fail summary per category.
Rules: cite the specific WCAG criterion. Distinguish confirmed failures from things needing manual/AT testing. Give the remedy, not just the violation. Don't claim full conformance from a static review.
```

**`design-research-synthesis` — Research Synthesis**
- tags: `["design","research","synthesis"]`
- description: "Use to turn raw user-research notes into themes and recommendations."
- prompt:
```
When to use: turning interview notes, survey results, or usability findings into insight.
Process: 1) Cluster raw observations into recurring themes. 2) For each theme, state the underlying user need or pain (the insight), not just the observation. 3) Note how strongly the data supports it (how many sources/sessions). 4) Translate insights into prioritized, actionable recommendations.
Output: Themes → for each: Insight, Supporting evidence (count/quotes), Confidence. Then a prioritized Recommendations list (impact vs effort). Note open questions the data can't answer.
Rules: ground every theme in actual data; quote where possible. Separate what users did/said from your interpretation. Don't over-generalize from a single session. Flag where the sample is too thin to conclude.
```

### 5.3 Research & Deep-research

**`research-quick` — Quick Research**
- tags: `["research"]`
- description: "Use for a fast, scoped factual lookup."
- prompt:
```
When to use: a focused factual question that needs a quick, reliable answer.
Process: 1) Pin down exactly what's being asked and any scope/time bounds. 2) Gather from the most authoritative sources available. 3) Cross-check the key fact against a second source when it matters. 4) Answer directly, then support.
Output: the direct answer first, then Supporting points with sources, then an explicit Confidence note (high/medium/low) and any caveats or staleness.
Rules: cite sources for non-obvious claims. Distinguish fact from inference. If sources conflict or are missing, say so rather than guessing. State the knowledge cut-off / recency limit when relevant. Keep it tight — this is the fast path, not deep research.
```

**`research-deep` — Deep Research**
- tags: `["research","deep-research"]`
- description: "Use for thorough multi-source investigation of a complex question."
- prompt:
```
When to use: a complex question needing thorough, multi-source investigation.
Process: 1) Decompose the question into sub-questions and plan what evidence each needs. 2) Gather from multiple independent sources per sub-question. 3) Track each claim with its source. 4) Reconcile contradictions explicitly — weigh source quality and recency. 5) Synthesize across sub-questions into a coherent answer. 6) Note gaps and what would change the conclusion.
Output: Question & scope, Key findings (each cited), Conflicting evidence (how you resolved it), Synthesis/answer, Confidence, Gaps & next steps. Include a source list.
Rules: never present a single source as settled fact; corroborate. Attribute every non-trivial claim. Separate evidence from your synthesis. Prefer primary/authoritative sources. Surface uncertainty instead of smoothing it over.
```

**`research-fact-check` — Fact-Check**
- tags: `["research","verification"]`
- description: "Use to verify specific claims against evidence."
- prompt:
```
When to use: verifying one or more specific claims.
Process: 1) Extract each discrete, checkable claim. 2) For each, find the best available evidence. 3) Assess whether the evidence supports, refutes, or is insufficient. 4) Note source quality and date.
Output: a per-claim table/list — Claim, Verdict (Supported / Refuted / Misleading / Unverifiable), Evidence with source, Notes. End with an overall assessment.
Rules: judge each claim independently. Quote or link the evidence; don't assert from memory on contested points. "Unverifiable" is a valid verdict — don't force one. Watch for claims that are technically true but misleading. Note recency when facts can change.
```

**`research-summarize` — Structured Summary**
- tags: `["research","summarization"]`
- description: "Use to summarize a document or body of material faithfully."
- prompt:
```
When to use: condensing a document or set of material.
Process: 1) Identify the source's purpose and main thesis. 2) Extract the key points and any decisions, numbers, or actions. 3) Preserve essential nuance and caveats. 4) Order by importance, not by original sequence.
Output: a one-line TL;DR, then Key points (bulleted), then Details/caveats if needed, then Action items or open questions if present.
Rules: stay faithful — do not add facts or opinions not in the source. Clearly separate the source's claims from any interpretation you add (label it). Keep proportion: don't amplify a minor point. Preserve critical qualifiers ("preliminary", "in some cases").
```

### 5.4 Writing & Product/PM

**`writing-clear` — Clear Writing**
- tags: `["writing","editing"]`
- description: "Use when drafting or editing prose that must be clear and concise."
- prompt:
```
When to use: drafting or tightening any prose.
Process: 1) State the one thing the reader must take away. 2) Lead with it. 3) Cut filler, hedging, and redundancy. 4) Prefer active voice, concrete nouns, and short sentences. 5) Read it back as the target reader.
Output: the revised text. For edits, optionally show before → after for the most impactful changes with a one-line reason.
Rules: one idea per sentence. Remove words that don't change the meaning. Replace jargon with plain terms unless the audience needs it. Don't sacrifice accuracy for brevity. Keep the author's voice; improve clarity, don't homogenize.
```

**`report-structured` — Structured Report**
- tags: `["writing","reports","product"]`
- description: "Use when producing a report or written deliverable that needs a clear structure."
- prompt:
```
When to use: producing a report or written deliverable from findings.
Process: 1) Identify the audience and the decision the report should enable. 2) Lead with the bottom line. 3) Organize evidence under clear sections. 4) Make risks and next steps explicit and owned.
Output: Summary (the bottom line up front), Findings (grouped, evidence-backed), Risks (with likelihood/impact), Next steps (concrete, prioritized). Add an appendix/sources section if there's supporting detail.
Rules: bottom line first — don't bury it. Every finding backed by evidence. Next steps must be actionable, not vague aspirations. Match depth to the audience's needs. Keep sections scannable with headings and short paragraphs.
```

**`product-brainstorm` — Product Brainstorming**
- tags: `["product","discovery","brainstorming"]`
- description: "Use before building a feature, to explore intent and requirements."
- prompt:
```
When to use: before designing or building a feature — to explore intent and requirements.
Process: 1) Understand the underlying problem and who has it before discussing solutions. 2) Ask clarifying questions ONE at a time — purpose, constraints, success criteria. 3) Once the problem is clear, propose 2-3 approaches with trade-offs and a recommendation. 4) Converge on a crisp description of what to build.
Output: while exploring, a single focused question. When ready: Problem, Constraints, Success criteria, Options (with trade-offs + recommendation), Proposed scope.
Rules: one question per turn — don't interrogate. Apply YAGNI; challenge features that don't serve the core problem. Don't jump to implementation before the problem is agreed. Separate must-have from nice-to-have.
```

**`pm-task-planning` — Task Planning**
- tags: `["product","planning","pm"]`
- description: "Use to break an initiative into prioritized, sequenced tasks."
- prompt:
```
When to use: turning a goal or initiative into an executable task plan.
Process: 1) Restate the outcome and its definition of done. 2) Decompose into tasks small enough to estimate. 3) Map dependencies and the critical path. 4) Prioritize (impact vs effort); identify a thin first slice that delivers value. 5) Flag risks and who/what each task needs.
Output: Outcome & DoD, Task list (each with rough size, dependencies, owner/skill needed), Suggested sequence / milestones, Risks. Call out the smallest shippable first increment.
Rules: tasks must be concrete and verifiable, not vague themes. Make dependencies explicit. Prefer delivering value early over big-bang. Don't pad scope; flag anything that isn't needed for the outcome. Surface unknowns as spikes.
```

---

## 6. Data & API impact

- **Model:** add `origin: str = "custom"` to `SkillModel` (+ Alembic migration; backfill
  existing rows to `"custom"`).
- **Exporter:** include `origin` in `export_skill` output (informational).
- **Seeder:** new `backend/app/skills/seeder.py` with `seed_base_skills(db)`; called from
  app startup after migrations. Reads `backend/resources/skills/base/*.skill.json`.
- **Packaging:** ensure `backend/resources/skills/base/` is bundled by PyInstaller
  (data files) per the Windows packaging spec.
- **API:** no new endpoints required. Existing `GET /api/skills` returns builtin +
  custom; clients filter/label by `origin`. (Optional later: `?origin=` filter.)
- **Frontend:** Skills view labels builtin skills and offers "Clone to edit"; editing a
  builtin is disabled. (Detailed UI work can be its own slice.)

---

## 7. Out of scope (v1)

- Marketplace / remote skill distribution.
- Per-user "dismissed builtin" persistence (deleted builtins simply re-seed).
- Bilingual (PT-BR) variants of base skills.
- Auto-suggesting which skill to activate based on the task.

---

## 8. Acceptance criteria

- 17 base skills ship as bundled JSON, each prompt ≤ 1200 chars and following the
  content pattern.
- On a fresh install, all 17 appear in the Skills list marked builtin.
- Re-running startup does not duplicate or clobber skills; custom skills are never
  modified by seeding.
- A builtin skill can be assigned to an agent/team and is injected as
  `[ACTIVE SKILL: …]` at runtime.
- Bumping a builtin's `version` in the bundle updates it on next start while preserving
  associations.
- Seeding events appear in the audit log.
```
