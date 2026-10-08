---
Task: t1920_opencode_add_model_wrapper_no_supersession_flag.md
Base branch: main
Output branch: main
---

# Plan: t1920 — list `--no-supersession` in the OpenCode add-model wrapper

## Context

t1910 added a `--no-supersession` flag to `/aitask-add-model`
(`.claude/skills/aitask-add-model/SKILL.md`, Step 1 flag list, line ~39).
The OpenCode wrapper `.opencode/skills/aitask-add-model/SKILL.md` delegates its
workflow to the Claude SKILL.md, but its `## Arguments` section enumerates the
accepted flags and that list now omits `--no-supersession`. The Codex wrapper
(`.agents/skills/…`) and the OpenCode command (`.opencode/commands/…`) carry no
flag list, so they need nothing.

## Implementation

1. In `.opencode/skills/aitask-add-model/SKILL.md`, `## Arguments`, insert
   `` `--no-supersession` `` after `` `--promote-ops <csv>` `` in the flag list
   (same order as the Claude Step 1 list: …`--promote`, `--promote-ops <csv>`,
   `--no-supersession`, `--dry-run`). Keep the existing example unchanged. Copy
   no workflow text.

No other files change.

## Verification

- `grep -n -- '--no-supersession' .opencode/skills/aitask-add-model/SKILL.md`
  finds the entry.
- `./.aitask-scripts/aitask_audit_wrappers.sh parity` reports no gap for
  `aitask-add-model`.

## Step 9 (Post-Implementation)

Current-branch mode: commit the code change (`chore: … (t1920)`), commit the
plan, then archive via `aitask_archive.sh 1920` per task-workflow Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
