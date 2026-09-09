---
Task: t1747_1_failopen_probe_audit_doc.md
Parent Task: aitasks/t1747_sweep_failopen_git_probes.md
Sibling Tasks: aitasks/t1747/t1747_2_automerge_rebase_skip_probe.md, aitasks/t1747/t1747_3_sync_authorization_probes.md, aitasks/t1747/t1747_4_setup_dirty_baseline_probe.md, aitasks/t1747/t1747_5_published_history_amend_probes.md, aitasks/t1747/t1747_6_lock_and_reservation_probes.md, aitasks/t1747/t1747_7_manual_verification_sweep_failopen_git_probes.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-09 15:23
---

# t1747_1 — The fail-open git-probe audit doc

## Context

A `|| true`-suppressed git probe collapses "the probe failed" into "the answer is
empty" — and empty is almost always the *permissive* answer ("no conflicts",
"nothing staged", "nothing dirty"). Two instances have already been closed as
fail-open **authorization** bugs (t1599_4, t1733). t1733's risk section spawned
t1747, whose audit found **13** authorizing sites across six files, plus a much
larger informational set that is correctly out of scope.

This is t1747's first child, ordered first so the five code children (t1747_2 …
t1747_6) can **point at** one doc instead of restating the rule in six places —
which would recreate the N-copies drift the sweep exists to fix. The parent plan
`aiplans/p1747_sweep_failopen_git_probes.md` holds the audit today and will be
archived with t1747; this task gives it a permanent home.

## What this verification pass changed

The plan's own top verification requirement was "every `file:line` cited resolves
in the current tree". **Eight of the cited references had already drifted** since
the plan was written yesterday, so this is not a formality — it is the plan's
main finding:

| cited | actual (HEAD `7e54ce865`) |
|---|---|
| `lib/task_utils.sh:473` (the rule) | `task_git_commit_scoped()` at **`:519`**; the rc-capture at **`:588-594`** |
| `lib/task_utils.sh:477` (A11) | same — **`:588-594`** |
| `aitask_metadata_commit.sh:174` | **`:175-177`** (comment `:172`) |
| `aitask_fold_mark.sh:915` | **`:916-918`** |
| `aitask_gate.sh:1035` | **`:1037-1042`** |
| `lib/data_symlinks.sh:104` | **`:105-108`** |
| `lib/task_utils.sh:718, :724, :1242-1252` | **`:854`, `:860`, `:1378-1388`** |
| `aitask_zip_old.sh:537-539` (Group C) | **wrong site** — the real one is **`:544-546`** (`task_git add … \|\| true` ×3, then the commit at `:562`) |

Confirmed exact, no change: every Group A row (`task_automerge.sh:203,:212`;
`sync.sh:772,:503,:919,:301`; `fold_mark.sh:961`; `issue_import.sh:686`;
`merge_task.sh:81,:82-83`; `setup.sh:3591-3594,:3647,:3763`; `lock.sh:195`), the
whole negative-space table, `issue_import.sh:650`, `txn_snapshot.sh:112`,
`setup.sh:1871`, `archive.sh:413,419`, and merge_task's 16 consumer sites.

**Consequence for the doc's design:** every citation is anchored on
`file::function` **first**, with the line number as a secondary hint and one
explicit "line numbers as of `7e54ce865`" note. That is what let all eight stale
references be recovered here.

**The conditional in the task body resolves to "do it".**
`aidocs/framework/shell_conventions.md` is **clean** — the only dirty paths are
`.aitask-scripts/aitask_create.sh` and an untracked `tests/test_create_id_claim_abort.sh`
from another session. So the back-reference lands, in its own commit.

## Implementation

### 0. Externalize this corrected plan FIRST — before any other action

The plan currently on disk (`aiplans/p1747/p1747_1_failopen_probe_audit_doc.md:29,30,34,44,48`)
still carries the eight stale references above. Plan mode is read-only, so the
correction cannot land before `ExitPlanMode`; it therefore lands as the **first**
post-approval action, ahead of the profile's `post_plan_action: ask` checkpoint
and ahead of every implementation step. No stop path — "approve and stop here"
included — can leave the stale text as the durable record.

Concretely: overwrite the external plan with this text (the corrected-reference
table below is part of it, so the persisted plan is self-contained), append the
`plan_verified` entry, and commit it via
`./.aitask-scripts/aitask_task_commit.sh` scoped to that one plan path — before
`aidocs/framework/failopen_git_probes.md` is created.

