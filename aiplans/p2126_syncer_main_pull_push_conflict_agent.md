---
Task: t2126_syncer_main_pull_push_conflict_agent.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2126 — syncer `main` pull/push: divergence conflict dialog + agent (incl. merged t1791)

## Context

In `ait syncer`, the aitask-data sync (`s`) has a purpose-built conflict flow
(`DataConflictContext` → `SyncConflictScreen` → `build_data_conflict_prompt`).
The `main`-row actions `u` (pull) and `p` (push) send every non-zero git exit to
the generic `SyncFailureScreen`, whose agent prompt is just command + status +
stderr tail — no help for the one failure that matters: local and remote `main`
have diverged. Separately (merged t1791), `u` refuses on *any* dirty worktree,
which with several live agents in one checkout means it almost never runs.

Outcome: a diverged pull and a non-fast-forward / fetch-first push each open a
dedicated "main diverged" dialog whose **Launch agent** opens
`AgentCommandScreen` with a purpose-built prompt rooted in that repo; `a`
re-opens it; every other failure keeps the generic path. The pull lets git
decide about dirty files, refusing up front only mid-merge/rebase.

## Decisions (made during planning)

- **Pull becomes fetch + pinned fast-forward merge**, not `git pull`. Probed on
  git 2.56: `git pull` rejects `--no-overwrite-ignore` (`error: unknown option`),
  so the only way to get the t1792-recommended protection is the same shape
  `ait sync` uses (`aitask_sync.sh` `do_pull_rebase`):
  `git fetch <remote> <merge-ref>` of the **named branch's** upstream → pin the
  fetched commit (FETCH_HEAD == `<branch>@{upstream}`) → re-validate the
  checkout → `git merge --ff-only --no-autostash --no-overwrite-ignore <sha>`
  (details and the two review fixes in step 2c).
  `--no-autostash`: a user `merge.autoStash` would stash/re-apply other sessions'
  dirty files (inode/ctime churn). `--no-overwrite-ignore`: git's default
  silently overwrites an ignored local file an incoming commit writes (probed:
  with the flag git refuses and leaves the file intact).
- **Classifier markers (probed, LC_ALL=C, git 2.56)** — each printed only by the
  step it is matched against:
  - pull (merge step only): line `fatal: Not possible to fast-forward, aborting.`
    (fetch never prints it; "would be overwritten" refusals print a different
    `error: … would be overwritten by merge:` and stay plain failures).
  - push: line ` ! [rejected]        <branch> -> <branch> (fetch first)` or
    `(non-fast-forward)`, anchored to the exact `branch -> branch` ref we push.
    `! [remote rejected] … (pre-receive hook declined)` does NOT match.
- **Locale pin**: every syncer git call runs with `LC_ALL=C` and `LANGUAGE`
  removed (gettext ignores LANGUAGE under C, removing it is belt-and-braces).
- **Dialog**: a new `MainConflictScreen` (not a generalised `SyncConflictScreen`:
  that one is file-list-shaped, offers "Resolve Interactively" with an
  `ait sync` meaning, and the board imports it — its contract stays untouched).
  Buttons: **Launch agent to integrate** / **Dismiss**. No interactive
  alternative: a plain terminal adds a launch path for no capability the user's
  tmux doesn't already give. Dismiss values reuse the closed set:
  `CONFLICT_CHOICE_AGENT` or `None`, dispatched by equality (t1911).
- **Pull-case goal does not include publishing**; the prompt says to ask the user
  before pushing. Push case requires publishing.

## Implementation steps

### 1. `.aitask-scripts/lib/sync_action_runner.py` — prompt builder

Add next to `build_data_conflict_prompt` (and list it in the module docstring):

```python
MAIN_CONFLICT_ACTIONS = ("pull", "push")
#: tmux window prefix for the main-divergence agent; + action ("pull"/"push").
MAIN_CONFLICT_WINDOW_PREFIX = "agent-syncfix-main-"

def main_conflict_window_name(action: str) -> str: ...  # ValueError on bad action

def build_main_conflict_prompt(action, branch, repo_root, output_tail) -> str:
```
Same shape as the data prompt — context, goal, constraints, pitfalls; not a
recipe (no git command sequence). `ValueError` for an action outside
`MAIN_CONFLICT_ACTIONS`. Content by intent:
- **Context**: which action in `ait syncer` on `<repo_root>`, branch `<branch>`;
  pull: the fast-forward-only update refused because local and remote have
  diverged — nothing changed; push: the push to `origin` was rejected because the
  remote has commits the local branch lacks — nothing published. Git's output
  tail quoted. State may have moved since; check it yourself.
