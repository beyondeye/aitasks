---
Task: t1675_with_attach_lock_disables_errexit_in_callback.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1675 — `with_attach_lock` disables errexit in its callback

## Context

`with_attach_lock` (`.aitask-scripts/lib/attachment_lock.sh:37-46`) runs its
transaction body as `"$@" || rc=$?`. Bash disables errexit for the *entire*
invocation whose status is tested, so every attach/artifact transaction runs with
errexit **off**: a failing command does not abort the callback, and a later
successful command overwrites its status, so the wrapper returns **0**.

t1668 fixed this at its own three `aitask_fold_mark.sh` call sites. The shared
seam still has no contract, no documentation of the property in its own header,
and no test — and `aitask_attach.sh` / `aitask_artifact.sh` were never audited.

### Verified, production-reachable, committed-partial-state

Two faults injected through the documented `AIT_PYTHON` seam against a real
legacy-mode fixture:

| injected failure | observed today |
|---|---|
| `frontmatter_patch.py append` in `_attach_add_txn` | `ait attach add` **exits 0**, prints `Attached 'f1.bin' … to t5`, **commits** blob + ledger — and the task frontmatter has **no** `attachments:` entry. A ref nothing points to: `ait attach ls` shows nothing and gc never reclaims the blob (refs non-empty). |
| `attachment_meta.py decref` in `_attach_rm_txn` | `ait attach rm` **exits 0**, prints `Removed attachment 'f1.bin' from t5`, **commits** — and the ledger still holds ref `"5"`. Same permanent silent leak, opposite direction. |

(`attach_meta incref` failing in `add` happens to be caught downstream — the
missing meta file makes the path-scoped `git add` fail. That is an accident of
staging, not a guard, and it reports a misleading `commit failed` cause.)

### Why the fix cannot be "seam-only"

The task proposes restructuring `with_attach_lock` so the callback runs under
errexit. **That is not achievable** — measured, not assumed:

- `( set -e; "$@" )` in a subshell — still suppressed.
- `set +e; set -e` toggle inside that subshell — still suppressed.
- `set -E` + an `ERR` trap — the ERR trap is suppressed by the same rule.
- Even if the wrapper stopped testing the status, `aitask_fold_mark.sh:825`
  (`with_attach_lock _fold_attach_txn || _fold_attach_rc=$?`) re-suppresses
  errexit through the **whole** callback chain. Its comment explains why it must
  test the status, so this is not removable.

Only a background subshell (`( set -e; "$@" ) & wait $!`) restores errexit, and
that forks away the parent state `_fold_attach_txn` depends on (`_fold_snap_add`
accumulation, EXIT-trap chaining) — it would break the rollback contract t1668
just established.

So the durable fix is the contract made **mechanical**: state it at the seam,
enforce it with a static guard, and clean the tree.

## Scope boundary — what belongs to t1698

Auditing this seam turned up three **pre-existing** data-integrity defects that
are independent of the errexit bug and share a different root cause (the
transaction boundary is not isolated from the worktree). At the user's direction
they are **out of scope here** and owned by **t1698**
(`t1698_attach_artifact_transaction_boundary_not_isolated_from_workt.md`,
`depends: [1675]`), which carries the empirical findings and their tests:

1. A **successful** commit absorbs an unrelated in-flight edit (`git add` stages
   the whole path).
2. The existing commit-failure rollback **destroys** an unrelated in-flight edit
   (`task_git checkout --` restores from HEAD).
3. A post-mutation abort leaves uncommitted ledger drift.

**Consequence for this task, and it is deliberate:** the `|| die` guards added in
§2 introduce new abort points, and t1675 **does not** add rollback calls at them.
Adding a HEAD restore there would multiply defect 2's trigger points from one to
a dozen — the exact hazard t1698 exists to fix properly. So t1675 stops the false
*success* (its own bug); the residual on-disk drift after an abort is t1698's.

This task therefore introduces **no** `txn_snapshot.sh`, **no** refactor of
fold's snapshot machinery, and **no** dirty-worktree preflight.

## Approach

### 1. Document the contract at the seam

