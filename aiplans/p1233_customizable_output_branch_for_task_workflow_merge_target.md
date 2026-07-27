---
Task: t1233_customizable_output_branch_for_task_workflow_merge_target.md
Base branch: main
plan_verified: []
---

# t1233 — Customizable output branch for the task-workflow merge target

## Context

The task-workflow lets a user control the branch a task worktree is **created
from** (`base_branch`, resolved at Step 5) but not the branch the finished work
is **merged into**. The merge target is hardcoded in the canonical Jinja source
`.claude/skills/task-workflow/SKILL.md`:

| Line | Text |
|------|------|
| 291 | `Where `<base-branch>` is `main` or the user-specified branch.` (Step 5 prose) |
| 579 | `"Proceed with merge of code changes to main branch?"` (merge-approval prompt) |
| 590 | `- **Merge branch into main:**` |
| 592 | `git checkout main` |

There is no variable and no read-back of the `Base branch:` value already
recorded in the plan metadata header. A project that bases worktrees on a
long-lived integration branch still gets its work merged into `main`. The
motivating case: a repo whose `main` is the production branch (a GitHub Release
from `main` auto-deploys) wants all task work to land on `dev`. The only
workarounds today are `create_worktree: false` (giving up worktree isolation) or
an advisory `CLAUDE.md` override the skill text contradicts.

**Outcome:** an `output_branch` execution-profile key that is a first-class,
separately configurable merge target, defaulting to the resolved `base_branch`
so existing behaviour is unchanged.

### The fact that shapes the design

**`planning.md` is not the writer of the plan header.** The `Base branch:` line
is emitted by `.aitask-scripts/aitask_plan_externalize.sh:311`
(`echo "Base branch: $primary"`, `primary=$(detect_primary_branch)`), inside
`build_header()`. The templates at `planning.md:375-396` are documentation plus
the manual-fallback format. Recording `Output branch:` therefore requires a
script change, not only a template edit — the task's "Files in scope" list misses
this file.

### Decisions taken with the user

- **Unset `output_branch` ⇒ silent fallback to the resolved `base_branch`. No
  new `AskUserQuestion` is added anywhere.** (The task text proposed a
  "profile-key-else-AskUserQuestion" pattern, which contradicts its own
  acceptance criterion "behaviour is byte-identical to today". The AC wins.)
- **`Output branch:` is always recorded in the plan header**, even when derived —
  including on the already-has-frontmatter input path (§1).
- **The remote drift check is extended** to also watch the output branch, but
  only when it differs from the base branch.
- **Legacy plans fall back to `main`, never to `Base branch:`.** A plan written
  before this feature has no `Output branch:` line. Resolving such a plan through
  `Base branch:` would change its merge target retroactively — an in-flight
  POSTIMPL plan recording `Base branch: develop` historically merged to `main`
  and would now merge to `develop`. That breaks both the re-entry "re-merge is a
  git no-op" property and the unset-behaviour criterion. The two-rung chain
  (`Output branch:` → `main`) keeps legacy plans byte-identical to today, and is
  safe precisely because every newly created plan records the line.

### Consequence deliberately *not* taken

Because the fallback stops at `main`, a `master`-primary repo whose plan predates
this change still hits today's failing `git checkout main` at Step 9. That is
pre-existing and stays out of scope; new plans on such a repo record
`Output branch: master` and work.

### Non-goals (declared, not overlooked)

1. **The header's `Base branch:` still records `detect_primary_branch()`, not the
   profile's `base_branch`.** That mismatch is pre-existing and independent: a
   `base_branch: develop` profile already records `Base branch: main` today, and
   `remote-drift-check.md:9` already reads the wrong value. Fixing it here would
   change drift behaviour for existing users and mix a behaviour change into an
   additive task. Leaving it is **strictly non-regressive** — the new
   `Output branch:` line is written independently, so Step 9 still merges to the
   right place. Split out as a follow-up.
2. **Step 9 does not push the merged output branch.** It pushes only
   `./ait git push` (task-data scoped, `lib/task_utils.sh:215`). Byte-identical
   to today.
3. **`aitask-web-merge` still merges to `main`** (`.claude/skills/aitask-web-merge/SKILL.md:69`).
   It is a separate branch-reconciliation skill, not part of the task-workflow
   Step 9 path.
4. **Nothing detects sibling child tasks resolving different output branches**
   across sessions run under different profiles.

---

## Implementation

### 1. `.aitask-scripts/aitask_plan_externalize.sh` — record the output branch

One new optional flag. Additive: when it is not passed, the emitted header gains
one line whose value equals today's `Base branch:` value.

New initialiser next to `FORCE=false` (~line 82):

```bash
OUTPUT_BRANCH_OVERRIDE=""
```

Arg parsing, after the `--internal` case (~line 88):

```bash
        --output-branch)
            [[ $# -ge 2 ]] || die "--output-branch requires a branch argument"
            OUTPUT_BRANCH_OVERRIDE="$2"
            shift 2
            ;;
```

In `build_header()` (~line 311), directly after the existing `Base branch:` line
and before `plan_verified:`:

