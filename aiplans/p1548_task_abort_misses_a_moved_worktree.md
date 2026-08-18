---
Task: t1548_task_abort_misses_a_moved_worktree.md
Base branch: main
Output branch: main
---

# t1548 — Task Abort misses a moved worktree

## Context

t1536 made the **Step 7 deferred worktree fork** *record-aware*: it resolves a
reusable worktree by reading the `worktree <path>` line of the
`git worktree list --porcelain` record whose `branch` is
`refs/heads/aitask/<task_name>` (`.claude/skills/task-workflow/SKILL.md:473-492`).
A worktree moved out of `aiwork/<task_name>` is therefore found and worked in
correctly.

The **Task Abort Procedure** (`.claude/skills/task-workflow/task-abort.md:57-84`)
did not follow — it removes only the hardcoded conventional path:

```bash
git worktree remove aiwork/<task_name> --force 2>/dev/null || true
rm -rf aiwork/<task_name> 2>/dev/null || true
git branch -d aitask/<task_name> 2>/dev/null || true
```

After a moved-worktree resume all three are no-ops — the first two miss the real
directory, and `git branch -d` then fails because the branch is still checked
out in the surviving worktree. The `2>/dev/null || true` guards (which exist so
an abort reached *before* the fork is quiet) swallow every failure, so the user
is told the task was aborted while the worktree and branch remain. t1536 landed
an *honesty* patch only; the cleanup itself is still wrong.

The same hardcoded trio appears **unguarded** in the Step 9 teardown
(`SKILL.md:838-840`) with the identical defect.

**Intended outcome:** one canonical record-aware classification, shared by every
site that resolves or tears down a task worktree, so abort actually removes a
moved worktree — and reports honestly, without destroying anything, when it
cannot.

## Ground truth (verified in a scratch repo, not assumed)

These probes drove the design; the pre-phase below re-runs them as the
regression baseline.

| Probe | Result |
|---|---|
| Manual `mv` of a worktree | Record survives as **`prunable gitdir file points to non-existent location`** — the `worktree <path>` line still names the *old* path. |
| `git branch -d` with that stale record present | **Refuses**: `cannot delete branch … used by worktree at …`. The stale record is what *protects* the branch. |
| `git worktree prune` then `git branch -d` | **Deletes the branch.** The user's moved directory remains on disk with a dangling `gitdir:` pointer and no branch — recoverable only via reflog. |
| `git worktree remove <path>` (success) | Cleans `.git/worktrees/<id>` itself. **`git worktree prune` is never needed on the success path.** |
| `<git_common_dir>/worktrees/<id>/gitdir` | Holds the **absolute path to that worktree's `.git` file**, written by git. This is the *trusted* side of the link — the admin dir can be identified from git's own registry without ever reading the target directory's pointer. |
| `git branch -d` while the worktree is still registered | Refuses **regardless of merge state** — so the branch delete can only succeed after the worktree is gone. |
| `git worktree remove --force` on a **locked** tree | `rc=128`, refuses (`use 'remove -f -f' to override or unlock first`); directory survives. |
| `git worktree remove` **without** `--force` on a dirty tree | `rc=128`, refuses; directory survives. |
| `git worktree remove .` with cwd **inside** the target | `rc=0`, succeeds — but the calling shell's cwd is then gone. |
| `--porcelain` on a path containing a TAB | Emits the raw tab **unescaped**. Any TAB-delimited output format is ambiguous. |
| `--porcelain` (line-based) on a path containing a **newline** | The record splits into `worktree /…/nl/foo` plus a bare `bar` line. A line-based resolver captures the **prefix** — and if that prefix exists as a directory (it did in the probe), the helper would target unrelated data. **Critical.** |
| `--porcelain -z` on the same path | Returns the full path, newline included, as one NUL-delimited field. Unambiguous. Supported here (git ≥ 2.36). |
| `out=$(git worktree list --porcelain -z)` | Bash **strips every NUL** (`warning: command substitution: ignored null byte in input`) — 25 delimiters lost. A `read -r -d ''` loop over the variable recovers **0** worktree fields; over a temp file, **6**. Command substitution cannot carry this data. |

## Approach

