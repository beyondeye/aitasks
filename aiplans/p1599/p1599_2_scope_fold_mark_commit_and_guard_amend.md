---
Task: t1599_2_scope_fold_mark_commit_and_guard_amend.md
Parent Task: aitasks/t1599_scope_task_data_commits_to_their_own_paths.md
Sibling Tasks: aitasks/t1599/t1599_1_*.md (archived), aitasks/t1599/t1599_3_*.md, aitasks/t1599/t1599_4_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-01 10:13
---

# p1599_2 — Scope `aitask_fold_mark.sh` and make its amend fail loudly

## Context

`aitask_fold_mark.sh` stages the whole `aitasks/` tree (`:598`, `:623`) and then
commits the **entire git index** (`:611`) — and, worse, `--amend`s **whatever
HEAD happens to be** (`:628`) with no hash argument, ancestry check, or
"is this my commit" guard. Any file a concurrent session is mid-edit on is swept
into a commit whose message names a different task.

Re-measured against the live data branch during this verify pass (2026-08-31),
excluding the fold's own legitimate `attachments/meta/*` rebinds:

| metric | value |
|---|---|
| fold commits in history | 12 |
| carrying a **foreign task file** | **4** (`14097318f`, `8664a6a76`, `a3eac4918`, `6bc213ba1`) |
| carrying foreign metadata | 1 (`21219b0b4` → `aitasks/metadata/gates.yaml`) |

Still live: `14097318f` ("Fold tasks into t1603: merge t1596") swallowed
`t1628` **and** `t1629`. Volume is low, but the `--amend` path is the most
dangerous code in the whole parent task — it can rewrite an already-pushed
commit, and `aitask_sync.sh` pushes non-force, so the next sync fails with
`ERROR:push_failed`.

This child owns `.aitask-scripts/aitask_fold_mark.sh` **exclusively**. Not
`aitask_pick_own.sh` (t1599_1, landed), not `aitask_sync.sh` / `aitask_lock.sh`
(t1599_3), not the t1599_4 sweep targets, and **not** `lib/task_utils.sh`.

## Verification of the existing plan (verify pass)

Every claim in the task file and the prior plan re-checked against HEAD. Five
material findings; the rest confirmed.