```bash
    echo "Base branch: $primary"
    echo "Output branch: ${OUTPUT_BRANCH_OVERRIDE:-$primary}"
```

Leave the `Branch:` line's `"$current_branch" != "$primary"` guard alone — it is
about the current checkout, not the base. `aitask_plan_verified.sh` parses the
header by key (`:84-158`), not positionally, so inserting a line is safe.

**The already-has-frontmatter path must also record the line.** `build_header()`
is skipped entirely when the source plan already opens with `---`
(`aitask_plan_externalize.sh:317-325`), so on that supported input path
`--output-branch dev` would be accepted and silently dropped — and Step 9 would
then merge somewhere else. Since the whole two-rung fallback in §4 rests on "every
new plan records the line", this is fixed here, not deferred. After the copy, when
`--output-branch` was passed and the target has frontmatter, splice the field into
the existing block:

```bash
splice_output_branch() {   # <file> <branch>
    # Replace an existing `Output branch:` line inside the leading frontmatter,
    # or insert one immediately before its closing `---`. No-op when the file
    # does not open with `---`. Writes via mktemp + mv, as build_header does.
}
```

Contract, pinned by tests:

- existing `Output branch:` line in the source frontmatter → **replaced**;
- absent → **inserted** before the closing `---`;
- the `^---$` count stays `2` (the invariant Test 7 already asserts);
- no frontmatter → no-op (the `build_header()` path already covered it);
- `--output-branch` not passed → no-op (no silent rewrite of an existing plan).

Update the file-header usage comment (lines 12-17) and the `usage()` heredoc
(lines 58-75).

### 2. `.claude/skills/task-workflow/SKILL.md` Step 5 — resolve `output_branch`

Insert a new Jinja block immediately after the `base_branch` block (after line
280), inside the **If Yes** (worktree) branch. Follow the comment convention in
`aidocs/framework/skill_authoring_conventions.md` — separator on the same line as
`{% if %}`, inline comments on `{% else %}` / `{% endif %}`:

```jinja
{# ---------- output_branch ---------- #}{% if profile.output_branch is defined %}
- Use output branch `{{ profile.output_branch }}` as the merge target for this task. Display: "Profile '{{ profile.name }}': using output branch {{ profile.output_branch }}".
{% else %}{# output_branch: key absent from profile #}
- **Profile check:** If the active profile has `output_branch` set, use it as the merge target and display: "Profile '\<name\>': using output branch \<branch\>". Otherwise the merge target is the base branch resolved above — **do not ask**; there is no separate question for the merge target.
{% endif %}{# ---------- end output_branch ---------- #}
```

Also fix line 291's hardcoded `main`, which survives **both** arms of the
`base_branch` conditional:

```markdown
  Where `<base-branch>` is the base branch resolved above.
```

**`create_worktree: false` is explicit:** the block lives in the "If Yes" arm, so
no output branch is resolved on current-branch profiles (`fast`). Step 9's merge
section is likewise gated on `**If a separate branch was created:**` (line 565),
so there is nothing to merge. Step 6 then omits `--output-branch` and the header
records the detected primary for both fields — the "always recorded" decision is
satisfied by the helper's default, not by a resolved value.

### 3. Step 6/8 — thread the output branch into *both* externalize calls

`.claude/skills/task-workflow/plan-externalization.md` — the flag must be
documented **once in the Procedure section as always-passed when known**, not
per-call-site. The Step 8 form (line 31) is the reactive fallback invoked from
`SKILL.md:459`, and it is the *only* call that builds the header when Step 6 was
skipped or returned `NOT_FOUND`. Threading the flag into Step 6 alone would let
Step 8 overwrite `output_branch: dev` with the detected primary — and Step 9 runs
immediately after Step 8 and reads that header.

```bash
# Step 6 (proactive, after ExitPlanMode)
./.aitask-scripts/aitask_plan_externalize.sh <task_id> --force --output-branch "<output_branch>"

# Step 8 (safety fallback, idempotent)
./.aitask-scripts/aitask_plan_externalize.sh <task_id> --output-branch "<output_branch>"
```

Add a sentence: pass `--output-branch` whenever Step 5 resolved one (worktree
mode). In current-branch mode omit it — the helper records the detected primary,
exactly as today.

`.claude/skills/task-workflow/planning.md` — add `Output branch: main` after
`Base branch: main` in **both** metadata header templates (lines 381 and 394).

`.claude/skills/task-workflow/planning-cross-repo.md:26` — the context table
lists `base_branch` as "standard workflow context". Add an explicit note that
`output_branch` is **not** inherited by cross-repo children: they live in a
different repo whose primary branch may differ, so a parent-profile
`output_branch` would be actively wrong there.

### 4. Step 9 — consume the output branch

`.claude/skills/task-workflow/SKILL.md`, under `**If a separate branch was
created:**` (line 565), before the NON-SKIPPABLE banner:

```markdown
- **Resolve the merge target.** Read the plan file's metadata header:
  1. `Output branch: <branch>` present → that is the merge target (provenance: `plan header`).
  2. Otherwise → `main` (provenance: `legacy plan, no Output branch field`).

  Do **not** fall back to `Base branch:`. A plan written before this field
  existed merged to `main`, and reading its `Base branch:` would retroactively
  change where in-flight work lands.

  Call the resolved value `<output_branch>`. Resolve it **only** from the plan
  header — never from `profile.output_branch`. A resumed session (POSTIMPL
  re-entry) may run under a different profile, and the header is what guarantees
  it merges into the same branch the original session did, keeping the "re-merge
  is a git no-op" property this workflow relies on.

- **Pre-flight the merge target.** Run from the repo root, not from
  `aiwork/<task_name>/`. Before asking for approval:

  ```bash
  # 1. It must exist as a LOCAL BRANCH — not a tag, remote-tracking ref, or SHA.
  git rev-parse --verify --quiet "refs/heads/<output_branch>" || echo "MISSING"

  # 2. If another worktree holds it, checkout will refuse.
  git rev-parse --show-toplevel        # the worktree we are operating in
  git worktree list --porcelain        # records: `worktree <path>` … `branch refs/heads/<b>`
  ```

  - **Fully-qualify the ref.** A bare `<output_branch>` resolves through the
    gitrevisions order, which places `refs/tags/<name>` *above*
    `refs/heads/<name>`. A tag named `dev` would pass a bare
    `git rev-parse --verify dev`, and the subsequent `git checkout dev` lands in
    **detached HEAD** — the merge then commits onto no branch at all and the
    output branch never moves. Verified: with only a tag `dev`,
    `git rev-parse --verify --quiet dev` succeeds while
    `refs/heads/dev` is correctly absent, and `git symbolic-ref --short HEAD`
    after checkout reports detached.
  - **Branch missing locally** (`MISSING`) → **stop and ask** the user (fetch or
    create it, pick a different target, or abort). Do not let `git checkout` DWIM
    a tracking branch into existence unnoticed.
  - **Held by another worktree** → parse the `worktree <path>` of the record
    whose `branch` is `refs/heads/<output_branch>` and compare it to
    `git rev-parse --show-toplevel`. **Reject only when the paths differ.** The
    repo root is itself listed in `git worktree list --porcelain`, so an
    unqualified match would stop the workflow whenever the root is already on the
    output branch — exactly the case where checkout is a safe no-op. When they
    differ, `git checkout` fails with `fatal: '<branch>' is already used by
    worktree at …`; surface that and ask rather than failing mid-merge (likely
    for a shared `dev` in this worktree-heavy workflow).
```

Then the three replacements — note the checkout gains a HEAD assertion:

- Line 579 → `"Proceed with merge of code changes into the` `` `<output_branch>` ``
  `branch (<provenance>)?"`. The branch name **and** its provenance live in the
  `question` text, per the AskUserQuestion-visibility rule in
  `aidocs/framework/skill_authoring_conventions.md`. Naming a guessed `main`
  without flagging it as a guess would miss the intent of acceptance criterion
  (iii).
- Line 590 → ``- **Merge branch into `<output_branch>`:**``
- Line 592 → switch to the branch, then **confirm HEAD is symbolic and points at
  it before merging** — this is what makes the detached-HEAD failure mode
  impossible rather than merely unlikely:
  ```bash
  git checkout <output_branch>
  git symbolic-ref --short HEAD    # MUST print <output_branch>; if not, stop — do not merge
  git merge aitask/<task_name>
  ```

Two things stay untouched, deliberately:

- **The NON-SKIPPABLE banner (lines 567-577) is byte-identical.** `output_branch`
  selects the *target*; it is not a bypass key, so the load-bearing
  "currently: none" opt-out list stays accurate.
- **`git branch -d aitask/<task_name>` (line 644) is already correct.** `-d`
  checks merged-into-HEAD, and HEAD is the output branch after the merge.

No Jinja in Step 9: the value is runtime data from the plan header, so Step 9
stays profile-invariant and all three `SKILL-*.md` goldens take the identical
diff.

### 5. `.aitask-scripts/aitask_remote_drift_check.sh` — an unsynced-branch mode

The helper short-circuits on line 3 of its real work:

```bash
_ait_detect_data_worktree
if [[ "$_AIT_DATA_WORKTREE" == "." ]]; then
    debug "legacy mode: task data on same branch as code, task_sync() already pulled"
    echo "LEGACY_MODE_SKIP"
    exit 0
fi
```

That premise is sound for the base branch and **false for the output branch**.
In legacy mode `task_sync()` runs a bare `git pull --rebase`
(`lib/task_utils.sh:186`) — it refreshes the *current* branch only. A separate
`dev` merge target is never checked out during implementation and never pulled,
so it can be arbitrarily stale. Without a bypass, every legacy-mode project
(a supported, common configuration) gets `LEGACY_MODE_SKIP` before either branch
is examined and the promised output-branch coverage silently does nothing.

Add an opt-in flag — named for the property it asserts, not for its caller:

```
--unsynced    Skip the legacy-mode short-circuit. Pass this for a branch the
              workflow has not pulled (the Step 9 output branch is never checked
              out during implementation), where the shortcut's premise —
              task_sync() already refreshed this branch — does not hold.
```