Lift the classification into a shared, unit-testable helper (the task's
suggested fix #1 — the option that preserves the flexibility t1536 introduced).

Two governing constraints:

1. **Strict superset of today's behaviour.** A record-*only* resolver would drop
   cases the hardcoded path catches (detached HEAD inside the worktree loses the
   record's `branch` line; a leftover `aiwork/<n>` from a failed `worktree add`
   has no record at all). Teardown acts on the **union** of {record path,
   `aiwork/<task_name>`}.
2. **Never destroy, never widen.** The helper performs **no repo-global
   mutation** — `git worktree prune` is dropped entirely — and stops rather than
   guesses whenever git itself is refusing.

### Pre-phase (risk mitigations)

**`reproduce_moved_worktree_first`** — before editing anything, rebuild the
scratch repo and re-run the Ground-truth table above as an explicit script,
including the end-to-end reproduction the task asks for: create a task worktree,
`git worktree move` it, run the three current abort commands, and confirm the
worktree **and** the `aitask/tX` branch both survive while the procedure would
report success. This is the negative control for the new tests and pins every
git behaviour the helper depends on.

### 1. New helper — `.aitask-scripts/aitask_task_worktree.sh`

Scope, stated in the header: **task worktrees only** — the `aitask/<task_name>`
branch and its worktree. Not the `.aitask-data` worktree (`ait git` /
`ait git-health`), not agentcrew worktrees (`aitask_crew_cleanup.sh`). Header
also records that the helper **never** runs `git worktree prune` and mutates
nothing outside the named task's worktree and branch.

```
Usage:
  aitask_task_worktree.sh resolve <task_name>
  aitask_task_worktree.sh remove  <task_name> [--force] [--strict]
```

#### `resolve` — the single canonical classifier

Prints exactly one line: **state first, path last** (reason-first ordering means
a parser takes fields 1..n and the remainder verbatim as the path — unambiguous
for any path without a newline, which TAB-separation is not).

```
NONE
USABLE  <path>     record matches, path is a directory
STALE   <path>     record matches but is `prunable`, or its path is not a directory
LOCKED  <path>     record carries a `locked` line
MAIN    <path>     the matching record IS the main worktree root
UNSAFE  <pct-encoded-path>   path contains TAB / newline / CR
```

Exit **0** for every state (absence and hazard are both normal answers, not
transport failures); exit **2** on usage error.

This is the one definition of "a usable worktree record" — `remove` branches on
the same function, so the producer's predicate and the consumer's guard cannot
drift. It replaces the awk inlined at `SKILL.md:476`.

`MAIN` matters because a user, or an agent in current-branch mode, can have
`aitask/<n>` checked out at the repo root — and Step 9 runs immediately after
`git checkout "$output_branch"` at the root (`SKILL.md:794`). Without this state
the `rm -rf` fallback would delete the user's repository.

#### `remove` — teardown, then re-verify, then report

1. `cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"`
   — the main worktree root. Necessary: once the target is unlinked the
   process's cwd no longer exists and every later `git` call fails.
2. Classify via `resolve`. **`STALE`, `LOCKED`, `MAIN`, `UNSAFE` are refusals**:
   emit `WORKTREE_KEPT <reason> <path>`, touch **nothing**, and **skip the branch
   delete entirely**. Verdict `RESIDUE`, exit 1.

   Skipping the branch delete on `STALE` is the whole point of the ground-truth
   probe: the stale record is what makes `git branch -d` refuse, so *not
   pruning* keeps the branch safe **by construction**, not by hope. The report
   names the surviving directory and the remedies — `git worktree repair <new
   path>` to re-link a manually-moved tree, or `git worktree prune` if the user
   really has abandoned it.
3. `USABLE` / `NONE`: build the candidate set {record path} ∪
   {`<repo_root>/aiwork/<task_name>`}, deduped, existing entries only.
4. `git worktree remove <path>` — `--force` **only when the caller passed
   `--force`**. Abort passes it (discarding is the intent, matching
   `task-abort.md:61`); Step 9 does **not**, so uncommitted work still blocks
   removal exactly as today, surfacing as `WORKTREE_KEPT dirty <path>`.
5. `rm -rf` fallback, only if the removal failed, and only for a path that is
   non-empty, is not the main root, and is control-char-free. Two disjoint
   sub-cases, with **different** admin-metadata rules:

   - **Registered** (the path came from a `USABLE` record): `rm -rf <path>`,
     then delete that worktree's admin directory — identified from git's own
     registry, never from the target. Scan
     `<git_common_dir>/worktrees/*/gitdir` for the entry whose *content* is
     `<path>/.git`; the admin dir is that file's parent. Guard the result: it
     must be a direct child of `<git_common_dir>/worktrees/`.
   - **Unregistered** (a plain leftover at exactly
     `<repo_root>/aiwork/<task_name>`, no record): `rm -rf` **that directory
     only**. Never read its `.git` file and never follow any `gitdir:` pointer
     it contains. A tampered or stale `.git` there can name
     `<repo_root>/.git`, or any arbitrary path, and following it would delete
     the user's repository — the old procedure only ever removed
     `aiwork/<task_name>`, and this preserves that bound exactly.

   Never `git worktree prune`: it is repo-global and would discard metadata for
   unrelated stale worktrees that crash recovery or another task depends on.
6. `git branch -d aitask/<task_name>` — **never `-D`**. Abort must not silently
   destroy commits made during the session.
7. Re-classify and re-check the branch ref, then print the result.

**Output** — two facts and a verdict, one per line, reason before path:

```
WORKTREE_NONE | WORKTREE_REMOVED <path> | WORKTREE_KEPT <reason> <path>
BRANCH_NONE   | BRANCH_DELETED <branch> | BRANCH_KEPT <reason> <branch>
CLEAN | PRESERVED | RESIDUE
```

Worktree reasons: `stale_record`, `locked`, `main_worktree`, `dirty`,
`unsafe_path`, `unknown`.
Branch reasons: `checked_out`, `skipped`, `unmerged_into:<head_ref>`, `unknown`.

`unmerged_into` is asserted **only** when
`git merge-base --is-ancestor refs/heads/aitask/<n> HEAD` exits exactly `1`;
exit `128` (missing ref / no commits) is `unknown`, never relabelled. The label
names the ref it compared against, because `git branch -d` measures against the
branch's upstream (or HEAD), and at abort time the root's HEAD need not be the
task's base.

**Three verdicts, deliberately.** `PRESERVED` means the helper did exactly what
it should and knowingly kept something (an unmerged branch). `RESIDUE` means it
tried and could not. Collapsing them would make the *correct* abort-after-commits
outcome report as a failure, and users would learn to ignore the message.

**Exit status carries the verdict too**, and `--strict` chooses how strictly:

| mode | exit 0 | exit 1 | exit 2 |
|---|---|---|---|
| default | `CLEAN`, `PRESERVED` | `RESIDUE` | usage |
| `--strict` | `CLEAN` **only** | `PRESERVED`, `RESIDUE` | usage |

**Step 9 calls `remove <task_name> --strict`, bare.** Its trio is unguarded
today, so any failure aborts the agent's bash call before archival — and
`PRESERVED` there is a real, reachable state (the worktree is removed but the
branch is unmerged into the root's HEAD, so `git branch -d` refuses). A default
`PRESERVED`/0 would let Step 9 archive with `aitask/<n>` still alive, which is
exactly the silent outcome the unguarded trio prevents today. `--strict` makes
"Step 9 requires CLEAN" an exit code rather than a sentence the agent is asked
to honour.

**Abort calls `remove <task_name> --force || true`** and parses — there
`PRESERVED` is the correct, expected outcome after an abort with commits, and
must not read as a failure.

**Parse `--porcelain -z`, NUL-delimited — not lines.** This is a correctness
requirement, not a nicety: on a path containing a newline the line-based record
splits, and `substr($0, 10)` captures the *prefix*. The probe above produced a
prefix that existed as a real, unrelated directory — `resolve` would have called
it `USABLE` and `remove --force` would have `rm -rf`'d it. Read with
`while IFS= read -r -d '' field`, which returns the full path as one field, so
the `UNSAFE` control-character check actually sees the newline.

Probe `-z` support once (`git worktree list --porcelain -z >/dev/null 2>&1`). If
it is unavailable (git < 2.36), fall back to the line parse **with a fail-closed
unknown-line rule**: any line inside a record that is not a known key
(`worktree `, `HEAD `, `branch `, `detached`, `bare`, `locked`, `prunable`, or
the blank separator) means the output is unparseable — that record resolves to
`UNSAFE` and `remove` deletes nothing. Document the residual gap: a path whose
embedded newline is followed by text that *mimics* a key would evade the
fallback, which is why `-z` is the primary path.

**Transport: a temp file, not a variable and not a pipe.** These three
constraints together admit exactly one shape:

```bash
wt_list="$(mktemp "${TMPDIR:-/tmp}/aitask_task_worktree.XXXXXX")"
trap 'rm -f "$wt_list"' EXIT
git worktree list --porcelain -z > "$wt_list" \
  || die "git worktree list failed — refusing to touch anything"
while IFS= read -r -d '' field; do … done < "$wt_list"
```

- **Not `out=$(…)`** — bash discards NUL bytes, which *are* the delimiters
  (measured above: 0 fields recovered vs 6). This silently defeats the
  newline-safe parser and returns to the prefix-capture hazard.
- **Not a pipe into `awk … exit`** — closing the pipe early gives git SIGPIPE
  (141) and, under `set -o pipefail`, kills the helper with no message
  (`aidocs/framework/shell_conventions.md:12-20`).
- **Not `< <(git …)`** — process substitution preserves NULs but makes the
  producer's exit status unobservable. A failed `git worktree list` would then
  read as an empty listing, i.e. `NONE`, and `remove` would proceed to
  `git branch -d` on the strength of a *failure*. The explicit `|| die` above is
  the point: a producer error is its own state, never a negative result.
`#!/usr/bin/env bash`, `set -euo pipefail`, `die`/`warn` from
`lib/terminal_compat.sh`, diagnostics to stderr, mode `100755`, clean under
`shellcheck .aitask-scripts/aitask_*.sh`.

### 2. Rewire the prose call sites (hand-authored sources only)

`.claude/skills/task-workflow/` holds the sources; every `task-abort.md` /
`SKILL.md` under `.claude/skills/*-/`, `.agents/skills/*-/`,
`.opencode/skills/*-/` is generated. `task-abort.md` is Jinja-free and renders
verbatim.

| File | Change |
|---|---|
| `task-abort.md` (top) | Add the prerequisite that the whole procedure runs **from the repo root** — it already invokes `./.aitask-scripts/…` and `./ait git`, which an abort taken from inside the worktree cannot resolve. |
| `task-abort.md:57-84` | Replace the trio **and** the advisory post-check awk with `aitask_task_worktree.sh remove <task_name> --force \|\| true`. Delete the now-fixed "Known limitation" block; keep the load-bearing "pre-fork abort is a clean no-op" sentence. On `PRESERVED`, report calmly and name what was kept ("your commits are on `aitask/<n>`"). On `RESIDUE`, name each survivor **with its reason and remedy** and do not report a clean abort. |
| `SKILL.md:473-481` | `resolve` replaces the inline awk, consumed as state+path: `USABLE` → reuse that directory (keep the "do not assume it equals `<worktree_path>`" note); `NONE` → cut below; **anything else → stop and ask the user**, naming the state and path. |
| `SKILL.md:483-488` | Because `resolve` no longer hands back dead records, note that a `STALE`/`LOCKED`/`MAIN`/`UNSAFE` result must not fall through to `git worktree add -b` (it would fail on the already-existing branch) — it stops and asks instead. No prune, no guessing: the user's work may be in that directory. |
| `SKILL.md:838-840` | Step 9 teardown: `remove <task_name> --strict` (no `--force`) replaces the hardcoded trio. Called **bare**, so any verdict other than `CLEAN` exits non-zero and stops before archival — including a surviving unmerged branch. |
| `SKILL.md:297` | Re-entry Routing cross-reference — name the helper instead of "extract it record-aware, as Step 7 does". |

Confirm during implementation that the helper is **not** reached on the paths
that intentionally leave a worktree in place: the Step 7 risk-mitigation
"before" stop (`SKILL.md:498-511`) and the crash-recovery decline path, neither
of which routes through `task-abort.md`.

### 3. Whitelist the helper

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_task_worktree.sh
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_task_worktree.sh   # must print nothing
```
Five touchpoints: `.claude/settings.local.json`, `.codex/rules/default.rules`,
and the three `seed/` mirrors.

### 4. Test — `tests/test_task_worktree_helper.sh`

Self-contained bash over a temp git repo, `assert_eq`/`assert_contains` from
`tests/lib/asserts.sh` (with `assert_counters_init` / `assert_counters_load` if
any body runs in a `( … )` subshell).

| # | Case | Assertion |
|---|---|---|
| 1 | `resolve`, nothing exists | `NONE`, exit 0 |
| 2 | `resolve`, conventional worktree | `USABLE <aiwork/n>` |
| 3 | `resolve` after `git worktree move` | `USABLE <newpath>`, and explicitly **not** `aiwork/<n>` |
| 4 | `resolve` after a manual `mv` | `STALE <oldpath>` — not `USABLE`, not `NONE` |
| 5 | **`remove --force`, moved worktree, clean branch** | `WORKTREE_REMOVED <newpath>` + `BRANCH_DELETED` + `CLEAN`, exit 0; directory gone, `git branch --list aitask/<n>` empty |
| 6 | **`remove --force` after a manual `mv`** | `WORKTREE_KEPT stale_record <oldpath>` + `BRANCH_KEPT skipped` + `RESIDUE`, exit 1; **the moved directory still exists, the branch still exists, and the admin dir `.git/worktrees/<id>` is intact** |
| 7 | **unrelated stale worktree survives** | with a *second*, unrelated worktree manually `mv`'d, `remove` on the task's worktree leaves that unrelated record present in `git worktree list --porcelain` (no global prune) |
| 8 | **`remove --force` on a locked worktree** | `WORKTREE_KEPT locked <path>` + `RESIDUE`, exit 1; **directory, branch and the lock all still present** (`git worktree list --porcelain` still shows `locked`) |
| 9 | **path containing a TAB** | `resolve` → `UNSAFE <pct-encoded>`; `remove --force` → `WORKTREE_KEPT unsafe_path …` + `RESIDUE`, exit 1, directory and branch untouched |
| 10 | `remove`, nothing exists (pre-fork abort) | `WORKTREE_NONE` / `BRANCH_NONE` / `CLEAN`, exit 0, **empty stderr** |
| 11 | `remove --force`, branch with unmerged commits | `BRANCH_KEPT unmerged_into:<ref>` + `PRESERVED`, exit 0 |
| 12 | `remove` (no `--force`) on a dirty worktree | `WORKTREE_KEPT dirty <path>` + `RESIDUE`, exit 1; the dirty file still on disk |
| 13 | `remove --force` when `aitask/<n>` is checked out at the **main** root | `WORKTREE_KEPT main_worktree <path>`, exit 1, repo intact |
| 14 | `remove --force` with cwd inside the worktree | still succeeds |
| 15 | leftover `aiwork/<n>` directory with **no** record | removed (superset property vs. the old `rm -rf`) |
| 16 | **Step 9 shape: `--strict`, no `--force`, unmerged branch** | worktree removed, `BRANCH_KEPT unmerged_into:<ref>`, verdict `PRESERVED` on stdout, **exit non-zero** — an archival-blocking signal |
| 17 | **hostile `gitdir:` pointer** | unregistered `aiwork/<n>` whose `.git` file reads `gitdir: <repo_root>/.git`; `remove --force` deletes `aiwork/<n>` **only** — `<repo_root>/.git` still exists and `git status` still works |
| 18 | registered-worktree admin cleanup | when the `rm -rf` fallback fires on a registered worktree, `<git_common_dir>/worktrees/<id>` is removed and **no other** admin dir is touched |
| 19 | **newline path whose prefix directory exists** | worktree at `<base>/foo\nbar` with `<base>/foo` also present as a real directory. Drives the **real script's entry point**, not a replica of its parser: `resolve` → `UNSAFE <pct-encoded full path>` (never `USABLE <base>/foo`); `remove --force` → `WORKTREE_KEPT unsafe_path …` + `RESIDUE`, exit 1, and **`<base>/foo` still exists** |
| 20 | **producer error is not a negative result** | with `git` made to fail for the listing (e.g. invoked outside any repository), `resolve` and `remove` exit non-zero with a diagnostic — never `NONE` / `CLEAN`, and `git branch -d` is never reached |

Case 5 is the t1548 regression test: run against the old hardcoded trio it fails,
since nothing is removed. Cases 6–9 and 16–20 are the concerns raised on review;
19 fails against a line-based parser (or a NUL-stripping `$()` transport) rather
than against the old code.
Case 10 pins the quiet-no-op property five pre-fork abort call sites depend on.

### 5. Regenerate generated artifacts (same commit)

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/SKILL.md aitasks/metadata/profiles/$p.yaml claude \
    > tests/golden/procs/task-workflow/SKILL-$p.md
done
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh $p; done
```

`task-abort.md` has no golden (no Jinja), but it has 9 rendered copies — three
of them (`-remote-`) git-tracked prerenders that must not drift.

### Post-phase (risk mitigations)

**`artifact_drift_sweep`** — after regenerating, prove no stale artifact ships:
review the golden diff line by line (it must contain only the Step 7 / Step 9 /
Re-entry edits — an unrelated hunk means a render regression), run
`tests/test_skill_render_task_workflow.sh`, and confirm `git status --porcelain`
lists only intended paths across all three agent trees.

## Out of scope

- **`git branch -D`.** Abort keeps `-d` and reports a preserved unmerged branch
  rather than destroying commits. Confirmed with the user.
- **`crash-recovery.md:38-46`** hand-parses the same porcelain records with a
  less robust "two lines above" rule. A natural further caller for `resolve`,
  but it is a read-only survey in a different procedure — left for a follow-up.
- **Operating on a newline/tab worktree path.** `-z` parsing lets the helper
  *see* such a path correctly, and it then refuses it as `unsafe_path` rather
  than trying to tear it down through a multi-field text protocol. Detecting it
  safely is in scope; handling it is not.
- **t1166_4** (`Ready`, blocked on t1166_1/t1166_2) plans to rewrite this same
  abort block for shared family worktrees. Moving the mechanism into a helper is
  where family-awareness belongs; its task file is not edited here.

## Risk

### Code-health risk: medium
- The helper is destructive (`rm -rf`, `worktree remove`, `branch -d`) and acts on paths *parsed from git* rather than constructed. The `main_worktree`, `locked`, `stale_record` and `unsafe_path` refusals are load-bearing, and each now has a dedicated test. · severity: high · → mitigation: inline pre-phase reproduce_moved_worktree_first
- The `rm -rf` fallback resolves administrative metadata. It must never follow a pointer stored *inside* the directory it is about to delete — an unregistered `aiwork/<n>/.git` is attacker- or accident-writable and can name `<repo_root>/.git`. Registered targets resolve through git's own registry with a containment guard; unregistered ones get no metadata handling at all. · severity: high · → mitigation: inline pre-phase reproduce_moved_worktree_first
- Wide artifact surface: 2 hand-authored sources, 9 rendered copies, 3 goldens, 5 whitelist touchpoints — and `task-abort.md` has no golden and no test guarding its prose, so a stale copy ships silently. · severity: medium · → mitigation: inline post-phase artifact_drift_sweep
- The Step 7 reuse block being rewired landed in t1536 hours ago; a regression there sends implementation into the wrong tree, and the failure mode is silent. · severity: medium · → mitigation: inline pre-phase reproduce_moved_worktree_first
- Step 9 teardown is swept in the same change (same defect class) but is not what the task reported, widening the reviewed surface. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Correctness rests on git behaviours that vary by version. Every one the design depends on is now measured (Ground truth table) and re-measured by the pre-phase, rather than assumed. · severity: medium · → mitigation: inline pre-phase reproduce_moved_worktree_first
- `BRANCH_KEPT` reason classification compares against the root's HEAD, which at abort time need not be the task's base — so the label is narrowed to `unmerged_into:<ref>` rather than a bare `unmerged`. Misreporting is bounded: the verdict is still `PRESERVED`. · severity: low · → mitigation: TBD

### Planned mitigations
- timing: pre-phase | name: reproduce_moved_worktree_first | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: destructive-path guards, unverified git behaviour, silent Step 7 regression | desc: Reproduce the moved-worktree abort failure and re-measure every git behaviour in the Ground truth table in a scratch repo before any edit.
- timing: post-phase | name: artifact_drift_sweep | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: wide artifact surface, stale rendered copy ships silently | desc: After regenerating goldens and rerendering all three profiles, review the golden diff line by line and confirm git status lists only intended paths.

## Verification

1. Pre-phase reproduction confirms the bug and the git contract (above).
2. `bash tests/test_task_worktree_helper.sh` — all 20 cases pass.
3. `shellcheck .aitask-scripts/aitask_*.sh` — clean.
4. `bash tests/test_skill_render_task_workflow.sh` — goldens match.
5. `bash tests/test_gate_plan_approval_transitions.sh` and
   `bash tests/test_gate_reentry.sh` — the `task-abort.md` demotion assertions
   still pass across every profile.
6. `./.aitask-scripts/aitask_skill_verify.sh` — templates render, stub and
   wrapper parity intact.
7. `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_task_worktree.sh`
   — no `MISSING:` lines.
8. Post-phase drift sweep (above).

Step 9 (Post-Implementation) handles cleanup, archival and merge.
