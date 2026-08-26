---
Task: t1627_setup_impossible_worktree_add_remedy.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1627 — Setup's impossible `git worktree add` remedy

## Context

`ait setup` → `setup_data_branch()` (`.aitask-scripts/aitask_setup.sh:1519-1523`)
creates the `.aitask-data/` worktree. On failure it prints:

```
Failed to create worktree. You may need to run: git worktree add .aitask-data aitask-data
```

That advises running the exact command that just failed, and `2>/dev/null`
throws away git's own explanation — so the user is left with no information
about *why*. t1624 fixed the identical text in `aitask_init_data.sh`; this is
the sibling instance it deliberately left out of scope.

Two findings from exploring the site changed the shape of the fix:

1. **The task file's premise about `return` is wrong, in the safe direction.**
   It says setup "continues past it into Step 3 (populate data) with no
   `.aitask-data` present". It does not: `return` exits `setup_data_branch()`
   entirely, so Steps 3–9 (populate, symlinks, gitignore, both commits) are all
   skipped in one jump. Nothing is ever written into a `.aitask-data/` that is
   not a worktree. What continues is `main()`'s remaining ~20 setup steps, which
   write into a plain on-main `aitasks/` — the legacy layout.
   `commit_framework_data_files()` (`:3352-3357`) already early-returns in that
   state. So `return` is correct; only the *message* is wrong, because it never
   says the run is continuing in legacy mode.

2. **A second, unguarded defect at the same site.** `project_dir` is
   `"$SCRIPT_DIR/.."` — the checkout `ait` was invoked from, not a caller-chosen
   directory. Task worktrees carry `.aitask-scripts/` (tracked on main, t1616),
   so `./ait setup` inside an *unlinked* `aiwork/<task>` resolves `project_dir`
   to that worktree and reaches Step 1, which **creates and pushes** the
   `aitask-data` orphan branch. Step 2 then either fails (primary holds the
   branch) or — when the primary was never initialized — **succeeds**, putting
   the repo's only task data inside a throwaway worktree. That is exactly
   t1624's `NOT_INITIALIZED` hazard, unguarded here.
   (A *linked* worktree is unaffected: `--link-worktree` gives it a
   `.aitask-data` symlink, so the "already configured" check at `:1442` fires
   first.)

Outcome: an honest, actionable failure message; a documented `return`; a
pre-Step-1 refusal for linked worktrees; and one shared definition of "is this a
linked worktree" instead of two — which, in being written once, also fixes a
latent false positive in t1624's own copy (see §1: it misreads a **git
submodule's primary checkout** as a linked worktree) and a matching one in
`--link-worktree`, whose primary-root resolution makes the offered remedy a
silent no-op on submodule-hosted repos (§2).

## Changes

### 1. `.aitask-scripts/lib/data_symlinks.sh` — extract the classifier

Add `ait_linked_worktree_roots <dir>` beside the existing `ait_canon_path`
(which it uses). Both call sites already source this lib.

**Three-state return — "cannot classify" is its own answer, never a negative:**