| claim | status |
|---|---|
| `rollback_paths` is exactly the right path set, built and used only for rollback | ✅ confirmed (`:574-587`, `_fold_rollback` `:590-593`) |
| `primary_file` can be empty ⇒ `rollback_paths` can be empty | ❌ **cannot** — `die` at `:101` guarantees ≥1 element |
| line refs `:567-580` / `:590-614` / `:615-626` / `:630-632` | ❌ **drifted +7** → `:574-587` / `:597-621` / `:622-634` / `:637-639` |
| amend re-attributes foreign files "under the fold message" | ❌ `--no-edit` keeps **HEAD's own** message (the *create* message). Harm is the SHA rewrite + silent retention, not a fold-message relabel. Probed empirically. |
| the plan should hand-roll `add` / `status --porcelain` / `commit -- <paths>` | ❌ **superseded** — t1626 promoted that exact shape into `task_git_commit_scoped` (`lib/task_utils.sh:217-243`) |
| strict "HEAD ⊄ rollback_paths ⇒ refuse" guard | ❌ **false-positives on the production path** (below) |
| amend callers at pr-import `:252`, explore `:301`, contribution-review `:249` | ✅ confirmed, plus every rendered per-profile/per-agent variant |
| `declare -A` is safe here | ✅ `aitask_fold_mark.sh` already uses it (bash 4+ is already this script's floor) |
| `git commit --amend -o -- <paths>` is supported | ✅ probed: excludes other staged paths (they stay staged), retains what the commit already had |

### Finding 1 — reuse `task_git_commit_scoped`, don't re-derive it

t1599_1 built `_commit_scoped`; t1626 promoted it to
`lib/task_utils.sh:217-243` as `task_git_commit_scoped <msg> <path>...`
(`0` = committed, `2` = verified nothing to commit, `1` = failed). It already
carries **both** non-obvious parts the prior plan asked to hand-write:

- the empty-pathspec guard (`git commit --` with no pathspec commits the whole
  index — `-o` additionally makes that case fatal rather than silent);
- capturing `git status`'s exit separately, so a failing status with empty
  stdout reads as *unverified*, never as *clean*.

The archived sibling's own handoff note says so explicitly: *"Reuse
`_commit_scoped`'s shape, including the two non-obvious parts."* Calling it
beats reimplementing it.

### Finding 2 — the strict amend guard breaks the real callers

`aitask_create.sh` stages `aitasks/metadata/labels.txt` **unconditionally** at
every commit site (`:863`, `:900`, `:2060`, `:2236-2237`, `:2269`) — unlike
`aitask_update.sh:2267-2270`, which gates on `_stage_labels`. So the creation
commit that `--commit-mode amend` is designed to amend routinely contains
`labels.txt` (and, for a child, the new task's own parent file). Neither is in
`rollback_paths`.

A guard that refuses on *any* path outside `rollback_paths` therefore aborts the
fold step of `aitask-explore` / `aitask-pr-import` **whenever the created task
introduced a new label** — a correct, everyday outcome. A guard that fires on
the correct path is worse than no guard.

**Resolution (user decision, then tightened in review):** classify by *task
attribution* rather than raw set difference, and add a separate
published-history refusal — but **default-deny**, with `labels.txt` as the one
enumerated non-task exception. An earlier draft let *any* non-task path warn and
proceed; that would have waved through the `aitasks/metadata/gates.yaml` swallow
this plan's own evidence found in `21219b0b4`. The accept list is closed because
the producers are enumerable: `ait create --batch` stages exactly the task file,
`LABELS_FILE`, and (child only) the parent file.

### Finding 3 — `-o` on an amend behaves as needed (probed, not assumed)

`git commit --amend --no-edit -o -- a.txt` with `b.txt`/`c.txt` also staged:
those stay staged (`M b.txt`, `A c.txt`) and do **not** enter the commit. But
content the commit **already had** is retained. Scoping the amend cannot remove
pre-existing foreign content — only the guard can. Both are needed.

### Finding 4 — `rollback_paths` is never empty

`primary_file` is `die`d on at `:101`, so the array always holds ≥1 element.
The empty-array guards below are defence in depth, not the load-bearing case;
`task_git_commit_scoped`'s own guard supplies it for free on the `fresh` path.

### Finding 5 — the pre-fix code has *two* swallow mechanisms, not one

`task_git add aitasks/` sweeps **dirty files under `aitasks/`**. The separate,
pathspec-less `task_git commit` / `commit --amend` sweeps **anything already
staged, anywhere** — `aiplans/`, source files, paths `add aitasks/` never
touches. They fail on disjoint inputs, so a single dirty-bystander fixture
proves only the first. The verification below fixtures each mechanism
separately.

---

## Step 1 — `fresh`: delegate to the canonical seam (`:597-621`)

Replace the whole `fresh)` arm. `task_git add aitasks/`, the now-redundant
`fold_meta_relpaths` add (those paths are already appended to `rollback_paths`
at `:585-587`), and the index-wide `elif task_git diff --cached --quiet` no-op
branch all disappear into the helper:

```bash
    fresh)
        joined=""
        for fid in "${folded_ids[@]}"; do
            fid="${fid#t}"
            if [[ -n "$joined" ]]; then joined="${joined}, t${fid}"; else joined="t${fid}"; fi
        done
        crc=0
        task_git_commit_scoped \
            "ait: Fold tasks into t${primary_id}: merge ${joined}" \
            "${rollback_paths[@]}" || crc=$?
        case "$crc" in
            0) hash=$(task_git rev-parse --short HEAD 2>/dev/null || echo "")
               echo "COMMITTED:${hash}" ;;
            2) echo "NO_COMMIT" ;;
            *) _fold_rollback
               die "fold commit failed — rolled back the whole fold transaction" ;;
        esac
        ;;
```

Notes:
- The no-op detection moves from index-wide (`diff --cached --quiet`) to
  path-scoped (`status --porcelain -- <paths>` inside the helper) — which is
  what the prior plan asked for, obtained by reuse.
- `rollback_paths` may contain the same parent file twice (two folded children
  of one parent). Duplicate pathspecs are harmless to git; no dedup needed.
- **Partial-commit semantics inherited from t1599_1:** `-o -- <paths>` commits
  those paths' **worktree** content and ignores their index entry. Correct here
  — every fold mutation is written to disk by `aitask_update.sh` before Step 6.

## Step 2 — `amend`: guard first, then scope (`:622-634`)

The guard runs before any *staging* — but Step 6 is reached only after Steps
3–5b have already written every fold mutation to disk (`aitask_update.sh` calls
at `:338`, `:352`, `:359`, `:368`, plus the attachment rebinds). **A refusal
therefore leaves the whole fold dirty in the worktree unless it rolls back**, and
a dirty primary/folded set is exactly the thing a later unscoped commit sweeps
up — the defect this task exists to close, re-created by its own guard.

Both existing Step-6 failure paths already call `_fold_rollback` before `die`
(`:618`, `:630`); a bare `die` in the guard would be the only exit in the block
that does not. **The guard must not `die` itself.** It sets a refusal reason and
returns non-zero; the `amend)` arm runs `_fold_rollback` and only then `die`s —
one rollback site, and the file's existing contract preserved.

### 2a — `_fold_amend_guard`

**Default-deny.** Every path in `task_git show --name-only --format='' HEAD` is
classified against an ordered accept list; **anything not accepted is fatal**.
There is no "warn and proceed" bucket — a warn-only branch would let the
historically-observed `aitasks/metadata/gates.yaml` swallow (`21219b0b4`) ride
into a rewritten commit, which is the exact failure this guard exists to stop.

Accept, in order:

1. **The fold's own files** — `path ∈ rollback_paths`. Covers the primary, the
   folded and transitive task files, parents of folded children, and the
   `attachments/meta/*` rebinds (which are not `.md` paths and would otherwise
   fall through to the deny branch).
2. **A task/plan file this fold owns by id** — extract the path's task id
   (`aitasks/t<P>/t<P>_<C>_*.md` ⇒ `P_C`, where the *directory* disambiguates a
   child from a parent whose slug starts with a digit; `aitasks/t<N>_*.md` and
   the `aiplans/p…` mirrors ⇒ `N`) and accept when it is in the owned-id set:
   `primary_id`, **its parent when the primary is itself a child** (`P_C ⇒ P` —
   this is the child-creation co-change staged at `aitask_create.sh:861-862`,
   and it is a distinct rule from "parents of *folded* children", which arrives
   via `rollback_paths` in branch 1; **pinned by test 11**, the only test that
   reaches it), every `folded_ids` and `transitive_ids` entry, and the parent of
   any child id among them.
3. **The label vocabulary** — `path == "$(labels_file_path)"`. This is the *only*
   non-task path any amend-preceding step legitimately co-commits:
   `aitask_create.sh` stages it unconditionally at every commit site (`:863`,
   `:900`, `:2060`, `:2237`, `:2269`). Use the canonical accessor
   (`lib/task_utils.sh:631-638`), never a hardcoded string. Accepting it is what
   keeps `aitask-explore` / `aitask-pr-import` working (Finding 2); `note` it so
   the rider is visible in the output.

Anything else — a foreign task/plan file, an unknown metadata file
(`gates.yaml`, `stats_config.json`, …), a source file staged by a bystander —
is **refused**: set `_fold_amend_refusal` to a message naming the offending
paths and the short HEAD and pointing the caller at `--commit-mode fresh`, then
`return 1`.

Then, independently, a second refusal:

4. **Already published.** If an upstream tracking ref resolves and
   `task_git merge-base --is-ancestor HEAD "$ups"` succeeds, HEAD is on the
   remote ⇒ refuse the same way. **What this does not buy:** it reads the *local*
   remote-tracking ref and deliberately does not fetch (a fold has no business
   doing network I/O), so a push made elsewhere since the last fetch is missed.
   It can therefore fail to catch a published commit; it can never wrongly
   refuse an unpublished one. Say so in the comment.

Membership uses a `declare -A` set, not `grep -vxF -f <(…)`: it sidesteps the
empty-pattern-file trap the task file flagged, needs no process substitution,
and is exact-match by construction. `declare -A` is already used in this script.

**A known, correct refusal.** `aitask_create.sh:1912`
(`run_auto_merge_if_needed`) runs its own fold with `--commit-mode fresh`
*after* the create commit. When auto-merge fires, HEAD is that fold's commit,
carrying task files from a **different** fold set — so the skill's subsequent
`--commit-mode amend` will be refused. That is the right outcome: the caller's
"the previous step created the task commit" assumption is genuinely false there,
and the `die` message already points at `--commit-mode fresh`. Do **not**
allowlist it.

### 2b — the amend itself

```bash
    amend)
        # Refusal must undo the fold's on-disk mutations, not just skip the
        # commit: Steps 3-5b already wrote them, and leaving them dirty hands
        # the next unscoped commit exactly the bystander this task removes.
        if ! _fold_amend_guard; then
            _fold_rollback
            die "$_fold_amend_refusal"
        fi
        (( ${#rollback_paths[@]} )) || die "internal: empty fold path set"
        task_git add -- "${rollback_paths[@]}" >/dev/null 2>&1 || true
        if task_git commit --amend --no-edit -o --quiet -- "${rollback_paths[@]}" \
             >/dev/null 2>&1; then
            echo "AMENDED"
        else
            _fold_rollback
            die "fold amend-commit failed — rolled back the whole fold transaction"
        fi
        ;;
```

`add` is needed only so an untracked path can be named by a pathspec.

`_fold_rollback` (`:590-593`) is `reset -q --` then `checkout --` over
`rollback_paths`, so it restores both index and worktree to HEAD for every path
the fold touched — including the rebound `attachments/meta/*` entries, which are
modifications of tracked files (`:528`), not new ones.

### Why the amend scoping stays local

`task_git_commit_scoped` has no amend variant, and adding one means editing
`lib/task_utils.sh` — shared substrate, outside this child's declared ownership,
with t1599_3 and t1599_4 still in flight. `aitask_fold_mark.sh` is the only
`--amend` call site in the framework, so a local implementation has exactly one
consumer. Revisit only if a second amend caller appears.

## Adjacent findings — RECORD in Final Implementation Notes, do not fix

- `amend` has no no-op branch (unlike `fresh`), so an amend with nothing newly
  staged still rewrites the commit and prints `AMENDED`.
- `_fold_rollback` (`:590-593`) restores only `rollback_paths`, so a failed
  commit that had staged foreign files left them staged. Scoping makes this moot.
- `--commit-mode` is validated only at `:637-639` — **after** every mutation has
  already been written to disk.
- `aitask_create.sh` stages `labels.txt` unconditionally where
  `aitask_update.sh` gates on `_stage_labels`; both then commit the whole index.
  Latent instance of the parent defect → **t1599_4's** sweep, not this child's.

## Verification

Extend `tests/test_fold_mark.sh` (plain functions, `pushd`/`popd`, no `( … )`
subshells ⇒ no `assert_counters_*` opt-in needed). `setup_project` already
copies `lib/task_utils.sh`, so `task_git_commit_scoped` is present in-fixture.

**The pre-fix code has two independent swallow mechanisms, and each needs its
own fixture.** `task_git add aitasks/` sweeps *dirty* files **under
`aitasks/`**; the separate, pathspec-less `task_git commit` / `commit --amend`
sweeps **anything already staged, anywhere** — including paths `add aitasks/`
never touches. A dirty-bystander test alone proves only the first.

1. **`fresh`, dirty bystander not swept** — seed an unrelated **dirty** task
   file under `aitasks/`, fold t_a into t_b, assert
   `git show --name-only --pretty=format: HEAD` contains only the fold's own
   paths and the bystander is still ` M` unstaged. *(Mechanism: broad `add`.)*
2. **`fresh`, pre-staged foreign path not swept** — `git add` an unrelated
   `aiplans/p999_*.md` (deliberately **outside `aitasks/`**, so `add aitasks/`
   cannot be what carries it) **before** the fold; assert it is absent from HEAD
   and **still staged** (`A ` / `M `) afterwards. *(Mechanism: index-wide
   commit.)*
3. **`amend`, dirty bystander not swept** — HEAD carries only accepted paths;
   assert `AMENDED`, bystander absent from HEAD and still dirty.
4. **`amend`, pre-staged foreign path not swept** — as 2, in amend mode: absent
   from HEAD, still staged. Verified reachable: `commit --amend -o -- <paths>`
   leaves other staged entries staged (probed).
5. **`amend` refuses a foreign task file in HEAD** — assert **non-zero exit**,
   the error names the offending path, and the **full three-way no-residue
   check** below.
6. **`amend` refuses unknown metadata in HEAD** — HEAD carries
   `aitasks/metadata/gates.yaml` (the `21219b0b4` shape); assert non-zero exit
   and the same three-way check. This is the concern that killed the
   warn-and-proceed bucket, so it must be executable.
7. **`amend` permits `labels.txt` in HEAD** — HEAD = primary task file +
   `$(labels_file_path)`; assert the amend **succeeds** (`AMENDED`). The
   Finding 2 regression test — the reason the strict guard was rejected. Pairs
   with 5/6 as the *permit* direction of the classifier; **not** a negative
   control (it passes pre-fix and post-fix alike, since pre-fix has no guard).
8. **`amend` refuses a published HEAD** — `git push -u` the fixture's branch so
   HEAD is an ancestor of `@{u}`; assert non-zero exit and the same three-way
   check.

   **Three-way no-residue check (tests 5, 6, 8).** A refusal must undo the
   fold, not merely decline to commit it. For each:
   - `git rev-parse HEAD` **unchanged** (nothing rewritten);
   - **index clean** for the fold paths (nothing staged);
   - **worktree clean** for the fold paths — `git status --porcelain --
     <primary, folded, transitive, folded children's parents>` is empty, *and*
     the frontmatter is actually back: `read_frontmatter_field` shows the
     folded task's `status` still `Ready` (not `Folded`) and no `folded_into`,
     and the primary has no new `folded_tasks` entry.

   The frontmatter assertion is the load-bearing half. `git status` alone would
   also pass if the guard had refused *before* any mutation, so it does not
   discriminate a working `_fold_rollback` from a fold that never ran — and the
   mutations demonstrably do run first (`:338`-`:368` precede `:595`). Assert
   the restored *values*, not just the absence of a diff.
9. **Child fold still commits the parent file** — fold a child id `P_C`, assert
   the parent `tP_*.md` (the `children_to_implement` edit) **is** in the commit.
   A **positive regression test only**: the pre-fix broad staging also commits
   that file, so this passes before and after the fix by construction and can
   never serve as a negative control. It guards against the *fix* over-narrowing
   — the case a naive "only the primary task file" scoping would wrongly drop.
10. **`--commit-mode none`** — existing test, unchanged: `NO_COMMIT`, no new
    commit (`rev-list --count`).
11. **`amend` permits a child primary's own parent file in HEAD** — primary is a
    child `P_C`; HEAD is a child-creation-shaped commit carrying
    `aitasks/t<P>/t<P>_<C>_*.md` **plus** its parent `aitasks/t<P>_*.md` **plus**
    `labels.txt` (exactly what `aitask_create.sh:859-866` stages); fold an
    unrelated task into `P_C`; assert **`AMENDED`** and that the parent file is
    still present in HEAD afterwards.

    This is the only test that reaches accept-branch 2's `P_C ⇒ P` sub-rule.
    Test 9 is a child **fold** in `fresh` mode — a *different* rule (parents of
    *folded* children, carried by `rollback_paths`) — and test 7 only covers
    `labels.txt`. Without test 11, omitting or mistyping the parent-primary rule
    would refuse the ordinary child `ait create` → amend flow while every other
    test still passed: the guard would be wrong in exactly the over-refusing
    direction Finding 2 was raised about. Permit test, not a negative control.

### Post-phase (risk mitigations)

- **`amend_guard_both_directions_test`** — after the guard and its scoping land,
  pin **both** directions of the default-deny classifier as executable
  assertions, so neither can regress silently. **Permit** side: test 7
  (`$(labels_file_path)` — accept-branch 3) and test 11 (a child primary's own
  parent file — accept-branch 2's `P_C ⇒ P` sub-rule); these are the legitimate
  `ait create` co-changes the originally-specified strict guard would have
  wrongly refused. **Refuse** side: tests 5, 6 and 8 (foreign task file, unknown
  metadata, published HEAD — each with the three-way no-residue check). Every
  accept branch must have at least one permit test: a guard that refuses
  everything passes the entire refuse side, so the permit side is what makes the
  refuse side meaningful. All five must hold simultaneously — none may be
  dropped or weakened to make another pass.

**Negative controls (required, executable).** A helper rewrites the fixture's
copy of `aitask_fold_mark.sh`, replacing the fixed `case "$commit_mode"` block
with the pre-fix body, and **asserts the substitution actually landed** (grep
the reverted file for `task_git add aitasks/` *and* for the pathspec-less
`task_git commit -m`) before running anything — a passing control that silently
patched nothing proves nothing.

Against that build:

| control | must FAIL pre-fix because |
|---|---|
| 1, 3 | `add aitasks/` stages the dirty bystander into the commit |
| 2, 4 | the pathspec-less commit takes the pre-staged `aiplans/` path |
| 5, 6, 8 | there is no guard — the bare amend rewrites HEAD |

Tests **7, 9, 10 and 11 are not negative controls** and must pass on both
builds: 7, 9 and 11 assert outcomes the fix must *preserve* (the pre-fix build
has no guard, so it permits them trivially), and 10 is unchanged behavior.
Listing an always-passing test as an expected-failure would make the control
suite unsatisfiable — do not.

**The permit tests are load-bearing, not decoration.** 7 and 11 are the only
executable evidence for accept-branches 3 and 2 respectively. Every refusal test
(5, 6, 8) is satisfied by a guard that refuses *everything*; only 7, 9 and 11
can catch that. Both directions must be green simultaneously.

Also: `shellcheck .aitask-scripts/aitask_fold_mark.sh`, and re-run the existing
three cases plus the sibling suites that source the same scaffold.

## Risk

### Code-health risk: low
- Single-file change confined to one `case` statement, replacing hand-rolled git
  plumbing with an existing shared helper — net less code, one fewer local
  reimplementation of a shared contract · severity: low · → mitigation: none needed
- The new `_fold_amend_guard` adds ~40 lines of path classification that only
  this script uses; if a second amend caller ever appears it will want promoting
  to `lib/` · severity: low · → mitigation: recorded in Final Implementation Notes
- A new early exit in a block whose every other exit rolls back is easy to get
  wrong — a `die`ing guard would leave the fold's mutations dirty and feed the
  next unscoped commit exactly the bystander this task removes · severity:
  medium · → mitigation: the guard returns instead of dying (Step 2b), and the
  three-way no-residue check on tests 5/6/8 asserts the *restored frontmatter
  values*, not merely a clean `git status`

### Goal-achievement risk: medium
- The amend guard must refuse the dangerous case **without** refusing the
  everyday one. Finding 2 shows the originally specified guard got this wrong in
  one direction (over-refusing); a warn-and-proceed bucket got it wrong in the
  other (under-refusing on `gates.yaml`). The default-deny classifier is only as
  good as its three accept branches, and a path shape this plan did not
  anticipate would be **refused**, not swallowed — a loud, recoverable failure
  (`--commit-mode fresh`) rather than a silent one · severity: medium ·
  → mitigation: inline post-phase `amend_guard_both_directions_test`
- The published-history check reads a possibly-stale local tracking ref and so
  under-detects · severity: low · → mitigation: stated as an accepted residual
  in the code comment and in Final Implementation Notes; never over-refuses

### Planned mitigations
- timing: post-phase | name: amend_guard_both_directions_test | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the amend guard's classifier must refuse the dangerous case without refusing the everyday one | desc: pin both directions of the default-deny amend guard as executable assertions — one permit test per accept branch (test 7 labels.txt, test 11 child primary's parent file) against the refusals (tests 5/6/8) with HEAD, index and worktree unchanged