`.aitask-scripts/lib/attachment_lock.sh` — add a `CALLBACK CONTRACT` block to the
header covering: errexit is OFF inside the callback; the four mechanisms above
that do **not** restore it (so the next reader does not retry them); the rule —
every status-returning mutating call carries an explicit `|| die`; and the guard
test that enforces it.

Record why the **success-sentinel** candidate is rejected: a callback that
continues past a swallowed failure still reaches its own success declaration, so
a sentinel catches nothing the return status does not already report — ceremony
without a caught class.

Add a forward pointer to **t1698** for the abort-path state question, so the next
reader knows the drift is tracked rather than unnoticed.

Also: one line in each of `lib/attachment_meta.sh` and `lib/artifact_manifest.sh`
noting those fronts return the Python helper's status and do **not** die (that is
where a new callback author looks); and extend the existing comment at
`aitask_fold_mark.sh:816-824` to record the caller-re-suppression finding.

### 2. Fix the audited call sites

Audit result — the dangerous set is exactly the helpers that **return** non-zero.
(`artifact_store`, `artifact_resolve`, `artifact_sha256`, `artifact_shard_path`,
`artifact_registry_activate`, `require_python`, `parse_duration_to_seconds`,
`artifact_manifest_relpath` all `die` internally, so `exit` beats the
suppression — those are already safe and are left alone.)

Pattern: append `|| die "<verb>: <what failed>"`. Three shapes need hoisting
first, because their status is structurally invisible:

- `x="$(mutator …)"` inside `[[ … ]]` — substitution status discarded
  (`aitask_artifact.sh:256`).
- `done < <(mutator …)` — process-substitution status unobservable
  (`aitask_attach.sh:605`, `aitask_artifact.sh:410`, `:484`).
- `mutator … | grep -q …` as an `if` condition — a failure reads as "no match"
  and silently takes the wrong branch (`aitask_attach.sh:468`).

| file | callback | sites |
|---|---|---|
| `aitask_attach.sh` | `_attach_add_txn` | `artifact_backend_put`, `attach_meta incref`, `frontmatter_patch.py append` |
| | `_attach_rm_txn` | `attach_meta decref`, `frontmatter_patch.py remove` |
| | `_attach_decref_deleted_txn` | `attach_meta refs` (hoist), `incref`, 2× `decref` |
| | `_attach_gc_txn` | `attach_meta refs`, `orphaned-at`, `zero-refcount` (hoist), `artifact_backend_delete` |
| `aitask_artifact.sh` | `_artifact_create_txn` | `artifact_manifest get` (hoist), `create`, both `frontmatter_patch.py append` branches |
| | `_artifact_update_txn` | `artifact_manifest current`, `_artifact_manifest_backend`, `set-current` |
| | `_artifact_move_txn` | `artifact_manifest versions` (hoist), `set-backend` |
| | `_artifact_rm_txn` | `artifact_manifest get`, `versions` (hoist), `_artifact_manifest_backend`, `frontmatter_patch.py remove`, `_artifact_handle_referenced_elsewhere`, `artifact_backend_delete` |

`gc`'s reads are the sharpest, and the two differ:
`attach_meta refs` failing yields `""` → read as zero refs, but a **second gate**
(the blocking-set scan) still saves a blob any task lists.
`attach_meta orphaned-at` failing has **no** second gate: `""` is read as "age =
infinite" → eligible → the blob is **deleted inside its grace window**. Both
become fail-closed; the second is the destructive one.

Existing rollback calls stay exactly where they are — inside the commit-failure
branches. Do not add new ones (see the scope boundary above).

### 3. `tests/test_attach_lock_callback_contract.sh` (new)

Follows `tests/test_attach_local_backend.sh` (fixture) and
`tests/test_no_raw_tmux.sh` (static guard + negative controls).

**Part A — behavioral pins.** Legacy-mode git fixture; faults injected through the
documented `AIT_PYTHON` override with a passthrough shim that fails only a named
script + subcommand, with an occurrence index ("fail the Nth call") so a fault
can be placed after earlier mutations in a loop. Every pin asserts the same three
things: **non-zero exit**, **no success message on stdout**, and **zero commits
added** — i.e. no partial state is *published*. Post-abort on-disk state is
deliberately **not** asserted here; that is t1698's invariant.

