---
priority: medium
effort: medium
depends: [t2299_3]
issue_type: documentation
status: Ready
labels: [sitrep, crash_recovery]
gates: [risk_evaluated]
anchor: 2299
created_at: 2026-11-15 12:55
updated_at: 2026-11-15 12:55
---

## Context

This is the fourth and last child of t2299. The three earlier children built crash recovery into sitrep:

- t2299_1: the `recover:t<N>` ref, the `incarnation` origin key, `recovery-apply`, and store format 3.
- t2299_2: the `aitask_sitrep_harvest.sh crashed` detector, `lib/sitrep_crash.py`, the ordered decision table, the survey passage, and ranking.
- t2299_3: the refresh `recovery` check, the monitor tick, the TUI `r` order, the `recover` classify key, and pick routing.

This child teaches the `/aitask-sitrep` skill about recovery items and documents the feature. Read all three siblings' archived plans and the parent plan (`aiplans/p2299/`) first. Describe what actually shipped, not the plan, if they differ.

## Key files to modify

### Skill: `.claude/skills/aitask-sitrep/SKILL.md.j2`

This is the source of truth; the Claude Code version comes first.

- **"The list" section.**
  - Add the `recover:t<N>` ref and its categories (`crashed` / `orphan` / `stale_lock`, the outcome's leading token).
  - Say that the survey passage (`SITREP_RECOVERY_SURVEY v1`, a `capture:` source) is read like any other capture.
  - State that unknown liveness and other-host locks are never items.
- **Writing rules.** Recovery items are written only by the detector and refresh. The agent does not create or reopen them, and `recovery-apply` is not an agent verb.
- **Situation text.** `>w` theme `crashed-agents`: the agent summarises the recovery items per theme and writes that situation text.
- **`>p`.** Advise a resume order using the ranks, in this order:
  1. implementing or post_impl with an approved, valid, fresh plan and surviving work;
  2. approved but stale or invalid (re-verify the plan);
  3. draft;
  4. planning or no plan.

  Also say what remains for post_impl.
- **Cleanup.** Flag stale locks and orphans for cleanup, naming `ait lock --unlock <N>` and `/aitask-pick <N>` for the user to run.
- **Dismissal and episodes.** A dismissed recovery item stays dismissed for the same claim attempt. It reopens only when the task is claimed again and crashes again.
- **Guardrail.** The agent never reclaims, unlocks or picks. It never suggests `git restore` / `git stash` / checkout on a tree with surviving work, and it calls out overlaps between tasks.
- **Then:**
  - regenerate the goldens (`tests/golden/skills/aitask-sitrep/`, see "Regenerate goldens after any `.md.j2` or closure edit" in `aidocs/framework/skill_authoring_conventions.md`);
  - run `./.aitask-scripts/aitask_skill_verify.sh`, `bash tests/test_skill_render_aitask_sitrep.sh` and `bash tests/test_sitrep_skill_contract.sh`;
  - if the TUI's `AGENT_REQUESTS` table changed in t2299_3, check the skill-parity test.

### Docs

Write current-state wording only (`aidocs/framework/documentation_conventions.md`, plus the doc guide at `aitasks/metadata/doc_update_guide.md`).

**`aidocs/framework/sitrep.md`:**
- Components table: add the crash detector row.
- Store section:
  - the `recover:` ref;
  - format 3;
  - `recovery-apply` and its rules;
  - the `incarnation` episode key;
  - the dismissal exception.
- The ordered decision table: summarize it or point to `lib/sitrep_crash.py`.
- The refresh `recovery` class.
- Maintenance order: harvest → detect → refresh.
- The TUI's `recover` key.
- The tests table: add `test_sitrep_crash.*`.

**`website/content/docs/workflows/sitrep.md`:**
- Add a "Crashed agents" section: what is detected, the categories, resuming with `p`, cleanup of stale locks and orphans, and dismissal.
- Amend step 6's "A dismissed item stays dismissed" to name the recovery exception (a new claim that crashes again reopens the item).

**`website/content/docs/tuis/sitrep/reference.md` and `how-to.md`:**
- The recovery item's What-to-do texts and keys.
- The detector's output lines (reference).
- "How to resume crashed work" (how-to).

**`website/content/docs/workflows/crash-recovery.md`:**
- Cross-link to sitrep ("find every crashed task at once").
- **This file already carries another task's uncommitted hunk (t2284's).** Stage only this task's hunks: generate the patch of your own edit and `git apply --cached` it. Never commit the foreign hunk, and never `git restore` / `git stash` it.

**Link checks:**
- Prefer `{{< relref "/docs/..." >}}` for new links.
- Run `cd website && python3 check_links.py --build` (mandatory), and offer `check_link_relevance.py`.

### Other code agents

Per CLAUDE.md, the Codex and OpenCode ports follow the Claude version. t2199 (port the sitrep skill to codex/opencode) already exists, so send it a note rather than creating a new task:

```bash
./ait note 2199 --from 2299_4 --file - <<'EOF'
…the recovery-item skill sections added in t2299_4 must be ported too…
EOF
```

## Verification

- The skill render and verify commands above pass, and the goldens are regenerated in the same commit.
- `check_links.py --build` is clean.
- `git diff --cached` on `crash-recovery.md` contains only this task's hunk.
- Read each changed page as a fresh reader against the doc guide's depth contract. The pages are `depth: [intermediate]`.

Never `git restore` / `git stash` / checkout in this repo. Commit only this task's paths, and use `./ait git` for task and plan files.
