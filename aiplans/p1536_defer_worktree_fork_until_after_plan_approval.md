---
Task: t1536_defer_worktree_fork_until_after_plan_approval.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1536 — Defer the worktree fork until after plan approval

## Context

`task-workflow` **Step 5** currently does two unrelated things: it *resolves*
the branch context (`base_branch` / `output_branch` / `create_worktree`) **and**
it immediately *forks* — `mkdir -p aiwork` + `git worktree add -b
aitask/<task_name> aiwork/<task_name> <base>` (`SKILL.md:340-349`).

Planning is Step 6. So on any `create_worktree: true` profile the fork point is
pinned to the local base HEAD **before any planning happens** — before the plan
is written, before the user approves it, and before the Remote Drift Check runs.
Consequences: the plan is designed against a tree the fork may already differ
from; the drift check's only remedy ("Stop and re-verify plan") strands a
worktree cut from the *pre-drift* HEAD; every "stop, don't abort" exit strands a
fork for work that never started; and a decomposed parent (children created in
Step 6) strands one too.

**Goal:** split resolution from forking. The *decision* stays at Step 5; the
*fork* happens at the top of Step 7 — after the plan is approved and after the
Remote Drift Check has returned "Continue anyway".

**Two decisions taken with the user before planning:**

1. **Fork site:** immediately **after** the Step 7 Pre-implementation ownership
   guard, before Agent Attribution / cross-repo assignment / gate recordings /
   the risk-mitigation "before" creation. Ownership is confirmed before anything
   is created, so a guard abort or a crash-recovery `decline` cannot strand a
   just-cut worktree; and the risk-mitigation "before" stop still reaches a real
   worktree, exactly as AC7 requires. **Trade-off, accepted knowingly:** this
   puts the ownership guard between the drift check and the fork, which is one
   of the two reasons the fork-point detector stays reachable (step 11).
2. **t1392** (`step5_worktree_reuse_on_repick`) is **closed as part of this
   task**: its only failing site — Step 5's `git worktree add -b` — ceases to
   exist, and AC4 carries the reuse check to the new fork site.

## Findings that change the acceptance criteria

Two ACs rest on premises that turned out to be false. Stating them up front
rather than silently re-scoping:

- **AC6 is a verify-and-clarify, not a fix.** `crash-recovery.md` does **not**
  read `Worktree:` from the plan header. Its Step 1.1 parses `git worktree list
  --porcelain` for `branch refs/heads/aitask/<task_name>` and falls back to
  `survey_dir=.` (`crash-recovery.md:34-41`), which the summary block renders as
  `(current branch)` (`:75`). `website/.../crash-recovery.md:92` already
  documents that derivation. So the value is live-derived and already correct
  for a task that crashed between approval and fork — the only defect is that
  `(current branch)` now *misdescribes* that state (the profile is worktree
  mode; the fork just has not happened). Fix = wording only.
- **AC10's "phase 6 before phase 7" is real, but the ordering is not the whole
  story.** `website/content/docs/skills/aitask-pick/_index.md:30` numbers
  "Environment setup" 6 and "Planning" 7. After this change the two split: the
  *decision* stays at 6, the *fork* moves inside 8 (Implementation). The entry
  needs rewording, not just renumbering.

One gap is **not** covered by any AC and is fixed here because leaving it would
be a regression:

- **`SKILL.md:73` (Step 3, Check 3 — manual verification)** says "Steps 4
  (ownership) and 5 (worktree) still run before dispatch". Manual verification
  skips Steps 6-8, so with the fork moved into Step 7 a manual-verification task
  on a worktree profile would silently get **no worktree**. That is the right
  behaviour (a checklist writes no code and Step 9 has nothing to merge), but
  the prose must say so instead of promising a worktree it no longer creates.

**The non-goal's gap is still reachable, so it is spun off (step 11), not
dissolved.** The task's "Non-goals" section asks whether the
fork-point-vs-current-base detector survives this change and says to spin it off
if so. It does, for two reasons:

- The drift check and the fork are **not** adjacent. The chosen fork site puts
  the Step 7 ownership guard between them — which can prompt, refresh a lock,
  and commit/push task data, i.e. real wall-clock time with a human in the loop.
  Neither step locks the base branch, so a concurrent agent committing to
  `<base>` in the same repo (or any local ref update) advances the fork point
  after the drift check validated it.
- More fundamentally, the divergence does not disappear — it **changes sign**.
  Today the fork is older than the plan; afterwards the fork is newer than the
  plan (designed during Step 6, cut at Step 7). Either way nothing compares the
  tree the plan was designed against with the tree the branch is cut from.

### Verified premises (checked, not assumed)