Only the short-circuit is skipped; everything after it (`NO_REMOTE`, the fetch,
`AHEAD:` / `UP_TO_DATE` / `FETCH_FAILED`, overlap detection) is unchanged and
already works in legacy mode. **The base-branch pass never passes the flag**, so
`LEGACY_MODE_SKIP` still fires for it exactly as today.

(One precision: §5a below does change which *token* the base pass emits when the
local base branch is absent — `LOCAL_BRANCH_MISSING` instead of `FETCH_FAILED`
or `NO_REMOTE`. Observable behaviour is unchanged, because §5b maps all three to
"return, no display" on the base pass. Nothing else about the base pass moves.)

#### 5a. A dedicated `LOCAL_BRANCH_MISSING` signal

`FETCH_FAILED` is currently emitted from **two** unrelated rungs: the fetch
wrapper (network timeout `124`, auth failure, branch absent on the remote) and
the `git rev-list` rung whose debug string guesses `"local '$BASE_BRANCH' likely
missing"`. Treating that one token as proof the local branch is absent would fire
a false *"the Step 9 merge will fail"* warning on any flaky network — pushing the
user toward "Stop and re-verify plan" when the local branch exists and can
receive the merge perfectly well.

Add a distinct, unambiguous signal, derived from a check that does not depend on
the network at all:

```bash
LOCAL_BRANCH_MISSING
```

emitted when `git rev-parse --verify --quiet "refs/heads/<branch>"` fails — the
same `refs/heads/` qualification the Step 9 pre-flight uses in §4, so a tag of
the same name cannot satisfy either check.

**Ordering is load-bearing:**

```
legacy short-circuit  →  [new] LOCAL_BRANCH_MISSING  →  NO_REMOTE  →  fetch  →  AHEAD/UP_TO_DATE/FETCH_FAILED
```

- **Before `NO_REMOTE`.** The check needs no network, and a repo with no `origin`
  *and* no local output branch is a guaranteed Step 9 failure — the one case
  where the warning matters most. Letting `NO_REMOTE` win there would return
  silently and lose it.
- **Before the fetch.** A genuine network failure can then neither masquerade as
  nor mask an absent branch. When both are true `LOCAL_BRANCH_MISSING` wins,
  correctly: the merge fails regardless of the network.
- **After the legacy short-circuit.** The base pass in legacy mode must keep
  emitting `LEGACY_MODE_SKIP` (Test 1, unchanged). The output pass reaches the
  new check anyway, because `--unsynced` skips that short-circuit.

The check is placed here **unconditionally**, not only on the `--unsynced` path.
Branching the order on a flag would mean two code paths and two sets of
expectations for one helper, and it buys nothing: §5b maps both
`LOCAL_BRANCH_MISSING` and `NO_REMOTE` to a silent return on the base pass, so
the base pass has no observable change either way.

The `rev-list`-empty rung keeps emitting `FETCH_FAILED` as a defensive case
(`origin/<b>` absent after a *successful* fetch); it is no longer the
"local missing" path.

**Two existing fixtures are broken and must be repaired, not designed around.**
Tests 2 (`NO_REMOTE`) and 6 (`FETCH_FAILED`) both build a repo with
`make_legacy_mode_repo()`, whose branch follows `init.defaultBranch` — `master`
on this machine — then invoke the helper with a hardcoded `main` that does not
exist locally. They pass today only because `NO_REMOTE` / `FETCH_FAILED` are
reached before anything inspects the branch: each asserts a signal for a repo
where the requested branch is absent, i.e. for the wrong reason. Point both at
the fixture's real default branch so they exercise "no origin" and "unreachable
origin" with a branch that actually exists.

`FETCH_FAILED` therefore returns to meaning exactly one thing — *we could not
reach the remote* — and stays silent, best-effort, on both passes.

### 5b. `.claude/skills/task-workflow/remote-drift-check.md` — cover both branches

- **Input table** (after line 9): add
  `` | `output_branch` | string | Merge target, resolved from the plan header by the *same* two-rung rule Step 9 uses: `Output branch:` when present, otherwise `main`. Never `base_branch` | ``

  This must match §4 exactly. Resolving it to `base_branch` here while Step 9
  resolves it to `main` would make the procedure check a branch the workflow is
  not going to merge into.
- **Step 2:** run the helper for `<base_branch>` as today; then, **only if
  `<output_branch>` differs**, run it a second time **with `--unsynced`**:

  ```bash
  ./.aitask-scripts/aitask_remote_drift_check.sh --unsynced "<output_branch>" "<plan_file>"
  ```
