---
Task: t1277_plan_header_resolved_base_branch.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1277 — Plan header records the resolved base branch

## Context

`.aitask-scripts/aitask_plan_externalize.sh:521` writes the plan header's
`Base branch:` field from `detect_primary_branch()`, ignoring the base branch
Step 5 actually resolved. A profile setting `base_branch: develop` therefore
produces a header reading `Base branch: main`, while `Output branch:` in the
*same* header is authoritative (t1233 gave it profile `output_branch` → resolved
base → primary). Two branch fields, two different sources.

Consequences today: `SKILL.md`'s **Re-entry Routing** binds `base_branch` from
that header line and hands it to the Remote Drift Check, so a resumed session
watches the repository primary instead of the branch its worktree was cut from.

t1536 escalates this from a reporting bug to a fork-correctness bug: it moves
`git worktree add` out of Step 5 into the top of Step 7, making the plan header
the *carrier* of branch context across the resolution→fork gap. A session
resumed in that gap would cut the worktree from `main` under a
`base_branch: develop` profile. t1536 records `depends: [1277]`; this task ships
first so t1536's `--worktree` flag is a small addition to an already-threaded
channel.

Outcome: both branch fields in a plan header derive from one resolution, through
the existing `<branch-flags>` caller contract.

## Design decisions (confirmed with the user)

1. **Flag surface — add `--base-branch[-file]`, keep the legacy pair.** The new
   pair carries the Step-5 resolved base: it sets `Base branch:` *and* feeds the
   output-branch fallback chain (preserving "output defaults to base").
   `--output-branch-default[-file]` stays accepted with its documented
   base-neutral meaning, but the workflow stops emitting it — which turns it into
   a genuine negative control in the test suite.

2. **`--no-worktree` suppresses base resolution, exactly as it already
   suppresses output.** No branch is cut in current-branch mode, so
   `Base branch:` records the detected primary and a stale value in existing
   frontmatter is overwritten. This keeps the shipped `fast` profile
   byte-identical.

### Resolution order after the change

```
Base branch:    --base-branch[-file]                      (file channel wins if both)
              > profile base_branch          (worktree mode only)
              > detected primary
              ... all suppressed to "detected primary" when --no-worktree / create_worktree:false

Output branch:  --output-branch
              > profile output_branch        (worktree mode only)
              > --output-branch-default[-file]            (legacy, base-neutral)
              > the resolved base (--base-branch[-file] / profile base_branch)
              > detected primary
              ... unchanged
```

## Implementation

### Pre-phase (risk mitigations)

1. `[characterize_output_branch_precedence]` In `tests/test_plan_externalize.sh`,
   add a table-driven characterization case that pins the **current**
   `Output branch:` outcome for the full flag matrix, one row per combination:
   `--output-branch` alone; profile `output_branch` alone; profile `output_branch`
   + `--output-branch`; `--output-branch-default`; `--output-branch-default-file`;
   profile `base_branch` alone; profile `base_branch` + `--output-branch-default`;
   profile `base_branch` + profile `output_branch`; each of the above with
   `--no-worktree`; and the bare no-flag call. Run it against **unmodified**
   `aitask_plan_externalize.sh` and confirm every row passes before editing the
   script — a row that fails here is a wrong expectation, not a bug. Keep the
   table green through step 1's refactor; any row that flips is a real merge-target
   regression from deleting the `_p_base → OUTPUT_BRANCH_DEFAULT` block.

### 1. `.aitask-scripts/aitask_plan_externalize.sh`

- **New flags** in the arg loop, mirroring the existing output pair:
  - `--base-branch <b>` — validated immediately by the existing
    `validate_branch_name()`.
  - `--base-branch-file <path>` — path recorded only; the value is read **after**
    the already-externalized short-circuit, so a no-op Step 8 call whose scratch
    file is gone still returns `PLAN_EXISTS` (the rule `:329-345` already
    establishes for `--output-branch-default-file`).
  - When both are given the **file channel wins**, whatever the argument order,
    because it is read after the parse loop — the same rule `:341` already
    establishes for the output pair.
  - Both set `OUTPUT_INTENT=true` (they feed the output fallback chain).

