---
Task: t1658_1_converge_local_data_branch_after_offbranch_push.md
Parent Task: aitasks/t1658_data_branch_metadata_push_strands_local_branch.md
Sibling Tasks: aitasks/t1658/t1658_2_anchor_data_worktree_resolution_to_repo_root.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-01 15:26
---

# t1658_1 — Converge the local data branch after an off-branch metadata push

Covers parent **AC1–AC4**. The cwd hazard (AC5) belongs to t1658_2 — do not
touch `_ait_detect_data_worktree()` here.

## Context

`commit_and_push_from_remote_clone()`
(`.aitask-scripts/lib/verified_update_lib.sh:109`) builds every metadata commit
in a throwaway `/tmp` clone of `origin/<data-branch>` and pushes `HEAD:<branch>`
straight to origin. **The local branch ref is never advanced.** Its only
compensation, `sync_current_repo_from_remote()` → `task_sync()`, is a bare
`git pull --rebase` (`_task_pull_rebase`, `task_utils.sh:478`, no `--autostash`,
`rebase.autoStash` unset) that refuses outright — exit 128, *before* it fetches —
whenever the shared `.aitask-data` worktree has unstaged changes. The outcome is
then discarded (`return 0`, no `TASK_SYNC_*` inspection), and `task_sync()` has
no push side, so once a local commit lands on the stale tip the branch is
genuinely diverged and every later `task_push()` fails non-fast-forward.

It fires twice per completed pick via `satisfaction-feedback.md`
(`aitask_usage_update.sh`, then `aitask_verified_update.sh`) — those two subjects
are ~15% of recent data-branch commits.

## Decisions already taken — do not re-litigate

**Reconcile seam = `git fetch` + `git merge --ff-only`** (user-approved
deviation from the parent's AC2, which enumerated `--autostash` and
`auto_commit()`). Measured on git 2.55.0, remote commit touching `meta.json`,
local worktree dirty on `task.md`:

| seam | dirty NON-overlapping | dirty OVERLAPPING |
|---|---|---|
| `pull --rebase` (today) | `rc=128` "cannot pull with rebase: You have unstaged changes" | same |
| `merge --ff-only` | `rc=0`, behind→0, `M task.md` preserved verbatim | `rc=1` "…would be overwritten by merge: meta.json / Aborting" |

`--autostash` is **rejected**: it runs an internal `git stash` across the shared
`.aitask-data` worktree, removing other live sessions' unstaged `aitasks/` /
`aiplans/` edits for the rebase window, and a failed pop leaves conflict markers.
`auto_commit()` is **rejected** for the mirror reason: it stages
`aitasks/ aiplans/` wholesale and would land other sessions' in-flight edits
under an `ait: Update usage count …` message — the unscoped-sweep pattern t1599
exists to remove. **Neither rejected hazard may re-enter through the
replacement: the chosen seam never stashes and never commits anything.**

**Success means the local-ref invariant holds.** A blocked fast-forward or an
already-diverged branch leaves the commit on origin but not locally, so a
distinct partial outcome is required rather than a warning attached to a success.

**The chain stops returning its value through stdout.** Verified:

```
FLAG=1; inner() { FLAG=0; echo 80; }; v="$(inner)"
after $( ): v=80 FLAG=1     # the assignment never crossed back
```

A global assigned inside `$( )` is discarded, so the convergence verdict cannot
ride back alongside the value that way.

## Implementation

### Pre-phase (risk mitigations)

None for this child.

### 1. `task_data_converge()` in `.aitask-scripts/lib/task_utils.sh`

New section immediately after the `task_push` block (after `_task_push_warn`,
before `--- YAML List Parsing ---`). Mirror the existing
best-effort-but-never-silent contract: **always returns 0**, outcome in globals,
one `warn()` on stderr, silent on success.

```bash
TASK_CONVERGE_STATUS=""   # converged | fast-forwarded | pushed | diverged | blocked | no-remote | failed
TASK_CONVERGE_REASON=""   # classifier code when blocked/diverged/failed
TASK_CONVERGE_AHEAD=""    # local commits not on upstream (post-cycle)
TASK_CONVERGE_BEHIND=""   # upstream commits not on HEAD (post-cycle)
_AIT_CONVERGE_MAX_PASSES=2
```

`task_data_converge [<context>]`, per pass (at most `_AIT_CONVERGE_MAX_PASSES` —
a race can turn one state into the other, and two passes bound it):

1. `_task_push_has_remote` false → `no-remote`, return 0.
2. `upstream="$(_task_push_upstream)"`; empty → `failed` / `no_upstream`, warn,
   return 0.
