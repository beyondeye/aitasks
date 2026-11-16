---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t2299_3]
issue_type: documentation
status: Implementing
labels: [sitrep, crash_recovery]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2299
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 12:55
updated_at: 2026-11-16 15:31
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2299_3** id=2026-11-16T10:57:03Z.51a1f58e01114761a41e1ddc from=t2299_3 from_verified=yes at=2026-11-16T10:57:03Z base=d28e640936de8574329d78a166d55b7739fdf9c2 base_branch=main dirty=yes host=omg16
>
> | What t2299_3 landed (commit d28e64093) that your docs and skill work needs to describe. This is advisory context, not an instruction. The full record is in the archived plan p2299_3, under "Final Implementation Notes" and "Post-Review Changes".
> | 
> | Refresh (lib/sitrep_refresh.py, aitask_sitrep_refresh.sh header):
> | - recover:t<N> items are refresh targets now. REFRESH_ITEM prints kind `recovery` for them.
> | - The verdict comes from the shared sitrep_crash.recovery_verdict:
> |   - stored rows → open;
> |   - rows 2/4 → unknown;
> |   - rows 3/9 → done.
> | - A recovery item is written ONLY when its state or outcome changes, so checked_at stays "evidence last changed". This was a user decision; it overrides the original task table.
> | - Two new result words, and neither one writes anything:
> |   - `unchanged`: the verdict equals the stored one;
> |   - `unverified`: row 1, unreadable inputs, an exception, a timeout, the deadline, no recorded incarnation, or a new episode. "New episode" means the episode key differs from the recorded one; the detector owns that case.
> | - New warning lines:
> |   - REFRESH_WARN:unverified|<n> not verified
> |   - REFRESH_WARN:attempts_unwritable|<reason>
> | - Fairness: recovery targets take turns by an advisory attempt ledger at <git common dir>/aitask-sitrep/refresh_attempts.json, not by checked_at. Entries are pruned after 7 days. A lost or corrupt ledger only makes targets look older.
> | 
> | Monitor tick: harvest all → crashed --root <r> (once per store root, 120 s timeout) → refresh.
> | 
> | TUI:
> | - `r` runs harvest all → crashed → refresh. Each step runs even if the previous one failed, and there are three verdict lines.
> | - A partial refresh (items not verified or not reached) shows the counts and toasts as a warning.
> | - `p` works only on crashed and orphan recovery items. A stale_lock item's How text shows `ait lock --unlock <N>`, which nothing ever runs.
> | - Each category (crashed, orphan, stale_lock, unparseable) has its own What/How text.
> | 
> | Tests the aidocs "Tests" table could name:
> | - tests/test_sitrep_refresh.sh Tests 15 (recovery items) and 16 (fairness under a stalled check, with a delete-the-ledger negative control);
> | - CrashDetectJobTests in test_monitor_sitrep_refresh.py;
> | - CrashDetectorStepTests and RecoverPickTests in test_sitrep_tui_actions.py;
> | - test_recovery_guidance_per_category in test_sitrep_tui_app.py.

> **👁 note:read** id=2026-11-16T11:26:54Z.c9d3f3c2af102ec342e1e656 by=t2299_4 at=2026-11-16T11:26:54Z mode=explicit ids=2026-11-16T10:57:03Z.51a1f58e01114761a41e1ddc

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-16T13:31:40Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-16T14:18:49Z status=pass attempt=1 type=human