- **Goal**: local and remote `<branch>` integrated with **both sides' commits
  kept**; push case: the integrated result **published** to the remote; pull
  case: publishing is not part of the goal — ask the user before pushing; in both:
  the **live checkout at `<repo_root>` up to date** with the integrated result.
  Choose your own approach; ask the user when the choice between merge and
  rebase, or an ambiguous conflict resolution, is theirs to make.
- **Constraints** (the checkout is shared by several live agent sessions):
  never force-push in any form; never stash, reset, check out/restore or clean
  other sessions' uncommitted edits — they must be byte-for-byte intact; do not
  leave a merge or rebase in progress in the shared checkout (other sessions
  commit there while you work).
- **Pitfalls (facts)**: a rebase drops merge commits (this repo's `main` carries
  merge commits from task branches); other sessions may commit to `<branch>`
  while you work, so re-check before publishing/finishing; an incoming change to
  a file another session has dirty blocks updating the live checkout — stop and
  ask rather than move their edits.
- **Verify** before finishing that the end state holds; remove any worktree you
  created.

### 2. `.aitask-scripts/syncer/syncer_app.py`

a. `import re`; import `CONFLICT_CHOICE_AGENT` (already), `build_main_conflict_prompt`,
   `main_conflict_window_name` from `sync_action_runner`; import
   `MainConflictScreen` from `sync_failure_screen`.

b. Module-level git runner (replaces the body of `SyncerApp._git`, which keeps
   delegating so instance patching still works):
```python
def run_git(args: list[str], cwd: str) -> tuple[int, str, str]:
    env = dict(os.environ); env["LC_ALL"] = "C"; env.pop("LANGUAGE", None)
    # subprocess.run(..., env=env, timeout=GIT_TIMEOUT_SECONDS) — same
    # 124/127 fallbacks as today
```

c. Pure classifier + step runners (in the "pure helpers" section, unit-tested
   without Textual):
```python
MAIN_OK, MAIN_REFUSED, MAIN_DIVERGED, MAIN_FAILED = "ok", "refused", "diverged", "failed"
_MIDOP_MARKERS = ("rebase-merge", "rebase-apply", "MERGE_HEAD",
                  "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG")  # = aitask_sync.sh _worktree_wedged
_PULL_DIVERGED_RE = re.compile(r"^fatal: Not possible to fast-forward, aborting\.$", re.M)

def classify_main_failure(action: str, branch: str, output: str) -> bool
    # pull → _PULL_DIVERGED_RE; push → rf"^ ! \[rejected\]\s+{b} -> {b} \((?:fetch first|non-fast-forward)\)$"
    # with b = re.escape(branch); any other action → False

@dataclass(frozen=True)
class MainActionResult:
    status: str          # MAIN_*
    message: str = ""    # MAIN_REFUSED notice
    command: str = ""    # display form of the git step that failed
    output: str = ""     # that step's stdout + stderr

def run_main_pull(git, cwd: str, branch: str) -> MainActionResult
    # Every ref below is bound to the NAMED branch, never to whatever HEAD is.
    # 1. checkout gate (helper _pull_checkout_refusal, reused in step 6):
    #    symbolic-ref -q HEAD != refs/heads/<branch> → REFUSED "Switch to … to pull";
    #    rev-parse --absolute-git-dir rc!=0 → REFUSED "could not inspect … — not
    #    pulling" (fail closed); first existing midop marker → REFUSED
    #    "Checkout is mid-<op> — finish or abort it before pulling."
    # 2. upstream of <branch>: rev-parse --symbolic-full-name <branch>@{upstream}
    #    (tracking ref; rc!=0 → FAILED with git's "no upstream configured" text),
    #    config --get branch.<branch>.remote / branch.<branch>.merge (missing →
    #    FAILED naming the key).
    # 3. fetch <remote> <merge-ref> — the upstream ref by name, so a deleted
    #    remote branch fails here ("couldn't find remote ref", probed) instead of
    #    a plain non-pruning `git fetch` exiting 0 over a stale tracking ref.
    #    rc!=0 → FAILED.
    # 4. pin: rev-parse --verify FETCH_HEAD^{commit} and <tracking>^{commit};
    #    they must be equal (proves the tracking ref holds what THIS fetch
    #    brought; catches an unmapped refspec or a concurrent fetch rewriting
    #    FETCH_HEAD) → else FAILED "remote-tracking ref not updated by this
    #    fetch — nothing changed, retry". pin = that oid.
    # 5. (nothing between 4 and 6 touches the checkout)
    # 6. apply-boundary revalidation: re-run the step-1 checkout gate; a refusal
    #    now reads "Checkout changed while fetching (<reason>) — nothing merged."
    #    (another session may have switched branch or started a merge/rebase
    #    during the fetch; merge would otherwise fast-forward THAT branch).
    # 7. merge --ff-only --no-autostash --no-overwrite-ignore <pin>; rc==0 → OK;
    #    classify("pull") → DIVERGED else FAILED.
    # Residual: git has no "merge only if HEAD is X", so a switch in the
    # instant between 6 and 7 is not closed; 6 shrinks the window from the
    # whole network fetch to two local git calls.
def run_main_push(git, cwd: str, branch: str) -> MainActionResult
    # push origin b:b; OK / DIVERGED (classify "push") / FAILED
```
   `command` strings: `"git -C " + shlex.join([cwd, *args])`-style display.
   The blanket `git status --porcelain` dirty refusal is **removed**.