- **Step 3:** label every display with the branch of the run being parsed, rather
  than always `<base_branch>`. Two signal rules, kept strictly separate:

  | Signal | Base pass | Output pass |
  |---|---|---|
  | `LOCAL_BRANCH_MISSING` | return, no display (as today) | **warn:** "output branch `<b>` is not present locally — the Step 9 merge will fail" |
  | `FETCH_FAILED` | return, no display | **return, no display** — genuine network/auth failure stays silent best-effort; it is *not* evidence about the local branch |
  | `NO_REMOTE` | return, no display | return, no display — it can no longer mask an absent branch, since §5a is checked first |

  The warning is the highest-value output of this whole procedure: it converts a
  mid-workflow Step 9 hard failure into a planning-time notice. Which is exactly
  why it must not also fire on a flaky network — a warning that cries wolf on
  every timeout would train users to click past it.

  `LEGACY_MODE_SKIP` can no longer occur on the output pass (§5), so it needs no
  handling rule beyond the shared list.
- **Single prompt:** collect the results of both passes first, present them
  together, then ask the step-4 `AskUserQuestion` **once**. Two independent runs
  must never produce two prompts whose answers can conflict.
- **Step 5** "Stop and re-verify plan": the message at line 68 names the branch
  (or branches) that actually drifted.

No profile conditional is added, so the file stays profile-invariant and keeps
its single `remote-drift-check-default.md` golden plus the Test 1b byte-equality
assertion.

`.claude/skills/task-workflow/planning.md` — the three Remote Drift Check call
sites (lines 425, 434, 449) now pass `base_branch`, `output_branch`, `plan_file`,
`active_profile`.

### 6. `.aitask-scripts/lib/profile_editor.py` — three parallel tables

```python
    "base_branch": ("string", None),
    "output_branch": ("string", None),            # PROFILE_SCHEMA, after line 53
```

```python
    "output_branch": (                            # PROFILE_FIELD_INFO, after line 140
        "Branch that finished work is merged into (defaults to base_branch)",
        "Only used when create_worktree is true. Specifies the branch the task "
        "branch is merged into at Step 9 (post-implementation). When unset, the "
        "resolved base_branch is used, so work lands where it was branched from. "
        "Set it when the merge target differs from where task branches are cut "
        "— e.g. base_branch: main with output_branch: dev."
    ),
```

```python
    ("Branch & Worktree", ["create_worktree", "base_branch", "output_branch"]),
```

All three are required: a key missing from `PROFILE_FIELD_GROUPS` is silently
never rendered (`profile_editor.py:581-586`), and **no test catches a missed
table** (`tests/test_profile_editor_rendered_gates.py:41-42` asserts only
`rendered_gates`).

### 7. Schema documentation

- `.claude/skills/task-workflow/profiles.md` — new row after line 29:
  `` | `output_branch` | string | no | Merge target for Step 9 (e.g., `"dev"`); omit to merge into the resolved `base_branch` | Step 5 (resolve), Step 9 (merge) | ``
  plus a second example after the existing one (lines 113-124):

  ```yaml
  name: integration
  description: Cut task branches from main, merge finished work into dev
  create_worktree: true
  base_branch: main
  output_branch: dev
  ```

- `.claude/skills/aitask-pickrem/SKILL.md.j2:548` — ignored-fields line gains
  `output_branch`.
- `.claude/skills/aitask-pickweb/SKILL.md.j2:348` — same.

### 8. Website docs

Pattern: wherever `base_branch` is listed, `output_branch` follows it.

- `website/content/docs/skills/aitask-pick/execution-profiles.md` — table row
  after line 27; `output_branch: dev` in the example YAML (lines 57-58).
- `website/content/docs/tuis/settings/reference.md` — row after line 112.
- `website/content/docs/tuis/settings/_index.md:98` — `**Branch & Worktree** --
  create_worktree, base_branch, output_branch`.
- `website/content/docs/skills/aitask-pickrem.md:90` and
  `website/content/docs/skills/aitask-pickweb.md:103` — ignored-key lists.
- `website/content/docs/workflows/parallel-development.md:20` — "merged back to
  main" → merged back into the configured output branch.

`website/content/docs/concepts/execution-profiles.md:11` is an explicitly partial
"for example" enumeration — left alone. Per
`aidocs/framework/documentation_conventions.md`, all prose describes the current
state only.

### 9. Tests

`tests/test_plan_externalize.sh` (extend; `run_externalize` at `:60-66` already
forwards extra args):

- Test 1: assert `Output branch:` is present and equals the `Base branch:` value.
- New: `--output-branch dev` ⇒ `Output branch: dev` with `Base branch:` unchanged.
- New: `--output-branch` with no argument ⇒ non-zero exit (`die`).
- Test 13 (master-primary repo): also assert `Output branch: master`.
- **Test 7 (already-has-frontmatter) extended** — this is the regression test for
  the splice path, so it grows rather than a new test being bolted alongside:
  - source with frontmatter + `--output-branch dev` ⇒ `Output branch: dev`
    present **and** `^---$` count still `2`;
  - source whose frontmatter already carries `Output branch: old` ⇒ replaced with
    `dev`, still exactly one such line;
  - source with frontmatter and **no** `--output-branch` ⇒ file unchanged
    (negative control: no silent rewrite).

`tests/test_remote_drift_check.sh` — extend around the existing
`make_legacy_mode_repo()` fixture (`:49`) and Test 1 (`:96-106`):

- **Negative control (unchanged base pass):** legacy repo, no flag ⇒ still
  `LEGACY_MODE_SKIP`. This is Test 1 as it stands; keep it green.