- **t1277 has landed.** `aitasks/archived/t1277_plan_header_resolved_base_branch.md`
  is `status: Done`, and the helper already resolves and records the Step-5 base
  (`aitask_plan_externalize.sh:481` `BASE_BRANCH_RESOLVED`, written at `:639`;
  `--base-branch` / `--base-branch-file` parsed at `:285-303`). So Re-entry
  Routing's `Base branch:` read already returns the Step-5 *resolved* base, not
  `detect_primary_branch()`, and **no `depends:` entry is needed**. What is
  still missing is a *cross-check*: nothing verifies the header agrees with the
  in-context Step-5 value at fork time. Step 1(c) adds that guard.
- **All agent trees render from one source.** `.agents/skills/` and
  `.opencode/skills/` contain only rendered closures
  (`task-workflow-<profile>[-<agent>]-`); `aitask_skill_render.sh:7,90-92`
  resolves the authoring template under `.claude/skills/<skill>/` for **every**
  agent, and the three trees' `plan-externalization.md` copies are byte-identical
  (verified with `diff -q`). So for `task-workflow` specifically, AC11's "port to
  Codex / OpenCode" is satisfied by the rerender in step 9 — there is no separate
  port to suggest and no window in which those trees call the helper under the
  old contract.
- **Caller audit (done now, not promised).** Repo-wide grep for
  `aitask_plan_externalize.sh`: exactly **one** production invocation contract —
  `.claude/skills/task-workflow/plan-externalization.md` (its Step 6 / Step 8 /
  `--internal` retry forms). Everything else is a rendered copy of that file, a
  test (`tests/test_plan_externalize.sh`, `tests/test_atomic_task_file_writes.sh`),
  a historical fixture (`tests/fixtures/skills/task-workflow/plan-externalization.md.pre-rewrite`),
  a CHANGELOG/aidocs mention, a board docstring, or a **permission allowlist**
  (`seed/claude_settings.local.json:75`, `seed/codex_rules.default.rules:50`,
  `seed/opencode_config.seed.json:64`, `.codex/rules/default.rules:51`) that
  matches any argument list and needs no change. The residual exposure is not a
  missed call site but a *runtime omission* — the contract is prose, so an agent
  can still forget the flag. Step 2 makes that non-silent.

## Files to modify

### Pre-phase (risk mitigations)

Runs before any edit below. Both steps are read-only or test-only.

1. `[pin_worktree_header_matrix]` Add the `Worktree:` emission-matrix block
   (cases 1-8 of step 8) to `tests/test_plan_externalize.sh` **first**, then run
   `bash tests/test_plan_externalize.sh` against the **unmodified** helper.
   Required outcome: case 2 (directory `aiwork/t999_sandbox_task` present on
   disk, `--worktree` **not** passed) FAILS, and cases 1/4/5/6/7 fail only
   because the flag does not exist yet. Record the observed failing case ids in
   the plan. A case 2 that *passes* here means the assertion is not probing the
   probe — fix the test, not the helper, before continuing.
2. `[audit_deferred_fork_consumers]` Enumerate every consumer that assumes the
   Step-5 fork and record each one's post-change disposition as a table in this
   plan, one row per consumer, each row citing `file:line`. Cover at minimum:
   Step 3 Check 3 (manual verification), `task-abort.md`, `crash-recovery.md`,
   Re-entry Routing, Step 9's merge pre-flight and its `git worktree remove`
   cleanup, `cross-repo-child-assignment.md`, the Step 6 decomposed-parent exit,
   and every consumer of the plan header's `Worktree:` field. Each row's
   disposition must be one of **updated** (an edit below covers
   it), **improved** (it now strands nothing where it used to), or **unchanged
   no-op** (it already tolerates the absence). A consumer that fits none of the
   three is an unhandled path — extend the edits below before proceeding.

### 1. `.claude/skills/task-workflow/SKILL.md` (authoring template — Jinja)

Four edits. Note the template is the source of truth; the three rendered
variants and the goldens are regenerated (step 9).

**(a) Step 3, Check 3 — `:73`.** Replace the "(worktree)" promise:

> - Step 4 (ownership) still runs before dispatch — manual verification is work
>   that should be owned and locked. Step 5 resolves the branch context but
>   **creates nothing**: the fork lives in Step 7, which this path skips, so a
>   manual-verification task always runs on the current branch. That is correct
>   — the checklist writes no code and Step 9 has no branch to merge.

**(b) Step 5 — `:319-351`.** Keep the resolution, delete the fork. Concretely:

- `{% if profile.base_branch is defined %}` true-branch (`:320`): the display
  line gains the deferral, per AC2 —
  `Display: "Profile '{{ profile.name }}': using base branch {{ profile.base_branch }} — the branch and worktree are created after plan approval and the remote drift check, not now."`
- `{% else %}` fallback (`:322-329`): the same sentence on the "Profile check"
  display line, and the `AskUserQuestion` **question text** becomes
  `"Which branch should the new task branch be based on? The branch and worktree are not created now — they are cut after you approve the plan and the remote drift check passes."`
  (Per t1150 the explanation must live **inside the widget**, not in same-turn
  prose.)