### 1. Create `aidocs/framework/failopen_git_probes.md`

Nine sections, in order:

1. **The rule** — quoted from `lib/task_utils.sh::task_git_commit_scoped`
   (`:588-594`): capture the probe's exit status separately; empty output only
   means "nothing" when `rc == 0`.
2. **The canonical fix shape**, with its four in-tree call sites:
   `lib/task_utils.sh::task_git_commit_scoped:588`,
   `aitask_metadata_commit.sh:175`, `aitask_issue_import.sh::_import_amend_guard:657`,
   `aitask_fold_mark.sh::_fold_amend_guard:916`.
3. **Disposition is site-specific** — the fail-safe direction is whichever branch
   is not destructive. Three dispositions, contrasted: the amend guards **refuse**;
   `task_git_commit_scoped` **commits anyway with a warning** (`:594`) because
   committing is safe there; `aitask_gate.sh:1037-1042` **returns 1** (persistence
   unverified). This is the section a reader most needs — the rule is *not*
   "always refuse".
4. **Exit status, not stdout**, wherever the value is consumed arithmetically or
   as a path. Carry t1747_6's measured trap: under `set -u`,
   `[[ "unverified" -gt 0 ]]` **aborts the script** (bash resolves the string as a
   variable name), while `-1` or `""` silently read as clean.
5. **Group A table** — all 13 authorizing sites, each with the child that owns it.
6. **Negative space** — sites deliberately left alone, with the reason each stays.
   This is what stops the next author "finishing the job".
7. **Exemplars to copy** — `lib/data_symlinks.sh:105-108` (round-trip
   verification) and `lib/txn_snapshot.sh:112` (explicit `die` naming the
   unverifiable path).
8. **Group C — named future work**, explicitly *not* this sweep (which is
   probes): swallowed **mutation** failures at `aitask_setup.sh:1871-1872`,
   `aitask_archive.sh:413,419`, `aitask_zip_old.sh:544-546`, and the
   `add … || true` immediately before both amend sites
   (`aitask_fold_mark.sh:1027`, `aitask_issue_import.sh:706`).
9. **Detection boundary, stated explicitly** — the audit is a grep-and-read over
   `.aitask-scripts/**/*.sh`. It catches the common single-command shape; a probe
   assembled through a variable or across statements is not seen. State this
   instead of claiming exhaustiveness.

Plus a short **"why no scanner"** note (see 2) and the line-number caveat.

### 2. Do NOT add a scanner

No regex tripwire over `|| true` on git probes. The legitimate/informational uses
outnumber the authorizing ones by roughly an order of magnitude, so a scanner
would fail on correct code and its false positives would break unrelated work.
State the decision *and its reason* in the doc so it is not silently revisited.
(Phrase the ratio qualitatively — a pinned corpus count would itself go stale.)

### 3. Cross-reference `shell_conventions.md` — in a separate commit

Add a one-line pointer under the existing commit-scoped bullet
(`aidocs/framework/shell_conventions.md:63-80`), which already documents
`task_git_commit_scoped`. Point, do not restate.

The rule from the task body, unchanged: if `git status --porcelain` for that file
is clean, add the pointer in its **own** path-scoped commit; if it is dirty
(another session's work), **skip it** and record the outstanding back-reference in
the Final Implementation Notes. The pointer is optional; the doc is the
deliverable.

It is clean as of this planning pass, so the expectation is that it lands.

Do **not** edit `CLAUDE.md`: it already routes anyone editing a shell script
under `.aitask-scripts/` to `shell_conventions.md`, so the chain
CLAUDE.md → shell_conventions.md → failopen_git_probes.md satisfies t1747_7's
reachability checklist item without a second top-level pointer.

### 4. Re-run the classification sweep at commit time — do not inherit the count

Resolving the cited rows proves each row is *accurate*; it cannot prove the set
is *complete*. A probe added or reclassified since the audit would be absent from
both the Group A table and the inherited Coverage map while every citation still
passes — so the doc's "13 authorizing sites" would be durably false with a fully
green verification.

**The audit's base is `c9834af7d`** (2026-09-08 18:32, the last `.aitask-scripts`
commit before t1747 was created at 18:35). **Seven commits** have landed on
`.aitask-scripts/` since — `062cb383f`, `3e89490fc`, `13e5b3d78`, `874043c73`,
`e7dc87fc0`, `21ad464fe`, `7e54ce865` — and `aitask_create.sh` is dirty from a
live session right now. Several of them post-date the *child* plan too, which is
exactly why its line references arrived stale.