3. `_ait_data_git fetch --quiet` (capture stderr). **This never touches the
   worktree** — it is the step today's code never reaches because the rebase
   refuses first. Failure → `failed`, reason
   `_task_push_classify "$fetch_err" ""`, warn, return 0.
   Use a plain `fetch` (the configured refspec): today's `pull --rebase` already
   fetches all of origin, so this is a strict subset of existing side effects.
4. `ahead="$(_task_push_unpushed_count)"`, `behind="$(_task_sync_unpulled_count)"`,
   then branch on the pair:

| ahead | behind | action | status |
|---|---|---|---|
| 0 | 0 | nothing | `converged` (terminal) |
| 0 | >0 | `_ait_data_git merge --ff-only --quiet "$upstream"` | `fast-forwarded` on 0, else `blocked` (terminal) |
| >0 | 0 | `_task_push_once` | `pushed` on 0; on failure see the pass rule below |
| >0 | >0 | none possible without a rebase | `diverged` (terminal) |

Re-sample `TASK_CONVERGE_AHEAD` / `TASK_CONVERGE_BEHIND` after any successful
action so the globals report the **post-cycle** state (same convention as
`TASK_PUSH_UNPUSHED`).

**What consumes pass 2 — exactly one thing.** The two-pass budget exists because
a race can turn one state into the other, but only one arm can actually observe
that race, and leaving it unspecified makes the ahead-only arm terminate on the
racing case: if another writer advances origin between our `fetch` and our
`push`, git rejects non-fast-forward and `_task_push_classify "$push_err" ""`
returns `diverged` — so a naive "non-zero → `failed`" reports status `failed` /
reason `diverged`, while the true state is ahead-**and**-behind and step 6's
`converge_race_stress` asserts status `diverged` / reason `local_diverged`. The
post-phase would fail against its own seam. So:

- **`>0/0`, push failed, `_task_push_classify "$push_err" ""` = `diverged`**
  (non-fast-forward / fetch first / rejected) → **a lost race, not a failure.**
  Consume the next pass: re-`fetch`, re-sample, re-branch. Pass 2 normally
  observes `>0/>0` and terminates `diverged` / `local_diverged` **from the
  counts** — the same rule stated below for that arm.
- **`>0/0`, push failed, any other reason** (`remote_unreachable`,
  `no_upstream`, `unknown`) → terminal `failed` with that reason. Not a race;
  retrying buys nothing.
- **`blocked` stays terminal and fails closed.** The worktree is still dirty, so
  a second pass would only burn the budget without changing the answer.
- **`converged`, `diverged`, `fast-forwarded`, `pushed` are terminal.** A
  successful action re-samples and reports post-cycle counts; it never consumes
  another pass.
