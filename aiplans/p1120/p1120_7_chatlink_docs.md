---
Task: t1120_7_chatlink_docs.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_1_*.md … t1120_6_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_*_*.md
Worktree: aiwork/t1120_7_chatlink_docs
Branch: aitask/t1120_7_chatlink_docs
Base branch: main
---

# Plan: t1120_7 — Chatlink user documentation

Deliverables and binding conventions are in the task file
(`aitasks/t1120/t1120_7_chatlink_docs.md`). **Document the landed source, not
the plans**: read the current `chatlink/` package, `aitask_chatlink.sh`,
`aitask-explorechat` skill, and seeded `chatlink_config.yaml` template before
writing a word.

## Step 1 — website workflow page

`website/content/docs/workflows/bug-report-intake.md` (Docsy front matter
matching sibling pages): sections — What it is (channel → thread → sandboxed
agent → Q&A → committed task); Prerequisites (chat tier `ait setup
--with-chat`, docker, bot created per Discord steps: privileged intents
Server Members + Message Content, invite scopes bot+applications.commands,
minimum permission set — condensed from `aidocs/chat/discord_bot_setup.md`,
current-state prose); Configure (`chatlink_config.yaml` fields with a generic
example project, token file placement + permissions); Run (`ait chatlink
--headless`, TUI view); Reporter experience (thread, select/modal answers,
initiating-user-only, reactions legend ⏳❓✅❌); Limits & safety (sandbox,
allowlist, ceilings) — genericized, no agent-specific naming beyond what the
docs conventions allow.

## Step 2 — `_index.md` bullet

Add the page bullet to `website/content/docs/workflows/_index.md` in the
appropriate hand-curated grouping (Tasks or Review & Quality — match nearest
neighbors).

## Step 3 — maintainer aidocs (gap-driven)

Only if reading the landed code exposes undocumented runtime behavior:
`aidocs/chat/chatlink_runtime.md` (session lifecycle, relay spool layout,
reaper semantics, audit events). Skip if the code+design doc
(`aidocs/chat/qa_relay_protocol.md`) already covers it.

## Verification

- `cd website && hugo build --gc --minify` passes.
- `_index.md` bullet present; internal links resolve.
- `grep -ri "sister" <new pages>` empty; no real repo names; no
  version-history phrasing; TUI lists omit diffviewer.

## Step 9 reference

Post-implementation follows task-workflow Step 9. Final child — parent t1120
archives when this completes (verify parent `children_to_implement` is empty
at archival, per convention).
