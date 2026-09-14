---
Task: t1784_restore_frozen_record_when_no_session_exists_for_its_root.md
Base branch: main
Output branch: main
---

# t1784 — Restore a frozen record when no session exists for its root

## Context

t1773 made an orphaned frozen record (window closed, tmux server restarted)
restore into a **new window** instead of respawning a dead pane. That branch,
`_launch_into_new_window()` (`.aitask-scripts/lib/agent_restore.py:288-333`),
still needs `discover_aitasks_sessions()` to return a session with a pane whose
cwd walks up to the record's root. When none exists it returns
`no_session_for_root:<root>` and the restore rolls back. This happens after a
server restart with no project session yet: restoring from another project's
monitor, or `ait frozen restore --all` from a bare shell after a reboot, where
no server is running at all. The failure is fail-safe (record stays `frozen`,
capture kept) but can never succeed.

A second defect travels with it. t1773 made the error *name the root*, but
`restore()` rolls back with the fixed reason `"respawn"` (`agent_restore.py:441`).
So the persisted `last_error`, the only channel the replacement viewer reads
(`frozenagent_app.py:553-557`), shows `last restore failed: respawn`. The root
never reaches the user, whatever the `:302-303` comment claims.

Intended outcome: a frozen record whose project has no tmux session restores
into that project's own, freshly created session. **A session the restore did
not create, and that is not already this project's, is never modified.** When
restore cannot succeed, the viewer names the reason.

## Decision: option (b) — create the project's session, owning it first

The task offered (a) the invoking pane's session with `cwd = record root`, or
(b) a dedicated session for the root. **(b)**, via the canonical bootstrap
`lib/tmux_bootstrap.sh` in a new **create-only** mode.

- `tmux_bootstrap.sh` is the documented single source of truth for a project
  session's name (`tmux.default_session`, via `_tmux_bootstrap_resolve_session`),
  its seeded first window (`monitor`), and the env it writes
  (`AITASKS_PROJECT_<session>`, the per-user registry, the syncer window). `ait
  ide` sources it, and `tui_switcher._ensure_session_live`
  (`tui_switcher.py:645-701`) already shells out to it from Python. It creates
  the tmux **server** when none is running, including systemd `session.slice`
  placement on Linux. The restored agent lands in the session `ait ide`
  attaches to next.