- **New — distinct output branch in legacy mode:** legacy repo with an `origin`
  whose `dev` is ahead of the local `dev`, invoked as
  `--unsynced dev <plan>` ⇒ must **not** return `LEGACY_MODE_SKIP`, and must
  report `AHEAD:<n>`. Without this test the bypass is unproven exactly where it
  matters.
- **New — flag is branch-agnostic:** legacy repo, `--unsynced main <plan>` where
  local `main` is up to date ⇒ `UP_TO_DATE`, proving the flag skips only the
  short-circuit and does not otherwise alter the result.
- **New — missing local output branch:** branch-mode pair,
  `--unsynced nosuchbranch <plan>` ⇒ `LOCAL_BRANCH_MISSING`, the signal §5b turns
  into the "not present locally" warning.
- **New — legacy mode + missing branch:** legacy repo, `--unsynced nosuchbranch`
  ⇒ `LOCAL_BRANCH_MISSING` (proves the bypass and the new signal compose).
- **New — no remote + missing output branch:** branch-mode-marked repo with **no
  `origin` at all**, `--unsynced nosuchbranch <plan>` ⇒ `LOCAL_BRANCH_MISSING`,
  explicitly **not** `NO_REMOTE`. This is the case the ordering exists for: no
  network is needed to know Step 9 will fail, and the old order lost it.
- **New — false-warning regression guard (the point of §5a):** branch-mode pair
  whose local branch **exists**, with an unreachable `origin` URL, invoked
  `--unsynced <existing_branch> <plan>` ⇒ `FETCH_FAILED`, and explicitly **not**
  `LOCAL_BRANCH_MISSING`. Without this assert, the two signals can silently
  collapse back into one.
- **Tests 2 and 6 repaired.** Both pass a hardcoded `main` to a
  `make_legacy_mode_repo()` fixture whose branch is `master` (this machine's
  `init.defaultBranch`), so each asserts its signal for a repo where the
  requested branch does not exist — passing for the wrong reason. Point both at
  the fixture's real default branch (as `make_branch_mode_pair()` already does,
  returning `root|default_branch`) so Test 2 asserts `NO_REMOTE` and Test 6
  asserts `FETCH_FAILED` with a branch that actually exists. Test 1
  (`LEGACY_MODE_SKIP`) is unaffected — the short-circuit still precedes the new
  check.
- `--unsynced` accepted in any position relative to the positionals (the parser
  already handles interleaved flags).

`tests/test_skill_render_task_workflow.sh`:

- Test 3: assert the default render carries the output-branch fallback prose, and
  that no new AskUserQuestion text was introduced.
- New synthetic-profile test in the style of the existing Test 4
  (`remote_drift_check: skip` temp profile): a temp profile with
  `output_branch: dev` must render `using output branch dev` and must **not**
  render the fallback prose.

`tests/test_skill_parity_runtime_vs_rendered.sh` needs no new rows — its scope is
the frozen pre-rewrite fixture, where `output_branch` does not exist. Add one
line to the "Coverage decisions" comment (`:22-31`) recording that.

### 10. Regeneration (same commit as the source edits)

- `./.aitask-scripts/aitask_skill_rerender.sh remote` — refreshes the 9
  git-tracked `*-remote-*` dirs (`task-workflow`, `aitask-pickrem`,
  `aitask-pickweb` × claude/codex/opencode). Skipping this makes
  `aitask_skill_verify.sh` fail with `PRERENDER_FAIL` (`:174-176`) — that is the
  enforcement for acceptance criterion (iv). Note it does **not** refresh the
  untracked local `-default-` / `-fast-` / `_skillrun_*` closures, so the
  implementing agent's own skill tree stays stale for the rest of the session.
- Regenerate goldens and **review the diff** rather than rubber-stamping it (the
  merge lines sit at different offsets in each `SKILL-*.md` — regenerate, never
  hand-patch):
  - `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`
  - `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md`
  - `tests/golden/procs/task-workflow/remote-drift-check-default.md`
  - `tests/golden/procs/task-workflow/planning-cross-repo-default.md`
  - `tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md`
  - `tests/golden/skills/aitask-pickweb/SKILL-remote-claude.md`

No new helper script is introduced, so no whitelist entries change and
`aitask-audit-wrappers` is a no-op. Both modified scripts are already permitted
by prefix/glob patterns that cover new flags — `Bash(…aitask_plan_externalize.sh:*)`
and `Bash(…aitask_remote_drift_check.sh:*)` in `seed/claude_settings.local.json`,
with the matching `prefix_rule` / `"… *"` forms in the Codex and OpenCode seeds. Step 9 reads the plan header in prose,
symmetric with how `remote-drift-check.md` already consumes `Base branch:`. No
cross-agent port task is needed: `task-workflow/` files and the pickrem/pickweb
`.j2` templates are render-closure sources regenerated by the rerender above.

---

## Verification

