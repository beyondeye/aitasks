---
priority: medium
effort: low
depends: [t635_19]
issue_type: manual_verification
status: Ready
labels: [gates]
anchor: 635
created_at: 2026-07-01 10:45
updated_at: 2026-07-01 10:46
---

## Context

Live end-to-end verification of the `docs_updated` procedure-backed gate shipped
in t635_19. The gate's value rests on the agent skill's inference + user
confirmation, which unit tests cannot exercise. This autonomous
manual-verification drives the whole flow against a real task.

## Verification checklist

- Declare `gates: [docs_updated]` on a scratch/real task and confirm `ait gates
  run <id>` reports it **needs agent** (deferred, no shell exec, exit 0).
- Run task-workflow Step 8: `procedure-gates` lists it; `begin-procedure` opens a
  running block + prints RUN_ID/ATTEMPT; the `aitask-gate-docs-updated` skill
  fires, inspects the change, infers the right doc page (e.g. a TUI/skill change →
  the matching `website/content/docs/...` page), **confirms with the user**,
  applies, and appends `pass` via `append --only-if-running`.
- The `_index.md` manual-list rule: a NEW `workflows/*.md` page without its
  `_index.md` bullet is flagged.
- No-docs-needed change → skill records **`skip`** (not pass); `archive-ready`
  still `ALL_PASS`.
- User-rejected doc work → `fail`; archival BLOCKED until resolved.
- Archive fail-safe: a declared-but-unrun `docs_updated` blocks archival.

## Notes
Coordinate: runs after t635_19 landed the gate. The **docs_updated_activation**
follow-up (**t635_28**) depends on THIS task passing.
