---
Task: t1658_data_branch_metadata_push_strands_local_branch.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1658 — Data-branch metadata push strands the local branch

## Context

Every completed pick fires two metadata updates through
`satisfaction-feedback.md` (`aitask_usage_update.sh`, then
`aitask_verified_update.sh`). Both route into
`commit_and_push_from_remote_clone()` in
`.aitask-scripts/lib/verified_update_lib.sh:109`, which builds the commit in a
throwaway `/tmp` clone of `origin/<data-branch>` and pushes `HEAD:<branch>`
straight to origin. **The local branch ref is never advanced.** The only
compensation, `sync_current_repo_from_remote()` → `task_sync()`, is a bare
`git pull --rebase` that refuses outright (exit 128, *before* it fetches)
whenever the shared `.aitask-data` worktree has unstaged changes — close to
permanent with several agents on one checkout. The outcome is then discarded
(`return 0`, no `TASK_SYNC_*` inspection), and `task_sync()` has no push side.

Result: the local data branch drifts behind origin; the next local commit lands
on the stale tip and creates real divergence; every later `task_push()` fails
non-fast-forward. `ait syncer` reports "remote commits not yet pulled" for
commits this machine authored, and it recurs after every manual sync.

Outcome wanted: a metadata update that **reports success only when the local
branch actually contains its commit**, survives a dirty data worktree, names a
recovery path that is *demonstrated* to converge, and closes the cwd hazard in
the same seam.

## Decisions taken (deviations recorded)

**Reconcile seam — `git fetch` + `git merge --ff-only`, not AC2's two options
(user-approved).** Measured in a throwaway fixture (git 2.55.0): remote commit
touching `meta.json`, local worktree dirty on `task.md`:

| seam | dirty NON-overlapping | dirty OVERLAPPING |
|---|---|---|
| `pull --rebase` (today) | `rc=128` "cannot pull with rebase: You have unstaged changes" | same |
| `merge --ff-only` | `rc=0`, behind→0, `M task.md` preserved verbatim | `rc=1` "…would be overwritten by merge: meta.json / Aborting" |

`--autostash` is rejected: it runs an internal `git stash` across the **shared**
`.aitask-data` worktree, removing other live sessions' unstaged `aitasks/` /
`aiplans/` edits for the rebase window, and a failed pop leaves conflict markers.
`auto_commit()` is rejected for the mirror reason: it stages `aitasks/ aiplans/`
wholesale and would land other sessions' in-flight edits under an
`ait: Update usage count …` message — the unscoped-sweep pattern t1599 exists to
remove. **Neither rejected hazard may re-enter through the replacement:** the
chosen seam never stashes and never commits anything.

**Success means the local-ref invariant holds.** `merge --ff-only` fails closed
when the metadata file itself is locally dirty, and a branch already diverged on
entry cannot be reconciled without a rebase. In both states the commit reaches
origin but *not* the local branch, so reporting the normal `UPDATED:` result
would assert exactly what AC1 forbids. The metadata scripts therefore gain a
**distinct partial outcome** rather than a warning attached to a success.

**The metadata-update chain stops returning its value through stdout.** The
convergence verdict has to reach `main()` alongside the value, and today the
whole chain runs inside `new_value="$(commit_metadata_update …)"` — a subshell,
so a global assigned inside it is discarded. Verified:

```
FLAG=1; inner() { FLAG=0; echo 80; }; v="$(inner)"
after $( ): v=80 FLAG=1     # the assignment never crossed back
```

So the interface changes to **out-param globals plus an exit code**, and every
`$( )` capture is removed from the chain. This also repairs a latent corruption
on the way: `git commit` writes its summary to **stdout**, and `run_git_quiet`
leaves it unredirected when `SILENT=false`, so a non-silent remote run currently
captures `[master 2f1b9fe] ait: Update usage count … / 1 file changed` into
`new_value` and reports it as the count. Without the substitution, git's chatter
goes to the terminal where it belongs.

**Recovery is demonstrated, not asserted.** AC4's "leave the ahead half to a
proven convergence path" is only met if the named recovery is executed in a
test, so the diverged and ff-blocked fixtures both run the documented command
and assert both counts reach zero.

**cwd hazard (AC5) — anchor detection *and* both entry scripts** (user-selected),
verified by driving the **real scripts** from a non-root cwd, not only the
resolution function.

