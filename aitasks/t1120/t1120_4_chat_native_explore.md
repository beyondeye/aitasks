---
priority: high
effort: high
depends: [t1120_3]
issue_type: feature
status: Implementing
labels: [chat_surface, python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1120
implemented_with: claudecode/fable5
created_at: 2026-07-05 11:59
updated_at: 2026-07-06 18:01
---

## Context

Fourth child of t1120. A chat-native explore flow: the inverse of
aitask-pickrem's no-questions contract — instead of eliminating decision
points, every decision point routes through the relay
(`aitask_relay_ask.sh`, t1120_1) rather than AskUserQuestion, ending in a
task-creation `payload.json` the gateway validates and commits. The headless
round-trip assumption was already validated by t1120_1's Step-0 spike — read
its archived plan (`aiplans/archived/p1120/p1120_1_*.md`) for spike findings
before starting. Parent plan:
`aiplans/p1120_discord_bug_report_channel_integration.md` (§PINNED).

**Contracts: snapshot of parent plan §PINNED — provisional until t1120_1
freeze.** Consumes contracts 2-3 (spool/schemas), 6 (timeout fail-safe),
7 (agent output contract).

## Design decisions (pinned)

- **Dedicated skill** (pickrem precedent: a separate skill with its own
  contract, NOT a runtime branch inside aitask-explore). Working name:
  `aitask-explorechat`. Skill-authoring conventions apply — read
  `aidocs/framework/skill_authoring_conventions.md` and
  `aidocs/framework/stub-skill-pattern.md` before creating skill files; run
  `./.aitask-scripts/aitask_skill_verify.sh` before committing; regenerate
  goldens if `.j2`/closure surfaces are touched.
- New `ait codeagent` operation (e.g. `explore-relay`) in
  `aitask_codeagent.sh` `SUPPORTED_OPERATIONS` (:28) — **explicit opt-in
  headless flag** (`claude -p` billing caveat,
  `aidocs/framework/shell_conventions.md:40-47`; follow the `batch-review
  --headless` precedent at :438-446).
- Skill environment inputs (relay session dir, output path) arrive as
  arguments/env threaded by the launcher — no interactive discovery.

## Agent output contract (contract 7, consumed verbatim)

Agent writes `payload.json` into the session dir and exits; exit code +
`payload.json` presence = completion signal. Payload fields: name/title,
priority, effort, issue_type, labels, description markdown. **The agent never
creates the task, never touches git** — the gateway validates fail-closed and
commits (validation itself is t1120_6's scope; this child produces
schema-conformant payloads).

## Key files to modify

- `.claude/skills/aitask-explorechat/` (new skill; adapt flow from
  `.claude/skills/aitask-explore-default-/SKILL.md` — intent → exploration →
  clarifying questions → task synthesis, with each AskUserQuestion decision
  point mapped to a relay question).
- `.aitask-scripts/aitask_codeagent.sh` — new operation dispatch per agent
  (claudecode first; codex/opencode ports as suggested follow-up tasks per
  CLAUDE.md skill-porting rule).
- `.aitask-scripts/aitask_relay_ask.sh` — consumed, not modified.

## Verification

- Render/stub verification via `aitask_skill_verify.sh`.
- Headless dispatch test: `ait codeagent … invoke explore-relay --headless`
  constructs the expected argv (dry-run seam; no live agent call in tests).
- Relay-conformance test with a scripted fake agent: questions emitted match
  contract 3 schema; timeout answer ⇒ flow proceeds and payload still written
  (fail-safe); payload validates against contract 7 schema.
- Live smoke (skip-capable, explicit opt-in): one real headless invocation
  round-trips a question and writes `payload.json`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-06T15:01:38Z status=pass attempt=1 type=human