- (a) is rejected. It puts project B's agent in project A's session, which breaks
  the one-session-per-project rule (`tui_conventions.md` §"Single tmux session
  per project") and misattributes the agent in `ait monitor`. It also has no
  session to borrow when restoring from a bare shell, or with no server.

### Why the bootstrap's default mode is NOT safe here

The bootstrap's default mode is "ensure", not "create".
`spawn_session_detached` (`tmux_bootstrap.sh:163-192`) creates the session only
when it is absent, but then runs `_tmux_bootstrap_set_project_registry` and
`_tmux_bootstrap_ensure_syncer_window` **unconditionally** (`:191-192`).

Suppose another project, or an unrelated session, already holds B's configured
name. Restoring B would then:
- overwrite `AITASKS_PROJECT_<name>` with B's root;
- add B's `syncer` window to that foreign session, when B has syncer autostart.

`discover_aitasks_sessions()` falls back to that mapping whenever no pane cwd
identifies a project (`agent_launch_utils.py:928-931`). So if the foreign
session's panes sit outside project dirs, re-discovery would **adopt it** and
launch B's agent there. That is the unsafe case this design must close.
(`ait ide` keeps the default mode deliberately: a user running it in B *means*
"this session is B's".)

### Ownership rule

The restore may **only** use a session that either:
1. discovery attributes to the root **before** the restore changes anything
   (today's lookup, unchanged); or
2. **this call created**, as proved by the bootstrap's `BOOTSTRAP_CREATED:<name>`
   in create-only mode.

Create-only mode performs the registry and syncer writes **only after it has
itself created the session**. An existing session of that name, or one created
concurrently between the check and `new-session`, is left completely untouched
and reported as `BOOTSTRAP_FAILED:session_exists:<name>`. The name still comes
from the one shared resolver, `_tmux_bootstrap_resolve_session`, so Python never
resolves it. That also sidesteps `load_tmux_defaults()` returning `"None"` for a
blank name (an upstream defect, see below).

## Changes

### 1. `.aitask-scripts/lib/tmux_bootstrap.sh` — opt-in `--create-only`

`spawn_session_detached <project_root> [--create-only]`. Only the new mode's
behaviour changes; the default path stays the same line for line, so `ait ide`
and the TUI switcher are unaffected.

- Reject any second argument other than `--create-only` (exit 2, usage).
- **Existing session + `--create-only`**: print
  `BOOTSTRAP_FAILED:session_exists:<name>` to stderr, then a human-readable line,
  and `return 43`. This happens **before** the registry and syncer calls, so
  nothing is written.
- **`new-session` fails + `--create-only`**: if `has-session` now succeeds,
  someone created it concurrently; report `session_exists` as above
  (`return 43`). Otherwise keep the existing `return 4`. Either way it returns
  before any write. The default mode keeps `return 4` exactly as today.
- **Created**: the existing registry and syncer steps run, then (create-only
  only) `BOOTSTRAP_CREATED:<name>` goes to stdout, then `return 0`.
- Standalone CLI: `bash tmux_bootstrap.sh [--create-only] <project_root>`.
  Update the usage line and the file header (contract, exit codes 42/43, the
  two sentinels, and why the mode exists).
- Shell conventions: explicit `return <n>` everywhere (never a bare `return`
  after a failed test); diagnostics on stderr. Run
  `shellcheck .aitask-scripts/lib/tmux_bootstrap.sh`.

### 2. `.aitask-scripts/lib/agent_restore.py`

**(a) `_session_for_root(root_real, *, name=None)`.** Extract the discovery
loop (`:295-300`). It returns the first session whose realpath root equals
`root_real`. When `name` is given, it must also carry that session name.

**(b) `_bootstrap_project_session(root) -> tuple[str, str]`**, returning
`(created_session, why)`. It runs
`subprocess.run(["bash", str(_LIB_DIR / "tmux_bootstrap.sh"), "--create-only",
root], capture_output=True, text=True, timeout=BOOTSTRAP_TIMEOUT)` with
`BOOTSTRAP_TIMEOUT = 15`, the TUI switcher's bound.

| outcome | `(created_session, why)` |
|---|---|
| exit 0 and stdout `BOOTSTRAP_CREATED:<name>` | `(<name>, "")` |
| stderr `BOOTSTRAP_FAILED:session_exists:<name>` | `("", "session_name_taken:<name>")` |
| stderr `BOOTSTRAP_FAILED:stale_path` | `("", "stale_path")` |
| exit 0 without the created line | `("", "no creation reported")` — never treated as ownership |
| any other exit | `("", <last stderr line or rc=<n>>)` |
| `TimeoutExpired` | `("", "timeout")` |
| `OSError` | `("", str(exc))` |

`import subprocess` goes at module level so tests can patch it. It spawns `bash`,
not `tmux`, so `tests/test_no_raw_tmux.sh` is unaffected. The helper reaches
tmux only through `lib/tmux_exec.sh` and honours the same `AITASKS_TMUX_SOCKET`
as `agent_frozen_ops`. The 15 s bound sits well inside the 60 s default
stale-op grace of the lease minted by `restore-begin`.

**(c) `_launch_into_new_window`**:

```python
root = os.path.realpath(rec.get("root", ""))
target = _session_for_root(root)            # rule 1: attributed BEFORE we change anything
if target is None:
    created, why = _bootstrap_project_session(rec.get("root", ""))
    # Rule 2: only a session THIS call created. A session that already existed —
    # foreign or not — was left untouched by --create-only, so nothing here could
    # have re-pointed a foreign session's registry entry at this root.
    target = _session_for_root(root, name=created) if created else None
    if target is None:
        detail = why or f"created {created} but no pane of it sits under the root"
        return "", 0, f"no_session_for_root:{rec.get('root', '')}|bootstrap:{detail}"
```

`session_exists` never triggers a second lookup. A same-root session created
concurrently by another restore of this project is a lost race, and the result
is fail-safe and retryable: the retry finds it through rule 1. Everything after
the target is unchanged.

**(d) Persist the failure detail.** In `restore()`'s respawn-stage `except`
(`:440-444`), pass `f"respawn:{exc}"` to `_rollback` instead of `"respawn"`.
The viewer then shows `last restore failed: respawn:no_session_for_root:<root>|bootstrap:session_name_taken:aitasks — capture kept`.
Consumers were checked: the viewer splits on the first `:` only, and the nonce
correlation reads the `<nonce>:` prefix only. Fix the `:302-303` comment.

**(e) Module docstring:** one paragraph on the gone-pane branch and the
ownership rule.

### 3. `tests/test_agent_restore.py` — scripted

**`TestNoProjectSessionBootstrapsOne`** calls `_launch_into_new_window` directly.
It patches `agent_restore.discover_aitasks_sessions` (a `side_effect` list),
`agent_restore._bootstrap_project_session` (`create=True`, see the pre-phase),
`agent_restore.launch_in_tmux` → `(51000, None)` and
`agent_restore.resolve_pane_id_by_pid` → `"%900"`, and swaps `ops._TMUX` for a
`_FakeTmux` answering `list-windows`.

1. **attributed session exists** → bootstrap not called; launch targets it.
2. **none → created `aitasks` → rediscovered** → bootstrap called once; launch
   gets `session="aitasks"`, `new_window=True`, `new_session=False`,
   `cwd=<root>`.
3. **none → `session_name_taken:aitasks`** → the error is
   `no_session_for_root:<root>|bootstrap:session_name_taken:aitasks`; launch is
   not called; **no second lookup is made** (a `side_effect` list of length 1
   proves it).
4. **ownership, not attribution** → the bootstrap reports
   `session_name_taken:aitasks`, but a scripted re-discovery *would* attribute
   a foreign `aitasks` session to this root (the clobbered-registry shape).
   Launch is not called and the result is the error, because rule 2 requires
   our own creation.
5. **created `aitasks`, but re-discovery attributes it elsewhere** → the error
   names it; launch is not called.
6. **stale path** → `…|bootstrap:stale_path`.

**`TestBootstrapHelper`** patches `agent_restore.subprocess.run`:

7. argv is exactly `["bash", <lib>/tmux_bootstrap.sh, "--create-only", root]`
   with a timeout. Every row of the §2b table maps as specified, including
   exit 0 without `BOOTSTRAP_CREATED` → no ownership.

**Through `restore()`** (the existing `_ScriptedTmux` `_run` shape):

8. pane gone (probe rc 1) with `_launch_into_new_window` →
   `("", 0, "no_session_for_root:/x|bootstrap:session_name_taken:aitasks")`. The
   store's `restore-abort` carries `--error respawn:no_session_for_root:/x|bootstrap:session_name_taken:aitasks`.

### 4. `tests/test_restore_session_bootstrap_live.sh` — NEW, real tmux, runs inside tmux

It mirrors `tests/test_frozen_respawn_atomic_live.sh`:
- `require_isolated_tmux` only, which unsets `$TMUX`/`$TMUX_PANE` and repoints
  `TMUX_TMPDIR`, so the suite is safe to run from inside tmux;
- `assert_counters_init`/`assert_counters_load`;
- its own `TMUX_TMPDIR`, and `cleanup` from `frozen_fixtures.sh`.

This is where the collision guarantee is **proven in this session**. The live
acceptance suite cannot run here.

Exported before any server starts:
- `AITASKS_PROJECTS_INDEX="$FIXTURE_DIR/projects.yaml"` (never the real `$HOME`);
- `AIT_NO_SYSTEMD_RUN=1` (a created server stays on the isolated socket);
- `PATH="$FIXTURE_DIR/bin:$PATH"`, where `bin/ait` stubs
  `monitor|syncer → exec sleep 1000`. The bootstrap's windows then stay up
  without booting TUIs, and a `syncer` window becomes observable.

Fixture projects (each has `aitasks/metadata/project_config.yaml`):
- **A**, the owner;
- **B**, the restored one, with `tmux: default_session: <shared name>` and
  `syncer: autostart: true`, so a clobber would visibly add a window;
- a plain non-project dir **O**.

`B` and `A` use the same unique session name `ait_boot_<pid>`.

**Part A — the `--create-only` contract** (drives `tmux_bootstrap.sh` directly):
- **A1 created**: no session. Exit 0; stdout `BOOTSTRAP_CREATED:<name>`; the
  session exists with a `monitor` window; `AITASKS_PROJECT_<name>` = B; the
  projects index names B.
- **A2 collision, panes OUTSIDE project dirs**: session `<name>` has one window
  in O, and the global `AITASKS_PROJECT_<name>=A` (so discovery attributes it to
  A only through the registry, the dangerous shape). Snapshot window names,
  pane ids and the env. Run create-only for B, then assert:
  - exit 43, stderr carries `BOOTSTRAP_FAILED:session_exists:<name>`;
  - `AITASKS_PROJECT_<name>` still names A, and the windows and panes are
    identical, with **no `syncer` window**;
  - the projects index was not written.
- **A3 collision, panes INSIDE project A**, no registry env: same assertions,
  and the env var is still unset.
- **A4 concurrent creation**: make `has-session` report absent at check time
  but the name taken by the time `new-session` runs. A PATH-shimmed `tmux`
  wrapper creates `<name>` (for A) immediately before the real `new-session`.
  Expect exit 43 / `session_exists` and the A2 assertions.
- **A0 control — the default mode on A2's fixture DOES clobber.** The same
  fixture without `--create-only` rewrites `AITASKS_PROJECT_<name>` to B and adds
  a `syncer` window. The assertions are inverted and stay in the suite
  permanently. They prove the A2/A3 detectors can see a clobber, and that the
  flag, not the fixture, is what prevents it (see the pre-phase).

**Part B — `agent_restore._launch_into_new_window` end to end.** A small Python
driver passes a record for B and the command `sleep 4242`, and prints the
`(pane, pid, error)` triple.
- **B1 created**: a server with only an unrelated session in O. Expect a real
  pane in `<name>`, inside a window with the record's window name; the registry
  names B.
- **B2 collision (A2's fixture)**: expect the error
  `no_session_for_root:<B>|bootstrap:session_name_taken:<name>`; A2's
  unchanged-state assertions; and **no `sleep 4242` process anywhere** on the
  server.
- **B3 no server**: `tm kill-server`, then B1's outcome, with the server created
  by the bootstrap.

### 5. `tests/test_frozen_agents_acceptance.sh` — cases 6c and 6d (full stack)

The full-stack proof goes through the shipped wrappers, outside tmux only.
- Suite-wide exports beside the store redirects (`:141`), before the fixture
  server starts: `AITASKS_PROJECTS_INDEX="$SCRATCH/projects.yaml"` and
  `AIT_NO_SYSTEMD_RUN=1`.
- Extend the end-of-run real-`$HOME` check (next to `REAL_SHIM_BEFORE`,
  `:132-133`) to fingerprint `$HOME/.config/aitasks/projects.yaml` as well.
- Monitor stub `$SCRATCH/bin_boot/ait` (`monitor) exec sleep 1000 ;; *) exec "$AIT" "$@"`),
  scoped to the server the case kills:
  - 6c: `tm set-environment -g PATH …`;
  - 6d: a `PATH=` prefix on the restore command.
- `reestablish_fixture_server` (kill-server, then the original
  `tm new-session -d -s "$SESSION" -n scratch -c "$SCRATCH" "sleep 1000"`)
  ends each case, so cases 7–10b run on the fixture they expect.
- **6c — server restarted; only an unrelated session (in `${SCRATCH}_other`)
  exists.** Assert:
  - `RESTORED:$RID`, `live`, a real pane;
  - that pane's session is `aitasks` (the seed default), holding the recorded
    window and `monitor`;
  - `AITASKS_PROJECT_aitasks` names `$SCRATCH`;
  - the unrelated session still has exactly its one window;
  - no second record; slot unchanged; captures deleted; the registry write
    went to `$SCRATCH/projects.yaml`.
- **6d — no server at all.** Assert:
  - `tm list-sessions` fails first;
  - then `RESTORED`, `live`, and session `aitasks` holding the recorded window
    and `monitor`.

  6d also proves that a missing server reads as pane-`gone`, not `unknown`,
  which would fail closed at the preflight.
- Update the header's `Structure` list.

### 6. Docs

- `website/content/docs/tuis/frozenagent/how-to.md` "Bring an agent back", one
  current-state paragraph:
  - a restore comes back in its own pane while the stand-in exists, otherwise in
    a new window of the project's tmux session;
  - if the project has no session (e.g. after tmux restarted), restore creates
    it as `ait ide` would;
  - if that session name is already held by another project, restore leaves
    that session alone and reports `session_name_taken:<name>`. Fix it by
    giving the projects distinct `tmux.default_session` values.

  Then run `cd website && python3 check_links.py --build`.
- The `tmux_bootstrap.sh` header (§1).

## Implementation steps

### Pre-phase (risk mitigations)

1. [pre_fix_control_bootstrap] **Before any source edit**, write the §3 unit
   tests and the §4 live suite and run both against the unfixed code. Record
   the observed lines in the Final Implementation Notes.

   **Unit lane** (`python3 tests/test_agent_restore.py`). Cases 1–6 patch
   `_bootstrap_project_session` with `create=True`; otherwise
   `mock.patch.object` raises on the missing attribute, and the run errors on
   shape instead of exercising the real unfixed routing. Expected results:
   - **1 passes**, a regression guard only;
   - **2 FAILS**, because unfixed code returns `no_session_for_root` instead of
     launching;
   - **3, 5, 6 FAIL**, because the error lacks `|bootstrap:`;
   - **4 passes pre-fix**, vacuously, since unfixed code never bootstraps.
     Note this: its evidence is post-fix only, and it is why Part B2 and A0
     exist;
   - **7 ERRORS**, because neither `_bootstrap_project_session` nor
     `agent_restore.subprocess` exists yet. That is a shape failure; its
     post-fix green is evidence about the helper contract only;
   - **8 FAILS**, because the persisted `--error` is the bare `respawn`.

   **Live lane** (`bash tests/test_restore_session_bootstrap_live.sh`, inside
   tmux). Expected results:
   - **A0 passes**: the unfixed default mode really clobbers A2's fixture. That
     proves A2/A3's unchanged-state detectors can fail;
   - **A1–A4 FAIL on shape**, because the unfixed CLI takes `--create-only` as
     the root path and exits 2;
   - **B1 and B3 FAIL**, because there is no bootstrap, so no session and no
     pane;
   - **B2 passes vacuously**, because nothing bootstraps.

   Acceptance 6c/6d are added in the same step. They cannot run inside tmux, so
   their pre-fix control is **not watched in this session**; say so rather than
   implying it ran.

### Main steps

1. `tmux_bootstrap.sh` `--create-only` (§1), then shellcheck it.
2. `agent_restore.py` §2a–2e.
3. Re-run §3 and §4; everything passes, including A0 (still clobbering in
   default mode) and B2 (now non-vacuous: the bootstrap ran and refused).
4. Acceptance 6c/6d and suite isolation (§5).
5. Docs (§6), plus `check_links.py --build`.
6. The verification set below.

### Post-phase (risk mitigations)

1. [acceptance_isolation_sweep] At Step 8 review, **before** "Commit changes",
   ask the user to run both live suites outside tmux with the `-L ait` server
   stopped: `bash tests/test_frozen_agents_acceptance.sh` and
   `bash tests/test_restore_flows_live.sh`. Confirm:
   - every case passes, including 7–10b after the 6c/6d restarts (a failure
     confined to after 6d points at `reestablish_fixture_server`);
   - the end-of-run check reports the real shim and
     `~/.config/aitasks/projects.yaml` unchanged;
   - `test_restore_flows_live.sh` case 7, whose session exists, still restores
     without bootstrapping.

   Record the pass counts. If they cannot be run, record the suites as
   unverified rather than calling the change end-to-end proven.

## Verification

In this session (inside tmux):

```bash
python3 tests/test_agent_restore.py
python3 tests/test_agent_frozen_ops.py
bash tests/test_restore_session_bootstrap_live.sh   # NEW — collision + creation, real tmux
bash tests/test_frozen_respawn_atomic_live.sh       # regression
bash tests/test_no_raw_tmux.sh
shellcheck .aitask-scripts/lib/tmux_bootstrap.sh
set -o pipefail; bash tests/run_all_python_tests.sh   # read the LAST line only
(cd website && python3 check_links.py --build)
```

Outside tmux, with `-L ait` stopped (the post-phase):
`bash tests/test_frozen_agents_acceptance.sh` and `bash tests/test_restore_flows_live.sh`.

Manual:
1. Freeze an agent, then `tmux -L ait kill-server`.
2. From a plain terminal run `./ait frozen restore --all`.
3. Expect the agent back in the project's session (`monitor` + agent window);
   `ait ide` attaches to it.

## Step 9

Commit as `bug: … (t1784)`, current branch `main`, and archive with the plan.

## Upstream defects identified (for Final Implementation Notes / Step 8b)

- `.aitask-scripts/lib/agent_launch_utils.py:1913-1914 — load_tmux_defaults()
  returns the string "None" for a blank tmux.default_session (the seed ships it
  blank), disagreeing with _read_default_session() and the bash resolver, which
  both return "aitasks"; callers include aitask_board.py:12205/12375,
  agent_command_screen.py, agentcrew_runner.py`

## Risk

### Code-health risk: low
- Two mid-suite server restarts in the shared acceptance suite could perturb
  cases 7–10b if the fixture server is not re-established with the suite's own
  env · severity: low (residual — addressed by inline post-phase
  acceptance_isolation_sweep) · → mitigation: inline post-phase acceptance_isolation_sweep
- A restore now runs a bootstrap that can create the tmux server and write
  tmux global env and the per-user registry, from a detached job. In tests these
  would escape isolation (systemd unit, real `$HOME`) without
  `AIT_NO_SYSTEMD_RUN` / `AITASKS_PROJECTS_INDEX` · severity: low (residual —
  addressed by inline post-phase acceptance_isolation_sweep) ·
  → mitigation: inline post-phase acceptance_isolation_sweep
- `tmux_bootstrap.sh` is shared with `ait ide` and the TUI switcher; an edit
  that leaks into the default path would change their behaviour · severity: low
  · → mitigation: none needed (the mode is opt-in and the default path stays
  the same line for line; Part A0 pins the default mode's behaviour on a
  collision fixture)
- The persisted rollback reason grows from `respawn` to `respawn:<detail>`; an
  exact-string consumer would break · severity: low · → mitigation: none needed
  (consumers checked at planning: the viewer splits on the first colon, and
  the nonce correlation reads the prefix only)

### Goal-achievement risk: medium
- The full-stack proof (acceptance 6c/6d) can only run outside tmux, and this
  session is inside the `ait` session · severity: medium (residual — reduced
  by inline post-phase acceptance_isolation_sweep and by the new in-tmux live
  suite §4, which proves creation and collision against real tmux here; the
  shipped-wrapper path still depends on a run outside this session) ·
  → mitigation: inline post-phase acceptance_isolation_sweep
- Tests written beside the fix could pass without ever having detected the
  defect · severity: low (residual — addressed by inline pre-phase
  pre_fix_control_bootstrap, including the A0 clobber control; the acceptance
  pre-fix control stays unwatched) · → mitigation: inline pre-phase pre_fix_control_bootstrap
- If the configured session name is held by another project, restore still
  cannot succeed. It now refuses without touching that session and names the
  cause · severity: low · → mitigation: none needed (a misconfiguration; the
  docs name the fix)

### Planned mitigations
- timing: pre-phase | name: pre_fix_control_bootstrap | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — tests written beside the fix could pass without detecting the defect | desc: Write the §3 unit tests (bootstrap patched with create=True) and the §4 live suite first, run both against unfixed code, and record which fail and which pass vacuously; the A0 default-mode control proves the collision detectors can fail.
- timing: post-phase | name: acceptance_isolation_sweep | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — mid-suite server restarts and bootstrap side effects escaping test isolation; goal-achievement — the full-stack proof cannot run inside tmux | desc: Have the user run the full acceptance suite and test_restore_flows_live.sh outside tmux before commit; confirm cases 7–10b pass after 6c/6d, the real HOME shim and registry fingerprints are unchanged, and restore_flows case 7 never bootstraps.

## Implementation record

**P0 pre-fix control — watched, 2026-09-14**, both lanes against unfixed code
(tests written first, no source edited).

Unit lane — `python3 tests/test_agent_restore.py TestNoProjectSessionBootstrapsOne
TestBootstrapHelper TestRespawnFailureIsPersisted`: `Ran 10 tests … FAILED
(failures=6, errors=8)` (errors count subtests).

- 1 `an_attributed_session_is_used_without_bootstrapping` — ok (regression guard only).
- 2 `no_session_bootstraps…` — FAIL `('%900', 51000, '') != ('', 0, 'no_session_for_root:…')`.
- 3 `a_taken_session_name…` / 5 `a_created_session_attributed_elsewhere…` /
  6 `a_stale_project_root…` — FAIL: the error has no `|bootstrap:` detail.
- 4 `ownership_not_attribution…` — **deviation from the prediction**: planned
  as a vacuous pass, it FAILED, but on the error SHAPE (no `|` suffix), not on
  adoption. Its "launch not called" half passed vacuously pre-fix, so its
  post-fix green is the only evidence about adoption; B2 is the live evidence.
- 7 `TestBootstrapHelper` (3 tests, 6 subtests) — ERROR
  `AttributeError: module 'agent_restore' has no attribute 'subprocess'`: a
  shape failure; the post-fix green is evidence about the helper contract only.
- 8 `the_rollback_reason_carries_the_launch_error` — FAIL
  `'respawn:no_session_for_root:/x|bootstrap:session_name_taken:aitasks' != 'respawn'`.

Live lane — `bash tests/test_restore_session_bootstrap_live.sh` (inside tmux):
`Passed: 19 / 44`.

- **A0 (control) passed all three assertions** — the unfixed default mode
  really rewrites the foreign `AITASKS_PROJECT_<name>` to B and adds B's
  `syncer` window to A's session. The A2/A3 unchanged-state detectors therefore
  demonstrably can fail.
- A1–A4 FAIL on shape: `spawn_session_detached: not a directory: --create-only`, exit 2.
- B1, B3 FAIL: `no_session_for_root:<proj_b>` — no session, no pane.
- B2: only the error-string assertion failed; its unchanged-state and
  "launched nowhere" assertions passed vacuously (nothing bootstraps).
- Observation: `pane_fmt "" …` resolves to the server's default pane, so B1's
  session/window assertions read `other_<pid>` / `base` pre-fix. The "pane is
  real" assertion is guarded with `[ -n "$pane" ]`, so this cannot mask a
  post-fix failure.

Acceptance 6c/6d: their pre-fix control is **not watched** — the suite refuses
to run inside tmux.

**Post-fix, 2026-09-14 (this session, inside tmux):**

| suite | result |
|---|---|
| `tests/test_agent_restore.py` | 40 OK (the 10 new tests included) |
| `tests/test_restore_session_bootstrap_live.sh` | 44/44 — A0 still clobbers in default mode; A2–A4 untouched; B1–B3 pass; B2 now non-vacuous (the bootstrap ran and refused) |
| `tests/test_frozen_respawn_atomic_live.sh` | 64/64 (regression) |
| `tests/test_agent_frozen_ops.py` | 60 OK |
| `tests/test_no_raw_tmux.sh` | 5/5 |
| `shellcheck .aitask-scripts/lib/tmux_bootstrap.sh` | clean |
| `bash tests/run_all_python_tests.sh` | `PYTHON SUITE: PASSED (runner=unittest, exit=0)` |
| `website/check_links.py --build` | `SWEEP: PASSED`, 0 broken |

**P1 `acceptance_isolation_sweep` — NOT verified.** At Step 8 review the user
was asked to run `tests/test_frozen_agents_acceptance.sh` (new cases 6c/6d, and
7–10b after them) and `tests/test_restore_flows_live.sh` outside tmux with the
`-L ait` server stopped. The user chose "Commit changes" without reporting
results. Both suites refuse to run inside tmux, so the full-stack path through
the shipped wrappers is **unverified**, as is the acceptance pre-fix control.
The acceptance file passes `bash -n`, and its only shellcheck warnings are
pre-existing variables read by the sourced fixtures.

## Final Implementation Notes
- **Actual work done:** Implemented as approved.
  - `tmux_bootstrap.sh` gained an opt-in `--create-only` mode: create the
    session (then register it and print `BOOTSTRAP_CREATED:<name>`), or change
    nothing and exit 43 with `BOOTSTRAP_FAILED:session_exists:<name>`. That
    includes a session created concurrently between `has-session` and
    `new-session`.
  - `agent_restore._launch_into_new_window` now bootstraps the project's own
    session when discovery attributes none to the root. It uses only a session
    attributed to the root before anything changed, or the session this call
    created; after a refused create it makes no second lookup.
  - `restore()` persists `respawn:<error>` rather than a bare `respawn`, so the
    viewer shows the root and the bootstrap's verdict.
  - Tests: 10 new unit tests; the new in-tmux live suite
    `tests/test_restore_session_bootstrap_live.sh`; acceptance cases 6c/6d with
    registry and systemd isolation and fixture re-establishment.
  - Docs: one how-to paragraph.
- **Deviations from plan:**
  - The collision-ownership design (`--create-only`, the ownership rule, the
    new live suite) was added at plan review, after the user caught that the
    bootstrap's default mode would clobber a foreign session. It is part of the
    approved plan.
  - The bootstrap's default path is behaviour-identical, but not literally
    line-for-line as the plan said. It gained an explicit `return 0` (the
    previous final status, from `_tmux_bootstrap_ensure_syncer_window`, was
    always 0) and a create-only `if` that is always false in default mode.
  - The real-`$HOME` registry check greps for the scratch path instead of
    comparing a checksum. A checksum would flake whenever the developer runs
    `ait ide` elsewhere during the run.
- **Issues encountered:**
  - Pre-fix, unit case 4 failed on the error shape rather than passing
    vacuously as predicted (recorded above).
  - `pane_fmt ""` resolves to the server's default pane, so "pane is real"
    assertions are guarded with `[ -n "$pane" ]`.
  - The acceptance and restore-flows suites could not run in this session (see
    P1).
- **Key decisions:**
  - Option (b), a dedicated session, over (a), the invoking pane's session:
    (a) breaks the one-session-per-project rule and misattributes the agent in
    `ait monitor`, and has no session to borrow from a bare shell or with no
    server.
  - Reuse the canonical bootstrap through an opt-in mode rather than forking
    its naming and registry logic. The session name stays with the single bash
    resolver.
  - Ownership is proven only by `BOOTSTRAP_CREATED`; an exit 0 without it is
    never treated as ownership.
  - A0 is kept permanently as the control that proves the unchanged-state
    detectors can fail.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/agent_launch_utils.py:1913-1914 — load_tmux_defaults() returns the string "None" for a blank tmux.default_session (the seed ships it blank), disagreeing with _read_default_session() and the bash resolver, which both return "aitasks"; callers include aitask_board.py:12205/12375, agent_command_screen.py, agentcrew_runner.py`