**Decomposition.** Two independent concerns with different blast radii and
different review needs, so this parent splits into two children (siblings
auto-depend, so t1658_2 runs after t1658_1 and reuses its test fixture). All
three confirmed risk mitigations are **inline** (user-selected) and live as
explicit phase blocks in the child plans that own them.

## Child decomposition

### t1658_1 — Converge the local data branch after an off-branch metadata push

Covers **AC1–AC4**.

#### `.aitask-scripts/lib/task_utils.sh` — new `task_data_converge()`

New section after the `task_push` block, following the existing
best-effort-but-never-silent contract (always returns 0; outcome in globals; one
`warn()` on stderr):

```bash
TASK_CONVERGE_STATUS=""   # converged | fast-forwarded | pushed | diverged | blocked | no-remote | failed
TASK_CONVERGE_REASON=""   # classifier code when blocked/diverged/failed
TASK_CONVERGE_AHEAD=""    # local commits not on upstream (post-cycle)
TASK_CONVERGE_BEHIND=""   # upstream commits not on HEAD (post-cycle)

task_data_converge [<context>]
```

Per pass, at most `_AIT_CONVERGE_MAX_PASSES=2` (a race can turn one state into
the other; two passes bound it):

1. `_task_push_has_remote` false → `no-remote`, return.
2. `_task_push_upstream` empty → `failed` / `no_upstream`, warn, return.
3. `_ait_data_git fetch --quiet` — **never touches the worktree**. This is the
   step today's code never reaches. Failure → `failed`, reason from
   `_task_push_classify "$fetch_err" ""`, warn, return.
4. Sample `ahead` = `_task_push_unpushed_count`, `behind` =
   `_task_sync_unpulled_count`, then branch on the pair:

| ahead | behind | action | status |
|---|---|---|---|
| 0 | 0 | nothing | `converged` |
| 0 | >0 | `_ait_data_git merge --ff-only --quiet @{upstream}` | `fast-forwarded`, else `blocked` |
| >0 | 0 | `_task_push_once` (plain push, no worktree op) | `pushed`, else `failed` |
| >0 | >0 | none possible without a rebase | `diverged` |

`_task_push_classify` stays the single source of pattern truth: a blocked ff
classifies as `dirty_worktree`, which `task_data_converge` remaps to the new
code `ff_blocked` so the hint names the real mechanism (a merge, not a rebase).
Two arms are added to `_task_push_reason_hint`, each naming the **exact command
the recovery tests drive** (`./ait sync`, not the `ait syncer` TUI):

- `ff_blocked` → "local edits to the same file(s) block the fast-forward; commit
  them or reconcile with './ait sync'"
- `local_diverged` → "local data branch has both unpushed and unpulled commits;
  reconcile with './ait sync'"

`_task_converge_warn` mirrors `_task_sync_warn`: context string + ahead/behind
pair + hint. Success statuses are silent.

**Why `diverged` is reported rather than resolved.** Resolving it needs a
rebase, and a rebase needs a worktree — either the shared one (the hazard this
task removes) or a scratch worktree whose result rewrites *other sessions'*
commit hashes and can stop on conflicts. The recorded user preference is
explicit: don't force-reconcile a diverged `aitask-data` branch mid-task when
other sessions have uncommitted work there — leave it to the syncer. Ownership
is therefore handed to `./ait sync`, whose convergence is **proved by test**
(below), and the metadata result is downgraded to partial so nothing claims the
commit is local when it is not.

#### `.aitask-scripts/lib/verified_update_lib.sh` — converge before *and* after

Divergence forms when the temp clone is cut from an origin tip that lacks
local's unpushed commits, so:

- **`commit_metadata_update()` — pre-converge, once, before the retry loop**,
  after `branch` / `remote_url` are resolved. An ahead-only branch is pushed
  first (plain push, no worktree op) so the clone's base already contains
  local's commits; a behind-only branch fast-forwards. A branch already diverged
  **on entry** is reported as pre-existing and the update proceeds anyway
  (best-effort — the usage/score bump must not be lost), but its result will be
  partial, not success.
- **`sync_current_repo_from_remote()` → renamed `converge_current_repo_with_remote()`**
  (it now pushes as well as pulls; scope-honest name, single internal call
  site), body `task_data_converge "$1"`.