```bash
# 1. Shell lint + unit tests
shellcheck .aitask-scripts/aitask_plan_externalize.sh .aitask-scripts/aitask_remote_drift_check.sh
bash tests/test_plan_externalize.sh

# 2. Render / golden / parity suite
bash tests/test_skill_render_task_workflow.sh
bash tests/test_skill_parity_runtime_vs_rendered.sh
bash tests/test_remote_drift_check.sh

# 3. Template + stub-surface verification (re-checks the committed remote
#    closure is not stale) — the enforcement for criterion (iv)
./.aitask-scripts/aitask_skill_verify.sh
```

**End-to-end acceptance checks**

1. **`output_branch` honoured (criterion i).** Scratch profile
   `aitasks/metadata/profiles/local/t1233.yaml` with `create_worktree: true`,
   `base_branch: main`, `output_branch: dev`:
   ```bash
   ./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile t1233 --agent claude
   grep -n "using output branch dev" .claude/skills/task-workflow-t1233-/SKILL.md
   ```
   Plus the header round-trip in a sandbox:
   ```bash
   ./.aitask-scripts/aitask_plan_externalize.sh <id> --force --output-branch dev
   grep -E '^(Base|Output) branch:' aiplans/p<id>_*.md   # → main / dev
   ```
   And the frontmatter path, which is the one that used to drop the flag:
   ```bash
   printf -- '---\nTask: t<id>_x.md\n---\n\n# body\n' > "$INTERNAL/p.md"
   ./.aitask-scripts/aitask_plan_externalize.sh <id> --force --output-branch dev
   grep -c '^---$' aiplans/p<id>_*.md        # → 2
   grep -c '^Output branch: dev$' aiplans/p<id>_*.md   # → 1
   ```

   **Honest limitation:** the suite proves the key renders and the header
   round-trips on both input paths; it does not perform a real `git merge` into a
   non-`main` branch. That last hop is verified by reading, and is the subject of
   the confirmed `manual_verify_output_branch_merge` follow-up.

2. **Unset ⇒ unchanged (criterion ii).** `git diff` the regenerated
   `SKILL-fast.md` golden: the only Step 9 changes are the `main` →
   `<output_branch>` substitutions plus the resolve/pre-flight bullets. No new
   question, no new profile branch. Specifically confirm the resolve bullet has
   **no `Base branch:` rung** — a legacy plan (no `Output branch:` line) must
   still resolve to `main`:
   ```bash
   grep -A4 'Resolve the merge target' tests/golden/procs/task-workflow/SKILL-fast.md
   ```

2b. **Pre-flight rejects a tag (criterion iii's failure mode).** In a scratch
   repo with a tag `dev` and no branch `dev`, the prescribed
   `git rev-parse --verify --quiet refs/heads/dev` must fail where the bare form
   succeeds — the check the plan text mandates is the one that catches it.

3. **Prompt names the real target (criterion iii).**
   ```bash
   grep -rn "merge of code changes to main branch" .claude/skills/ .agents/skills/ \
     .opencode/skills/ tests/golden/ | grep -v fixtures/   # → no hits
   ```
   and the rendered prompt carries both `<output_branch>` and its provenance.

4. **All rendered variants agree (criterion iv).** After
   `aitask_skill_rerender.sh remote`, `git status` shows the 9 tracked
   `*-remote-*` dirs updated and `aitask_skill_verify.sh` exits 0.

5b. **Legacy mode really is covered.** The whole point of §5 is that the
   promised output-branch check is not a no-op on legacy-mode projects:
   ```bash
   # in a legacy-mode fixture whose origin/dev is ahead of local dev
   ./.aitask-scripts/aitask_remote_drift_check.sh dev plan.md              # → LEGACY_MODE_SKIP
   ./.aitask-scripts/aitask_remote_drift_check.sh --unsynced dev plan.md   # → AHEAD:<n>
   ```
   The first line is the unchanged base-pass behaviour; the second is the new
   output pass. If both print `LEGACY_MODE_SKIP`, the feature is inert.

5c. **The missing-branch warning does not cry wolf.** The two failure signals
   must stay distinguishable — an existing local branch behind an unreachable
   remote must stay silent:
   ```bash
   # local branch exists, origin URL is bogus
   ./.aitask-scripts/aitask_remote_drift_check.sh --timeout 2 --unsynced master plan.md
   # → FETCH_FAILED   (silent best-effort; NOT LOCAL_BRANCH_MISSING)

   ./.aitask-scripts/aitask_remote_drift_check.sh --unsynced nosuchbranch plan.md
   # → LOCAL_BRANCH_MISSING

   # no origin configured at all, output branch absent
   ./.aitask-scripts/aitask_remote_drift_check.sh --unsynced nosuchbranch plan.md
   # → LOCAL_BRANCH_MISSING   (NOT NO_REMOTE — no network is needed to know
   #                           Step 9 will fail)
   ```

5. **Drift check.** `tests/test_remote_drift_check.sh` passes, including the
   pre-existing Test 1 (`LEGACY_MODE_SKIP` without the flag) as the negative
   control that the base pass is untouched, and the regenerated
   `remote-drift-check-default.md` golden is byte-identical across the three
   profile renders (Test 1b).

---

## Risk

### Code-health risk: medium

- Additive-only in mechanism — two optional CLI flags on existing scripts
  (`--output-branch`, `--unsynced`), each with a preserved default, and an
  `is defined`-guarded profile key so all three shipped profiles render
  identically apart from the new prose block. No new script, so no whitelist
  churn. · severity: low · → mitigation: none
- **The `--unsynced` bypass removes a guard on a supported configuration.** In
  legacy mode the output pass now performs a real `git fetch` where previously
  nothing ran. It is bounded — the flag is opt-in, the base pass never sets it,
  the helper still exits 0 on every network failure, and the pre-existing Test 1
  is retained as the negative control — but it is the one place this change
  makes a previously-inert path do work. · severity: low ·
  → mitigation: none (pinned by the legacy-mode tests in §9)
- **Introducing `LOCAL_BRANCH_MISSING` ahead of `NO_REMOTE` and the fetch changes
  the base pass's emitted token** when the local base branch is absent (it
  previously surfaced as `NO_REMOTE` or `FETCH_FAILED`, depending on the repo).
  Downstream behaviour is identical — §5b maps all three to a silent return on
  the base pass — and it removes a real false-warning path, but it is a widened
  output contract on a shared helper. It also exposed that Tests 2 and 6 were
  passing for the wrong reason, which is a net gain in coverage honesty.
  · severity: low · → mitigation: none (pinned by the §9 signal-separation tests:
  `FETCH_FAILED` and **not** `LOCAL_BRANCH_MISSING` for an existing branch behind
  an unreachable remote, and `LOCAL_BRANCH_MISSING` and **not** `NO_REMOTE` for a
  missing branch in a repo with no origin)
