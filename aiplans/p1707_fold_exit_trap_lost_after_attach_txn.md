---
Task: t1707_fold_exit_trap_lost_after_attach_txn.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1707 — fold EXIT trap after the attach transaction

## Context

t1707 was spawned from t1698's Step 8b review carrying two "upstream defects".
Investigation shows the headline one **does not exist**, so this task's real
deliverable changes shape: prove the absence with an executable guard, fix the
doc defect narrowly, and correct the record so the false positive is not
re-spawned by a future review.

### Finding 1 — the trap defect is not real (evidence)

The task claims `aitask_fold_mark.sh:~800` has no EXIT trap after the Step 5b
attach transaction returns. It has one:

```
:819    with_attach_lock _fold_attach_txn || _fold_attach_rc=$?
:820    trap '_fold_abort_cleanup' EXIT   # registry_lock_release did `trap - EXIT`
:821    (( _fold_attach_rc == 0 )) \
:822        || die "fold: attachment transfer failed (exit ${_fold_attach_rc})"
```

- `git log -L 818,822` attributes line 820 to **`b1d6d7215` (t1668)** — the very
  task the defect is blamed on. t1668's own plan
  (`aiplans/archived/p1668_…:292`) specifies it verbatim. It was never removed.
- The only handler-less window is `registry_lock.sh:153` (`trap - EXIT`) →
  `fold_mark:820`. It crosses two variable clears, two `return`s and one
  assignment. No `die` is reachable in it, and errexit cannot fire because
  `:819`'s `|| _fold_attach_rc=$?` suppresses it across the whole wrapper call.
- Every Step 6 arm downstream runs with the trap armed (via `:820`, or via the
  top-level arm at `:518` when `_fold_any_attach_or_artifacts` is false and the
  lock is never taken). The task's premise that "the shipped Step 6 arms all call
  `_fold_rollback` explicitly" is **also false**: `:1025`
  (`die "internal: empty fold path set"`) and `:1051`
  (`die "internal: unvalidated --commit-mode"`) call no rollback at all. They are
  correct *because* the trap is armed — and `:1050`'s shipped comment says so
  outright: "the EXIT trap performs the rollback". Those two arms are positive
  evidence that the re-arm is present and load-bearing.
- No nested `registry_lock_acquire` exists anywhere in `_fold_attach_txn`'s call
  tree, so `registry_lock_release`'s dir/token early-return (`:148`) is
  unreachable from the fold path. The bare `trap` at `:820` is therefore correct
  as written: `txn_snapshot.sh:205-212` scopes the must-chain rule to a trap
  installed **inside** the callback, and `:820` is outside it, after the release.
  **No production code change is warranted.**

The reviewer read `_fold_attach_txn` (which chains at `:776`) and missed the
call-site re-arm 44 lines below.

### Finding 2 — the doc defect is real, and there are two instances

Neither `ait artifact` nor `ait attach` has a command-reference page anywhere in
`website/content/`. Two links promise one:

- `website/content/docs/skills/aitask-trail.md:85` → `/docs/commands/task-management`
  (headings: `ait create`, `ait ls`, `ait update` — zero artifact content).
- `website/content/docs/development/task-format.md:98` → `/docs/workflows/implementation-trails`
  (zero `ait artifact` content beyond the lede).

Both `relref` targets exist, so `hugo build` and `check_links.py` pass them.

In-flight **t1687** (`Implementing`, no plan yet, locked since 2026-09-02) owns
the structural decision: its step 5 says to "decide explicitly whether that
reference gap is in scope here or belongs to a spawned follow-up", and its step 4
owns the cross-linking. So this task makes the minimal honest fix and hands the
re-link to t1687.

### Scope confirmed with the user

- Finding 1 → record-correct **and** pin it with a negative control. No
  production code change.
- Finding 2 → remove both misleading links, note t1687.

---

### Pre-phase (risk mitigations)

