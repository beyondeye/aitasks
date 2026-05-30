---
priority: medium
effort: low
depends: [853]
issue_type: documentation
status: Implementing
labels: [documentation, codeagent]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-29 09:31
updated_at: 2026-05-30 21:47
---

## Goal

After Opus 4.8 becomes the default (t853), update the files that reference the
default model string but are **NOT patched** by the `aitask-add-model` skill.
These are the skill's explicit "Manual review needed" out-of-scope list plus
test fixtures that assert the old default.

## Depends on

t853 (add + promote opus4_8). Do this only once the default is actually
`claudecode/opus4_8`.

## Files to update

Authoritative map: `aidocs/model_reference_locations.md` (tags
`needed_for_promote`). Concretely:

- **`aidocs/claudecode_tools.md`** (line ~5) — the `**Model:** Claude Opus ...`
  asof-today statement → Opus 4.8 / `claude-opus-4-8`.
- **`website/content/docs/commands/codeagent.md`** — the operational-defaults
  table and the "Hardcoded default: `claudecode/...`" line (the audit lists
  lines ~54-57 and ~167 as `needed_for_promote`; the rest are
  `informational_only` format examples — leave those).
- **Test fixtures asserting the default:**
  - `tests/test_codeagent.sh` — model-resolution assertions
  - `tests/test_agent_string.sh` — DEFAULT_AGENT_STRING expectation
  - `tests/test_brainstorm_crew.py` — default agent_string fixtures
  (Some of these may already have been touched in t853 if they blocked that
  task; reconcile rather than duplicate.)

## Doc-writing rules (CLAUDE.md)

User-facing docs describe **current state only** — do NOT write "previously the
default was Opus 4.7" / version-history prose. State Opus 4.8 positively.
Version history belongs in git/PR descriptions.

## Verification

- `bash tests/test_codeagent.sh`, `bash tests/test_agent_string.sh`,
  `python tests/test_brainstorm_crew.py` (or its bash runner) pass.
- `cd website && hugo build --gc --minify` succeeds.
- grep confirms no remaining `needed_for_promote` references still point at the
  old default model string.

## Note

A new changelog/blog entry announcing Opus 4.8 as the default (mirroring the
existing `v0161-claude-opus-4-7-is-now-the-default...` blog post) is a separate
concern — handle via `/aitask-changelog` at release time, not in this task.