d. `MainConflictContext` (frozen dataclass, sibling of `DataConflictContext`):
   `action`, `target: ActionTarget`, `command`, `output_tail`; properties
   `repo_root` (`(target.root or Path(".")).resolve()`) and `branch`
   (`target.branch or "main"`). `_last_failure` annotation widened.

e. Workers become thin: `_main_pull_worker` / `_main_push_worker` call
   `run_main_pull(self._git, cwd, branch)` / `run_main_push(...)` then
   `call_from_thread(self._on_main_action_done, row, target, action, result)`
   (busy flag reset in `finally` as today).

f. `_on_main_action_done(row, target, action, result)` on the app thread:
   - OK → notify `main: Pulled.` / `main: Pushed.` + `_post_action_refresh(row)`
   - REFUSED → warning notify (prefixed with label)
   - DIVERGED → `ctx = MainConflictContext(...)`, `self._last_failure = ctx`,
     `_open_main_conflict_screen(ctx)`, `_post_action_refresh(row)`
   - FAILED → `self._fail(row, action, result.command, "ERROR", tail, result.output)`
     (unchanged generic path; tail = last `FAILURE_TAIL_LINES` lines)

g. `action_agent_resolve`: `isinstance(ctx, MainConflictContext)` →
   `_open_main_conflict_screen(ctx)`.

h. `_open_main_conflict_screen` / `_on_main_conflict_resolved` (equality on
   `CONFLICT_CHOICE_AGENT`, then `_tick_refresh`) / `_launch_main_conflict_agent`
   → `self._launch_agent(title=f"Integrate diverged {branch} ({action})[ on <label>]",
   window_name=main_conflict_window_name(action), prompt=build_main_conflict_prompt(...),
   project_root=ctx.repo_root)` — reuses the existing guarded launch boundary.

### 3. `.aitask-scripts/syncer/sync_failure_screen.py` — `MainConflictScreen`

`GuardedModalScreen` with own `DEFAULT_CSS` (pattern of `SyncFailureScreen`;
border `$warning`). `__init__(action, branch, repo_root, output_tail, repo_label="")`.
Title `"<branch> diverged from the remote[ — <label>]"`; body names the repo
root and states what diverged (pull: local and remote both have commits the
other lacks, fast-forward refused, nothing changed; push: remote has commits
local lacks, push rejected, nothing published) + scrollable output tail.
Buttons `#btn_main_conflict_agent` → `dismiss(CONFLICT_CHOICE_AGENT)`,
`#btn_main_conflict_dismiss` / escape → `dismiss(None)`. Constant imported from
`sync_action_runner` (lib dir is already on its `sys.path`).

### 4. Tests

- **New `tests/test_syncer_main_pull_push.py`** (no Textual boot; real git in
  `tempfile` scratch repos with `GIT_CONFIG_GLOBAL=/dev/null`,
  `GIT_CONFIG_NOSYSTEM=1`, author/committer env, via `mock.patch.dict(os.environ)`;
  outputs captured through `run_git`, i.e. under the production locale pin):
  - classifier on real output: diverged pull (`run_main_pull` → DIVERGED and the
    marker in `.output`); push fetch-first and non-fast-forward → DIVERGED.
    Negative controls → FAILED / classifier False: pull blocked by an untracked
    file the remote adds; push rejected by a `pre-receive` hook (`[remote
    rejected]`); push to a missing remote. Cross-op: pull output fed to the push
    classifier and vice versa → False; push rejection for a different ref name →
    False.
  - t1791 ACs: unrelated dirty tracked file + remote ahead (+ `merge.autoStash=true`
    in repo config) → OK, file bytes **and inode** unchanged; remote changes the
    dirty file → FAILED and `.output` names it; diverged → DIVERGED (above);
    real mid-merge (conflicting `git merge`) and real mid-rebase → REFUSED, with a
    recording `git` wrapper proving no `fetch`/`merge` ran; an ignored local file
    the remote adds → FAILED and the file content intact.
  - Branch binding (review concern 1): a `git` wrapper that, after the real
    `fetch` returns, runs `git checkout -q feature` (feature = an older main
    commit, so an unguarded ff-merge WOULD fast-forward it) → REFUSED with
    "changed while fetching"; `refs/heads/feature` and `refs/heads/main` both
    unchanged. Same wrapper starting a real conflicting `git merge` after the
    fetch → REFUSED, no `merge --ff-only` call recorded.
  - Stale upstream (review concern 2): remote `main` deleted
    (`update-ref -d` in the bare repo) while local `origin/main` stays → FAILED,
    `.output` contains "couldn't find remote ref", HEAD unchanged — and a
    control showing a plain `git fetch` exits 0 in that state (so the test
    pins why the named-ref fetch is needed). Pin cross-check: wrapper that moves
    `refs/remotes/origin/main` to another commit right after fetch → FAILED,
    nothing merged.
  - Bound upstream: on `main` with `branch.main.merge` naming a remote branch
    other than the current HEAD's default, the fetched/merged ref is
    `main`'s configured one.
  - `run_git` passes `LC_ALL=C` and drops `LANGUAGE` (patch `subprocess.run`).
