---
Task: t1128_fix_setup_noninteractive_framework_commit_sweep.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: t1128 — Fix `ait setup` commit sweep + Discord silent `attachments` drop

## Context

Two independent, pre-existing defects surfaced during t1074_3's Step 8b review.

**1. `ait setup` sweeps foreign uncommitted work into a framework commit.**
`commit_framework_files()` (`.aitask-scripts/aitask_setup.sh:2592-2754`) does not
know what setup wrote. It rediscovers state from
`git ls-files --others/--modified` over a hardcoded framework-path whitelist, so
`changed_files` is *whatever is dirty right now under those paths* — including a
concurrent session's in-progress edits. Non-interactive callers (`[[ -t 0 ]]`
false — the Bash tool, CI) auto-accept the "Commit framework files to git?"
prompt, so the sweep is silent. This actually happened during t1074_3: running
`ait setup --with-chat` to verify the chat-SDK install committed another
session's `applink/pusher.py`, `monitor_app.py`, etc. as
`ait: Add aitask framework` (91b0c3dfa, reset away).

A second, distinct sweep vector lives on the same path: line 2712 runs a **bare**
`git commit -m "…"` with no pathspec, so any file a developer had *pre-staged*
is swept in too, even if it lies outside the framework whitelist. The twin
`commit_framework_data_files()` (2756-2854) has the same bare commit over the
`.aitask-data` worktree — where concurrent sessions almost always have staged
task files.

**2. `DiscordAdapter.send_message` silently drops `attachments`.**
`.aitask-scripts/chat/discord_adapter.py:812-832` accepts the ABC's `attachments`
parameter and never references it. With `capabilities().supports_files = True`,
a caller sending text + files gets a partial send reported as success. t1074_3
fixed the identical gap for Slack (`slack_adapter.py:906-915`) by raising base
`ChatError` pointing at `upload_attachment`.

**Intended outcome:** `ait setup` commits only the files it itself wrote, leaving
pre-existing dirty paths and any foreign staged index untouched (in *both*
interactive and non-interactive modes); and Discord rejects `attachments` loudly
instead of dropping them.

**Scope decisions (user-confirmed):**
- Fix strategy: **baseline diff**, applied in both modes — not a
  non-interactive-only guard.
- `commit_framework_data_files()` twin: **in scope**.
- `install.sh::commit_installed_files()`: **out of scope** — structurally
  similar, but it is sentinel-gated to non-bootstrap runs and reached via
  `curl|bash` on a fresh install, so the risk is largely theoretical. It is
  recorded as an upstream defect for a follow-up task (Step 8b).

---

## Part 1 — Setup commit sweep

### The core idea

Setup cannot tell "I wrote this file" from "the developer has uncommitted work
here" by looking at the working tree at commit time. It *can* tell by looking
**twice**: snapshot the dirty set **before** setup writes anything, then commit
only `changed_at_commit_time − baseline`. The difference is exactly what setup
produced — derived from an independent observation, not from instrumenting ~44
`cp` sites (there is no write-accumulator today, and adding one would touch every
installer helper plus the `sed`/heredoc writers).