- **`BASE_INTENT` is derived, not flag-enumerated.** Computed in the post-parse
  resolution block, after `create_worktree` may have flipped `WORKTREE_MODE`:

  ```
  BASE_INTENT=false
  if [[ -n "$BASE_BRANCH_OVERRIDE" || "$WORKTREE_MODE" != true ]]; then BASE_INTENT=true; fi
  ```

  i.e. **true iff a base was actually supplied** (`--base-branch`,
  `--base-branch-file`, or a profile that really contains `base_branch`) **or the
  caller positively asserted there is no fork** (`--no-worktree` /
  `create_worktree: false`, where the primary is the right answer and a stale
  value must go). It gates **only the splice** — `build_header()` always writes
  the resolved base, which is the primary when nothing was supplied.

  The deliberate asymmetry with `OUTPUT_INTENT`: a profile with no
  `output_branch` still *determines* the merge target (it falls back to
  base/primary), so `--profile` alone is a complete claim about the output field.
  A profile with no `base_branch` determines nothing — Step 5 asked the user, and
  the answer arrives separately via `--base-branch-file`. Treating `--profile`
  alone as base intent would rewrite an existing `Base branch:` to the primary on
  an invented basis, and that field is exactly what Re-entry Routing reads to
  decide where the work is cut from. So `--profile` (output-only or bare),
  `--output-branch`, and `--output-branch-default[-file]` all leave an existing
  `Base branch:` line untouched. Pinned by Test 14c; stated in the caller
  contract (§2).
- **Factor the value-file reader.** The `--output-branch-default-file` block
  (`:332-345`) becomes `read_branch_value_file <path> <flag>`, assigning to a
  global rather than printing — `die` inside `$( )` would only kill the subshell.
  Both file flags call it, so the one-line/empty/unsafe rejections stay
  single-sourced. **Each call site copies the shared result global into its own
  variable immediately, before the next call runs** — the two reads must not be
  batched with the copies deferred, or one file would supply both branches.
  Pinned by Test 14e.
- **Profile pickup.** In the `--profile` block, add the base rung:
  `[[ -z "$BASE_BRANCH_OVERRIDE" && WORKTREE_MODE && -n "$_p_base" ]]` →
  `BASE_BRANCH_OVERRIDE="$_p_base"` (re-validated, as the output rung does).
  **Delete** the now-redundant `_p_base → OUTPUT_BRANCH_DEFAULT` block at
  `:371-375`; the new last output rung covers it with identical precedence.
- **Suppression + resolution**, replacing `:378-379`:
  ```
  [[ "$WORKTREE_MODE" == true ]] || { OUTPUT_BRANCH_OVERRIDE=""; OUTPUT_BRANCH_DEFAULT=""; BASE_BRANCH_OVERRIDE=""; }
  [[ -n "$OUTPUT_BRANCH_OVERRIDE" ]] || OUTPUT_BRANCH_OVERRIDE="$OUTPUT_BRANCH_DEFAULT"
  [[ -n "$OUTPUT_BRANCH_OVERRIDE" ]] || OUTPUT_BRANCH_OVERRIDE="$BASE_BRANCH_OVERRIDE"
  PRIMARY_BRANCH="$(detect_primary_branch)"
  BASE_BRANCH_RESOLVED="${BASE_BRANCH_OVERRIDE:-$PRIMARY_BRANCH}"
  ```
  Must stay *after* the profile block, which is where `create_worktree` can flip
  `WORKTREE_MODE`.
- **`build_header()`** drops its local `primary` and emits
  `Base branch: $BASE_BRANCH_RESOLVED` /
  `Output branch: ${OUTPUT_BRANCH_OVERRIDE:-$PRIMARY_BRANCH}`. The `Branch:`
  line keeps comparing the checked-out branch against `$PRIMARY_BRANCH` —
  unchanged, and out of scope.