| pin | injected fault | shape exercised | additionally asserts |
|---|---|---|---|
| `attach add` | `frontmatter_patch.py append` | — | no frontmatter entry and no ledger ref reach HEAD (measured pre-fix: exit 0, committed) |
| `attach rm` (post-mutation) | `frontmatter_patch.py remove` | — | pre-fix `decref` lands in a commit while the frontmatter entry survives |
| `attach rm` (pre-mutation) | `attachment_meta.py decref` | — | the recorded pre-fix case above |
| `attach gc`, one orphan | `attachment_meta.py orphaned-at` | — | **the blob still exists** — the destructive read path, which pre-fix deletes and commits it inside its grace window |
| `attach gc` | `attachment_meta.py zero-refcount` | **process substitution** | pre-fix the empty read makes the loop a no-op → `swept=0` → no commit → `success: gc: swept 0 …` at **exit 0**: a sweep that never ran, reported as a clean one |
| `attach decref-deleted` | `attachment_meta.py refs` | **pipeline-in-`if`** | pre-fix this misreads as "no ref" and takes the wrong rebind branch at exit 0 |
| `attach decref-deleted`, 2 doomed tasks, fault on the **2nd** | `attachment_meta.py decref` | mid-loop | pre-fix task #1's release is committed while task #2's is silently skipped |
| `artifact create` | `frontmatter_patch.py append` | — | direct analogue of the measured `attach add` case: pre-fix commits manifest + blob at exit 0 while the task lists no artifact |
| `artifact update` | `artifact_manifest.py set-current` | — | pre-fix prints `current is now <hash>` at exit 0 **without** moving `current` |
| `artifact move` (**dir → local**) | `artifact_manifest.py set-backend` | — | pre-fix reports `Moved … to backend 'local'` at exit 0 while the manifest still says `dir` |
| `artifact rm` | `artifact_manifest.py get` | **command substitution** | pre-fix misreads as the stale-reference branch and drops a live entry at exit 0 |

**Rejected as non-discriminating** (verified against the current source, not
assumed):

- `artifact move` ← `artifact_manifest.py versions`. The empty read leaves
  `versions=()` and the **existing** `(( ${#versions[@]} > 0 )) || die` at
  `aitask_artifact.sh:411` already exits before any copy, so the assertions pass
  *both* pre- and post-fix. The fix's only gain there is diagnostic. The
  status-handling form at that line is covered by the static guard instead; the
  process-substitution *shape* is pinned behaviorally by `attach gc` ←
  `zero-refcount` above.
- `artifact create` ← `artifact_manifest.py create`. Same accidental catch as
  `attach add` ← `incref`: the absent `manifest_rel` makes the path-scoped
  `git add` fail, so pre-fix already rolls back and exits non-zero. Replaced by
  the `frontmatter_patch.py append` fault above.

The `artifact move` pin needs a second registered backend; reuse the `dir`
backend fixture from `tests/test_artifact_dir_backend.sh`. Its direction is
load-bearing: **dir → local**. Moving *to* `dir` stages no blob paths, so the
pre-fix commit would be empty and fail on its own (`_artifact_commit` has no
empty-commit guard), making the pin non-discriminating again.

Negative control: every verb above run under the shim with **no** fault → exit 0,
the expected commit count and success message — proving the shim is a passthrough
and the pins discriminate on the injected fault, not on a broken fixture.