- **`pin_control_anchor_uniqueness`** — before writing the control, add to
  `install_attach_rearm_removed()` an assertion that the shipped
  `aitask_fold_mark.sh` contains **exactly one** line equal to the full re-arm
  text (indented, with its trailing `# registry_lock_release did …` comment),
  and that the top-level arm — a distinct line, `trap '_fold_abort_cleanup' EXIT`
  at column 0 — is present both before and after the substitution. The two lines
  share the trap text, so a loose anchor would mutate the wrong trap and the
  control would pass while proving nothing. Fail the test loudly (bump
  `FAIL`/`TOTAL`, `return 1`) on either count being wrong, in the same shape as
  the injector's other guards.

## Step 1 — Pin the re-arm with a negative control

`tests/test_fold_mark.sh:1218 test_attach_txn_nonzero_return_rolls_back` already
exercises this exact path (callback returns non-zero, `trap - EXIT` has already
run, the `die` at `:822` must still roll back). But it has **no paired negative
control**, which this file's own convention requires (`assert_defect_present`
at `:1515`, and the comment at `:1512-1517`: without one the positive test
"proves nothing"). Adding it both closes that gap and converts t1707's claim
into a permanent executable guard.

### 1a. Injector — `install_attach_rearm_removed()`

Add beside the other injectors (near `install_attach_txn_returns_nonzero`,
`tests/test_fold_mark.sh:1618`), following that function's exact three-part
shape: python3 rewrite of the **fixture copy** (`setup_project` copies
`aitask_fold_mark.sh` into the temp repo), `sys.exit(1)` on a stale anchor, then
greps proving the substitution landed.

```bash
# t1707: delete the post-attach-lock re-arm at aitask_fold_mark.sh:820, leaving
# an armed transaction with no EXIT handler. This is the build t1698's Step 8b
# review believed was shipped; the control proves it is not, and that removing
# the re-arm is observable. Injected, not a production scenario.
install_attach_rearm_removed() {
    python3 - "$PWD/.aitask-scripts/aitask_fold_mark.sh" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
# Anchor on the FULL line incl. its trailing comment. The bare trap text also
# matches the top-level arm at :518, which must survive.
old = "    trap '_fold_abort_cleanup' EXIT   # registry_lock_release did `trap - EXIT`\n"
if old not in s:
    sys.stderr.write("anchor: post-attach-lock re-arm not found\n"); sys.exit(1)
open(p, 'w').write(s.replace(old, '', 1))
PY
    ...
}
```

Guards it must run afterwards, each bumping `FAIL`/`TOTAL` and `return 1` on
failure (the `install_prefix_commit_block` "did not excise too much" pattern,
`:1505`):

| direction | grep | why |
|---|---|---|
| removed | `re-arm line absent` | the injection landed |
| survived | `^trap '_fold_abort_cleanup' EXIT$` | the **top-level** arm at `:518` is untouched — it shares the trap text, so this is the discriminating check |
| survived | `with_attach_lock _fold_attach_txn \|\| _fold_attach_rc=\$?` | the call site itself is intact; only the re-arm went |

### 1b. Control — `test_negative_control_attach_rearm_removed()`

Same fixture as `test_attach_txn_nonzero_return_rolls_back` (`:1218-1251`):
`setup_project`, `_copy_attachment_libs`, `write_task aitasks/t10_primary.md`,
`_seed_attachment aitasks/t20_a.md 20 …`, commit, record `before=$(git rev-parse HEAD)`.

Injector order is load-bearing: **`install_attach_rearm_removed` first**, then
`install_attach_txn_returns_nonzero` — the latter deletes `_fold_snapshot_meta_tree`,
which the former's guards must not be asked to see. Both call sites use the
established `install_x || { teardown; return; }` form.

Then `_run_fold_split --commit-mode fresh 10 20` and assert **via
`assert_defect_present`** that the defect is observable:

- exits non-zero and stderr still names `attachment transfer failed (exit 3)`
  (plain `assert_eq`/`assert_contains` — the `die` itself is unaffected);