- **`tests/test_syncer_rows.py`**: `MainConflictAgentTests(_TabbedShellBase)`
  reusing `DataConflictAgentTests.agent_seams` (as `AgentRunInTerminalTests` does):
  DIVERGED pull → `MainConflictScreen`; escape keeps `MainConflictContext` in
  `_last_failure`; `action_agent_resolve` re-opens it (not `SyncFailureScreen`);
  agent button on a two-repo push case → spy `AgentCommandScreen` with
  `default_window_name == "agent-syncfix-main-push"`, `project_root` = that repo,
  prompt names root and forbids force-push; FAILED result → `SyncFailureScreen`
  (generic path unchanged); REFUSED → no modal, no `_last_failure`.
  Button-visibility check at 80 columns.
- **`tests/test_sync_action_runner.py`**: `BuildMainConflictPromptTests` by intent
  (pattern of `BuildDataConflictPromptTests`): names root/branch/action + tail;
  both sides' commits kept; push requires publishing, pull says ask before
  pushing; never force-push; never stash/reset/check out others' edits; no
  merge/rebase left in progress; ask user on merge-vs-rebase; rebase-drops-merge-
  commits pitfall; window names distinct from `DATA_CONFLICT_WINDOW_NAME` and the
  generic `agent-syncfix-pull/push`; bad action → `ValueError`.
- **Mutant check** (verification, not committed): make `classify_main_failure`
  return `False` → the classification tests must fail; restore.

### 5. Docs — `website/content/docs/tuis/syncer/_index.md`

- Key table: `u` row → fetch, then fast-forward only to the upstream
  (`git merge --ff-only --no-autostash --no-overwrite-ignore`); `a` row → most
  recent failure, data-sync conflict or diverged-`main` dialog.
- Replace the "refuses to pull on a dirty working tree" sentence: refuses when
  HEAD is not on `main` or the checkout is mid-merge/rebase/cherry-pick/revert/
  bisect; a dirty tree is fine unless the incoming commits touch a modified,
  untracked or ignored file, in which case git's own message (naming the files)
  is shown.
- "Failure handling": new paragraph/bullets for the diverged-`main` dialog
  (pull diverged / push rejected as non-fast-forward or fetch-first; Launch agent
  → `agent-syncfix-main-<action>` rooted in that repo, goal and constraints in
  current-state prose; Dismiss; `a` re-opens). Other failures still get the
  generic modal.
- Run `cd website && python3 check_links.py --build`.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir <scratch dir with the 3 modules>  # or:
~/.aitask/venv/bin/python -m pytest tests/test_syncer_main_pull_push.py tests/test_sync_action_runner.py tests/test_syncer_rows.py -q
# mutant: classify_main_failure → return False; the new classification tests must fail; restore
cd website && python3 check_links.py --build
```
Then Step 9 (Post-Implementation): review, commit, archive per task-workflow.

## Risk

### Code-health risk: medium
- The pull path changes from one `git pull --ff-only` to a multi-step fetch → pin → merge sequence, which opens check-to-apply windows `git pull` did not have (branch switched or upstream deleted mid-sequence) · severity: medium · → mitigation: covered in plan (step 2c binds every ref to the named branch, fetches the upstream ref by name, cross-checks FETCH_HEAD against the tracking ref, re-validates the checkout at the apply boundary; step 4 deterministic tests for each; residual instant between revalidation and merge stated)
- A repo whose upstream is configured unusually (no upstream, unmapped fetch refspec) now fails at a different step than before · severity: low · → mitigation: covered in plan (each step surfaces git's own message on the unchanged generic failure path)
- `_last_failure` grows a third context type; any consumer that dispatches on it must handle the new one · severity: low · → mitigation: covered in plan (only `action_agent_resolve` dispatches; step 4 re-open test)

### Goal-achievement risk: low
- Classification depends on git's English wording; a future git rewording silently degrades to the generic failure modal (the safe direction) · severity: low · → mitigation: covered in plan (locale pin + real-output tests that fail on the installed git if wording changes)