**Part B — static contract guard.** Discovers `with_attach_lock <fn>` across
`.aitask-scripts/**/*.sh`, computes each file's callback closure to a fixpoint
(seed = named callbacks; add any same-file function named in an in-closure body —
this is what reaches the transitively-called helper shape that caused t1668), and
flags any logical line (physical line + `\`-continuations) that invokes a mutator
without a **terminating-or-propagating** status handler.

Accepted forms are only those whose non-zero propagation is **visible in the
line itself** — the guard cannot know what a variable holds:

- `|| die …`
- `|| { … die …; }`
- `|| return $?` (the failed command's own status — non-zero by construction)
- `|| return <literal non-zero>` (`|| return 1`)

Everything else **fails the guard**, including `&&`, a bare `if mutator; then`,
`; then`, `|| <var>=$?`, `|| return 0`, `|| return "$anyvar"`, `|| true`, and
`if ! mutator; then … fi`. That last one looks like handling but is not:
`if ! attach_meta incref …; then warn "failed"; fi` branches on failure and
**still continues**, which is t1675's bug verbatim. The guard cannot see whether
a branch ends in `die` or in a bare `warn`, so it must not assume. None of those
makes a failure terminal: `attach_meta incref … && log_ok` and
`if artifact_manifest create …; then …; fi` both continue past a failed mutator
and let a later command return success, and `rc=0; attach_meta incref … ||
return "$rc"` *returns success outright* — the exact bug, passing a naive lint.
The variable case is not hypothetical: `|| return 0` is a pervasive idiom in this
tree (`aitask_project_resolve.sh`, `yaml_utils.sh`, `aitask_changelog.sh`, and
~20 more), so a rule accepting a bare `|| return` would wave through the worst
shape. No mutator site uses a variable return today, so the tightening costs
nothing.

**The allowlist is the guard's one judgement seam, and it is per-site.** Every
exempted shape is one the matcher cannot verify, so widening `ACCEPT_RE` to admit
them would admit the unsafe cases too — a swallowing `|| true` alongside a
rollback's, an `if ! …; then warn` alongside the one that dies. Each entry
instead cites its own evidence. Seven entries:

| entry | evidence |
|---|---|
| 4 × `artifact_backend_delete … \|\| true` | best-effort, inside a rollback a line or two before `die`; a leftover blob is unreferenced and gc-reclaimable |
| `aitask_artifact.sh:163` | pipeline **head**; `set -o pipefail` carries the status to the function's return, and both callers `\|\| die` |
| `aitask_attach.sh:576` | **tail** position — the status *is* the function's return value, and the sole caller `\|\| die`s it |
| `aitask_artifact.sh:572` | the tree's only `if !`; its branch restores from HEAD and dies at `:580-584` |

The bar for an entry is *refactor first*. That is what
`aitask_fold_mark.sh:738-739` did, trading `|| rc=$?` plus a next-line check for
a **directly-recognized form**:

```bash
# before: rc's non-zero-ness is only guaranteed by the NEXT line
rc=0
out="$(attach_meta rebind "$fid" "$primary_id")" || rc=$?
(( rc == 0 )) || die "fold: attachment rebind failed for t${fid} (exit ${rc})"

# after: fail-propagation visible in the line itself, no allowlist needed
out="$(attach_meta rebind "$fid" "$primary_id")" \
    || die "fold: attachment rebind failed for t${fid} (exit $?)"
```

Verified: after a failed command substitution, `$?` inside the `die` **argument**
still holds the failed command's status (probed — a helper returning 7 reports
`exit 7`), so the message keeps its exit code and the success path still binds
`$out`. This is strictly better than a machine-checked exemption: a later edit
cannot weaken an adjacent check that no longer exists.

An entry pins a **line number**, so it stops matching if the file shifts — which
re-exposes its site to the guard rather than quietly exempting whatever moved
into that line.

A second rule flags a mutator inside a `$( )` within `[[ … ]]`, whose status is
discarded even on a line that has `||`.

MUTATORS is a single named list with a per-entry reason: `attach_meta`,
`artifact_manifest`, `artifact_backend_put`, `artifact_backend_delete`,
`frontmatter_patch.py`.

Documented non-coverage (a guard that overclaims is worse than one with a stated
boundary): a mutator reached through a function defined in *another* file; a
mutator not on the list; and a mutator in a non-final pipeline position — which
is precisely why `aitask_attach.sh:468` is hoisted by hand rather than left to
the guard.

**Part C — negative controls** over a synthetic fixture tree, testing the guard's
matcher only (all real transaction behavior is pinned in Part A). Not flagged:
`|| die`, `|| { …; die; }`, `|| return $?`, `|| return 1`, and a mutator in a
function *not* reachable from any callback. Flagged: a bare mutator; `&& log_ok`;
`if mutator; then …; fi`; **`rc=0; mutator || return "$rc"`** and
**`mutator || return 0`**; a mutator in a transitively-called same-file helper
(the t1668 shape); `mutator || rc=$?` with **no** adjacent check; and
`[[ -z "$(artifact_manifest get x)" ]] || die`.

`if ! mutator; then warn "failed"; fi` is a required control — the shape that
looks handled and is not. Two further controls cover the allowlist mechanism: a
`file:line` entry suppresses **only** that exact line, and the same shape one
line away is still flagged.

## Verification

1. `bash tests/test_attach_lock_callback_contract.sh` — must pass.
2. **Pre-fix control — mandatory, per pin.** Run every Part A pin against a
   scratchpad copy of the unfixed scripts and confirm each one **fails** there
   (recorded evidence above for two of them: exit 0, 1 commit, success message).
   A pin that passes both ways proves nothing, and two candidates were already
   dropped for exactly that (see "Rejected as non-discriminating"). **Any pin
   that survives this control is replaced or removed before the task lands.**
   The trap is systematic here: several transactions stage a path the failed
   mutator was supposed to create, so `git add` fails and the pre-fix run
   *appears* correct for the wrong reason.
3. Regression net — all must pass:
   `test_attach_local_backend.sh`, `test_attach_meta.sh`,
   `test_attach_archive_gc.sh`, `test_attach_gc_manifest_blocking.sh`,
   `test_attach_task_delete_decref.sh`, `test_attach_fold_rebind.sh`,
   `test_attachment_meta_lib.sh`, `test_artifact_cli.sh`,
   `test_artifact_dir_backend.sh`, `test_artifact_fold_transfer.sh`,
   `test_artifact_share_resolution.sh`, `test_artifact_manifest_lib.sh`,
   `test_fold_mark.sh`.
4. `shellcheck .aitask-scripts/aitask_attach.sh .aitask-scripts/aitask_artifact.sh .aitask-scripts/aitask_fold_mark.sh .aitask-scripts/lib/attachment_lock.sh .aitask-scripts/lib/attachment_meta.sh .aitask-scripts/lib/artifact_manifest.sh`
5. `bash tests/test_no_raw_tmux.sh` — unchanged; confirms the new guard did not
   disturb the existing lint idiom.

Step 9 (Post-Implementation) handles cleanup, archival and merge.

## Risk

### Code-health risk: medium

- Sweep across two load-bearing transactional scripts (~24 call sites). Each edit
  is uniform and strictly fail-closed — the change direction only ever converts
  "continue silently" into "abort" — and the existing attach/artifact e2e suite
  is a dense regression net. · severity: medium · → mitigation: run the full
  regression net (step 3) before committing.
- The new `|| die` guards create abort points that leave uncommitted on-disk
  drift, because t1675 deliberately adds no rollback there. · severity: medium ·
  → mitigation: **owned by t1698**, which `depends: [1675]` and carries the
  measured evidence. The alternative — a HEAD restore at each new abort — would
  multiply a known data-loss bug, so leaving the drift visible and tracked is the
  safer interim state. The seam header carries a forward pointer.
- A site where lenient behavior is load-bearing would break. Checked the one real
  candidate: `_artifact_rm_txn`'s stale-reference branch keys on *empty output*,
  and `artifact_manifest get` on a missing handle exits **0** with empty output
  (pinned by `test_artifact_manifest_lib.sh:48`), so `|| die` does not collapse
  that branch. · severity: low · → mitigation: none needed — verified.
- The `aitask_fold_mark.sh:738-739` refactor touches a line t1668 fixed. It is
  status-equivalent (`|| rc=$?` + `(( rc == 0 )) || die` → `|| die "… (exit $?)"`,
  with `$?` verified to carry the failed substitution's status) and
  `_fold_rebind_refs` is inside this task's audit scope. · severity: low ·
  → mitigation: `test_fold_mark.sh` is in the regression net and already covers
  this path's failure branch.

### Goal-achievement risk: low

- The task asks for a seam-only fix; this delivers contract + static guard +
  call-site sweep instead, because seam-only was measured to be impossible. The
  deviation was put to the user and that option was chosen explicitly.
  · severity: low · → mitigation: none needed — user-assented.
- Three data-integrity defects found during the audit are not fixed here.
  · severity: low · → mitigation: split to **t1698** at the user's explicit
  direction, with the empirical findings, design constraints and test plan
  preserved in that task rather than summarized away.
- The static guard is grep-shaped and cannot see cross-file or pipeline-position
  mutators. Its boundary is documented in the file, the three unobservable shapes
  are hoisted by hand, and the Part A pins cover real transaction behavior that
  the synthetic Part C controls cannot. · severity: low · → mitigation: the
  documented non-coverage block is part of the deliverable.

The task's three scope items are covered: (1) the audit, (2) the durable fix,
(3) the pinning test.

## Final Implementation Notes

- **Actual work done:** All three scope items landed as planned.
  §1 — a `CALLBACK CONTRACT` block in `lib/attachment_lock.sh` (errexit is off;
  the four measured non-fixes; the `|| die` rule; the rejected success-sentinel;
  a forward pointer to t1698), a `RETURNS the helper's status; it NEVER dies`
  note on the `attach_meta` and `artifact_manifest` fronts, and an extension of
  the `_fold_attach_txn` comment recording the caller-re-suppression finding.
  §2 — the audited sweep across `aitask_attach.sh` (+70) and
  `aitask_artifact.sh` (+80), plus the `_fold_rebind_refs` refactor to a
  directly-recognized form. All five structurally-invisible shapes were hoisted:
  the `[[ … ]]` substitution, the three process substitutions, and the
  pipeline-in-`if`. §3 — `tests/test_attach_lock_callback_contract.sh` (696
  lines): 11 Part A behavioral pins, 8 per-verb negative controls, the Part B
  static guard with its 7-entry per-line allowlist, and the Part C matcher
  controls. **91 assertions, 0 failures.**

- **Deviations from plan:** None in substance. The plan's Part A table is
  implemented in full, including the `artifact move` (dir → local) pin that the
  first session had not reached.

- **Issues encountered:**
  - The session implementing this task crashed after §1 and §2 were complete and
    Part A was written up to A10. Work was resumed from the gate ledger
    (`plan_approved`) with the uncommitted tree intact; nothing was redone.
  - The plan's "every verb above" negative control was implemented for 2 of the
    8 verbs. Extending it to all 8 required a second registered backend (`dir`),
    two more fixture tasks and four reserved payloads — a payload shared with an
    earlier pin makes the commit stage nothing for that path, which is precisely
    how a control stops being one.
  - **A control that passed for the wrong reason.** The first version of the gc
    control asserted a global `swept 1`. It passed — on a *different* orphan.
    `decref-deleted` clears only the ledger, so the task file still lists the
    blob and gc's blocking-set scan correctly retains it. Replaced with a
    self-contained control: its own untouched payload (`h.bin`), released with
    `rm` (which drops both the ledger ref and the frontmatter entry), asserted by
    the concrete outcome — that specific blob is gone. The global count moves
    with unrelated orphans left by earlier pins and must not be the assertion.
  - That fix also made the controls hold against the **unfixed** tree, which is
    what a negative control has to do: it checks fixture and shim soundness, not
    the fix. The earlier version failed pre-fix because a.bin carries a permanent
    stuck ledger ref there — it was measuring the bug rather than the fixture.

- **Key decisions:**
  - The pre-fix control was run by extracting `git archive HEAD` into a
    scratchpad and copying only the *new test* over it, so the scripts stay
    unfixed while the pins are current. All 11 pins fail there (exit 0, the
    success message, and a commit made) and no control does. Part B correctly
    flags all 31 unguarded sites in that tree and 0 in this one.
  - The gc pins fail pre-fix on exit status and success message but not on
    "commits nothing" — pre-fix gc sweeps 0 and therefore commits nothing either.
    Kept as-is: a pin has to fail pre-fix, not fail on every assertion.
  - `dir` is registered as a second backend, never as the default, so
    `artifact create` still resolves to `local` for every other pin.

- **Upstream defects identified:** None. The three data-integrity defects this
  audit surfaced were already split out to t1698 during planning (`depends:
  [1675]`), and the new `|| die` abort points deliberately add no rollback — a
  HEAD restore there would multiply t1698's defect 2. That residual on-disk
  drift after an abort is t1698's, and the seam header says so.