- **Generalize the splice.** `splice_output_branch()` → `splice_header_branches
  <file> <base> <out>`, one `awk` handling both fields in a **single**
  `ait_atomic_render` (an empty argument means "no intent — leave that field
  alone"). Missing fields are inserted before the closing `---` in
  `build_header` order (Base, then Output), keeping the `---` count at 2. Call it
  when `has_frontmatter` and either intent flag is set, passing
  `BASE_BRANCH_RESOLVED` / the resolved output only for the flags whose intent
  fired. Use `if` blocks, not `[[ … ]] && x=y`, so a false test cannot trip
  errexit at the tail of the script.
- Update the usage/header comment block, including the corrected
  "`--output-branch-default` does **not** change `Base branch:`" note (still
  true) and the new precedence table.

### 2. Caller contract — `.claude/skills/task-workflow/plan-externalization.md`

- `<branch-flags>` gains `--base-branch-file <path>` for an **interactively**
  chosen base branch, replacing `--output-branch-default-file` in the caller
  contract (same non-shell scratch-file rule, same "keep the file alive until
  Step 8 has run"). Both call-sites — `planning.md` Step 6 (`--force`) and
  `SKILL.md` Step 8 — pass it, as they do today for the output flags.
- Note that `--profile` now supplies `base_branch` for the header field as well
  as the merge-target fallback, and that `--no-worktree` clears both.
- State the base-neutrality rule explicitly, since it is the caller-visible half
  of the derived `BASE_INTENT` above: an invocation that supplies **no** base —
  `--output-branch`, `--output-branch-default[-file]`, or a `--profile` whose
  YAML has no `base_branch` — never rewrites a `Base branch:` line that a plan's
  frontmatter already carries. A caller that wants the field updated must say so,
  with `--base-branch[-file]`, a profile that sets `base_branch`, or
  `--no-worktree`.
- Add a worked example for a worktree profile setting `base_branch`.
- `--output-branch-default[-file]` stays documented as a legacy, base-neutral
  escape hatch that the workflow no longer emits.

### 3. Supporting doc edits (all under `.claude/skills/task-workflow/`)

- `planning.md` — the "header values are placeholders" note currently covers only
  `Output branch:`; extend it so `Base branch:` is called out as the Step-5
  resolved base (detected primary in current-branch mode). This is the surface
  non-Claude agents follow, since they write plan headers by hand.
- `remote-drift-check.md` — Input table: `base_branch` is the Step-5 resolved
  base branch, which the plan header now records (removes the standing
  inconsistency with `planning.md`'s Checkpoint, which passes it from context).
- `profiles.md` — `base_branch` row: note it is recorded in the plan header and
  consumed on re-entry.

The rendered variants (`task-workflow-*-/` under `.claude/`, `.opencode/`,
`.agents/`) are gitignored and re-render on demand — nothing to commit there, and
no golden under `tests/golden/skills/` embeds these procedure files (verified).

### 4. Open question from the task description — resolved, no code change

"Should `remote-drift-check.md` compare base vs output differently now that they
may legitimately differ more often?" — **No.** The fix makes them *converge*: the
common `base_branch: develop` profile previously produced base=`main` (wrong) and
output=`develop`, i.e. two passes one of which watched the wrong branch; it now
produces base=output=`develop` and a single pass. The existing "run the output
pass only when it differs from base" rule gets strictly more accurate. Record
this in the plan's Final Implementation Notes. The t1536-flavoured half of the
question (what a base-branch drift warning *means* once the fork is
hypothetical) is not actionable until t1536 lands and stays with that task.

## Tests

`tests/test_plan_externalize.sh` — new **Test 14** block:

| case | assertion |
|---|---|
| profile `base_branch: develop`, worktree | `Base branch: develop`, `Output branch: develop` |
| `--base-branch develop`, no profile | both `develop` |
| `--base-branch-file` | `develop`; `develop$(id -u)` rejected with no leak; two-line / empty file rejected |
| profile `base_branch: develop` + `output_branch: staging` | base `develop`, output `staging` |
| `--base-branch develop --output-branch-default release` | base `develop`, output `release` (legacy flag keeps its meaning and wins its rung) |
| `create_worktree: false` + `base_branch: develop`; and `--base-branch develop --no-worktree` | `Base branch: main` — plus a positive control on the same profile with the worktree enabled |
| frontmatter source carrying `Base branch: stale` + `--base-branch develop` | replaced; exactly one `Base branch:` line; `---` count still 2 |
| frontmatter source with no base field + base intent | field inserted |
| `--output-branch-default release` alone | `Base branch: main` (negative control) |

**Test 14b — precedence boundaries (pairwise, one collision per row).** Each rung
of the two chains is currently exercised only in isolation, so an assignment
landing in the wrong order would still pass every row above while selecting the
wrong fork point or merge target. One case per boundary, asserting **both**
header fields:

| collision | expected winner |
|---|---|
| `--base-branch alpha --base-branch-file <beta>` (and the reverse argument order) | `Base branch: beta` — the file channel wins regardless of order, because it is read after parsing (mirrors `:341` for the output pair) |
| `--base-branch alpha` + profile `base_branch: dev` | `Base branch: alpha` — explicit flag over profile |
| `--base-branch-file <alpha>` + profile `base_branch: dev` | `Base branch: alpha` — explicit file over profile |
| `--output-branch staging --base-branch alpha` | `Base branch: alpha`, `Output branch: staging` — the two chains are independent |
| `--output-branch staging` + profile `base_branch: dev` | `Base branch: dev`, `Output branch: staging` |
| `--base-branch alpha --output-branch-default release` | `Base branch: alpha`, `Output branch: release` — legacy rung outranks the base rung it now precedes |
| profile `output_branch: staging` + profile `base_branch: dev` | `Base branch: dev`, `Output branch: staging` |

**Test 14c — the shared splice must not move a field its caller said nothing
about.** All rows use a source whose frontmatter already carries
`Base branch: stale` **and** `Output branch: stale`, so a spurious rewrite is
visible. This is the case Tests 7b/7c cannot see: their sources have no
`Base branch:` line at all.

| invocation | `Base branch:` | `Output branch:` |
|---|---|---|
| `--output-branch dev` | `stale` — untouched (no base intent) | `dev` |
| `--output-branch-default release` | `stale` — untouched; this is what "legacy, base-neutral" means for an *existing* header, not only a generated one | `release` |
| `--base-branch develop` | `develop` | `develop` |
| `--profile <p>` where `p` has **only** `output_branch: dev` | `stale` — untouched: the profile makes no claim about the base, and inventing the primary here would overwrite the field Re-entry Routing reads | `dev` |
| `--profile <p>` where `p` has **neither** key | `stale` — untouched | `main` |
| `--profile <p>` where `p` has `base_branch: dev` | `dev` — **positive control**: the profile really does supply a base, so a stale value is corrected | `dev` |
| `--no-worktree` | `main` — the caller asserted there is no fork, so a stale base must go | `main` |
| `--profile <p>` (`create_worktree: false`, `base_branch: dev`) | `main` — same assertion via the profile key | `main` |

Also assert on each row that the frontmatter still has exactly two `---` lines and
exactly one line per field, so an insert-instead-of-replace bug cannot hide.

**Test 14e — the shared value-file reader keeps its two consumers apart.**
Factoring the read into `read_branch_value_file` introduces a *shared result
global* and a second call site, neither of which exists today: both file flags in
one invocation is a brand-new path, and correctness rests on each call copying the
global into its own variable before the next call overwrites it. A
copy-after-both-reads mistake would make one file silently supply both branches.

| invocation | `Base branch:` | `Output branch:` |
|---|---|---|
| `--base-branch-file <develop>` + `--output-branch-default-file <release>` | `develop` | `release` — neither file leaks into the other's field |
| the same two flags in the reverse argument order | `develop` | `release` — the result must not depend on parse order |
| `--output-branch-default release --output-branch-default-file <staging>` | `main` | `staging` — the legacy pair's own "file wins" rule, untouched by the refactor (currently unpinned: Tests 7l/7p exercise only the file form) |
| `--base-branch alpha --base-branch-file <beta>` | `beta` | `beta` — same rule on the new pair (also listed in 14b) |

**Test 14d — `--base-branch-file` is read after the short-circuit** (the base
counterpart of Test 7q, which covers only `--output-branch-default-file`):
externalize once with `--base-branch-file <scratch>`, delete the scratch file,
then re-run **without** `--force` and assert `PLAN_EXISTS:` with the recorded
`Base branch:` intact. Then re-run **with** `--force` and assert it fails closed
on the missing file — the pairing is what stops a future refactor from "fixing"
the no-op by hoisting the read (or from making the writing call silently fall
back).

Existing edits:
- **Test 7h** flips: its `--profile` case (`base_branch: dev`) currently asserts
  `Base branch: main`; it becomes `Base branch: dev`. Its comment changes from
  "untouched by the fallback" to naming the two flags' now-distinct roles.
- **Test 7n** gains a `Base branch: main` assertion for
  `create_worktree: false` + `base_branch: dev`.

`tests/test_skill_render_task_workflow.sh` Test 4d:
- widen the "no call-site substitutes a branch value" grep to
  `--(base-branch|output-branch(-default)?) ` (the trailing space keeps
  `--base-branch-file <path>` out of the match);
- "interactive base uses the file channel" now asserts `--base-branch-file`.

**AC deviation, stated rather than silent:** the task's Acceptance names
"Test 1 and Test 13 updated". They must **not** change — with no base resolved
they exercise exactly the "behaviour unchanged (detected primary)" clause of the
same Acceptance, and are its negative controls. The test that genuinely flips is
**7h**. I will note this in the task's Final Implementation Notes.

## Verification

```bash
bash tests/test_plan_externalize.sh
bash tests/test_skill_render_task_workflow.sh
bash tests/test_atomic_task_file_writes.sh        # covers both renderer paths
shellcheck .aitask-scripts/aitask_plan_externalize.sh
./.aitask-scripts/aitask_skill_verify.sh
```

Live acceptance (the headline AC, driven through the real entry point): in a
scratch sandbox, a profile with `base_branch: develop` and no `create_worktree`
key must yield `Base branch: develop` in the externalized header; the same
profile with `create_worktree: false` must yield `Base branch: main`.

Negative control: revert only the `build_header` line to `detect_primary_branch`
and confirm the named new assertions fail.

Step 9 (Post-Implementation) then handles gates, cleanup and archival as usual.

## Risk

### Code-health risk: medium
- Deleting the `_p_base → OUTPUT_BRANCH_DEFAULT` block (`:371-375`) and rebuilding
  its precedence as the new last output rung could silently change the **merge
  target** — a wrong-branch merge at Step 9, not a wrong label · severity: medium
  · → mitigation: inline pre-phase characterize_output_branch_precedence
- The flag surface grows to two nearly-identical pairs
  (`--base-branch[-file]` vs the retained base-neutral
  `--output-branch-default[-file]`); a future edit that forgets the distinction
  reintroduces exactly this bug from the other side · severity: medium
  · → mitigation: retire_output_branch_default_flags
- `aitask_plan_externalize.sh` is on the path of every Claude Code plan
  externalization, so a regression is felt by every task, not only worktree
  profiles · severity: low
  · → mitigation: inline pre-phase characterize_output_branch_precedence

### Goal-achievement risk: low
- None identified. The mechanism is a direct mirror of the already-shipped
  `Output branch:` resolution (t1233) in the same file, every acceptance clause
  maps to a named assertion, and the one contested acceptance clause (Test 1 /
  Test 13) is flagged in the plan rather than silently reinterpreted.

### Planned mitigations
- timing: pre-phase | name: characterize_output_branch_precedence | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: merge-target regression from deleting the `_p_base → OUTPUT_BRANCH_DEFAULT` precedence block | desc: table-driven characterization of the current `Output branch:` resolution across the full flag matrix, pinned green before the refactor and kept green through it
- timing: after | name: retire_output_branch_default_flags | type: refactor | priority: low | effort: medium | inline_risk: high | added_complexity: high | addresses: two nearly-identical branch-flag pairs left behind by the backward-compatible surface | desc: once t1536 has landed and both externalize call-sites are settled, decide whether `--output-branch-default[-file]` can be deleted and its test cases migrated onto `--base-branch[-file]`

**Post-inline reassessment:** with the characterization pre-phase in the plan, the
merge-target regression risk is materially reduced, but the duplicated flag surface
remains in-plan (its mitigation is a spawned follow-up, not part of this change).
Levels are unchanged: code-health **medium**, goal-achievement **low**.