| code | meaning | caller must |
|---|---|---|
| 0 | `<dir>` is inside a **linked** worktree; `AIT_WT_TOPLEVEL` / `AIT_WT_MAIN_ROOT` set | act on the remedy |
| 1 | definitively **not** linked — primary checkout (a submodule's included), a plain subdirectory of one, or not a repository at all | proceed normally |
| 2 | **indeterminate** — inside a repository, but the topology could not be resolved | refuse conservatively |

Globals, not stdout: a two-line stdout payload would break on a path containing
a newline, and `ait_link_worktree_data` already sets `AIT_LINK_WORKTREE_CHANGED`
this way.

**Predicate: `git-dir != git-common-dir`, not `dirname(git-common-dir)`.**
t1624's Check 3b derives the primary root as `dirname(--git-common-dir)`. That
is wrong for a **git submodule**: a submodule's primary checkout has its common
dir at `<super>/.git/modules/<name>`, whose `dirname` is `<super>/.git/modules`
— never equal to its toplevel `<super>/<name>`, so the submodule's own primary
checkout is classified as a linked worktree. Under the new early return (§3a)
that would silently disable data-branch setup for every submodule-hosted
project. Verified live in this repo:

| checkout | `--git-dir` | `--git-common-dir` | verdict |
|---|---|---|---|
| primary | `/…/aitasks/.git` | `/…/aitasks/.git` | equal → not linked |
| linked (`.aitask-data`) | `/…/.git/worktrees/-aitask-data` | `/…/aitasks/.git` | differ → linked |
| submodule primary | `<super>/.git/modules/<n>` | `<super>/.git/modules/<n>` | equal → not linked |
| `--separate-git-dir` | `<X>` | `<X>` | equal → not linked |

**Primary-root resolution is its own helper**, because three call sites need it
and `dirname` is wrong at all three. Add `ait_main_worktree_root <dir>` (sets
`AIT_WT_MAIN_ROOT`; 0 ok, 1 not a repository, 2 unresolvable).

> **Deviation from the approved plan, found during implementation.** The plan
> said the first entry of `git worktree list --porcelain` is authoritative for
> submodules. It is not, on two counts measured against real fixtures:
>
> 1. git reports a submodule's main worktree as `<super>/.git/modules/<name>` —
>    it derives that entry the same broken way `dirname(git-common-dir)` does;
> 2. it emits paths **raw and unquoted**, so splitting the listing truncates any
>    path containing a newline (its `-z` form needs git 2.36 *and* cannot
>    survive `$(...)`, which strips NUL).
>
> The shipped resolution is therefore **parse-free** and goes through the
> git-common-dir: `rev-parse --show-toplevel` run *from* it (which `core.worktree`
> answers for a submodule), else `dirname` (git's own definition for an ordinary
> repo), then a validation that the winner is a working tree that is its own
> toplevel. It must be `-C <common>`, never `--git-dir=<common>` — the latter
> treats the *caller's* cwd as the work tree and returns the caller's own repo
> root. `--show-superproject-working-tree` is unusable: empty from a linked
> worktree *of* a submodule, exactly the case that needs it.
>
> **Accepted layout boundary:** `git init --separate-git-dir` answers state 2.
> Its linkage is one-way (no `core.worktree` in the gitdir), so nothing — git
> included — can name the checkout from it. Refusing beats the `dirname` form's
> silent wrong answer (the gitdir's unrelated parent). Pinned by Test 21.
>
> Verified across eleven topologies: primary, primary subdir, linked worktree,
> superproject, submodule primary, linked worktree of a submodule,
> `--separate-git-dir`, newline-named main worktree, worktree of a
> newline-named main, newline-named linked worktree, and non-repo.

It keeps the property the existing
`--link-worktree` comment relies on ("derive the main root FROM the supplied
dir, so the same-repo check is free and no ambient cwd can pick a different
repository"). `ait_linked_worktree_roots` is then just the predicate above plus
this helper.

**No new git floor.** Deliberately avoid `--path-format=absolute` (git 2.31+),
which t1624 uses: relying on it would make every pre-2.31 invocation
*indeterminate*, and with §3a refusing on indeterminate that becomes a hard
regression on old git. `--git-dir` / `--git-common-dir` (2.5+) are canonicalized
against `<dir>` through `ait_canon_path` instead, so state 2 stays genuinely
exceptional (a path that will not canonicalize, or `worktree list` failing).

### 2. `.aitask-scripts/aitask_init_data.sh` — rewire Check 3b

Replace the four inline `rev-parse`/`ait_canon_path` lines (`:194-215`) with a
call to the new helper. Ordering (after Check 3, so `NO_DATA_BRANCH` still
wins), the `WORKTREE_UNLINKED` / `NOT_INITIALIZED` tokens, their exit code 3 and
both message texts are unchanged. Two deliberate behaviour changes:

- **A submodule's primary checkout stops being refused.** This is the latent
  t1624 false positive above, fixed at its source rather than worked around.
- **`--link-worktree` gets the same primary root.** Its own `main_root`
  (`:100`) is `dirname(git-common-dir)` too, so on a linked worktree **of a
  submodule** it resolves to `<super>/.git/modules` — a directory that exists,
  so `ait_canon_path` succeeds and nothing errors. At that bogus root the
  `.aitask-data/.git` probe fails and it prints **`NOT_INITIALIZED`, exit 0**:
  the remedy `setup_data_branch` and Check 3b both *print* would silently do
  nothing. The `target_canon != main_root` (`:116`) and `.aitask-data`-nesting
  (`:121-123`) refusals are evaluated against that same bogus root and so can
  never fire for a submodule either. Replace `:97-101` with
  `ait_main_worktree_root "$target_dir"`, mapping its 1 / 2 onto the two
  existing `die` messages verbatim. Everything downstream is unchanged — it
  simply now runs against the real root.
- **State 2 refuses instead of falling through.** t1624 documents unresolvable
  metadata as falling through to Step 4 "as before" — but Step 4 is exactly the
  route that, with an uninitialized primary, *succeeds wrongly* and puts the
  repo's only task data in a throwaway worktree. So add a third token,
  `WORKTREE_INDETERMINATE` (exit 3), and document it in the script header and
  `--help` beside the other two. Safe for consumers: the pickweb/pickrem skills
  that call this bare parse only `INITIALIZED` / `ALREADY_INIT` / `LEGACY_MODE`
  / `NO_DATA_BRANCH` and otherwise say *"if the command fails (non-zero exit),
  display the error and abort"* — which is already how t1624's two exit-3 tokens
  reach them.

### 3. `.aitask-scripts/aitask_setup.sh` — `setup_data_branch()`

**(a) New pre-check**, inserted *after* the "already configured" early return
(`:1441-1445`) and *before* the migration detection — so it cannot intercept a
configured worktree, and lands before Step 1 creates/pushes a branch. Placement
matters: an early return here intercepts every downstream case.

All three helper states are handled — `warn` + `return` (non-fatal, matching the
function's existing opt-out contract at `:1484-1487`; `die` would abort
venv/shim/agent setup over an optional feature):

- **0 (linked worktree)** — refuse, naming the worktree, the primary, and the
  remedy. Two sub-cases, mirroring t1624's wording:
  - primary **has** `.aitask-data` → `"$SCRIPT_DIR/aitask_init_data.sh" --link-worktree "<wt>"`
  - primary **has not** → run `ait setup` at the primary first, then `--link-worktree`
- **2 (indeterminate)** — refuse too, with a distinct message saying the
  checkout's git topology could not be resolved and that setup is *not* touching
  the data branch rather than guessing. Falling through here would leave the
  unsafe Step 1 + Step 2 route reachable in exactly the situation where we
  cannot tell whether it is safe, which is the defect this task exists to close.
- **1 (not linked)** — proceed unchanged.

**(b) Step 2 message.** Capture stderr instead of discarding it, keeping the
existing `(cd … && …)` subshell shape:

```bash
local wt_add_err=""
if ! wt_add_err="$(cd "$project_dir" && git worktree add .aitask-data aitask-data 2>&1 >/dev/null)"; then
    warn "Failed to create the .aitask-data worktree in '$project_dir'. git said: ${wt_add_err:-<no output>}"
    warn "Continuing without a separate task data branch: task and plan files stay on the current branch (legacy layout). Re-run 'ait setup' once the problem above is fixed."
    ...
    return
fi
```

Plus a code comment recording finding 1 (why `return`, not `die`), and — when
`branch_exists` is still `false`, which after the creation block means "we just
created it" — one `info` line saying the `aitask-data` branch is left in place
for the retry. No linked-worktree hint here: the pre-check owns that cause, and
Step 2 can still fail for others (a leftover `.aitask-data/` directory, an
invalid ref after a failed fetch, permissions).

**(c) Neighbouring `warn` paths with discarded stderr** — same treatment,
`warn "… : <git's error>"`, behaviour otherwise unchanged:

- `:1515` `git push -u origin aitask-data` → "Could not push aitask-data branch to remote"
- `:1612` `git push` (data branch, Step 4) → "Could not push data branch to remote"

**Deliberately not touched:** `:1496` `git fetch … 2>/dev/null || true`. It is a
probe, not a `warn`/`return` path, and I have no way to make it fail
deterministically in a fixture — an untested behaviour change. Its failure mode
(`branch_exists=true` on a failed fetch → Step 2 dies on `invalid reference`) is
already served by (b) surfacing git's real error.

### 4. Tests

`tests/test_data_branch_setup.sh` (sources the real script; each test rebinds
`SCRIPT_DIR` to its fixture). Counters are in-process — assertions stay outside
subshells, per the file's existing rule.

- **Step-2 failure message.** Fixture: local repo with a leftover non-empty
  `.aitask-data/` directory (no `.git`, so "already configured" does not fire) —
  production-reachable via a pruned worktree or a botched migration. Assert the
  output contains git's own words (`already exists`), does **not** contain
  `You may need to run: git worktree add` (negative control on the impossible
  remedy), carries the legacy-mode consequence sentence, and that `rc` is 0.
  Assert `.aitask-data/.git` absent and `aitasks`/`aiplans` **not** symlinked —
  pinning that `return` really skipped Steps 3–9.
- **Linked worktree, primary already initialized.** Fixture: run
  `setup_data_branch` normally at a primary, then `git worktree add aiwork/t1`,
  rebind `SCRIPT_DIR` there, run again. Assert the refusal names the worktree
  and prints the `--link-worktree` command, and that no second `aitask-data`
  worktree was created.
- **Linked worktree, primary NOT initialized** — the case the guard exists for,
  and the one a placement or classification regression would silently break.
  Fixture: repo **with a remote**, `aitask-data` branch absent everywhere, no
  `.aitask-data` at the primary; `git worktree add aiwork/t1`; rebind
  `SCRIPT_DIR` there; run. Assert *no side effects at all* — `git show-ref
  refs/heads/aitask-data` fails, `git ls-remote --heads origin aitask-data` is
  empty (Step 1 never created **or pushed** the branch), and neither the
  worktree nor the primary has a `.aitask-data` (Step 2 never placed the only
  data checkout in a throwaway worktree) — plus the "run `ait setup` at the
  primary first" remedy and `rc` 0.
- **Submodule primary is not a linked worktree.** Fixture: superproject +
  `git submodule add` of a second repo (or an equivalent `.git`-file checkout
  whose gitdir is `<super>/.git/modules/<n>`). Assert
  `ait_linked_worktree_roots` returns **1** there, and that
  `setup_data_branch` run inside it configures fully (branch, worktree,
  symlinks) instead of refusing. This is the discriminating case for the
  `git-dir != git-common-dir` predicate — `dirname(git-common-dir)` fails it.
- **Positive control (guard placement).** On the primary fixture, assert
  `ait_linked_worktree_roots` returns 1 for the primary root *and* for a plain
  subdirectory of it, and that Test 1's full configuration still happens — a
  misclassified primary would silently skip data-branch setup for everyone.
- **Push warns.** Fixture: `origin` pointed at a nonexistent path. Assert both
  warns contain the remote path git echoes back (portable across git versions),
  and that Step 2 still succeeds afterwards.

`tests/test_init_data.sh` — its existing `WORKTREE_UNLINKED` / `NOT_INITIALIZED`
/ `--link-worktree` coverage (t1616/t1624) is the regression guard for the
extraction and must pass unchanged. Add three cases for the behaviour §2
deliberately changes:

- a submodule primary checkout now proceeds instead of being refused;
- an indeterminate classification emits `WORKTREE_INDETERMINATE` at exit 3;
- **the offered remedy actually completes on a linked submodule worktree** —
  superproject + submodule, the submodule's own `.aitask-data` configured, then
  `git worktree add` inside the submodule. Run the exact command Check 3b
  prints. Assert it emits `LINKED` (today: `NOT_INITIALIZED`, exit 0) and that
  the three symlinks really exist in the worktree afterwards. Without the last
  assertion the test passes on a token alone.

### Post-phase (risk mitigations)

- **`guard_placement_positive_control`** — after §1–4 land, pin that the new
  early return did not intercept the primary checkout: assert
  `ait_linked_worktree_roots` returns 1 for the primary's own root **and** for a
  plain subdirectory of it, and re-confirm Test 1's full primary configuration
  (branch, worktree, symlinks, gitignore) still passes end to end. Without both
  halves the guard could silently disable data-branch setup for every user.
- **`submodule_classification_fixture`** — build a real superproject +
  `git submodule add` fixture and pin that the submodule's own primary checkout
  returns 1 from the classifier and configures fully, in **both**
  `tests/test_data_branch_setup.sh` and `tests/test_init_data.sh`. This is the
  case that separates the new predicate from t1624's; without it the predicate
  change rests on reasoning alone.
- **`linked_submodule_remedy_e2e`** — on a linked worktree *of* a submodule
  (submodule's own `.aitask-data` configured first), run the exact
  `--link-worktree` command Check 3b prints and assert it emits `LINKED` and
  that the three symlinks exist afterwards. Closes the loop the reviewer named:
  a correct refusal is worthless if the remedy it offers silently no-ops.

## Verification

```bash
shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/aitask_init_data.sh \
           .aitask-scripts/lib/data_symlinks.sh
bash tests/test_data_branch_setup.sh      # new + existing
bash tests/test_init_data.sh              # extraction regression guard
bash tests/test_task_git.sh               # other data_symlinks consumers
bash tests/test_task_worktree_helper.sh
```

Manual end-to-end for the pre-check (the one path no fixture fully reproduces —
a real `ait` dispatch rather than a sourced function):

```bash
cd aiwork/<some_task_worktree> && ./ait setup   # expect the refusal + --link-worktree line
```

## Risk

### Code-health risk: medium
- New early return in `setup_data_branch()` intercepts every downstream case; a
  primary checkout misclassified as linked would silently skip data-branch setup
  for all users · severity: medium · → mitigation: inline post-phase
  guard_placement_positive_control
- The extraction does not preserve t1624's Check 3b semantics — it deliberately
  changes the predicate (`git-dir != git-common-dir` instead of
  `dirname(git-common-dir)`) and makes the indeterminate state refuse. Both are
  fixes, but they are behaviour changes to code that landed hours ago, in a path
  every `ait init-data` traverses · severity: medium · → mitigation: inline
  post-phase submodule_classification_fixture, plus `tests/test_init_data.sh`'s
  existing `WORKTREE_UNLINKED` / `NOT_INITIALIZED` cases passing unchanged
- Fixing `--link-worktree`'s `main_root` makes three previously-unreachable
  guards (`not a worktree root`, `is the main checkout`, `is the .aitask-data
  worktree`) reachable for submodule-hosted repos for the first time, and moves
  the `LEGACY_MODE` / `NOT_INITIALIZED` probes onto a different directory ·
  severity: medium · → mitigation: inline post-phase linked_submodule_remedy_e2e
- Refusing on the indeterminate state converts a previously-silent fall-through
  into a user-visible stop; if state 2 turns out to be reachable in an ordinary
  layout, `ait setup` and `ait init-data` both stop for it · severity: low · →
  mitigation: none by design — the predicate deliberately avoids
  `--path-format=absolute` so no supported git version can produce state 2, and
  the refusal message names what could not be resolved rather than guessing
- Two new user-facing message strings could drift from t1624's wording ·
  severity: low · → mitigation: none — wording is asserted by substring in the
  new tests

### Goal-achievement risk: low
- The task file's premise about `return` reaching Step 3 is factually wrong; the
  plan documents the correction instead of acting on it. If that reading is
  rejected, the `return`-vs-`die` decision changes · severity: low · →
  mitigation: stated explicitly in Context finding 1 for review at approval
- Scope was widened beyond the task's "Suggested fix" to cover the unguarded
  wrong-success case · severity: low · → mitigation: confirmed with the user
  before planning

### Planned mitigations
- timing: post-phase | name: guard_placement_positive_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — new early return may intercept the primary checkout | desc: assert ait_linked_worktree_roots returns 1 for the primary root and a plain subdirectory of it, and re-confirm Test 1's full primary configuration still passes
- timing: post-phase | name: linked_submodule_remedy_e2e | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — --link-worktree main_root fix makes three guards reachable and moves the LEGACY_MODE/NOT_INITIALIZED probes | desc: run the exact remedy command Check 3b prints on a linked worktree of a submodule and assert LINKED plus the three symlinks actually exist
- timing: post-phase | name: submodule_classification_fixture | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — extraction changes t1624's Check 3b predicate and indeterminate handling | desc: real superproject+submodule fixture pinning that a submodule primary checkout classifies as not-linked and configures fully, in both test_data_branch_setup.sh and test_init_data.sh

## Final Implementation Notes

- **Actual work done:** All four plan sections landed. `lib/data_symlinks.sh`
  gained `ait_main_worktree_root` and the three-state `ait_linked_worktree_roots`;
  `aitask_init_data.sh` routes both Check 3b and `--link-worktree` through them
  and documents a new `WORKTREE_INDETERMINATE` token; `aitask_setup.sh` gained
  the pre-Step-1 refusal, reports git's stderr at Step 2 with the legacy-mode
  consequence, and carries git's error in both push warns. Tests: 89 → 136 in
  `test_data_branch_setup.sh`, 118 → 140 in `test_init_data.sh`.

- **Deviations from plan:** One, in §1's primary-root resolution — see the
  boxed note in §1. The plan's `git worktree list --porcelain` first-entry
  approach was wrong twice over (it reports a submodule's main worktree as the
  *gitdir*, and it emits paths raw and unquoted so any line split truncates a
  newline-containing path). Shipped a parse-free resolution through the
  git-common-dir instead, with `--separate-git-dir` as a documented,
  test-pinned refusal. Nothing else deviated.

- **Issues encountered:**
  - `git worktree list --porcelain` is not authoritative for submodules — git
    derives that entry the same broken way `dirname(git-common-dir)` does.
    Found by building a real superproject+submodule fixture rather than trusting
    the API's description.
  - `--git-dir=<common> rev-parse --show-toplevel` is actively dangerous as a
    resolver: with no `--work-tree` git treats the *caller's* cwd as the work
    tree and returns the caller's own repository root. Only `-C <common>` is
    safe. Caught because the probe returned this repo's path for an unrelated
    fixture.
  - `--porcelain -z` would be newline-safe but needs git 2.36 *and* cannot
    survive `$(...)`, which strips NUL — so it was not a usable escape hatch.
  - A first draft piped `worktree list` into `head -n1`; under the `set -o
    pipefail` every sourcing script sets, `head` closing the pipe early can
    SIGPIPE git and turn a good answer into a failure. Removed the pipe.

- **Key decisions:**
  - **`return`, not `die`, at the Step 2 failure** — recorded as a code comment.
    The task file's premise that control continues into Step 3 is wrong: the
    `return` exits the function, skipping Steps 3–9 in one jump, so nothing is
    populated into a non-worktree `.aitask-data/`. The step is optional
    (answering `n` reaches the identical state) and dying would abort ~20
    unrelated setup steps.
  - **The predicate is `git-dir != git-common-dir`**, not a comparison of roots.
    They are equal exactly when a checkout owns its repository — ordinary
    primary, submodule primary, `--separate-git-dir` — and differ only for a
    linked worktree.
  - **`--path-format=absolute` (git 2.31+) deliberately avoided.** With callers
    refusing on the indeterminate state, depending on it would have turned every
    older git into a hard refusal.
  - **Indeterminate refuses at both call sites.** The fall-through it replaces
    reached the exact route that succeeds *wrongly* against an uninitialized
    primary.
  - **No linked-worktree hint at the Step 2 failure** — the pre-check owns that
    cause, and Step 2 can still fail for unrelated reasons.
  - Every new assertion was negative-controlled against unfixed source, and the
    two load-bearing ones were mutation-tested in isolation (predicate swapped
    back → only Test 17 fails; line parser restored → only Test 20 fails).

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:1496 — `git fetch origin aitask-data
    2>/dev/null || true` sets `branch_exists=true` unconditionally afterwards,
    so a failed fetch is recorded as "branch found" and Step 2 then dies on an
    invalid reference. Left out of scope deliberately: it is a probe rather than
    a warn/return path, and there is no deterministic way to make only the fetch
    fail in a fixture. Its symptom is now at least legible, since Step 2 reports
    git's real error.
  - `.aitask-scripts/aitask_setup.sh:1524-1526 — `cp -a … 2>/dev/null || true`
    in the migration branch of Step 3 silently swallows a failed copy of the
    user's existing `aitasks/`/`aiplans/` data, then proceeds to Step 5, which
    `git rm -r`s the originals from main. A partial copy is therefore
    indistinguishable from a complete one at the point the source is deleted.