- **`commit_and_push_from_remote_clone()` — capture, converge, then *verify the
  invariant on the local ref*.** Before `rm -rf "$tmpdir"` on the success path
  capture `pushed_sha="$(git -C "$clone_dir" rev-parse HEAD)"`. After
  converging, assert directly:

  ```bash
  if _ait_data_git merge-base --is-ancestor "$pushed_sha" HEAD 2>/dev/null; then
      AIT_METADATA_LOCAL_CONVERGED=1
  else
      AIT_METADATA_LOCAL_CONVERGED=0
  fi
  ```

  This is AC1's assertion, evaluated at runtime rather than inferred from
  `TASK_CONVERGE_STATUS` — a status token describes the mechanism, the ancestry
  check describes the fact. On `0`, `warn` one contextual line naming
  `$pushed_sha`, the converge status/reason, and the `./ait sync` recovery.

#### Function interface — out-params, not stdout

The three chain functions stop returning through stdout so both the value and
the verdict cross back to `main()` in the caller's own shell:

```bash
AIT_METADATA_VALUE=""            # the new count / score
AIT_METADATA_LOCAL_CONVERGED=""  # 1 = local branch has the commit, 0 = origin only
```

- `commit_metadata_update`, `commit_metadata_update_local` and
  `commit_and_push_from_remote_clone` set **both** globals on every path that
  returns, and both are initialised at the top of the two entry functions so
  `set -u` never bites. Control flow stays on the exit code, unchanged:
  `commit_and_push_from_remote_clone` still returns `10` to request a retry, and
  `die`s are untouched.
- Every `echo "$new_value"` / `printf '%s\n' "$new_value"` in the chain is
  replaced by an `AIT_METADATA_VALUE=` assignment, and the two `main()` call
  sites drop the substitution:

  ```bash
  commit_metadata_update "$models_file" "$AGENT_STRING" "$SKILL_NAME" "$PARSED_MODEL" "$SCORE"
  new_score="$AIT_METADATA_VALUE"
  ```

- The no-remote branch sets `AIT_METADATA_LOCAL_CONVERGED=1` by construction —
  it commits straight to the local branch.
- The one remaining substitution is the `update_model_file` callback
  (`new_value="$("$_AIT_UPDATE_MODEL_FILE_FN" …)"`), which is a pure jq value
  producer that sets no globals. It stays.

#### Outcome contract — a partial result is not a success

`main()` in **both** `aitask_usage_update.sh` and `aitask_verified_update.sh`
reads `AIT_METADATA_LOCAL_CONVERGED` after the (substitution-free) call:

| invariant | stdout | exit |
|---|---|---|
| holds | `UPDATED:<agent>:<skill>:<value>` | `0` |
| does not hold | `UPDATED_REMOTE_ONLY:<agent>:<skill>:<value>` | `3` |

The two tokens are disjoint under a plain `grep 'UPDATED:'`, so no existing
consumer silently mistakes one for the other. `--help` documents both tokens and
exit 3. The local-only (no-remote) path is unaffected: it commits to the local
branch by construction, so it always reports `UPDATED:` / `0`.

**Consumer.** `.claude/skills/task-workflow/satisfaction-feedback.md` (the
single Claude source; `aitask_skill_rerender.sh` regenerates the `default` /
`fast` / `remote` variants for Claude, Codex and OpenCode alike, so there is no
per-agent port) learns the third outcome: on exit 3 / `UPDATED_REMOTE_ONLY:`,
tell the user the score or run count **is** recorded on origin but the local data
branch does not have it yet, name `./ait sync`, and **continue** — a partial
metadata update must not fail the workflow. Run
`./.aitask-scripts/aitask_skill_verify.sh` and regenerate the affected goldens in
the same commit.

#### Tests (t1658_1)

`tests/test_task_push.sh` — the `task_data_converge` state matrix, legacy **and**
branch mode (it already has `setup_remote_and_clone`, `advance_remote`,
`setup_branch_mode`, `reload_task_utils`):

- clean + behind → `fast-forwarded`; `git merge-base --is-ancestor <remote sha> HEAD` holds.
- dirty **non-overlapping** + behind → still `fast-forwarded`, dirty file byte-identical afterwards. Negative control in the same fixture state: `git pull --rebase` exits 128.
- dirty **overlapping** + behind → `blocked` / `ff_blocked`, warning emitted, local ref unmoved, dirty file untouched.
- ahead only → `pushed`, remote has the commit, worktree untouched.
- ahead **and** behind → `diverged` / `local_diverged`, warning emitted, no ref moved.
- no upstream → `failed` / `no_upstream`; no remote → `no-remote`, silent.