- Delete the `mkdir -p aiwork` bullet (`:340-343`) and the `git worktree add`
  bullet (`:345-349`).
- Replace them with a forward pointer:
  > - **Nothing is created here.** Record the resolved `<task_name>`,
  >   `<base_branch>` and `<output_branch>` as workflow context; the branch and
  >   worktree are cut at the top of **Step 7**, after the plan is approved and
  >   the Remote Drift Check Procedure has returned "Continue anyway". Step 6
  >   therefore externalizes the plan **before** the worktree exists — which is
  >   why the `Worktree:` header field comes from this resolved intent
  >   (`--worktree`), never from a directory probe.
- Keep "Work in the `aiwork/<task_name>/` directory for implementation" but
  qualify it as "from Step 7 onward".

**(c) Step 7 — new block, inserted between the Pre-implementation ownership
guard (ends `:392`) and "Record implementing agent" (`:394`).** No new Jinja
gate: Step 5 already renders both its **If Yes** / **If No** bodies in every
profile, so this block mirrors that and stays profile-invariant.

> **Deferred worktree fork (Step-5 intent, cut now):**
>
> This is the fork Step 5 resolved but did not perform. Reaching here means the
> plan was approved *and* the Remote Drift Check returned "Continue anyway", so
> the fork point is the base branch as it stands after any pull the drift check
> prompted.
>
> **If Step 5 resolved current-branch mode** (its **If No** branch), this block
> is a no-op — continue below.
>
> **If Step 5 resolved worktree mode** (its **If Yes** branch):
>
> - **Confirm the fork base before cutting.** `<base_branch>` reaches this block
>   by exactly one of two routes, and **both always bind it** — there is no path
>   that arrives here with nothing:
>
>   - **fresh** — Step 5 resolved it (profile `base_branch`, else the user's
>     answer). Provenance: `Step 5`.
>   - **re-entry** — Step 5 was skipped; **Re-entry Routing** already resolved it
>     from the plan header, falling back to `main` with
>     `provenance_base="legacy plan, no Base branch field"` for a plan written
>     before that field existed. Provenance: whatever that step recorded.
>
>   Three checks, in order. Each fails closed; none guesses:
>
>   1. **Bound.** If `base_branch` is empty, neither route ran — a defect state,
>      not a legacy one. **Stop and ask the user** for the base. Never call
>      `git worktree add` with an empty final argument: git would silently cut
>      from the current HEAD, which is precisely the wrong-base failure this
>      task exists to remove.
>   2. **Legacy fallback is confirmed, never assumed.** If the provenance is the
>      `legacy plan, no Base branch field` fallback, the value is a *guess*
>      (`main`) that is about to become a real branch, not just a comparison.
>      Confirm it with `AskUserQuestion` before cutting — question text naming
>      the plan file, the guessed base, and the reason ("this plan predates the
>      `Base branch:` header, so the base was defaulted") — with options
>      "Use `main`" / "Pick a different base branch". This is the same
>      name-the-provenance rule Step 9 and Re-entry Routing already state, raised
>      from *display* to *confirm* because this call site writes rather than
>      reads. After confirming, write the answer to the `--base-branch-file`
>      scratch file so **Step 8's externalize fallback** splices it into the plan
>      header (`splice_header_branches` updates a plan that already carries
>      frontmatter, and `--base-branch[-file]` is what claims that field) — the
>      next resume of this task is then no longer legacy.
>   3. **Agreement.** When both a Step-5 value and a non-empty header value are
>      available they must match — the header is what a future resume reads, so a
>      disagreement means the branch is cut from one base and resumed against
>      another:
>
>      ```bash
>      header_base=$(sed -n 's/^Base branch: //p' "<plan_file>" | head -n1)
>      [ -z "$header_base" ] || [ "$header_base" = "$base_branch" ] \
>        || echo "BASE_MISMATCH:$header_base vs $base_branch"
>      ```
>
>      `BASE_MISMATCH` → **stop and ask the user** which base is correct; do not
>      guess and do not cut. An empty `header_base` on the *fresh* route is
>      normal only if Step 6's externalize was skipped — proceed with the Step-5
>      value, which check 2 has already confirmed if it was a fallback.
>
> - **Reuse check next** (same rule as Re-entry Routing). If
>   `git worktree list --porcelain` already shows a
>   `branch refs/heads/aitask/<task_name>` record, that worktree survives from an
>   earlier session that stopped inside Step 7 (the risk-mitigation "before"
>   stop is the reachable case). `git worktree add -b` on an existing branch
>   fails, so **reuse it** — and reuse means working in **its** directory, which
>   is the `worktree <path>` line of the *same record*, not a guessed
>   `aiwork/<task_name>`. The porcelain format emits `worktree <path>` first and
>   `branch <ref>` later within one blank-line-separated record, so extract the
>   path record-aware (the same parse Step 9's merge pre-flight and
>   `crash-recovery.md:34-41` already do):
>
>   ```bash
>   reuse_dir=$(git worktree list --porcelain | awk -v b="branch refs/heads/aitask/<task_name>" '
>     /^worktree /  { p = substr($0, 10) }
>     $0 == b       { print p; exit }')
>   ```
>
>   If `reuse_dir` is non-empty: work in `"$reuse_dir"` and **skip the cut
>   below**. Do not assume it equals `aiwork/<task_name>` — a worktree created
>   under a different layout, or a repo whose root moved, both make the guess
>   wrong, and the failure mode is silent (implementing in the wrong tree).
>
> - **Otherwise cut it now**, from the confirmed `<base_branch>`:
>
>   ```bash
>   mkdir -p aiwork
>   git worktree add -b aitask/<task_name> aiwork/<task_name> "$base_branch"
>   ```
>
>   Bind the base to a shell variable rather than substituting the literal — the
>   same injection rule Step 5 and Step 9 state for user-authored branch names.
>
> - Work in the reused or newly cut directory for the implementation below.

**(d) Re-entry Routing — `:276`.** "Otherwise run Step 5 as normal" no longer
creates anything. Re-point it:

> - **Environment setup with reuse:** If a worktree for `<task_name>` already
>   exists — `git worktree list --porcelain` shows a
>   `branch refs/heads/aitask/<task_name>` line — reuse it (work in that
>   directory). Otherwise run **Step 7's Deferred worktree fork block** with the
>   `base_branch` resolved from the plan header above — Step 5 creates nothing
>   any more, so a resumed task that never reached its fork still gets one. For
>   current-branch profiles (no worktree) this is a no-op.

### 2. `.aitask-scripts/aitask_plan_externalize.sh`

`build_header()` currently emits the field from a directory probe:

```bash
[[ -d "aiwork/${task_name}" ]] && echo "Worktree: aiwork/${task_name}"   # :633
```

Externalization runs in Step 6, i.e. **before** the deferred fork, so that probe
would drop `Worktree:` from every worktree-mode plan. Replace intent-from-disk
with intent-from-caller:

- New globals beside `WORKTREE_MODE` (`:177`): `WORKTREE_PATH=""`,
  `WORKTREE_FLAG_SEEN=false`, `NO_WORKTREE_FLAG_SEEN=false`.
- New `validate_worktree_path()` next to `validate_branch_name()` (`:187`),
  same fail-closed shape and the **same shell-safe subset**
  (`^[A-Za-z0-9._/-]+$`), plus a rejection of any `..` path segment and of a
  leading `/` — the value is persisted into a plan header and later consumed by
  an agent as a working directory.
- New `--worktree <path>` arm in the parser, mirroring `--no-worktree`
  (`:328-335`): requires an argument, validates it, sets `WORKTREE_PATH` and
  `WORKTREE_FLAG_SEEN=true`. It asserts worktree mode; it makes no claim about
  either branch, so it does **not** set `OUTPUT_INTENT` / `BASE_INTENT`.
- **Mutual exclusion, fail closed.** `--worktree` after `--no-worktree` (or the
  reverse) `die`s with "conflicting worktree intent". After the profile parse
  (`:449-472`), a `--worktree` combined with a profile whose `create_worktree`
  is `false` `die`s the same way — a contradiction between an explicit runtime
  fact and configured intent must never be silently resolved.
- `build_header()`: replace `:633` with
  `[[ -n "$WORKTREE_PATH" ]] && echo "Worktree: $WORKTREE_PATH"`. **The probe is
  deleted, not kept as a fallback** — with it in place a Step-8 fallback call
  (which runs *after* the fork) would re-introduce the disk-derived value and
  hide a missing flag.
- Update the header comment block (`:13-71`), `usage()` (`:119-154`), and the
  resolution-order comment so `--worktree` is documented exactly like the
  branch flags.

**Contract, stated positively:** `Worktree:` is emitted **iff `--worktree` is
passed**. Its absence means "no worktree declared", which keeps every existing
flagless call (and `--no-worktree`) byte-identical to today.

- **Make an omitted claim loud, not silent.** The caller audit above shows the
  contract lives in prose, so an agent can still *forget* the flag — and the
  probe used to paper over exactly that. When **neither** `--worktree` nor
  `--no-worktree` was supplied, emit one line to **stderr** (never stdout —
  stdout is the single-line status channel every caller parses):
  `Warning: no worktree claim (--worktree/--no-worktree) — 'Worktree:' omitted from the plan header.`
  This fires precisely on the forgot-the-flag case, never on either explicit
  flag, and it is what makes the probe's removal non-silent as AC5 requires.
  Existing flagless test calls will print it; the emitted header and the exit
  status are unchanged, so nothing regresses.

**Scope note (deliberate, not an oversight):** `splice_header_branches()`
(`:658`) handles only `Base branch:` / `Output branch:` for plan sources that
already carry frontmatter. `Worktree:` is *not* added to the splice — it never
was spliced, and extending the awk to a third field is a separate change with
its own regression surface. Recorded here so the asymmetry is a decision rather
than a gap.

### 3. `.claude/skills/task-workflow/plan-externalization.md`

This file is where `<branch-flags>` is defined, and both call-sites
(`planning.md` Step 6, `SKILL.md` Step 8) reuse it verbatim — so threading the
new flag is a single edit here, per the AC5 contract.

- New bullet beside `--no-worktree` (`:26`): `--worktree aiwork/<task_name>` —
  when Step 5 resolved worktree mode. **Pass it in Step 6 even though the
  directory does not exist yet**: the fork is deferred to Step 7, so the header
  records Step 5's resolved intent, not a disk fact. The helper emits the
  `Worktree:` field only when this flag is present.
- Extend the "minimal set" paragraph (`:43`): worktree mode **always** includes
  `--worktree aiwork/<task_name>` exactly as current-branch mode always includes
  `--no-worktree`; the two are mutually exclusive and the helper fails closed on
  both.
- Update the two worktree-profile examples (`:70-94`) to carry
  `--worktree aiwork/t42_<name>`.
- The `MULTIPLE_CANDIDATES` retry warning (`:107`) already says to preserve the
  full `<branch-flags>`; add `Worktree:` to the list of fields a dropped retry
  would lose.

### 4. `.claude/skills/task-workflow/plan-approved-stop.md`

Both worktree claims become conditional on the caller (AC7):

- `:20` — "the plan is kept and the task returns to `Ready`. Whether a worktree
  is left behind depends on where this procedure was called from — see Notes."
- Notes bullet at `:90` — replace with:
  > - **Whether a worktree exists here depends on the call site.** From
  >   `planning.md`'s "Approve and stop here" or `remote-drift-check.md`'s "Stop
  >   and re-verify plan", **no worktree exists yet** — both stops happen before
  >   Step 7's deferred fork. That is the improvement: the drift stop no longer
  >   strands a fork cut from the pre-drift HEAD, and the re-pick cuts a fresh
  >   one from the pulled base. From Step 7's risk-mitigation "before" stop the
  >   worktree **does** exist and is intentionally left in place; the next pick
  >   reuses it via the reuse check at the fork site. Only the **Task Abort
  >   Procedure** removes a worktree.

### 5. `.claude/skills/task-workflow/task-abort.md`

`:57` — "If a worktree was created in Step 5" → "in **Step 7**". Add one line
recording the verified no-op property (AC8): each command is guarded with
`2>/dev/null || true`, so when the abort is reached before the fork (a Step 6
"Abort task", or the Step 7 ownership-guard abort that now precedes the fork)
all three are clean no-ops — nothing is removed and nothing is reported as
removed.

### 6. `.claude/skills/task-workflow/crash-recovery.md`

`:75` — the summary line's placeholder becomes
`- Worktree: <path or "(none — current branch, or fork not reached)">`, and a
sentence in Step 1.1 records that a task interrupted between plan approval and
the Step 7 fork legitimately has no worktree even on a worktree profile. The
derivation itself (`git worktree list --porcelain`, `survey_dir=.` fallback) is
already correct and is **not** changed.

### 7. Website docs

- `website/content/docs/skills/aitask-pick/_index.md:30` — item 6 becomes
  "**Branch resolution** — resolves the base branch and merge target, and
  decides whether the task gets its own worktree. Nothing is created yet."
  Item 8 ("Implementation") gains "…creating the `aiwork/<task_name>/` worktree
  first when one was chosen, so the fork point is the base branch as it stands
  after plan approval." The "Abort handling" capability bullet keeps its
  "cleans up worktree/branch if created" wording (still accurate).
- `website/content/docs/workflows/parallel-development.md:20` — "This creates an
  isolated working directory at `aiwork/<task_name>/`…" gains "…created once the
  plan is approved and the remote drift check has passed, so the branch is cut
  from an up-to-date base."
- `website/content/docs/workflows/crash-recovery.md` — `:92` gains the
  fork-not-reached case to match edit 6; `:97` ("crashed before making any
  changes") already covers the shape.

Per `documentation_conventions.md` these are current-state rewrites — no "used
to happen in Step 5" history in doc bodies.

### 8. Tests — `tests/test_plan_externalize.sh`

Append a block covering the new flag. The sandbox helper (`new_sandbox`) already
gives an isolated tree; `run_externalize` already `cd`s into it.

| # | case | assertion |
|---|---|---|
| 1 | `--worktree aiwork/t999_sandbox_task` | header contains `Worktree: aiwork/t999_sandbox_task` |
| 2 | **negative control** — `mkdir -p aiwork/t999_sandbox_task` on disk, **no** flag | header contains **no** `Worktree:` line (proves the probe is gone; this test fails on today's code) |
| 3 | no flag, no directory | no `Worktree:` line (unchanged legacy behaviour) |
| 4 | `--no-worktree --worktree <p>` and the reverse order | non-zero exit, stderr names the conflict |
| 5 | `--worktree 'aiwork/$(id)'`, `--worktree ../escape`, `--worktree /abs` | non-zero exit each (unsafe path rejected) |
| 6 | `--worktree` with no argument | non-zero exit |
| 7 | `--worktree` + a profile with `create_worktree: false` | non-zero exit, names the contradiction |
| 8 | `--worktree` + `--base-branch develop` | both `Worktree:` and `Base branch: develop` present — the flags are independent |
| 9 | no worktree flag at all | **stderr** carries the "no worktree claim" warning; **stdout** is exactly the one status line (assert stdout separately from stderr) |
| 10 | `--worktree <p>` and `--no-worktree` each alone | stderr carries **no** warning — it fires only on omission |
| 11 | **legacy persistence:** source plan already carries frontmatter with **no** `Base branch:` line; run the Step-8 form with `--base-branch-file <f>` (`develop`) | `Base branch: develop` is **inserted** (not replaced), appears exactly once, `---` count stays 2, and the rest of the frontmatter is byte-unchanged. Existing Test 7b covers this for `--output-branch`; the `Base branch:` insert path is **uncovered today** and is the persistence half of the legacy route |
| 12 | **round-trip:** feed the case-11 output back through Re-entry Routing's documented resolution snippet (`SKILL.md:259-264`) | yields `base_branch=develop` with `provenance_base="plan header"` — i.e. the plan is no longer legacy. Assert provenance, not just the value: a snippet that returned `develop` via the `main` fallback would be wrong and indistinguishable without it |

Case 2 is the load-bearing one: it is the single assertion that distinguishes
"intent-driven" from "probe-driven", and it must fail against the current
implementation before the fix lands.

### 9. Regenerate rendered variants and goldens

Goldens are byte-diffs of the render, so every edited wrapped file needs its
three profile goldens rewritten:

```bash
# python_resolve.sh is a SOURCED library, not an executable — the test suite
# obtains the interpreter this way (tests/test_skill_render_task_workflow.sh:40).
source .aitask-scripts/lib/python_resolve.sh
PY="$(require_ait_python)"
R=".aitask-scripts/lib/skill_template.py"
for f in SKILL plan-approved-stop; do
  for p in default fast remote; do
    "$PY" "$R" .claude/skills/task-workflow/$f.md \
      aitasks/metadata/profiles/$p.yaml claude \
      > tests/golden/procs/task-workflow/$f-$p.md
  done
done
```

`plan-externalization.md`, `task-abort.md` and `crash-recovery.md` carry no
Jinja and have no goldens — they are copied by the renderer, so the rerender
below is all they need.

```bash
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh $p; done
./.aitask-scripts/aitask_skill_verify.sh
```

All three agents render from the single `.claude/skills/task-workflow/`
authoring source (verified above), so this loop refreshes the Codex
(`.agents/skills/task-workflow-<profile>-codex-`) and OpenCode
(`.opencode/skills/task-workflow-<profile>-`) closures in the same pass —
**AC11's "port to the other agents" is this rerender, not a separate task.**
(That is specific to `task-workflow`, which has no per-agent authoring copy;
CLAUDE.md's suggest-separate-tasks rule still holds for skills that do.)
Staging follows the "commit only paths" rule: an explicit path list, never
`git add -A`, because the tree already carries unrelated uncommitted work.

### 10. Close t1392

After the code lands (post-commit, in Step 9's neighbourhood so the closure
references a real commit): `t1392_step5_worktree_reuse_on_repick` is fully
dissolved — Step 5's `git worktree add -b` no longer exists and the reuse check
now lives at the Step 7 fork site (AC4). Mark it Done and archive it with a note
naming t1536 as the landing task, using `ait` tooling and `./ait git`.

### 11. Spin off the fork-point divergence detector

The task's Non-goals explicitly instruct: *"spin it off if the plan confirms it
is still reachable after this change."* It is (see "Verified premises" above), so
create one standalone follow-up task via the standard **Batch Task Creation
Procedure** — not a child, and **with `depends: [1536]` set explicitly**. The
follow-up is created at Step 8b/8c, i.e. after the code commit but while t1536
is still `Implementing` and not yet archived; without the dependency another
agent could pick a task whose entire premise ("after t1536 the fork happens at
the top of Step 7") is not yet finalized. Spawned follow-ups ship with no
`depends:` by default, so this must be passed, not assumed.

- **Name:** `detect_fork_point_vs_plan_base_divergence`, `issue_type:
  enhancement`, priority medium, effort medium, `depends: [1536]`.
- **Body:** After t1536 the fork happens at the top of Step 7, but nothing
  compares the base HEAD the Remote Drift Check validated with the base HEAD
  `git worktree add` actually cuts from. Two windows remain: (a) the Step 7
  ownership guard sits between check and fork and neither locks `<base>`, so a
  concurrent agent committing to `<base>` in the same repo advances the fork
  point after the check passed; (b) the plan is designed in Step 6 against one
  tree and the branch is cut in Step 7 from another — the same divergence as
  before t1536, with the sign flipped (fork now *newer* than the plan rather
  than older). Suggested shape: record `git rev-parse <base>` at drift-check
  time into the workflow context, re-read it immediately before
  `git worktree add`, and surface a comparison to the user when they differ.
  Reference this plan and the t1536 commit.

### Post-phase (risk mitigations)

1. `[exercise_worktree_profile_live]` Execute the new fork path for real — no
   shipped profile does, so without this the block ships unexecuted. In a
   scratch clone (never the working repo):
   a. Write `aitasks/metadata/profiles/scratch_wt.yaml` with
      `create_worktree: true`, `base_branch: main`, and render
      `.claude/skills/task-workflow/SKILL.md` against it.
   b. Run `./.aitask-scripts/aitask_plan_externalize.sh <id> --force --profile
      <scratch> --worktree aiwork/<task_name>` with **no** `aiwork/` directory
      present, and assert the header carries `Worktree:`, `Base branch:` and
      `Output branch:`.
   c. Assert the base-agreement guard: with the header written by (b), the
      `header_base` vs `base_branch` comparison yields **no** `BASE_MISMATCH`.
      Then rewrite the header's `Base branch:` to a different name and assert
      the guard **does** print `BASE_MISMATCH` — a guard that never fires is
      not a guard. Also assert the refusal branch: an empty `base_branch`
      reaches "stop and ask" rather than running `git worktree add` with a
      missing final argument.
   d. Copy the two fork commands out of the **rendered** Step 7 block verbatim
      and run them. Assert `aiwork/<task_name>/` exists and
      `git worktree list --porcelain` reports
      `branch refs/heads/aitask/<task_name>`.
   e. Re-run the block's reuse extraction. Assert it (i) short-circuits — the
      second run does **not** invoke `git worktree add -b`, which would fail on
      an existing branch — and (ii) yields a **non-empty `reuse_dir` equal to
      the real worktree path** reported by `git worktree list`. Then move the
      worktree to a path that is *not* `aiwork/<task_name>`
      (`git worktree move`) and re-run: `reuse_dir` must follow the record to
      the new path. That second run is what distinguishes record-aware
      extraction from a hardcoded `aiwork/<task_name>` guess.
   f. **Legacy route — the successful path, end to end.** Step (c) only proves
      the *refusal* branch; this proves the branch that actually runs. Set the
      scratch clone up so the two candidate bases **diverge** (`main` and
      `develop` at different commits) — without divergence the final assertion
      cannot discriminate and would pass vacuously.
      1. Write a plan file with frontmatter that has **no** `Base branch:` line.
      2. Run Re-entry Routing's resolution snippet (`SKILL.md:259-264`) verbatim
         against it. Assert `base_branch=main` **and**
         `provenance_base="legacy plan, no Base branch field"` — this is the
         fallback binding a value, which the whole route depends on.
      3. Take the fork block's check 2: with that provenance the route is
         *confirm*, not *cut*. `AskUserQuestion` cannot be scripted, so simulate
         the confirmation by supplying `develop` (deliberately **not** the
         `main` the fallback guessed — if the answer were ignored, the next
         assertion fails).
      4. Write `develop` to the `--base-branch-file` scratch file, then run the
         fork command with the confirmed base. Assert
         `git rev-parse aitask/<task_name>` equals `git rev-parse develop`, not
         `git rev-parse main`. That is the proof the user's answer was honored
         rather than the fallback silently winning.
      5. Run the Step-8 externalize form with `--base-branch-file <f>` against
         that legacy plan and assert the header now reads `Base branch: develop`
         (the persistence step; case 11 covers the same splice at helper level).
      6. Re-run the snippet from (2) on the updated plan. Assert it now yields
         `develop` with `provenance_base="plan header"` — the task is no longer
         legacy, closing the round trip.
   Record the transcript summary in the Final Implementation Notes. A step that
   cannot be run must be reported as not-run, never as passed.

## Verification

Run from the repo root, in this order:

```bash
shellcheck .aitask-scripts/aitask_plan_externalize.sh
bash tests/test_plan_externalize.sh              # new --worktree block + negative control
bash tests/test_skill_render_task_workflow.sh    # golden diffs across 3 profiles
./.aitask-scripts/aitask_skill_verify.sh         # stub-surface / closure integrity
bash tests/test_no_raw_tmux.sh                   # untouched, cheap regression guard
```

The **live acceptance run of the path this session cannot exercise** is the
`exercise_worktree_profile_live` post-phase above — the active profile is `fast`
(`create_worktree: false`), so nothing in the normal flow executes the new fork
block. Its steps (b)-(d) are the acceptance evidence for AC3 and AC4.

Doc build (`cd website && hugo build --gc --minify`) if the website edits touch
anything beyond prose.

## Risk

Levels below are the **post-inline reassessment** — they describe the plan as
approved (implementation body + the two mitigation phases), not the
pre-insertion plan.

### Code-health risk: medium

- The change is spread across 6 skill/procedure files, 1 shell helper, 3 website
  pages and ~6 regenerated goldens; most of it is **prose that no test
  executes** — goldens pin bytes, not semantics, so a logically wrong
  instruction renders and diffs cleanly · severity: medium (unmitigated —
  inherent to editing a prose workflow) · → mitigation: none
- Deleting the `-d "aiwork/…"` probe removes a fallback: any externalize call in
  worktree mode that forgets `--worktree` omits the header field that Step 9 and
  Re-entry Routing depend on · severity: low (residual — the caller audit bounds
  the exposure to one prose contract, the new stderr warning makes a forgotten
  flag loud rather than silent, and inline pre-phase
  `pin_worktree_header_matrix` proves the probe's removal with a control
  observed failing first) · → mitigation: inline pre-phase pin_worktree_header_matrix
- No shipped profile sets `create_worktree: true` (`fast` sets it false;
  `default`/`remote` leave it undefined), so neither this session nor the test
  suite ever runs the new fork block end to end · severity: medium (residual —
  addressed by inline post-phase `exercise_worktree_profile_live`, which runs
  the rendered block in a scratch clone; still a one-off manual execution, not a
  suite regression guard) · → mitigation: inline post-phase exercise_worktree_profile_live

### Goal-achievement risk: medium

- **The fork base can differ from the base the plan records or the drift check
  validated.** t1277 makes the header carry the Step-5 resolved base, but
  nothing reconciles the three values (Step-5 context, plan header, base HEAD at
  cut time), and the Step 7 ownership guard sits between the drift check and the
  fork without locking `<base>` · severity: medium (residual — step 1(c)'s three
  ordered checks fail closed on an unbound base, confirm a legacy `main`
  fallback with the user instead of cutting from it, and reconcile the *name*
  against the header; step 11 spins off the *HEAD-movement* detector the task's
  Non-goals asked for. None of these is a lock, so a concurrent commit to
  `<base>` inside the guard window is still possible)
  · → mitigation: none (plan steps 1(c) and 11)
- **A reused worktree could be detected but worked in from the wrong
  directory.** The reuse check matches a branch record; the directory must come
  from the same record, not from a guessed `aiwork/<task_name>` · severity: low
  (residual — step 1(c) uses record-aware `awk` extraction and the post-phase's
  `git worktree move` re-run is the control that a hardcoded guess would fail)
  · → mitigation: none (plan step 1(c) + post-phase step (e))
- Moving the fork changes which workflow exits leave a worktree behind. Several
  consumers assume the Step-5 fork (Check 3 manual verification, task-abort,
  crash-recovery, Re-entry Routing, Step 9's merge pre-flight); missing one
  leaves a path that either strands or lacks a worktree with no error
  · severity: low (residual — addressed by inline pre-phase
  `audit_deferred_fork_consumers`, whose three-disposition table has no "not
  considered" slot) · → mitigation: inline pre-phase audit_deferred_fork_consumers
- Two ACs (6 and 10) rest on premises that proved false, so their delivered form
  is a judgement call rather than a literal implementation · severity: low
  · → mitigation: none (stated explicitly above and confirmed at review)

### Planned mitigations
- timing: pre-phase | name: pin_worktree_header_matrix | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — probe removal silently omits the Worktree header | desc: Write the Worktree emission-matrix tests and observe the negative control fail against the unmodified helper before touching build_header().
- timing: pre-phase | name: audit_deferred_fork_consumers | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a consumer of the Step-5 fork is missed | desc: Enumerate every consumer assuming the Step-5 fork and record each one's post-change disposition (updated / improved / unchanged no-op) as a cited table in the plan.
- timing: post-phase | name: exercise_worktree_profile_live | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — no shipped profile exercises the new fork block | desc: In a scratch clone with a synthetic create_worktree:true profile, run the rendered Step 7 fork block and its reuse check for real, proving both the fresh-cut and reuse branches.

No **new** risks are introduced by the augmented plan: both phases are
read-only or test-only additions that touch no production path.