- `folded_tasks` on `aitasks/t10_primary.md` is still `[20]` — **not** rolled back;
- `aitasks/t20_a.md` status is still `Folded`;
- stderr does **not** contain `rolled back every mutation`
  (`lib/txn_snapshot.sh:233`, the string this file already pins at `:921`, `:1339`, `:1411`).

Register the function in the runner list next to the t1668 group
(`tests/test_fold_mark.sh:2116`), under a `# t1707` comment naming what it
guards.

**Stop-and-report condition:** if the control does **not** observe the defect,
the analysis above is wrong somewhere. Report it and stop — do not weaken the
assertions to make it pass.

## Step 2 — Remove the two dead-end links

Keep the literal `` `ait artifact` `` and its subcommand list; drop only the
misleading `relref` wrapper. No prose is rewritten.

- `website/content/docs/skills/aitask-trail.md:85` — ``[`ait artifact`]({{< relref "/docs/commands/task-management" >}})`` → `` `ait artifact` ``
- `website/content/docs/development/task-format.md:98` — ``[`ait artifact`]({{< relref "/docs/workflows/implementation-trails" >}})`` → `` `ait artifact` ``

**Verification for this step is grep-based, not `check_links.py`.** That check
passes these links *today* — both targets exist — so it also passes if a wrapper
is left in place, and it says nothing about whether the literal command text
survived. Each assertion below is discriminating because the relref string being
counted is **unique to its file** (verified: 1 occurrence each; `task-format.md`
separately uses `relref "/docs/commands/task-management"` at `:13`, which must
not be touched):

```bash
# 1. Both misleading wrappers are gone (each string occurs exactly once today).
[ "$(grep -c 'relref "/docs/commands/task-management"' website/content/docs/skills/aitask-trail.md)" = 0 ]
[ "$(grep -c 'relref "/docs/workflows/implementation-trails"' website/content/docs/development/task-format.md)" = 0 ]

# 2. The literal command text and its subcommand list were retained, unlinked.
grep -qF 'Manage them with `ait artifact` (`ls`, `get`, `versions`, `rm`).' \
  website/content/docs/skills/aitask-trail.md
grep -qxF '`ait artifact` and' website/content/docs/development/task-format.md

# 3. No collateral: every other relref in both files survives (7 → 6, 11 → 10).
[ "$(grep -c relref website/content/docs/skills/aitask-trail.md)" = 6 ]
[ "$(grep -c relref website/content/docs/development/task-format.md)" = 10 ]

# 4. Shape: one line changed in each file, nothing else.
git diff --numstat -- website/content/docs/skills/aitask-trail.md \
                      website/content/docs/development/task-format.md
#   expect exactly:  1  1  <path>   for each of the two files
```

(For t1687's benefit: the one substantive artifact section that exists today is
`task-format.md:78`, `### Nested fields: \`artifacts\` and \`attachments\``, anchor
`#nested-fields-artifacts-and-attachments`. It documents the frontmatter shape,
not the CLI, which is why it is not used as a retarget here.)

## Step 3 — Hand the re-link to t1687

```bash
./ait note 1687 --from 1707 --with-live --file - <<'EOF'
…
EOF
```

Content: both dead-end pointers by `file:line`, that neither `ait artifact` nor
`ait attach` has a command-reference page, that t1707 removed the links rather
than retargeting them so t1687's step-4 cross-linking can point them at whatever
reference page its step-5 decision produces, and the existing
`#nested-fields-artifacts-and-attachments` anchor. Advisory, hedged, and marked
as written against this SHA.

## Step 4 — Correct the record

This plan is the durable record. But the task file
`aitasks/t1707_fold_exit_trap_lost_after_attach_txn.md` asserts the absent
re-arm in **three** places, not one — rewriting only the first would leave a
later reader able to follow the survivors and re-create the same false-positive
task. Every one must be corrected or explicitly labelled disproved:

| section | live claim to correct |
|---|---|
| `## Upstream defect`, bullet 1 | "fold has NO EXIT trap after its Step 5b attach transaction returns" — and the sub-claim "The shipped Step 6 arms all call `_fold_rollback` explicitly" |
| `## Diagnostic context` | "the release then clears the whole chain when Step 5b returns successfully"; "From that point to Step 6, fold is running an armed transaction (`_fold_txn_active=true`) with no handler to fire it"; "every Step 6 failure arm calls `_fold_rollback` by hand"; the stale `line ~533` (the top-level arm is at `:518`) |
| `## Suggested fix` | "Re-arm the trap after `with_attach_lock` returns in Step 5b … issued once more after the lock is released" — prescribes work already shipped |

Rewrite each to state the disproof and its evidence (`b1d6d7215`, `:819-822`,
the `:1025` / `:1051` trap-only arms), keeping the doc bullet and its suggested
fix intact. Leave `## Inbox` untouched — it is a received record, not a claim of
this task's.

**Completion check for this step** — after editing, no live claim may survive:

```bash
grep -nEi 'no EXIT trap|with no handler|clears the whole chain|Re-arm the trap|arms all call|by hand' \
  aitasks/t1707_fold_exit_trap_lost_after_attach_txn.md
```

Every remaining hit must sit inside prose that marks it as the **disproved**
original claim (e.g. under a `DISPROVED —` label or a quotation being refuted),
never as a standing assertion. Read each hit in context and confirm that; an
empty result is also acceptable.

---

## Verification

```bash
bash tests/test_fold_mark.sh                     # whole file; new control included
shellcheck .aitask-scripts/aitask_fold_mark.sh   # unchanged, sanity only
cd website && python3 check_links.py --build     # required after any content/ edit
```

- All 100+ existing tests in `test_fold_mark.sh` stay green — in particular
  `test_attach_txn_nonzero_return_rolls_back` (`:1218`) and
  `test_abort_inside_attach_txn_rolls_back` (`:1253`), the two positive pins the
  new control is paired with.
- The new control **must report the defect** against the mutated build; the
  injector proves its own substitution landed first, including that the
  top-level trap at `:518` survived.
- `check_links.py --build` passes. It is run because `CLAUDE.md` mandates it for
  any `website/content/` edit — **not** as evidence for Step 2. It cannot see a
  mis-targeted-but-existing relref, and removing a link cannot dangle one, so it
  would pass whether or not the edit landed. Step 2's four grep assertions are
  the real proof, and all of them must pass.
- Step 4's completion grep returns no *standing* assertion of the absent re-arm.
- No production shell script is modified by this task; `git diff --stat` should
  show only `tests/test_fold_mark.sh`, the two `website/content/` pages, and the
  task file.

## Post-implementation

Step 9 (Post-Implementation) handles cleanup, archival and merge as usual. No
worktree: profile `fast` works on the current branch.

## Risk

### Code-health risk: low
- The injector's anchor is a source line whose *bare* trap text also matches the top-level arm at `:518`; a future reword, or an anchor that matches the wrong line, would silently mutate the wrong trap · severity: medium · → mitigation: inline pre-phase pin_control_anchor_uniqueness
- Two injectors compose in one test; a wrong order makes one injector's survival grep unsatisfiable · severity: low · → mitigation: none — order is fixed in Step 1b and each guard is scoped to lines the other does not touch

### Goal-achievement risk: low
- The negative control might not observe the defect, which would mean the "already fixed" conclusion is wrong somewhere · severity: medium · → mitigation: none — Step 1b's stop-and-report condition: surface it, never weaken the assertions
- Only two instances of the dead-end-relref class were found, by inspecting `ait artifact` alone; `check_links.py` cannot see this class by construction, so others may remain · severity: low · → mitigation: t1759
- Removing the links rather than retargeting leaves the reader with no pointer at all until t1687 lands · severity: low · → mitigation: none — the Step 3 note hands the re-link to the task that owns the reference-page decision

