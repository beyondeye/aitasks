---
priority: medium
effort: medium
depends: [t1555_1]
issue_type: feature
status: Implementing
labels: [verification, task-workflow]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1538
created_at: 2026-08-17 19:00
updated_at: 2026-08-18 11:29
---

Seed the two staleness fields at Step 8c, per
`aidocs/framework/manual_verification_staleness.md` (read it first — it is the
source of truth). Slice 2 of 3. Depends on t1555_1 (the check helper + the
`verification_baseline:` field).

## Why Step 8c specifically

At Step 8c the origin task's code has just been committed, so its files are
discoverable **and HEAD is its landing point** — which is what makes the baseline
correct with no ancestry computation.

This is *not* generalisable to the aggregate / parent-planning path, and must not
be attempted here: measured, `t1505_5` was seeded 2026-08-13 12:31 while its four
origins landed 2026-08-13 21:43 through 2026-08-17 11:36, so at seed time
`--task-files` returns **empty** for every origin and HEAD is not the origins'
landing point. See the doc's "Deferred" section.

## Scope

In `.claude/skills/task-workflow/manual-verification-followup.md` (the Claude Code
source of truth — the Codex / OpenCode ports are separate tasks), extend the
seeding step:

1. **Derive candidates**:
   `./.aitask-scripts/aitask_revert_analyze.sh --task-files <origin>` →
   `FILE|<path>|<ins>|<del>`. It is already children-inclusive, which matters:
   `(t623)` matches 0 commits directly because that work landed under child ids,
   yet `--task-files 623` correctly returns 24 files.
2. **Narrow** to the files the checklist actually exercises, using the plan
   `## Verification` bullets already being read to seed the checklist items.
3. **User confirms** the shortlist.
4. **Write both fields**: the paths as repeatable `--file-ref` arguments (**bare
   paths — no range suffixes**, v1 ignores them) and `verification_baseline:` =
   HEAD, via the setter t1555_1 ships:

   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <new_id> \
       --verification-baseline "$(git rev-parse HEAD) @ $(date '+%Y-%m-%d %H:%M')"
   ```

   Do **not** hand-mutate the frontmatter and do not invent a second setter — the
   interface is specified in t1555_1 precisely so this task does not have to.

## Narrowing is mandatory, not a nicety

Writing the derived set unfiltered reproduces the always-fires behaviour that
makes the check worthless. Measured for origin t632 — derived set of 10 files,
with the number of distinct tasks that have touched each:

```
lib/agent_launch_utils.py     40 tasks   (+49 lines)  <- relevant
test_tmux_exact_session_...sh  4 tasks   (+149)       <- relevant
board/aitask_board.py         91 tasks   (+7)         <- incidental call site
monitor/monitor_app.py        73 tasks   (+7)         <- incidental call site
monitor/minimonitor_app.py    72 tasks   (+11)        <- incidental call site
```

The hub files got a one-line call-site update each. A curated two-entry list is
informative; the unfiltered ten-entry list fires on nearly every commit.

## Only the promptable path is in scope

Where Step 8c cannot prompt, **write nothing** and let the task skip. That costs
nothing today: `manual_verification_followup_mode: never` on `remote.yaml` and
both seed profiles means those profiles create no manual-verification task at 8c
at all.

If the shortlist comes out empty, **write nothing** — do not invent a sentinel to
record "no scope". Expressing that durably requires presence tracking in the
shared `aitask_update.sh` writer plus a fold rule, and is deliberately deferred
(see the doc). An absent field already means "skip".

## Tests

- The **non-promptable** path explicitly: no fields written, no prompt, no error.
  This is the path that would otherwise block automation or silently lose
  coverage.
- The **empty-shortlist** path: no fields written, and specifically **no** empty
  `file_references: []` emitted.
- The happy path: both fields written, and a subsequent
  `aitask_verification_stale.sh check` on the new task returns `FRESH` (nothing
  has changed since HEAD was recorded).

## Acceptance

- After the change, run `./.aitask-scripts/aitask_skill_verify.sh` before
  committing (skill/template surface change).
- Regenerate any affected goldens in the same commit — see "Regenerate goldens
  after any `.md.j2` or closure edit" in
  `aidocs/framework/skill_authoring_conventions.md`.
- Suggest separate tasks to port the change to the Codex CLI and OpenCode skill
  trees (per CLAUDE.md: Claude Code version first).