Files in the baseline are **left alone and reported**, never committed. This
fails safe: if setup rewrites a file that was already dirty, that file is
excluded (setup's own change to it goes uncommitted) rather than sweeping the
developer's edit.

### The bootstrap edge case

On a fresh install the *installer* has already placed the framework files on disk
before `ait setup` runs, so at snapshot time they are untracked — they would land
in the baseline and never get committed. The distinguishing predicate is whether
the project has **opted into tracking the framework at all**:

```bash
git rev-parse --verify HEAD &>/dev/null &&
git ls-files --error-unmatch -- .aitask-scripts/VERSION &>/dev/null
```

Reuse `.aitask-scripts/VERSION` — this is already the canonical sentinel in
`install.sh::commit_installed_files()` (`install.sh:812-818`, "projects that want
framework files tracked commit it"). Do not invent a second signal.

When the predicate is false → **bootstrap**: baseline stays empty, everything
under the framework paths is committed. When true → capture the baseline.

**Honest limits of the predicate:** "VERSION not tracked" does **not** prove
there is no foreign work under the framework paths — an existing repo can have a
partial install, a previously-failed setup, hand-copied framework files, or
manual pre-first-commit edits sitting there. The predicate only distinguishes
"this project has opted into framework tracking" from "it has not"; in the
latter case there is no baseline that *could* separate installer output from
anything else, so commit-all is a deliberate trade-off, not a proof. To keep
that trade-off visible instead of silent, the non-interactive bootstrap path
must say so explicitly: alongside the existing file listing and
"(non-interactive: auto-accepting default)" line, print a warning of the form
"first-time framework tracking: committing ALL <N> listed framework-path files
automatically — if that is not desired, rerun `ait setup` interactively or
commit the intended files manually first". (No "decline" phrasing: in
non-interactive mode the prompt auto-accepts, so there is no decline
opportunity at that point — the remedies are rerun-interactive or
pre-commit-manually.) Interactive bootstrap already shows the list and asks.

Verified against four scenarios:

| Scenario | VERSION tracked? | Baseline | Result |
|---|---|---|---|
| Fresh `git init`, framework on disk | no | empty | commit all ✔ |
| Existing repo, first `ait setup` | no | empty | commit all ✔ (tests 1b/2/10 stay green) |
| Upgrade / re-run on dirty tree | yes | dirty framework files | foreign work excluded ✔ |
| Upgrade adding a brand-new path (`.claude/skills/`) | yes | doesn't contain it (snapshot precedes the write) | new files committed ✔ |

### Verified git semantics

Confirmed by experiment, not assumed:

- `git add -- <fw>` then `git commit -m … -- <fw>` commits never-before-tracked
  paths correctly, and a foreign pre-staged path **survives staged and
  uncommitted**. This is the fix for the bare-commit sweep.
- `git commit -- <path>` on a path that is untracked **and** not `git add`ed is
  fatal (`pathspec did not match`). So always `git add` first and guard against
  an empty path list.
- The existing finalize guard `git diff --cached --quiet` is **global**: it reads
  "dirty" when only a *foreign* file is staged, which would then drive a
  path-scoped commit that fails with "no changes added". The guard must become
  `git diff --cached --quiet -- "${to_commit[@]}"`.

### Changes to `.aitask-scripts/aitask_setup.sh`

**a. Hoist and share the change-listing logic.** `_filter_changes()` is currently
a nested function inside `commit_framework_files` (2653-2659), and
`commit_framework_data_files` open-codes an equivalent (2780-2786). Replace both
with module-level helpers near the commit functions:

```bash
# Emit the filtered untracked+modified+STAGED set under <paths...> in <workdir>.
# <data_branch_re> is a regex of paths to exclude (empty = exclude nothing).
_ait_list_framework_changes() {
    local workdir="$1" data_branch_re="$2"; shift 2
    local cache_artifacts_re='(^|/)__pycache__/|\.py[co]$|\.pyd$'
    local untracked modified staged
    untracked="$(git -C "$workdir" ls-files --others --exclude-standard -- "$@" 2>/dev/null)" || true
    modified="$(git -C "$workdir" ls-files --modified -- "$@" 2>/dev/null)" || true
    staged="$(git -C "$workdir" diff --cached --name-only -- "$@" 2>/dev/null)" || true
    printf '%s\n%s\n%s\n' "$untracked" "$modified" "$staged" \
        | sed '/^$/d' | sort -u \
        | grep -Ev "$cache_artifacts_re" \
        | { [[ -n "$data_branch_re" ]] && grep -Ev "$data_branch_re" || cat; }
}

# Print items from stdin that are NOT present in the named array.
_ait_subtract() { … }   # baseline-array name + items → filtered items
```

**The `--cached` term is load-bearing, not belt-and-suspenders.** A framework
file whose edit was fully *staged* (`git add`) before setup runs is invisible to
both `ls-files --others` (it's tracked in the index) and `ls-files --modified`
(worktree matches index) — the original snapshot design would miss it, `git add`
at commit time would fold the user's staged hunk together with setup's rewrite,
and the path-scoped commit would still sweep it. With `git diff --cached
--name-only` included at **both** snapshot and commit time, the staged file
enters the baseline, is subtracted from `to_commit`, and survives the commit
intact. Verified by experiment: after the fix the file shows `MM` in
`git status --porcelain` — user's staged hunk still staged, setup's rewrite left
unstaged, HEAD contains neither. (At commit time nothing setup wrote is ever
staged — setup never runs `git add` before the commit functions — so every
staged framework path at commit time is foreign by definition; including the
`--cached` term in the commit-time listing is safe.)

Emit any diagnostics to **stderr** and make the helpers non-fatal (`|| true`) —
per `aidocs/framework/shell_conventions.md`, a `warn` inside `"$(…)"` capture is
swallowed and the non-zero status kills the run under `set -e`.

**b. New globals + snapshot function** (module scope, near the commit functions):

```bash
AIT_SETUP_DIRTY_BASELINE=()
AIT_SETUP_DATA_DIRTY_BASELINE=()
AIT_SETUP_BASELINE_ARMED=0

snapshot_pre_setup_dirty() { … }
```

`snapshot_pre_setup_dirty` sets `AIT_SETUP_BASELINE_ARMED=1` unconditionally,
then: if the bootstrap predicate says "framework not yet tracked", leaves both
baselines empty; otherwise fills `AIT_SETUP_DIRTY_BASELINE` from
`_ait_list_framework_changes` over the project dir. It fills
`AIT_SETUP_DATA_DIRTY_BASELINE` **only if `.aitask-data/.git` already exists** at
snapshot time — on a first-ever data-branch setup the worktree does not exist
yet, so an empty data baseline correctly means "commit all" there too.

**c. Call site in `main()`** — insert between `ensure_git_repo` (3221) and
`setup_data_branch` (3224). `ensure_git_repo` only inits/validates and never
commits, so the repo exists and framework-tracking state is untouched at that
point. This is the last moment before any framework file is written.

**d. `commit_framework_files()` rework** (2648-2748):
- source `changed_files` from `_ait_list_framework_changes`;
- `to_commit = changed_files − AIT_SETUP_DIRTY_BASELINE`;
- if the subtraction removed anything, print the excluded paths under a clear
  heading ("pre-existing uncommitted changes — left alone");
- if `to_commit` is empty → `success "All framework files already committed"` and
  return (no `git add` with an empty pathspec);
- keep the existing prompt/`[[ -t 0 ]]` branch and the file listing, but drive
  them off `to_commit`;
- `git add -- "${to_commit[@]}"` (unchanged shape);
- guard: `git diff --cached --quiet -- "${to_commit[@]}"`;
- finalize: `git commit -m "ait: Add aitask framework" -- "${to_commit[@]}"`;
- subtract the baseline from the post-commit `still_untracked` check too,
  otherwise a baselined file re-triggers the "remain untracked" warning.

**e. `commit_framework_data_files()`** (2756-2854): same treatment against
`AIT_SETUP_DATA_DIRTY_BASELINE`, `git -C "$data_dir"`, and message
`ait: Add aitask framework data`.

Leave `check_paths` alone; the whitelist stays duplicated in `install.sh` per the
existing sync comment (2600-2603).

### Behavior when the snapshot never ran

`commit_framework_files` is also called directly by the test suite. If
`AIT_SETUP_BASELINE_ARMED` is `0`, treat the baseline as empty — i.e. today's
behavior. Fail-open here is deliberate: the only production caller is `main()`,
which always arms; fail-closed would silently commit nothing if a future refactor
dropped the call, and would force arming edits into six existing tests for no
production benefit.

The real protection against that refactor is a **structural ordering test** (see
below) that reads `declare -f main` and asserts `snapshot_pre_setup_dirty` appears
and precedes `setup_data_branch`. That is the guard; fail-open is the fallback.

The fail-open shape leaves a hidden contract: any *production* caller of the
commit helpers must arm the baseline first, and the structural test only covers
today's `main()` path — a future direct call would silently reintroduce the
sweep. Make the contract explicit at both helper definitions with a contract
comment (and an unarmed-path `warn` to stderr so a violation is at least
visible at runtime):

```bash
# CONTRACT: production callers MUST run snapshot_pre_setup_dirty() first
# (main() does, before any framework file is written). Unarmed
# (AIT_SETUP_BASELINE_ARMED=0) means "empty baseline" = legacy commit-all
# sweep behavior — acceptable ONLY for direct test invocation.
if [[ "${AIT_SETUP_BASELINE_ARMED:-0}" != "1" ]]; then
    warn "commit_framework_files: baseline not armed — committing without pre-setup dirty protection" >&2
fi
```

(The existing direct-call tests will see this warning on stderr; they assert on
specific substrings, not absence of others, so they stay green — verify when
running the suite.)

---

## Part 2 — Discord `attachments` rejection

`.aitask-scripts/chat/discord_adapter.py`, `send_message` (812). Mirror
`slack_adapter.py:906-915` exactly: make the rejection the **first statement in
the body**, before `_resolve_channel` or any kwargs construction, so no partial
send can occur.

```python
if attachments:
    # Platform gap, surfaced loudly: discord.py sends files as fresh uploads,
    # not by re-attaching existing handles — silently dropping them would fake
    # a partial send as success. Send the text, then upload via
    # upload_attachment.
    raise ChatError(
        "Discord cannot attach existing file handles to a message; "
        "use upload_attachment for files"
    )
```

Raise the **base** `ChatError` (as Slack does), and keep the substring
`upload_attachment` — the test asserts on it. `upload_attachment` already exists
and is fully implemented (1122-1149), so the redirect the message names is real.
`capabilities().supports_files` stays `True` (files *are* supported, via
`upload_attachment`) — matching Slack.

`MockChatAdapter.send_message` (`chat/mock.py:218-242`) stores attachments rather
than rejecting; that stays as-is. Slack already diverges from Mock the same way,
and the ABC docstring does not forbid platform-specific rejection.

---

## Verification

**Setup** — `bash tests/test_setup_git.sh`. Existing tests 1b / 2 / 3 / 10 / 11 /
12 / 14 must stay green unchanged (they all run in bootstrap conditions, where
the baseline is empty by construction). Add three blocks:

1. **Positive** — bootstrap project; call `snapshot_pre_setup_dirty` (arms, empty
   baseline); create a new framework file (`aireviewguides/x.md`);
   `commit_framework_files </dev/null`. Assert `git show --name-only HEAD`
   contains `aireviewguides/x.md`.

2. **Negative control** (the load-bearing one) — project with the framework
   *tracked* (so not bootstrap: `git add -A && git commit`, VERSION tracked).
   Then three foreign-work fixtures:
   - an **unstaged** edit to a tracked framework file
     (`.aitask-scripts/placeholder.sh` — concurrent session's worktree edit);
   - a **fully staged** edit to another tracked framework file
     (`echo x >> .aitask-scripts/staged.sh && git add .aitask-scripts/staged.sh`
     — exercises the `--cached` term; invisible to `ls-files
     --others/--modified`);
   - a pre-staged **non-framework** file
     (`echo x >> readme.txt && git add readme.txt` — exercises the path-scoped
     commit).
   Call `snapshot_pre_setup_dirty`; create a legitimate new setup file; run
   `commit_framework_files </dev/null`. Assert on `git show --name-only HEAD`:
   - does **not** contain `placeholder.sh`, `staged.sh`, or `readme.txt`,
   - **does** contain the legitimate new file.
   Plus: `git status --porcelain` still shows `staged.sh` and `readme.txt`
   staged (the framework one as `M ` or `MM`).

3. **Structural ordering** — `main_body="$(declare -f main)"`; assert both
   `snapshot_pre_setup_dirty` and `setup_data_branch` appear, and the former's
   offset precedes the latter's.

4. **Data-branch twin negative control** — `commit_framework_data_files` has no
   coverage today and this task refactors it onto the shared helper, so it must
   not be changed blind. Build a `.aitask-data` worktree fixture, dirty a file
   under `aitasks/metadata/`, pre-stage a foreign file in the data worktree's
   index, snapshot, then create a legitimate new metadata file and run
   `commit_framework_data_files </dev/null`. Assert the
   `ait: Add aitask framework data` commit contains the new file and neither the
   dirtied nor the foreign staged file.

Then a **live** end-to-end check in this repo, which is the exact scenario that
produced the original defect: with the working tree dirty, run `./ait setup`
non-interactively and confirm no sweep. This deliberately exercises the
dangerous path in the real repo, so bracket it defensively:
- **Before:** save `git status --porcelain` and `git log -1 --format=%H` (both
  worktrees — main and `.aitask-data`) to scratchpad files, and confirm the
  current dirty state is the intentional test fixture (this task's own edits),
  nothing precious and unstageable.
- **Run** `./ait setup </dev/null`.
- **After:** diff the saved snapshots against fresh ones. Expected: HEAD
  unchanged (no `ait: Add aitask framework` / `… framework data` commit swept
  anything — a commit containing *only* setup-written files is acceptable if
  setup legitimately updated something), and every pre-existing dirty/staged
  path still present with unchanged status letters. Any unexpected delta is a
  fix bug: recover with `git reset --mixed HEAD~1` (as in the original
  incident) before continuing.

**Discord** — `bash tests/test_chat_discord.sh`. Add a spy block in `main()`
mirroring `tests/test_chat_slack.sh:430-439`, using the Discord suite's existing
`ch.send_calls` spy (the same before/after idiom already used at 469-476 and
498-506):

```python
sends_before = len(ch.send_calls)
try:
    await adapter.send_message(CH_REF, "with files",
                               attachments=[da.Attachment(id="1", filename="a.txt")])
    check("send_message: attachments rejected loudly", False)
except ChatError as exc:
    check("send_message: attachments rejected loudly",
          type(exc) is ChatError and "upload_attachment" in str(exc))
check("send_message: rejected attachments → no send happened (spy)",
      len(ch.send_calls) == sends_before)
```

Also run `bash tests/test_chat_contract.sh` (pins ABC signatures) and
`bash tests/test_chat_slack.sh` (shared `_subscription` module), and
`shellcheck .aitask-scripts/aitask_setup.sh` — diff findings against the pre-edit
baseline; introduce none.

---

## Risk

### Code-health risk: medium
- `commit_framework_files` is a load-bearing install/upgrade path; a wrong
  bootstrap predicate silently stops committing framework files on fresh installs
  (failure is invisible until someone clones the project). · severity: medium ·
  → mitigation: the four-scenario table above is encoded as tests; the existing
  bootstrap tests (1b/2/10) act as the regression net · → mitigation: TBD
- Hoisting `_filter_changes` out of a nested scope and reusing it across both
  commit functions changes the data-branch twin's filtering from open-coded to
  shared; a subtle regex/pathspec difference between the two call sites could
  alter what the data branch commits. `commit_framework_data_files` has **no test
  coverage today**. · severity: medium · → mitigation: in-task — Verification
  step 4 adds a data-branch negative-control test (user-confirmed, 2026-07-10)
- Fail-open when unarmed leaves the old sweep reachable for any future caller
  that forgets `snapshot_pre_setup_dirty`; mitigated by the structural ordering
  test, the contract comment at both helper definitions, and a runtime
  unarmed-path `warn` (review feedback, 2026-07-10). · severity: low ·
  → mitigation: in-task
- Bootstrap commit-all is a stated trade-off, not a proof of "no foreign work":
  a partial install / failed setup / hand-copied files in a not-yet-tracked repo
  get committed on first setup. Mitigated by an explicit non-interactive
  bootstrap warning listing the blast radius (review feedback, 2026-07-10). ·
  severity: low · → mitigation: in-task

### Goal-achievement risk: low
- The baseline-diff excludes a file that was *both* pre-dirty and rewritten by
  setup, so setup's own update to that file goes uncommitted. This is the
  intended fail-safe direction (never sweep foreign work), but it means "commit
  exactly what setup wrote" is not literally achieved in that overlap. · severity:
  low · → mitigation: report the excluded paths so the user can commit them
  deliberately · → mitigation: TBD
- Part 2 is a five-line mirror of a landed, tested fix; approach and coverage are
  settled. · severity: low · → mitigation: TBD

---

## Step 9 — Post-Implementation

Per `task-workflow` Step 9: merge approval, `./ait gates run 1128`
(`risk_evaluated`), then `./.aitask-scripts/aitask_archive.sh 1128`.

Record in Final Implementation Notes → **Upstream defects identified**:
`install.sh:921,1015 — commit_installed_files / commit_installed_data_files
finalize with a bare `git commit`, sweeping a foreign pre-staged index on a dirty
`curl|bash` upgrade; path-scope both (user deferred this out of t1128)`.

Also delete the now-obsolete memory `project_ait_setup_dirty_tree_commit_sweep.md`
once this lands.

## Final Implementation Notes
- **Actual work done:** Implemented per the approved plan (both parts).
  Part 1: hoisted the framework-path whitelist into `_ait_framework_paths` /
  `_ait_data_framework_paths`, added `_ait_list_framework_changes` (untracked +
  modified + **staged** via `git diff --cached --name-only` — the load-bearing
  term for pre-staged framework edits), `_ait_subtract` / `_ait_intersect`
  (grep -Fx based, macOS-portable), globals + `snapshot_pre_setup_dirty()`
  (VERSION-tracked bootstrap sentinel, data baseline captured only when the
  data worktree pre-exists), armed in `main()` between `ensure_git_repo` and
  `setup_data_branch`. Both `commit_framework_files` and the
  `commit_framework_data_files` twin now commit only `changed − baseline`,
  report excluded paths ("left alone"), path-scope the `git commit` and the
  `--cached --quiet` guard, warn on the unarmed path, and announce the
  bootstrap commit-all blast radius in non-interactive mode. Part 2:
  `DiscordAdapter.send_message` rejects non-empty `attachments` with base
  `ChatError` naming `upload_attachment`, first statement in the body —
  exact mirror of the Slack fix. Tests: `test_setup_git.sh` +4 blocks
  (bootstrap positive + warning assertions; three-fixture negative control
  incl. a fully-staged framework edit; `declare -f main` structural ordering;
  data-branch twin negative control — first coverage of that function),
  `test_chat_discord.sh` +2 spy checks.
- **Deviations from plan:**
  - Baselines are newline-joined **strings**, not bash arrays
    (`AIT_SETUP_DIRTY_BASELINE=""`), with `grep -Fxv/-Fx -f <(printf …)`
    subtraction/intersection — simpler and avoids bash-4.3 nameref
    portability questions. Behavior identical to the planned array shape.
  - Added `_ait_intersect` (not in the plan) so the excluded-paths report is
    computed the same exact-match way as the subtraction.
  - `install.sh` untouched, per the user's explicit scope decision.
- **Issues encountered:** none material. `tests/test_init_data.sh` fails
  23/30 — verified identical on the unmodified baseline (pre-existing,
  unrelated).
- **Key decisions:** reuse `.aitask-scripts/VERSION` as the bootstrap
  sentinel (same signal as `install.sh commit_installed_files` — no second
  signal); fail-open when unarmed (legacy behavior for direct test calls)
  guarded by the structural ordering test + contract comments + runtime
  stderr warn; the staged (`--cached`) term included at both snapshot and
  commit time — at commit time any staged framework path is foreign by
  definition since setup never pre-stages; bootstrap warning phrased without
  "decline" (non-interactive auto-accepts — remedies are rerun-interactive
  or pre-commit-manually).
- **Verification highlights:** unarmed run reproduces the legacy sweep
  (meaningful negative control); live `./ait setup </dev/null` on this
  dirty repo (the exact original-incident scenario, bracketed with
  before/after `git status --porcelain` + HEAD snapshots of both worktrees)
  left everything byte-identical and reported the 3 pre-existing dirty
  framework files as left alone. `test_setup_git.sh` 70/70,
  `test_chat_discord.sh` 142, contract 148, Slack green; shellcheck findings
  identical to the pre-edit baseline.
- **Upstream defects identified:**
  - `install.sh:921,1015 — commit_installed_files / commit_installed_data_files finalize with a bare git commit (no pathspec), sweeping a foreign pre-staged index on a dirty curl|bash upgrade; path-scope both commits and their --cached --quiet guards (user deferred this out of t1128)`
  - `tests/test_init_data.sh — 23 of 30 checks fail on the unmodified baseline (pre-existing breakage, unrelated to t1128; reproduced on a clean stash of this task's changes)`