- **On pass exhaustion** (pass 2's push also loses the race), take the final
  ahead/behind sample as the truth: `>0/>0` → `diverged` / `local_diverged`.
  Only a non-race failure reports `failed`.

The outcome contract (step 4) is unaffected either way — both routes fail the
ancestry check and report partial. It is the **reason token** that must be right,
because that is what the recovery hint and the race test read.

**Reason codes derive from the existing classifier — do not duplicate its
greps.** A blocked ff produces "Your local changes to the following files would
be overwritten by merge", which `_task_push_classify "" "$ff_err"` already maps
to `dirty_worktree`; `task_data_converge` remaps exactly that value to the new
code `ff_blocked` so the hint names the real mechanism (a merge, not a rebase).
Any other classifier answer passes through unchanged. The `diverged` arm sets
`local_diverged` directly from the counts — never from an error string, because
`merge --ff-only` on a diverged branch says only "Not possible to fast-forward",
which the classifier reports as `unknown`.

Add two arms to `_task_push_reason_hint()` (`task_utils.sh:557`), each naming
**the exact command the recovery tests drive** — `./ait sync`, the
non-interactive converger, not the `ait syncer` TUI:

```bash
ff_blocked)
    echo "local edits to the same file(s) block the fast-forward; commit them or reconcile with './ait sync'" ;;
local_diverged)
    echo "local data branch has both unpushed and unpulled commits; reconcile with './ait sync'" ;;
```

`_task_converge_warn <context>` mirrors `_task_sync_warn` (:354): upstream name,
the ahead/behind pair, the hint, and the caller's context string. Success
statuses emit nothing.

**It must mirror `_task_sync_warn`'s undeterminable-counts arm too.** Both count
probes print **nothing** when the branch has no upstream, so expanding them as
`${TASK_CONVERGE_AHEAD:-0}` makes the `no_upstream` warning claim a concrete
"0 local unpushed, 0 remote unpulled" — a **false statement** about a state
where the counts are simply unknown, on a path this task deliberately makes
user-visible. When BOTH are empty, say "unreconciled commit counts unavailable"
instead, exactly as `_task_sync_warn` (:361) does. The state matrix's
no-upstream case asserts the wording and asserts the concrete zero is **absent**.

It also names `TASK_CONVERGE_STATUS` in the line: unlike `_task_sync_warn`,
which only ever reports `failed`, this one function emits three distinct
non-success statuses (`blocked` / `diverged` / `failed`) and the hint alone does
not separate them.

**Why `diverged` is reported rather than resolved.** Resolving it needs a
rebase, and a rebase needs a worktree — either the shared one (the hazard this
task removes) or a scratch worktree whose result rewrites *other sessions'*
commit hashes and can stop on conflicts. The recorded user preference is
explicit: do not force-reconcile a diverged `aitask-data` branch mid-task when
other sessions have uncommitted work there. Ownership is handed to `./ait sync`,
whose convergence is **proved by test** in step 6, and the metadata result is
downgraded to partial (step 4) so nothing claims the commit is local when it is
not.

### 2. Converge before *and* after, in `.aitask-scripts/lib/verified_update_lib.sh`

Divergence forms when the temp clone is cut from an origin tip that lacks
local's unpushed commits. Both halves are needed:

- **`commit_metadata_update()` — pre-converge once, before the retry loop**,
  after `branch` / `remote_url` are resolved and before the first
  `commit_and_push_from_remote_clone`. An ahead-only branch is pushed first
  (plain push, no worktree op) so the clone's base already contains local's
  commits; a behind-only branch fast-forwards. A branch already diverged **on
  entry** is reported as pre-existing and the update proceeds anyway
  (best-effort — the usage/score bump must not be lost), but its result will be
  partial, not success.
- **`sync_current_repo_from_remote()` → `converge_current_repo_with_remote()`.**
  It now pushes as well as pulls, so the old name is untrue. Single internal
  call site (`:149`), no external references — verified by
  `grep -rn 'sync_current_repo_from_remote' .` Body:
  `task_data_converge "$1"`.
- **`commit_and_push_from_remote_clone()` — capture, converge, then verify the
  invariant on the local ref.** On the success path, *before*
  `rm -rf "$tmpdir"`, capture `pushed_sha="$(git -C "$clone_dir" rev-parse HEAD)"`.
  After converging:

  ```bash
  if _ait_data_git merge-base --is-ancestor "$pushed_sha" HEAD 2>/dev/null; then
      AIT_METADATA_LOCAL_CONVERGED=1
  else
      AIT_METADATA_LOCAL_CONVERGED=0
  fi
  ```

  This is AC1's assertion evaluated at runtime, **not** inferred from
  `TASK_CONVERGE_STATUS` — a status token describes the mechanism, the ancestry
  check describes the fact. On `0`, `warn` one line naming `$pushed_sha`, the
  converge status/reason, and the `./ait sync` recovery.

### 3. Out-param interface — the value and the verdict must cross the boundary

Today the whole chain runs inside `new_value="$(commit_metadata_update …)"`, a
subshell. Convert to out-param globals plus an exit code:

```bash
AIT_METADATA_VALUE=""            # the new count / score
AIT_METADATA_LOCAL_CONVERGED=""  # 1 = local branch has the commit, 0 = origin only
```

**Only the remote path produces a value.** `main()` in both scripts tests
`has_remote_tracking` *itself* and never enters `commit_metadata_update` on the
local path — it already holds the value from `update_model_file` **before**
calling the helper:

```bash
if has_remote_tracking; then
    new_runs="$(commit_metadata_update …)"      # :252 / :280 — substitution dropped
else
    new_runs="$(update_model_file …)"           # :257 / :285 — substitution STAYS
    commit_metadata_update_local …              # :258 / :286 — must NOT clobber it
fi
```

So a blanket "all three set both globals" is wrong and destructive: having
`commit_metadata_update_local` assign `AIT_METADATA_VALUE` empties or overwrites
the count/score, including on its bare `return` when `diff --cached --quiet`
finds nothing staged (`verified_update_lib.sh:101-103`). One contract, no
exceptions:

| site | `AIT_METADATA_VALUE` | `AIT_METADATA_LOCAL_CONVERGED` |
|---|---|---|
| lib file scope | `=""` (declare) | `=""` (declare) |
| `main()`, immediately before the `has_remote_tracking` branch | `=""` (reset) | `=""` (reset) |
| `commit_and_push_from_remote_clone` | sets, every returning path | sets, every returning path |
| `commit_metadata_update` (remote arm) | sets, every returning path | sets, every returning path |
| `commit_metadata_update` (no-remote arm) | **never touches** | `=1` |
| `commit_metadata_update_local` | **never touches** | `=1`, every successful return **including the early one** |
| `main()` local path | assigns from `update_model_file` | reads what the helper set |

Both initialisation sites are load-bearing and neither alone suffices under
`set -u`: the file-scope declaration covers the out-param unit test, which
sources the lib and calls `commit_metadata_update` **directly** rather than
through `main()`; the `main()` reset keeps the read site's state fresh.
`commit_metadata_update`'s own no-remote arm is unreachable from either script's
`main()` today — it follows the same rule so a future caller inherits one
uniform contract rather than a special case.
- Control flow stays on the exit code, unchanged:
  `commit_and_push_from_remote_clone` still returns `10` to request a retry, and
  every `die` is untouched.
- Replace each `echo "$new_value"` / `printf '%s\n' "$new_value"` in the chain
  with an `AIT_METADATA_VALUE=` assignment, and drop the substitution at both
  `main()` call sites (`aitask_usage_update.sh:252`,
  `aitask_verified_update.sh:280`):

  ```bash
  commit_metadata_update "$models_file" "$AGENT_STRING" "$SKILL_NAME" "$PARSED_MODEL" "$SCORE"
  new_score="$AIT_METADATA_VALUE"
  ```

- Both no-remote branches — `main()`'s and `commit_metadata_update`'s — set
  `AIT_METADATA_LOCAL_CONVERGED=1` by construction, because they commit straight
  to the local branch. Per the table above, neither touches
  `AIT_METADATA_VALUE`; on `main()`'s local path that value comes from
  `update_model_file` and must survive the helper call.
- The one substitution that **stays** is the `update_model_file` callback
  (`new_value="$("$_AIT_UPDATE_MODEL_FILE_FN" …)"`), a pure jq value producer
  that sets no globals.

**Bonus defect this removes.** `git commit` writes its summary to **stdout**
(verified: `[master 2f1b9fe] test commit / 1 file changed, 1 insertion(+)`), and
`run_git_quiet` leaves it unredirected when `SILENT=false` — so a non-silent
remote run currently splices that text into `new_value` and reports it as the
count. Without the substitution, git's chatter goes to the terminal.

### 4. Outcome contract — a partial result is not a success

`main()` in **both** `aitask_usage_update.sh` and `aitask_verified_update.sh`
reads `AIT_METADATA_LOCAL_CONVERGED` after the (substitution-free) call:

| invariant | stdout | exit |
|---|---|---|
| holds | `UPDATED:<agent>:<skill>:<value>` | `0` |
| does not hold | `UPDATED_REMOTE_ONLY:<agent>:<skill>:<value>` | `3` |

The two tokens are disjoint under a plain `grep 'UPDATED:'`, so no existing
consumer mistakes one for the other. Document both tokens and exit 3 in each
script's `--help`. The local-only (no-remote) path always reports
`UPDATED:` / `0`.

### 5. Consumer — `satisfaction-feedback.md`

Edit `.claude/skills/task-workflow/satisfaction-feedback.md` (the **single
Claude source**; `aitask_skill_rerender.sh` regenerates the `default` / `fast` /
`remote` variants for Claude, Codex and OpenCode alike, so there is no per-agent
port task). It learns the third outcome: on exit 3 / `UPDATED_REMOTE_ONLY:`,
tell the user the score or run count **is** recorded on origin but the local
data branch does not have it yet, name `./ait sync`, and **continue** — a
partial metadata update must not fail the workflow.

Then run `aitask_skill_rerender.sh`, regenerate the affected goldens
(`tests/golden/procs/task-workflow/satisfaction-feedback-{default,fast,remote}.md`)
and commit them **in the same commit** (see "Regenerate goldens after any
`.md.j2` or closure edit" in `aidocs/framework/skill_authoring_conventions.md`).

Run **both** `./.aitask-scripts/aitask_skill_verify.sh` **and**
`bash tests/test_skill_render_task_workflow.sh`. `aitask_skill_verify.sh` runs no
golden assertions — the file that actually fails on a stale golden is
`test_skill_render_task_workflow.sh` Test 1 (`assert_eq`, per golden;
`satisfaction-feedback.md` is in its list at `:62`). Review the golden diff
rather than rubber-stamping it: it should contain the third-outcome prose and
nothing else.

### 6. Tests

`tests/test_task_push.sh` — the `task_data_converge` state matrix, in **legacy
and branch mode** (the file already has `setup_remote_and_clone`,
`advance_remote`, `setup_branch_mode`, `reload_task_utils`):

- clean + behind → `fast-forwarded`; `git merge-base --is-ancestor <remote sha> HEAD` holds.
- dirty **non-overlapping** + behind → still `fast-forwarded`, dirty file byte-identical afterwards. **Negative control in the same fixture state:** `git pull --rebase` exits 128.
- dirty **overlapping** + behind → `blocked` / `ff_blocked`, warning emitted, local ref unmoved, dirty file untouched.
- ahead only → `pushed`, remote has the commit, worktree untouched.
- ahead **and** behind → `diverged` / `local_diverged`, warning emitted, no ref moved.
- no upstream → `failed` / `no_upstream`; no remote → `no-remote`, silent.
- **lost push race (the pass-2 trigger).** Seed ahead-only, then advance origin
  *between* the fetch and the push — deterministically, via a second clone
  (`advance_remote`), never by sleeping. Assert the outcome is
  `diverged` / `local_diverged` with correct counts, **not** `failed`. Without
  the pass rule this returns `failed` / `diverged`, so the assertion is what
  pins it. **Negative control in the same fixture family:** a non-race push
  failure (no upstream) still terminates `failed` / `no_upstream` and does not
  consume pass 2 — otherwise "always retry" would pass the positive case too.

**Recovery convergence (AC4's "shows that it converges") — executed, not
claimed.** Two fixtures, each continuing from a state above:

- from the clean **diverged** state, run the documented recovery
  `./.aitask-scripts/aitask_sync.sh --batch`; assert its token is `SYNCED` (or
  `AUTOMERGED`) **and** that both `git rev-list --count @{u}..HEAD` and
  `git rev-list --count HEAD..@{u}` are `0`, and that the local **work** is
  still present (no work lost).
- from the **ff_blocked** state, same recovery; assert converged and that the
  previously-dirty metadata file's content survived into a commit.

**Both recovery cases must assert the recovery command's own exit status, and
must not read it through a pipeline.** `out="$(cmd | tail -n1)"` followed by
`${PIPESTATUS[0]}` reads the **assignment's** status in the enclosing shell —
always `0` — so the exit assertion is vacuous and a failing recovery that still
prints a success-looking final line would satisfy AC4's proof. Capture `$?`
directly from the substitution (no pipeline), then trim to the verdict line.

Two fixture facts these tests depend on, both learned the hard way:
- The recovery **rebases**, which rewrites commit hashes — so "the original sha
  is still an ancestor" is the wrong invariant. Assert the surviving *content*.
- `aitask_sync.sh`'s `auto_commit` runs `git add aitasks/ aiplans/`, which fails
  **wholesale** (staging nothing) if either directory is missing. A real project
  always has both; a fixture must seed both or the recovery silently no-ops.

`tests/test_verified_update.sh` + `tests/test_usage_update.sh` — the invariant
with zero coverage today, asserted **on the local ref**:

- after a successful remote update: `git rev-list --count HEAD..@{u}` is `0`,
  the pushed commit is an ancestor of local `HEAD`, stdout is exactly
  `UPDATED:…`, exit `0`.
- the same with an unrelated dirty file present (the reported bug) — still
  `UPDATED:` / `0`.
- **divergence prevention**: local unpushed commit *and* origin advanced from a
  second clone → the pre-converge publishes the local half first, so the result
  is converged with `UPDATED:` / `0`, not ahead+behind.
- **partial, both directions**: metadata file locally dirty → stdout is exactly
  `UPDATED_REMOTE_ONLY:<agent>:<skill>:<value>` and the **exit status is
  captured separately and asserted to be `3`** — not merely "non-zero", and not
  inferred from the stdout token, because the whole point is that the verdict
  reached `main()`. The warning is on **stderr only**, and the value is still
  correct on origin. Paired positive control: the identical run with a clean
  file yields `UPDATED:` / `0` — the dirty overlap is the only discriminator.
- **the out-param boundary itself**, at unit level: source
  `verified_update_lib.sh`, call `commit_metadata_update` **directly, not inside
  `$( )`**, and assert both `AIT_METADATA_VALUE` and
  `AIT_METADATA_LOCAL_CONVERGED` are set in the caller's scope. **Negative
  control in the same test:** the identical call wrapped in `$( )` leaves
  `AIT_METADATA_LOCAL_CONVERGED` at its pre-call value — so a future refactor
  back to a substitution fails here instead of silently reporting every partial
  update as a success.
- **non-silent value integrity**: run against a remote **without** `--silent`
  and assert the `UPDATED:` line's value field is a bare integer — no
  `[master abc1234] ait: Update …` git summary spliced into it.
- **the local (no-remote) path, which no remote fixture reaches.** `main()`
  bypasses `commit_metadata_update` entirely there, so every assertion above
  leaves it uncovered — and it is exactly the path the out-param contract can
  corrupt. It needs **two tests at two different levels**, because the helper's
  two returning paths are not both reachable from the script:

  1. **End-to-end, no remote.** Run the script on a repo with no remote and
     assert stdout is exactly `UPDATED:<agent>:<skill>:<value>` carrying the
     **correct count/score**, exit `0`. **The count is the discriminator, not
     the token** — a helper that clobbers `AIT_METADATA_VALUE` still prints
     `UPDATED:`, just with an empty or stale value, so asserting the token alone
     would miss the regression entirely.
  2. **Helper-level, for the early return — which end-to-end cannot reach.**
     `update_model_file` always increments a counter and `mv`s the result, so
     `main()`'s local path **always** stages a model-file change and
     `commit_metadata_update_local` can never take its `diff --cached --quiet`
     branch from there. Driving it through the script is infeasible, so call the
     helper **directly** (sourced lib, **not** inside `$( )`) with a clean index:
     seed `AIT_METADATA_VALUE` to a sentinel, call
     `commit_metadata_update_local`, then assert the sentinel is **unchanged**
     and `AIT_METADATA_LOCAL_CONVERGED=1`. Repeat the same sentinel assertion
     with a real staged change, so the "never touches the value / always sets
     the verdict" rule is pinned on **both** of the helper's returning paths.

  Test 1 alone would leave the early return unproven; test 2 alone would not
  prove `main()` wires the globals together correctly. Both are required.

Note: if any new test body runs inside a `( … )` subshell, opt into the
file-backed counters (`assert_counters_init` / `assert_counters_load`) per
CLAUDE.md, or the file will report zero failures no matter what failed.

### Post-phase (risk mitigations)

1. `[branch_mode_metadata_fixture]` Write the branch-mode fixture as a **shared
   helper** `tests/lib/metadata_update_fixture.sh` ::
   `setup_branch_mode_metadata_repo` — a real `.aitask-data` worktree (via
   `setup_data_branch` from `aitask_setup.sh --source-only`, as
   `tests/test_task_git.sh` Test 5 does), the `aitasks` / `aiplans` symlinks
   (`ait_ensure_data_symlinks` from `lib/data_symlinks.sh`), a seeded
   `models_claudecode.json` on the data branch, and the `ait` shim
   `tests/test_verified_update.sh:48` already builds. Re-run the convergence and
   outcome assertions of step 6 through it, so the seam is exercised in the shape
   production actually runs rather than only legacy mode. It is a shared lib, not
   a local helper, because **t1658_2 reuses it** for its non-root-cwd entry-point
   tests — do not inline it into one test file.
2. `[converge_race_stress]` Drive two metadata updates plus a competing pusher
   against one origin (reuse the
   `AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK` seam that
   `tests/test_verified_update.sh:190` already uses to inject a competing push)
   and assert every run ends **either** `UPDATED:` / `0` with the local-ref
   invariant holding, **or** `UPDATED_REMOTE_ONLY:` / `3` with
   `diverged` / `local_diverged` and correct counts. Never a silent strand, and
   never `UPDATED:` without the invariant. Keep it deterministic — inject the
   race through the documented hook rather than by sleeping.

## Verification

```bash
bash tests/test_task_push.sh
bash tests/test_verified_update.sh
bash tests/test_usage_update.sh
bash tests/test_skill_render_task_workflow.sh
./.aitask-scripts/aitask_skill_verify.sh
shellcheck .aitask-scripts/aitask_usage_update.sh \
           .aitask-scripts/aitask_verified_update.sh \
           .aitask-scripts/lib/task_utils.sh \
           .aitask-scripts/lib/verified_update_lib.sh
```

Read only the last line of a test file's output for its verdict, and remember
that piping discards the exit status — use `set -o pipefail` or check
`${PIPESTATUS[0]}`.

Live check on this repo: run
`./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --silent`,
confirm it prints `UPDATED:` and exits `0`, then confirm
`./ait git rev-list --count HEAD..@{u}` is `0` and `./ait git log -1 --format=%s`
names the usage-count commit — i.e. the commit reached the **local** branch.

Step 9 (Post-Implementation) covers cleanup, archival and merge.

## Risk

### Code-health risk: medium
- `git merge --ff-only` is a **new write** to the shared `.aitask-data` worktree on a path that previously did nothing whenever it was blocked; it updates files a concurrent agent may be mid-read on · severity: medium · → mitigation: none — accepted; bounded by the `ff_blocked` fails-closed case and its recovery test in the state matrix
- Converting the metadata chain from stdout returns to out-param globals rewrites the calling convention of four functions at once, and a missed `echo` / `$( )` would strand the verdict silently again · severity: medium · → mitigation: none — accepted; the unit test asserting the globals cross the boundary, with its `$( )` negative control, fails loudly on exactly that regression
- `main()` bypasses `commit_metadata_update` on the local path and already holds the value before calling `commit_metadata_update_local`, so an out-param contract that has that helper set `AIT_METADATA_VALUE` corrupts the count/score on a route no remote fixture exercises · severity: medium · → mitigation: none — accepted; the contract table in step 3 states one rule (only the remote path produces a value), and step 6 covers it at both levels — an end-to-end no-remote **count** assertion, plus a direct sentinel-preservation call on both of the helper's returning paths, since the early return is unreachable from the script
- The pre-converge adds a `git push` inside a metadata update, publishing other sessions' *committed* data-branch commits earlier than they would otherwise leave the machine · severity: low · → mitigation: none — accepted; `ait sync` already publishes them the same way
- A third exit status (3) and a second stdout token widen the metadata scripts' contract, and the consumer lives in a rendered skill surface across three agents · severity: low · → mitigation: none — accepted; the tokens are disjoint under `grep 'UPDATED:'`, the single Claude source rerenders to all agents, and `aitask_skill_verify.sh` plus `tests/test_skill_render_task_workflow.sh` gate the change — the latter is the one that fails on stale goldens, which `aitask_skill_verify.sh` does not check

### Goal-achievement risk: low
- The residual `diverged` state is reported, not resolved, and ownership is handed to `./ait sync` · severity: low · → mitigation: inline post-phase converge_race_stress
- The metadata-update tests are legacy-mode fixtures while production is branch mode; a mode-specific defect in the converge seam would be invisible to them · severity: low · → mitigation: inline post-phase branch_mode_metadata_fixture
- An ahead-only push that loses a race to another writer would have terminated `failed` rather than re-fetching, so `converge_race_stress` was asserting an outcome (`diverged` / `local_diverged`) the seam could not reach · severity: medium · → mitigation: none — accepted; step 1's pass rule names the single pass-2 trigger and the exhaustion classification, and step 6 adds a lost-race case with a non-race negative control

### Planned mitigations
- timing: post-phase | name: branch_mode_metadata_fixture | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement risk 2 | desc: build `tests/lib/metadata_update_fixture.sh` :: `setup_branch_mode_metadata_repo` (real `.aitask-data` worktree, the `aitasks`/`aiplans` symlinks, seeded models file, `ait` shim) and re-run the convergence and outcome assertions through it, so the seam is exercised in the shape production runs and t1658_2 can reuse the fixture
- timing: post-phase | name: converge_race_stress | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement risk 1 | desc: drive two metadata updates plus a competing pusher against one origin and assert every run ends either `UPDATED:`/`0` with the local-ref invariant holding, or `UPDATED_REMOTE_ONLY:`/`3` with `diverged`/`local_diverged` and correct counts — never a silent strand

## Final Implementation Notes

- **Actual work done:** All of steps 1–7 as planned, including both inline
  post-phases. `task_data_converge()` + `_task_converge_warn()` +
  `ff_blocked`/`local_diverged` hint arms in `task_utils.sh`; pre-converge,
  the `sync_current_repo_from_remote` → `converge_current_repo_with_remote`
  rename, the pushed-sha capture and the `merge-base --is-ancestor` invariant
  check in `verified_update_lib.sh`; the out-param conversion across the chain
  and both `main()`s; `UPDATED_REMOTE_ONLY:` / exit 3 documented in both
  `--help`s; the third outcome taught to `satisfaction-feedback.md` (rerendered,
  3 goldens regenerated). Tests: 56 new assertions in `test_task_push.sh`
  (182 total), 43 in `test_verified_update.sh` (135), 13 in
  `test_usage_update.sh` (49), plus the shared
  `tests/lib/metadata_update_fixture.sh`.

- **Deviations from plan:** Three, all approved during plan verification and
  recorded in the body above rather than only here.
  1. The plan's "all three functions set both globals" bullet was **wrong** for
     `commit_metadata_update_local` — `main()` already holds the value on the
     local path — and was replaced with a single contract table (only the remote
     path produces a value).
  2. The two-pass loop had no specified trigger, and its ahead-only arm
     terminated `failed` on the racing case, making `converge_race_stress`'s
     `diverged`/`local_diverged` assertion unreachable. A lost non-fast-forward
     push is now the one thing that consumes pass 2.
  3. The Verification block gained `tests/test_skill_render_task_workflow.sh`:
     `aitask_skill_verify.sh` runs **no** golden assertions, so it cannot catch
     a stale golden.

  Two further deviations came out of review:
  4. `_task_converge_warn` gained an undeterminable-counts arm mirroring
     `_task_sync_warn` — without it the `no_upstream` warning claimed a concrete
     "0 local unpushed, 0 remote unpulled" for a state where both probes print
     nothing.
  5. The recovery tests' exit assertions were vacuous: `out="$(cmd | tail -n1)"`
     followed by `${PIPESTATUS[0]}` reads the assignment's status (always 0).
     Both now capture `$?` from the substitution with no pipeline, and the
     ff_blocked case gained the exit assertion it was missing.

- **Issues encountered:**
  - `shellcheck` SC2034 on the last `TASK_CONVERGE_STATUS` assignment: the
    sibling `TASK_*_STATUS` globals escape it only because each has an in-file
    reader. Resolved by making `_task_converge_warn` name the status — which is
    independently justified, since that one function emits three distinct
    non-success statuses where `_task_sync_warn` emits one. The lib's
    `AIT_METADATA_*` out-params, which genuinely have no in-file reader, carry a
    narrow `disable=SC2034` with the reason.
  - The first draft of the converge tests captured `task_data_converge` in
    `$( )` — the exact defect this task removes — so every global read back
    empty. The tests now redirect stderr to a file and read the globals in the
    caller.
  - Two fixture facts: the recovery **rebases** (so an original-sha ancestry
    assertion is wrong; assert surviving content), and `auto_commit`'s
    `git add aitasks/ aiplans/` fails wholesale when either directory is
    missing, silently no-opping the recovery.
  - A concurrent session was active in this worktree throughout (resource-
    admission and gate-ledger work). All commits here are path-scoped; no file
    belonging to that stream was staged.

- **Key decisions:**
  - The local-ref invariant is evaluated as a **runtime fact**
    (`merge-base --is-ancestor "$pushed_sha" HEAD`), never inferred from
    `TASK_CONVERGE_STATUS` — a status token describes the mechanism, the
    ancestry check describes whether the commit is actually present.
  - `blocked` is terminal and fails closed; `diverged` is reported, not
    resolved, with ownership handed to `./ait sync` — and that hand-off is
    **executed** by two recovery tests rather than asserted in prose.
  - Every new test carries a negative control: `pull --rebase` exiting 128 in
    the same fixture state where `merge --ff-only` returns 0; a `$( )` wrapper
    leaving the verdict at its pre-call value; a non-race push failure still
    terminating `failed`; a clean-file run yielding `UPDATED:`/0. Four mutation
    probes confirmed the load-bearing assertions fail on the pre-fix behaviour.
  - The branch-mode assertions were made **discriminating** — `verified.pick`
    stays 80 either way, so the test asserts the data branch gained a commit and
    that `verifiedstats` (absent from the seed) was written there.

- **Upstream defects identified:** None

- **Notes for sibling tasks:**
  - `tests/lib/metadata_update_fixture.sh` is the shared fixture t1658_2 should
    reuse: `setup_remote_metadata_repo <script>` (legacy origin+work) and
    `setup_branch_mode_metadata_repo <script>` (a real `.aitask-data` worktree
    with `aitasks/`/`aiplans/` symlinks and a data-branch-routing `ait` shim).
    Both take the script basename, so t1658_2 can point them at whatever entry
    point it exercises.
  - **`task_data_converge` reports through globals — never call it inside
    `$( )`.** Same for the `AIT_METADATA_*` pair. The unit test in
    `test_verified_update.sh` has a `$( )` negative control that fails loudly on
    a refactor back to a substitution.
  - A branch-mode fixture assertion must be chosen so it cannot pass in legacy
    mode. Prefer "the data branch gained a commit" / "a key absent from the seed
    now exists" over any value that is equal in both modes.
  - t1658_2 owns the cwd / data-worktree-resolution hazard (parent AC5);
    `_ait_detect_data_worktree()` was deliberately left untouched here.
- **Manual-verification failure:** item "[t1658_1] From that partial state, run `./ait sync` and confirm the branch converges (both `./ait git rev-list --count @{u}..HEAD` and `HEAD..@{u}` reach 0) with no work lost." failed; follow-up task t1696.