### Planned mitigations
- timing: pre-phase | name: pin_control_anchor_uniqueness | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (the injector anchor is ambiguous with the top-level trap arm at :518) | desc: Assert in the injector that exactly one full re-arm line exists and that the distinct top-level arm survives the substitution, so the control cannot pass by mutating the wrong trap.
- timing: after | name: sweep_dead_end_relrefs | type: chore | priority: low | effort: medium | inline_risk: medium | added_complexity: high | addresses: goal-achievement risk 2 (only the two `ait artifact` instances of the class were found) | desc: Sweep website/content for relrefs whose target page exists but contains none of the referenced subject — a class hugo build and check_links.py pass by construction. | created: t1759

## Final Implementation Notes

- **Actual work done:** Exactly the approved plan's four steps. (1) Added
  `install_attach_rearm_removed()` and `test_negative_control_attach_rearm_removed()`
  to `tests/test_fold_mark.sh` (+88 lines), registered in the runner beside the
  other negative controls; the pre-phase mitigation
  `pin_control_anchor_uniqueness` is implemented as the injector's two
  precondition counts (`grep -cxF` on the full re-arm line and on the column-0
  top-level arm) plus three post-substitution guards. (2) Removed the two
  dead-end relref wrappers, keeping the literal `ait artifact` unlinked.
  (3) Sent the advisory note to t1687. (4) Rewrote all three sections of the
  task file that asserted the absent re-arm. **No production code was changed** —
  `aitask_fold_mark.sh` is byte-identical to HEAD.
- **Deviations from plan:** None in substance. One addition beyond the written
  plan: before accepting the control's green result I ran a **discrimination
  probe** — temporarily bypassing `install_attach_rearm_removed` so the re-arm
  stayed in place — and confirmed all three `assert_defect_present` assertions
  flip to FAIL (273/276). The probe edit was reverted by an exact inverse edit,
  never by `git restore` (a concurrent session shares this worktree). Without
  that probe the control's pass would have been consistent with a vacuous test.
- **Issues encountered:**
  - The injector anchor is genuinely ambiguous: `trap '_fold_abort_cleanup' EXIT`
    matches **both** the re-arm at `:820` and the top-level arm at `:518`. The
    plan anticipated this; the implementation anchors on the full line including
    its trailing `# registry_lock_release did …` comment and asserts both counts
    are exactly 1 before substituting.
  - The worktree changed owner mid-task — at session start it carried
    `tests/lib/fake_agent_binary.py`; by Step 8 a different session's t1725_2
    work was present instead. All commits were therefore path-scoped to this
    task's own four files.
  - `check_links.py --build` was run (mandated for any `website/content/` edit)
    but is **not** evidence for Step 2: it passes a mis-targeted-but-existing
    relref by construction. The six grep assertions in Step 2 are the real proof.
- **Key decisions:**
  - **No production change to `aitask_fold_mark.sh:820`.** The bare `trap` there
    is correct: `lib/txn_snapshot.sh:205-212` scopes the must-chain rule to a
    trap installed *inside* the callback, and `:820` runs after
    `registry_lock_release` already cleared EXIT. `registry_lock_release`'s
    dir/token early-return (`registry_lock.sh:148`) is unreachable from the fold
    path — nothing in `_fold_attach_txn`'s call tree takes a nested registry
    lock — so converting it to `txn_chain_exit_trap` would be a no-op on every
    reachable path.
  - **Links removed rather than retargeted.** t1687 (`Implementing`) explicitly
    reserves the decision on the missing `ait artifact` / `ait attach`
    command-reference page. Retargeting at `task-format.md:78`
    (`#nested-fields-artifacts-and-attachments`) was rejected: that section
    documents the frontmatter shape, not the CLI surface, so it would have been
    a second mis-targeted pointer.
  - **The false positive is corrected in three places, not one.** The task
    asserted the absent re-arm in `## Upstream defect`, `## Diagnostic context`
    and `## Suggested fix`; correcting only the first would have left a reader
    able to follow the survivors and re-spawn the same task.
- **Upstream defects identified:** None