**Recovery convergence (AC4's "shows that it converges") — executed, not
claimed.** Two fixtures, each continuing from the state above:

- from the clean **diverged** state, run the documented recovery
  `./.aitask-scripts/aitask_sync.sh --batch`; assert its token is `SYNCED` (or
  `AUTOMERGED`) **and** that both `git rev-list --count @{u}..HEAD` and
  `git rev-list --count HEAD..@{u}` are `0`, and that the local commit is still
  reachable (no work lost).
- from the **ff_blocked** state, same recovery; assert converged and that the
  previously-dirty metadata file's content survived into a commit.

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
- **partial, both directions** (the new outcome, pinned so it can fail):
  metadata file locally dirty → stdout is exactly
  `UPDATED_REMOTE_ONLY:<agent>:<skill>:<value>` and the **exit status is
  captured separately and asserted to be `3`** (not merely "non-zero", and not
  inferred from the stdout token — the whole point is that the verdict reached
  `main()`), the warning is on **stderr only**, and the value is still correct on
  origin. Paired positive control: the identical run with a clean file yields
  `UPDATED:` / `0` — the discriminator is the dirty overlap, nothing else.
- **the out-param boundary itself**, at unit level: source
  `verified_update_lib.sh`, call `commit_metadata_update` **directly, not inside
  `$( )`**, and assert both `AIT_METADATA_VALUE` and
  `AIT_METADATA_LOCAL_CONVERGED` are set in the caller's scope. Negative control
  in the same test: the identical call wrapped in `$( )` leaves
  `AIT_METADATA_LOCAL_CONVERGED` at its pre-call value — so a future refactor
  back to a substitution fails here instead of silently reporting every partial
  update as a success.
- **non-silent value integrity** (the latent corruption this restructure
  removes): run against a remote **without** `--silent` and assert the
  `UPDATED:` line's value field is a bare integer — no `[master abc1234] ait:
  Update …` git summary spliced into it.

**Inline post-phase `branch_mode_metadata_fixture`** (risk mitigation): the
branch-mode fixture is written as a shared helper
`tests/lib/metadata_update_fixture.sh` :: `setup_branch_mode_metadata_repo`
(real `.aitask-data` worktree via `setup_data_branch`, the `aitasks`/`aiplans`
symlinks, a seeded `models_claudecode.json` on the data branch, and the `ait`
shim), then the convergence assertions above are re-run through it. It is a
shared lib rather than a local helper because t1658_2 reuses it for the non-root
cwd tests.

**Inline post-phase `converge_race_stress`** (risk mitigation): drive two
metadata updates plus a competing pusher against one origin and assert the local
branch either converges (`UPDATED:` / `0`) or reports
`UPDATED_REMOTE_ONLY:` / `3` with `diverged` / `local_diverged` and correct
counts — never a silent strand, never `UPDATED:` without the invariant.

### t1658_2 — Anchor data-worktree resolution and the metadata entry scripts to the repo root

Covers **AC5**. Carries the wide blast radius; depends on t1658_1 for the shared
fixture helper.

**`_ait_detect_data_worktree()` ladder** — replace the single cwd-relative probe
with four rungs (first hit wins; result still cached in `_AIT_DATA_WORKTREE`):

1. `./.aitask-data/.git` (dir or file) → `.aitask-data` — today's fast path,
   byte-identical when cwd is the repo root.
2. `<toplevel>/.aitask-data/.git`, `toplevel = git rev-parse --show-toplevel` →
   that absolute path. Covers `website/`, `tests/`, any subdirectory, and a task
   worktree's own link.
3. `<main>/.aitask-data/.git`, `main` from the canonical `ait_main_worktree_root`
   in `lib/data_symlinks.sh` (`AIT_WT_MAIN_ROOT`) → that absolute path. Covers a
   linked worktree never `--link-worktree`d — the crew-worktree case reproduced
   in the task.
4. otherwise `"."` — now reachable only from a genuinely legacy-mode project.

`task_utils.sh` gains `source "${SCRIPT_DIR}/lib/data_symlinks.sh"` (which
sources only `terminal_compat.sh`, so no cycle). **Per the source-on-startup ↔
test-scaffold rule, `setup_fake_aitask_repo` in `tests/lib/test_scaffold.sh`
must copy `data_symlinks.sh` in the same commit** — every scaffolded test that
sources `task_utils.sh` breaks otherwise.

Consumers are safe with an absolute value: each is either
`git -C "$_AIT_DATA_WORKTREE"` or a `"$_AIT_DATA_WORKTREE/<suffix>"` prefix
(`artifact_manifest.sh:34`, `attachment_meta.sh:34`, `attachment_lock.sh:31`,
`artifact_backends/local.sh:18`, `aitask_sync.sh:436`), and the only equality
tests are against `"."` (`aitask_remote_drift_check.sh:131`,
`aitask_sync.sh:92,435`, `task_utils.sh:52,75,154,197`), which legacy still
yields exactly. `_ait_data_gitdir`'s relative `.git/worktrees/-aitask-data` fast
path simply misses off-root and falls through to its `git -C … rev-parse`
branch, correct from anywhere.

**Entry scripts.** `aitask_usage_update.sh` / `aitask_verified_update.sh`
resolve `aitasks/metadata/models_<agent>.json` and `./ait` relative to cwd, so
from a subdirectory they die on "Model config not found" before any fix is
reached. Add `ait_cd_repo_root` to `task_utils.sh` beside the ladder (documented:
entry-point scripts only, never a library) and call it once at the top of each:

```bash
ait_cd_repo_root "$SCRIPT_DIR"   # dirname(SCRIPT_DIR); same rule as `ait`'s cd "$AIT_DIR"
```

No-op in every existing test (they already `cd` to the fixture root).

#### Tests (t1658_2)

`tests/test_task_git.sh` (has `setup_data_branch`) — the resolution rungs: from
`<root>/website/` → the data worktree, not `"."` (rung 2); from a linked
worktree created *without* `--link-worktree` → the main checkout's data worktree
(rung 3); legacy project from a subdirectory → still `"."` (rung 4); existing
tests 1–3 and 5 pass unchanged.

**Real entry points from a non-root cwd** — the resolution tests alone cannot
see a missing, misplaced or later-regressed `ait_cd_repo_root`, so
`tests/test_usage_update.sh` and `tests/test_verified_update.sh` each gain
subprocess tests built on t1658_1's `setup_branch_mode_metadata_repo`:

- launch the real script from `<root>/website/`, and again from an unrelated cwd
  (`/tmp`) via an absolute path;
- assert stdout is exactly `UPDATED:<agent>:<skill>:<value>` and exit `0` — not
  the `Model config not found` die, and not `UPDATED_REMOTE_ONLY:`;
- assert local-ref convergence in the data worktree: the pushed commit is an
  ancestor of local `HEAD` and `git rev-list --count HEAD..@{u}` is `0`;
- run both scripts, since each has its own `main()` and its own `cd` call site.

**Inline pre-phase `characterize_data_worktree_seam`** (risk mitigation), run
**before** the ladder is touched: pin today's `_ait_detect_data_worktree` answer
for every shape (repo root, subdirectory, inside `.aitask-data`, a linked
worktree, a legacy project); assert every `$_AIT_DATA_WORKTREE` consumer plus
`_ait_data_gitdir` resolves the same physical location when the value is
absolute; record the **current failure** of the two non-root entry-point
invocations above so the post-fix pass is a demonstrated flip rather than an
untested green; and sweep for callers relying on the entry scripts' cwd-relative
resolution before the `cd` changes their contract.

## Verification

```bash
bash tests/test_task_push.sh          # t1658_1
bash tests/test_verified_update.sh    # t1658_1, then t1658_2
bash tests/test_usage_update.sh       # t1658_1, then t1658_2
bash tests/test_task_git.sh           # t1658_2
bash tests/test_remote_drift_check.sh # t1658_2 — shares _ait_detect_data_worktree
bash tests/test_init_data.sh          # t1658_2 — shares data_symlinks.sh
bash tests/run_all_python_tests.sh    # t1658_2 — scaffold change reaches Python tests
./.aitask-scripts/aitask_skill_verify.sh          # t1658_1 — skill edit
shellcheck .aitask-scripts/aitask_usage_update.sh \
           .aitask-scripts/aitask_verified_update.sh \
           .aitask-scripts/lib/task_utils.sh \
           .aitask-scripts/lib/verified_update_lib.sh
```

Live check on this repo after t1658_1: run
`./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6
--skill pick --silent`, confirm it prints `UPDATED:` and exits `0`, then confirm
`./ait git rev-list --count HEAD..@{u}` is `0` and `./ait git log -1 --format=%s`
names the usage-count commit — the commit reached the **local** branch. After
t1658_2, repeat it from `website/`.

Step 9 (Post-Implementation) covers cleanup, archival and merge.

## Risk

Levels below are the **post-inline reassessment** (all three mitigations
confirmed inline, plus the decomposition and the partial-outcome contract), not
the pre-mitigation reading.

### Code-health risk: medium
- `_ait_detect_data_worktree()` is sourced by essentially every framework script and 15 of them perform data-branch git ops; rungs 2/3 return an **absolute** path where today's value is the relative `.aitask-data`, so a consumer assuming the relative spelling could silently target a different branch. The new `data_symlinks.sh` dependency also reaches every scaffolded test. Reduced from high: it now lands alone in t1658_2 behind a characterization pre-phase · severity: medium · → mitigation: inline pre-phase characterize_data_worktree_seam
- `git merge --ff-only` is a **new write** to the shared `.aitask-data` worktree on a path that previously did nothing whenever it was blocked; it updates files a concurrent agent may be mid-read on · severity: medium · → mitigation: none — accepted; bounded by the `ff_blocked` fails-closed case and its recovery test in t1658_1's matrix
- The pre-converge adds a `git push` inside a metadata update, publishing other sessions' *committed* data-branch commits earlier than they would otherwise leave the machine · severity: low · → mitigation: none — accepted; `ait sync` already publishes them the same way
- A third exit status (3) and a second stdout token widen the metadata scripts' contract, and the consumer lives in a rendered skill surface across three agents · severity: low · → mitigation: none — accepted; the tokens are disjoint under `grep 'UPDATED:'`, the single Claude source rerenders to all agents, and `aitask_skill_verify.sh` gates the change
- Converting the metadata chain from stdout returns to out-param globals rewrites the calling convention of four functions at once, and a missed `echo`/`$( )` would strand the verdict silently again · severity: medium · → mitigation: none — accepted; the unit test asserting the globals cross the boundary (with the `$( )` negative control) fails loudly on exactly that regression, and the change simultaneously removes a real stdout-capture corruption in the non-silent path
- `aitask_usage_update.sh` / `aitask_verified_update.sh` gain a `cd`, changing their cwd contract for any caller relying on cwd-relative resolution · severity: low · → mitigation: inline pre-phase characterize_data_worktree_seam

### Goal-achievement risk: low
- The residual `diverged` state is reported, not resolved, and ownership is handed to `./ait sync`. Reduced from medium: the recovery is now executed in a fixture that asserts both counts reach zero, and the metadata result is downgraded to partial so no caller reads a stranded commit as success · severity: low · → mitigation: inline post-phase converge_race_stress
- The metadata-update tests are legacy-mode fixtures (single repo, branch `main`) while production is branch mode; a mode-specific defect in the converge seam would be invisible to them. Reduced from medium: the production shape is now exercised through a shared fixture both children use · severity: low · → mitigation: inline post-phase branch_mode_metadata_fixture

### Planned mitigations

All three dispositions are **inline** (user-selected). Because this parent
decomposes, each phase block is written into the child plan that owns it —
named in `addresses` — rather than into this parent plan; no tasks are created
for any of them, so Step 7 / Step 8d find nothing and no-op.

- timing: pre-phase | name: characterize_data_worktree_seam | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health risks 1 and 5 (t1658_2) | desc: before touching the resolution, pin today's `_ait_detect_data_worktree` answer for every shape (repo root, subdirectory, inside `.aitask-data`, linked worktree, legacy), assert every `$_AIT_DATA_WORKTREE` consumer plus `_ait_data_gitdir` still resolves the same physical location under an absolute value, record the current failure of the two non-root entry-point invocations so the fix is a demonstrated flip, and sweep for callers relying on the entry scripts' cwd-relative resolution
- timing: post-phase | name: branch_mode_metadata_fixture | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement risk 2 (t1658_1) | desc: build `tests/lib/metadata_update_fixture.sh` :: `setup_branch_mode_metadata_repo` (real `.aitask-data` worktree, the `aitasks`/`aiplans` symlinks, seeded models file, `ait` shim) and re-run the convergence and outcome assertions through it, so the seam is exercised in the shape production runs and t1658_2 can reuse the fixture
- timing: post-phase | name: converge_race_stress | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement risk 1 (t1658_1) | desc: drive two metadata updates plus a competing pusher against one origin and assert every run ends either `UPDATED:`/`0` with the local-ref invariant holding, or `UPDATED_REMOTE_ONLY:`/`3` with `diverged`/`local_diverged` and correct counts — never a silent strand