- **Table fanout with no drift guard.** The change touches 3 `profile_editor.py`
  tables + `profiles.md` + 5 website pages + 2 `.j2` ignored-field lines + 6
  goldens. Nothing in `tests/` catches a partially-applied edit, and this is at
  least the third task to hand-edit the same five surfaces.
  · severity: medium · → mitigation: none (accepted; caught by review of the
  regenerated golden diff)
- **Step 9 gains a new runtime failure surface at `git checkout <output_branch>`**
  (name resolving to a tag instead of a branch, branch absent locally, branch held
  by another worktree, wrong cwd). The §4 pre-flight fully-qualifies `refs/heads/`,
  compares worktree paths rather than matching blindly, and asserts symbolic HEAD
  before merging — but the guard is prose, not code.
  · severity: medium · → mitigation: manual_verify_output_branch_merge

### Goal-achievement risk: medium

- **The merge target is resolved by prose instructing an agent to grep a header
  line and apply a 3-level fallback**, at the one site whose failure mode is
  "merged into the wrong branch". The provenance display in the approval prompt
  makes a wrong resolution visible to the user before it lands.
  · severity: medium · → mitigation: manual_verify_output_branch_merge
- **`build_header()` is skipped when the plan source already has frontmatter**
  (`aitask_plan_externalize.sh:317-325`). Addressed in-task by the splice in §1 —
  it is load-bearing, because the two-rung fallback in §4 is only safe if every
  new plan really does record the line. · severity: medium · → mitigation:
  addressed in §1 (splice + extended Test 7)
- **Residual:** a plan first externalized under a current-branch profile records
  `Output branch: <primary>`; if the task is later re-picked under a worktree
  profile whose `plan_preference` is `use_current`, Step 6 may not re-externalize
  and Step 9 would read that stale value rather than the freshly resolved one.
  Narrow (requires a mid-task profile switch) and fails toward today's behaviour.
  · severity: low · → mitigation: none (accepted)
- **The test suite cannot verify criterion (i) end-to-end** — it asserts that
  prose renders and that the header round-trips, never that a real merge lands on
  a non-`main` branch. · severity: medium · → mitigation: manual_verify_output_branch_merge
- The plan header's `Base branch:` still records `detect_primary_branch()` rather
  than the profile's `base_branch` (declared non-goal 1). Non-regressive, but it
  leaves the two header fields derived from different sources.
  · severity: low · → mitigation: plan_header_resolved_base_branch

### Planned mitigations
- timing: after | name: manual_verify_output_branch_merge | type: manual_verification | priority: medium | effort: low | addresses: goal-achievement — the suite cannot verify criterion (i) end-to-end; code-health — the Step 9 checkout pre-flight is prose, not code | desc: Run a real worktree task under a profile setting output_branch to a non-primary branch and confirm the whole chain — Step 5 resolution, the Output branch line in the plan header, the checkout pre-flight (missing branch / branch busy in another worktree), the provenance-bearing merge prompt, and the merge actually landing on the configured branch
- timing: after | name: plan_header_resolved_base_branch | type: bug | priority: medium | effort: medium | addresses: goal-achievement — the plan header records detect_primary_branch() instead of the profile-resolved base_branch, so remote-drift-check watches the wrong branch | desc: Add --base-branch to aitask_plan_externalize.sh and thread the Step 5 resolved base branch through Step 6/8, so Base branch and Output branch in the plan header derive from the same source; update tests/test_plan_externalize.sh Tests 1 and 13 accordingly