Two-part rerun, both required, immediately before the doc commit:

```bash
# (a) corpus tripwire — the candidate population, whole tree
grep -rnE '(git|task_git|_ait_data_git|_ait_data_gitdir)[^|]*(\|\| *true|\|\| *echo|\|\| *[A-Za-z_]+=)' \
  .aitask-scripts --include='*.sh' | wc -l          # baseline at 7e54ce865: 167
grep -rnE 'if +!? *[^;]*\b(git|task_git|_ait_data_git) .*&>/dev/null' \
  .aitask-scripts --include='*.sh' | wc -l          # baseline at 7e54ce865: 35

# (b) diff-scoped read — every git call ADDED since the audit's base
git log --oneline c9834af7d..HEAD -- .aitask-scripts
git diff c9834af7d..HEAD -- .aitask-scripts | grep -E '^\+' | \
  grep -E '\b(git|task_git|_ait_data_git)\b'
git diff -- .aitask-scripts   # uncommitted work from concurrent sessions
```

Read every hit from (b) and classify it authorizing / informational. If (a)'s
counts moved but (b) shows nothing, a probe was *removed or reshaped* — read that
diff too. Reconcile any authorizing finding into **both** the Group A table and
the Coverage map (a new row with no owning child is a defect that must be
resolved before the doc lands, not recorded as a caveat).

Measured during this planning pass at `7e54ce865`: (b) yields three added git
lines, all of which already capture rc explicitly (`|| a_rc=$?`, `|| c_rc=$?`) —
so 13 is correct as of this SHA. That is a point-in-time result, not a standing
one.

**How the doc states the count.** The Group A table is an enumeration and stands
on its own. The *count* is written as "13 authorizing sites as audited at
`<sha>`", with the sweep above reproduced in the doc so the next reader can
re-derive it — never as a timeless corpus statistic.

## Verification

- Re-resolve **every** `file:line` the finished doc cites against the tree at
  commit time (a `sed -n` spot-check per row) — the eight corrections above prove
  this is a live failure mode, and the doc is committed hours after the check.
- The classification sweep of step 4 is re-run and its residue read, not assumed.
- The Group A table's child assignments equal the parent plan's Coverage map.
  Verified now: 13 rows partition as t1747_2 ← A1,A2 · t1747_3 ← A3,A4,A5,A10 ·
  t1747_4 ← A9,A9b · t1747_5 ← A6,A7 · t1747_6 ← A8,A8b,A12 (2+4+2+2+3 = 13),
  with A11 excluded as correct-as-written and t1747_7 being the aggregate
  manual-verification task, not a Group A owner.
- No `website/content/` page and no `check_links.py` run: this is an `aidocs/`
  framework doc, not user-facing product documentation.
- `git status --porcelain aidocs/framework/shell_conventions.md` re-checked
  immediately before the pointer commit; dirty ⇒ skip it and record the
  outstanding back-reference in the Final Implementation Notes.

## Risk

### Code-health risk: low
- Documentation only: one new `aidocs/` page plus a one-line pointer in an
  existing doc. No executable surface, no test surface. · severity: low ·
  → mitigation: none needed.

### Goal-achievement risk: low
- The doc goes stale as the five code children land and line numbers move — this
  risk **materialized during planning** (8 of the plan's own references drifted
  within a day). · severity: low · → mitigation: none needed as a separate task —
  handled inline: every citation anchors on `file::function` with the line as a
  secondary hint, plus an explicit as-of-SHA caveat, which is exactly what made
  all eight stale references recoverable.
- The doc must outlive `aiplans/p1747_*.md`, which is archived with the parent,
  so an incorrect Coverage map would leave the parent's "every authorizing probe"
  claim unfalsifiable. · severity: low · → mitigation: none needed — the
  partition is verified in this task and re-checked by t1747_7's checklist.
- The audit set is **inherited**, not re-derived: a probe added or reclassified
  between `c9834af7d` and the doc's commit would be missing from both tables while
  every cited row still resolves — a green verification over a false claim.
  · severity: low · → mitigation: none needed as a separate task — handled inline
  by step 4 (corpus tripwire + diff-scoped read of `c9834af7d..HEAD`, reconciled
  into both tables), and by scoping the count to a named SHA in the doc so a
  future reader knows it is re-derivable rather than standing.

**No `### Planned mitigations` block:** both identified risks are already fully
mitigated *inside this plan*, so spawning a separate mitigation task would
duplicate work that lands with the doc itself.
