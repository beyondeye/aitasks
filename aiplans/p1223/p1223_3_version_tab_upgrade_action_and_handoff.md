---
Task: t1223_3_version_tab_upgrade_action_and_handoff.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_4_cross_repo_settings_seam.md, aitasks/t1223/t1223_5_settings_tab_and_push_action.md, aitasks/t1223/t1223_6_syncer_scope_documentation.md, aitasks/t1223/t1223_7_manual_verification_expand_syncer_scope_version_and_settings.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_1_tabbed_syncer_shell.md, aiplans/archived/p1223/p1223_2_framework_version_and_upgrade_command_model.md
Worktree: (none — profile 'fast': current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-26 17:07
---

# p1223_3 — Version tab, upgrade action, exit-handoff — verified 2026-07-26

> Execution view for `aitasks/t1223/t1223_3_version_tab_upgrade_action_and_handoff.md`.
> Parent design and binding contracts **A, B, C, F, G**:
> `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.
> This plan revises the pre-existing p1223_3 after verification against live
> source at `03eade720`.

## Context

t1223_1 landed the tabbed shell (`tab_versions` is an empty placeholder pane);
t1223_2 landed the headless model `.aitask-scripts/lib/framework_version.py`.
This child wires them together and adds the only framework-mutating action in
the feature: launching `ait upgrade` + `ait setup` for a target repo, including
the safety-critical launcher change in `.aitask-scripts/aitask_syncer.sh`.

**This is the highest-risk child.** Every refusal path is proven by a no-spawn
test, not by inspection.

## Verification findings

Re-read against live source. Anchors from the task file all resolve; thirteen
findings, five of which change the pinned spec (1, 2, 10, 11, 13).

1. **Self-target vs. the active-target gate — the pinned check order makes the
   handoff unreachable.** *(AC deviation, user-confirmed.)* The task file pins
   version-prompt → active-target gate → self-target. But the syncer's own repo
   is exactly where the user works: the live `aitasks` session right now holds
   `monitor`, `board`, `agent-pick-…`×5, `agent-trail-635` — every one of them in
   `tui_registry.TUI_NAMES` or under the `agent-` prefix. Contract C would
   therefore refuse **every** self-upgrade, leaving the contract-A handoff — the
   designated *safe* path, which exits the TUI before touching a file —
   reachable only through the destructive force-override, desensitising that
   confirmation.
   **Decision:** the self-target check runs **first**; for a self target the
   activity result is **advisory** (listed verbatim in the handoff confirmation
   as "these framework windows are live and may break"), never a refusal and
   never force-gated. Cross-repo targets keep the pinned refuse-or-force
   behaviour unchanged. Update the task file's `## Implementation plan` step
   ordering in the same commit.

2. **The upgrade rewrites the wrapper while bash still holds it open.**
   *(AC deviation, user-confirmed.)* `ait upgrade` runs `install.sh --force`,
   which extracts over `.aitask-scripts/` — including `aitask_syncer.sh` itself.
   Once `exec` is dropped, the wrapper is a live bash process reading that file.
   (Measured: GNU tar unlinks and recreates, so on Linux the running fd keeps
   the old inode — the hazard is real but not currently biting.) **Decision:**
   the validated upgrade runs via `exec`, so bash never reads the wrapper again,
   and the upgrade's exit status propagates naturally. Because `exec` skips the
   `EXIT` trap, the handoff dir is removed explicitly immediately before it; the
   trap still covers every other path. Update the task file's wrapper skeleton.

3. **`tests/test_syncer_rows.py:501` asserts the versions placeholder text.**
   `test_placeholder_panes_render_their_text` checks
   `"Framework versions" in query_one("#versions_placeholder").render().plain`.
   Replacing that Static with the versions table **breaks an existing test** —
   narrow it to `#settings_placeholder` and add a `#versions` DataTable
   assertion.

4. **The existing test fixture does not patch the new impure seams.**
   `booted()` (`test_syncer_rows.py:462-477`) patches only `syncer_app.snapshot`
   and `syncer_app.discover_syncer_sessions`. But
   `test_branch_actions_inert_on_other_tabs_negative_control` (:556) **activates
   `tab_versions`** — so a lazy load fired from tab activation would make the
   existing suite issue a real GitHub call and real `tmux list-windows` against
   the user's live session. `booted()` must additionally patch
   `syncer_app.resolve_latest_version`, `syncer_app.get_tmux_windows_result`
   (finding 10) and `syncer_app.resolve_pane_id_by_pid` — plus the two seams in
   finding 12; the new names are therefore imported **into `syncer_app`'s
   namespace** so `mock.patch.object` reaches them. The Verification section
   below carries the authoritative patch list.

5. **`_active_tab()` fail-open is fail-*closed* for the new gate.** It degrades
   to `"tab_branches"` on any exception (`syncer_app.py:471-482`), so a
   pre-mount / no-running-app `check_action("upgrade")` returns `False` — the
   destructive action is inert, which is the safe direction. Pin it with a test
   rather than leaving it incidental.

6. **Spawn target for a registry-only repo.** `AitasksSession.session` is
   populated even for `is_live=False` entries (resolved from that project's
   `tmux.default_session`), so the canonical pattern applies verbatim:
   `new_session = <session name> not in get_tmux_sessions()`
   (`agentcrew_runner.py:438`), guarded by `is_tmux_available()`. In this plan
   the session name is read off the captured `UpgradeTarget` (finding 11), never
   off a live `AitasksSession`.
   `TmuxLaunchConfig`'s first four fields are positional-required.

7. **API shapes confirmed.** `build_upgrade_command(root, version)` →
   `(command_str, [quoted_ait, version])`, so `[0]` is correct.
   `build_handoff_request` → exactly `{"root": abspath, "version": v}`.
   `write_handoff_request` uses `mkstemp` (mode `0600`) + `os.replace` and does
   **not** create the target directory — the wrapper owns it.
   `detect_target_activity(session, windows)` takes the tmux session **name**
   (a `str`, currently unused in the body) and `windows` as `(index, name)`
   tuples from `get_tmux_windows(session_name)`. `AitasksSession` has **no**
   `label` field — labels come from `build_labels()` → `{session.key: label}`.

8. **Launcher facts.** `aitask_syncer.sh` (23 lines) sources **three** libs —
   `lib/aitask_path.sh`, `lib/python_resolve.sh` and `lib/terminal_compat.sh`
   (the last supplies `die`) — runs under `set -euo pipefail`, and `exec`s on
   line 23. Dropping `exec` means the app's non-zero exit would abort the script
   before the handoff is handled, so its status must be captured
   (`rc=0; "$PYTHON" … || rc=$?`). The script has **no `--source-only` guard**,
   so its test exercises it end-to-end only. `AIT_PYTHON` is the first candidate
   in `resolve_python` (`lib/python_resolve.sh:50-52`) — that is the test seam
   for stubbing the app. `tests/test_no_raw_tmux.sh` does **not** allowlist the
   wrapper; it adds no tmux, and the guard is run to prove it.

9. **`test_shortcuts_registry_coverage.sh` instantiates `SyncerApp`** with
   `Namespace(interval=None, no_fetch=False, dry_run=False)` and asserts every
   `Binding.action` is registered under scope `"syncer"`. New bindings get that
   free through the existing `ShortcutsMixin` path — provided the constructor
   stays I/O-free (another reason the version load is lazy).

10. **The activity gate is fail-OPEN on an enumeration failure — the pinned
    wiring is unsafe.** `get_tmux_windows` returns `[]` whenever `rc != 0`
    (`agent_launch_utils.py:279`), and `TmuxClient.run` folds
    `TimeoutExpired` / `FileNotFoundError` / `OSError` into `(-1, "")` — so a
    tmux timeout, a vanished session and "this session genuinely has zero
    windows" are **indistinguishable** at the call site. Fed straight into
    `detect_target_activity`, an empty list yields `offending == []` and
    `registry_ok == True` → **`"idle"`** (`framework_version.py:193-200`), and a
    live target is upgraded un-forced. The *classifier* is fail-closed
    (t1223_2's contract); the *enumeration* is not.
    **Fix:** add `get_tmux_windows_result(session) -> tuple[list[tuple[str, str]],
    str | None]` to `agent_launch_utils` preserving the failure reason, and
    reimplement the existing `get_tmux_windows` as a thin wrapper over it so its
    ~10 current callers are untouched. The syncer uses the checked variant and
    maps a non-`None` reason to `unknown:tmux-enumeration-failed` — a refusal
    (force-overridable), never `idle`. `rc == 0` with zero windows still means
    `idle`, correctly.

11. **The upgrade target must be captured, not re-resolved.** The flow chains
    2–4 modal screens, each resuming in an async `push_screen` callback. Rows are
    immutable today (`self.sessions` / `self._rows` / `_rows_by_key` are built
    once in `__init__`, `syncer_app.py:378-389`, and never reassigned), so a
    lookup-map *reorder* is not currently reachable — but the DataTable cursor
    **is** movable between one modal dismissing and the next being pushed, and
    t1223_5 adds a second matrix that makes a runtime rebuild a plausible near
    change. **Fix:** build an immutable `UpgradeTarget` when the action starts
    and thread it through every callback; nothing after the first step reads the
    table, `_version_rows_by_key`, or the `AitasksSession` it was derived from.
    The frozen target therefore carries **every** field a later step needs —
    `session_key`, `session_name`, `is_live`, `root`, `label`, `installed`:
    `is_live` gates the activity probe, and `session_name` is what the spawn,
    the pane-id resolution and the lifecycle re-poll all use. A target missing
    either field forces a callback to reach back for a session object, which is
    exactly the coupling this fix removes.

12. **`get_tmux_sessions()` and `is_tmux_available()` are also live seams.** The
    spawn path uses `get_tmux_sessions()` (a real `list-sessions`) to choose
    `new_session`, and `is_tmux_available()` calls `shutil.which`. Both must be
    patched in `booted()` alongside the seams in finding 4, or the suite's
    assertions become host-dependent.

13. **Contract B says "exactly two members" — validate the shape, not just the
    field types.** Rejecting non-`str` values and newline-bearing roots does not
    refuse an extra member, and `json.loads` silently keeps the **last** of
    duplicate keys. A test that only proves nothing was executed does not prove
    malformed input was refused. **Fix:** the parser validates the exact object
    shape — a `dict` whose key set is exactly `{"root", "version"}`, both values
    `str`, no embedded newline — using `object_pairs_hook` to reject duplicate
    keys, and exits non-zero on any deviation so the wrapper's `die` fires and
    nothing runs.

Also: the task file's verification block says `bash tests/test_syncer_rows.py`;
it is a Python file — correct it to `python3` while implementing (same
correction t1223_1 made in its own task file).

## Steps

### 1. Version rows (read-only first)

Read `aidocs/framework/tui_conventions.md` and `aidocs/framework/tmux_gateway.md`
first (both required by CLAUDE.md).

In `.aitask-scripts/syncer/syncer_app.py`, next to `RowSpec` / `build_rows`:

- `@dataclass(frozen=True) VersionRow(row_key, session_key, project_label)` —
  one row **per repo**, not per repo×ref.
- `build_version_rows(sessions, labels) -> list[VersionRow]` — pure, keys `v0`,
  `v1`, … reusing `build_labels()` (`:168`) for collision-safe labels. Keys are
  **opaque and positional**, recovered through `self._version_rows_by_key`,
  exactly as `RowSpec` documents (`:109-124`). Never parse a path out of a key.
- Replace the `#versions_placeholder` Static in `TabPane(id="tab_versions")`
  with `DataTable(id="versions", cursor_type="row", zebra_stripes=True)`,
  columns **Project · Installed · Latest · Status · State**. `compose()` is not
  otherwise re-shaped (per t1223_1's sibling note).

### 2. Lazy shared-latest resolution

- Per-repo `installed` comes from `read_installed_version(root)`; `latest` is
  resolved **once per refresh, shared by every row** — never N network calls.
- **Loaded lazily**, on the first activation of `tab_versions` (hook the
  existing `on_tabbed_content_tab_activated`, `:496-505`) and on the re-check
  key. Nothing fires at boot, so a user who never opens the tab makes no network
  call and `SyncerApp.__init__` stays I/O-free (finding 9).
- Honour the existing `f` fetch-off toggle (`self._fetch`): with fetch off,
  make **no** network call and render the last known latest with a stale marker.
  (`toggle_fetch` stays Branches-only; `self._fetch` is global state.)
- Run in `@work(thread=True, exclusive=True, group="syncer-versions")` with its
  own `_versions_gen` / `_versions_active` / `_pending_versions` triple, reusing
  the existing pure `coalesce_request()` helper (`:259-279`) — the same
  generation-guard + single-pending-slot machinery, not a second invention. The
  apply callback drops results when `gen != self._versions_gen`.
  A separate worker group keeps the 10 s-bounded GitHub call off the Branches
  refresh tick.

### 3. Upgrade action (`U`) and re-check (`c`)

Two new `Binding`s appended to `BINDINGS` (`:360-370`) — `Binding("U",
"upgrade", "Upgrade")` and `Binding("c", "recheck_version", "Re-check")` —
remappable for free through `register_app_bindings("syncer", …)`. Add a
module-level `VERSION_TAB_ACTIONS = ("upgrade", "recheck_version")` and a
symmetric gate at the top of `check_action` (returning `False`, mirroring the
tab gate) so both keys are inert on `tab_branches` and `tab_settings` — a
sibling tuple, per t1223_1's note, not a parallel check. Both bindings are
`show=True`. (`a`/`agent_resolve` stays `show=False`: it is a Branches-tab
failure-recovery action, unchanged by this task.)

**Flow — order is binding:**

0. **Capture the target (finding 11).** The first thing `action_upgrade` does is
   resolve the highlighted version row **once** into a frozen
   `UpgradeTarget(session_key, session_name, is_live, root, label, installed)`.
   Every later step and every modal callback receives that object; nothing
   downstream reads the DataTable cursor, `_version_rows_by_key`, or the
   originating `AitasksSession` again.
1. **Version prompt** — `UpgradeTargetScreen`: a `RadioSet` with `latest` /
   `pinned` (explicit mode selector, no magic value) plus an `Input` for the
   pinned value, validated in-dialog with `re.fullmatch(VERSION_RE, value)`.
   Rejects inline; never passes an invalid value on.
2. **Self-target check (contract A) — now first (finding 1).**
   `is_self_target(target.root, Path.cwd())`.
   - **Self:** if `os.environ.get("AIT_SYNCER_HANDOFF")` is unset → **refuse**
     with "relaunch via `ait syncer`, or run `ait upgrade` from a shell"; never
     spawn, never silently no-op. Otherwise run `_probe_activity` (below) and
     show `HandoffConfirmScreen`: names the repo + version, explains the TUI
     exits first and the upgrade runs in this window, and — when the result is
     not `idle` — lists the detected window names (or the `unknown` reason)
     **verbatim** as an advisory, with the note that this syncer is among them
     and exits before the upgrade runs. Default focus = Cancel. On confirm:
     `write_handoff_request(path, build_handoff_request(target.root, version))`,
     then `self.exit()`. **No framework file is touched while the TUI is alive**,
     and `launch_in_tmux` is never called.
3. **Active-target gate (contract C) — cross-repo targets only.** Both branches
   call one shared probe, which is where finding 10 is fixed:
   ```python
   def _probe_activity(target) -> str:
       if not target.is_live:
           return "idle"                  # registry-only: no tmux call at all
       windows, err = get_tmux_windows_result(target.session_name)
       if err is not None:
           return "unknown:tmux-enumeration-failed"   # never fall through to idle
       return detect_target_activity(target.session_name, windows)
   ```
   Only a literal `idle` proceeds un-forced; `busy:<names>` **and**
   `unknown:<reason>` both **refuse**, naming the offending windows or the
   reason. An `rc == 0` enumeration returning zero windows is still, correctly,
   `idle`.
4. **Force override** (cross-repo refusals only, never the self-target rule).
   `UpgradeRefusalScreen` shows the reason with Cancel focused and a non-default
   "Force upgrade anyway…" option. Choosing it re-runs `_probe_activity`; if the
   fresh result differs from what the refusal displayed, the force is
   **aborted** and the refusal is re-shown with the new state. Otherwise a
   **separate** `ForceConfirmScreen` lists the freshly-detected names verbatim,
   focuses Cancel, and labels its confirming option exactly "Force upgrade
   anyway — I accept the listed windows may break". No "don't ask again" state
   is ever persisted.
5. **Spawn** — `UpgradeConfirmScreen` names the project label **and** the
   resolved root path, then (all fields read from the captured `target`, never
   re-resolved):
   ```python
   command, _ = build_upgrade_command(target.root, version)
   new_session = target.session_name not in get_tmux_sessions()
   pane_pid, err = launch_in_tmux(command, TmuxLaunchConfig(
       session=target.session_name,
       window=unique_window_name(existing, f"upgrade-{target.label}"),
       new_session=new_session, new_window=True, cwd=str(target.root)))
   ```
   guarded by `is_tmux_available()`.

**Shared-helper addition (finding 10).** In
`.aitask-scripts/lib/agent_launch_utils.py`, add
`get_tmux_windows_result(session) -> tuple[list[tuple[str, str]], str | None]`
carrying the failure reason, and reimplement the existing `get_tmux_windows` as
`return get_tmux_windows_result(session)[0]` so its current callers are
behaviourally untouched. This is the only edit outside `syncer/` and the
launcher.

Modal screens live in a new `.aitask-scripts/syncer/upgrade_screens.py`
(`syncer_app.py` is already 1058 lines), shaped after
`syncer/sync_failure_screen.py`: own `DEFAULT_CSS`, `Binding("escape",
"cancel", show=False)`, `dismiss(<typed result>)`. They declare no
`_shortcuts_scope`, so no manifest entry is needed.

### 4. Lifecycle (contract G)

Per-repo `upgrade_state`, keyed by `target.session_key` (the same
`AitasksSession.key` realpath identity the other per-repo maps use):

- `idle` — normal row.
- `launched` — set at spawn with `pane_pid`, `pane_id`
  (`resolve_pane_id_by_pid(target.session_name, pane_pid)`), `target.session_name`
  and a timestamp. Recording the session name **in the state entry** is what lets
  the later re-poll run without reaching back for a session object. State cell
  reads `upgrading…`; Installed/Latest keep the last **read** values with a
  stale marker — never an assumed new version. If `pane_pid` is `None` (launch
  succeeded, pid uncapturable) go straight to the next state: we cannot observe
  it, so we must not claim to.
- `finished (result unknown)` — the pane is gone, inferred from a later
  `resolve_pane_id_by_pid(state.session_name, state.pane_pid) is None` (checked
  inside the versions worker, so no tmux call on the UI thread). State cell reads
  `re-check needed`. That helper also returns `None` when tmux itself fails; the
  resulting label is a conservative "re-check needed", never a success claim, so
  a false positive is benign — documented, not hidden.

**The UI must never render a success it did not observe.** `c` re-reads
`<root>/.aitask-scripts/VERSION` on demand.

### 5. The launcher change (contracts A + B)

`.aitask-scripts/aitask_syncer.sh` — drop `exec` (line 23):

```bash
_handoff_dir="$(mktemp -d)"; chmod 700 "$_handoff_dir"
# shellcheck disable=SC2064  # expand now, not at signal time
trap "rm -rf '$_handoff_dir'" EXIT INT TERM
export AIT_SYNCER_HANDOFF="$_handoff_dir/request.json"   # unconditional

rc=0
"$PYTHON" "$SCRIPT_DIR/syncer/syncer_app.py" "$@" || rc=$?      # NOT exec

[[ -f "$AIT_SYNCER_HANDOFF" ]] || exit "$rc"
_req="$(cat "$AIT_SYNCER_HANDOFF")"
rm -f "$AIT_SYNCER_HANDOFF"          # unlink BEFORE running: a crash cannot re-trigger

# ONE `"$PYTHON" -c` call, json.load from stdin; prints version then root.
# STRICT SHAPE (contract B, finding 13) — exits non-zero unless the payload is
# a dict whose key set is EXACTLY {"root","version"}, both values str, root
# free of newlines (the two-line output protocol must stay decidable), and
# with no duplicate keys (object_pairs_hook — json.loads otherwise silently
# keeps the last). NEVER source, NEVER eval, NEVER interpolate unparsed.
_parsed="$(printf '%s' "$_req" | "$PYTHON" -c '…')" || die "…"
IFS= read -r _version <<<"$_parsed"
_root="$(printf '%s' "$_parsed" | tail -n +2)"

# Revalidate — this is the security boundary, independent of the app's check
[[ "$_root" == /* && -d "$_root" \
   && -f "$_root/aitasks/metadata/project_config.yaml" \
   && -x "$_root/ait" ]] || die "…"
[[ "$_version" =~ ^(latest|[0-9]+\.[0-9]+(\.[0-9]+)?)$ ]] || die "…"

rm -rf "$_handoff_dir"; trap - EXIT INT TERM
exec bash -c '"$1/ait" upgrade "$2" && "$1/ait" setup' bash "$_root" "$_version"
```

Binding properties:

- **The wrapper owns the path** — `export` is unconditional, so an inbound
  `AIT_SYNCER_HANDOFF` has no effect. Dir `0700`; the file is `0600` by
  `mkstemp` default on the app side.
- **Data only, exact shape** — two JSON string scalars, no command string,
  parsed with `json.load`; any extra member, missing member, duplicate key,
  non-string value or newline-bearing root is refused with a non-zero exit and
  nothing is run.
- **Revalidated wrapper-side** (mirrors `path_is_aitasks_project`,
  `aitask_project_resolve.sh:207-211`) before anything is constructed.
- **Built from validated parts** — passed as **positional arguments** to
  `bash -c`, so nothing is interpolated into shell text at all (strictly
  stronger than quoting, and the `&&` stays load-bearing).
- **Cleared on every exit path** — unlinked after read; `rm -rf` + `trap -`
  immediately before the `exec`; the `EXIT INT TERM` trap covers normal exit,
  `die`, and signals.
- `die` comes from the already-sourced `terminal_compat.sh`.

## Verification

```bash
python3 tests/test_syncer_rows.py
bash    tests/test_syncer_upgrade_handoff.sh
bash    tests/test_no_raw_tmux.sh
bash    tests/test_shortcuts_registry_coverage.sh
shellcheck .aitask-scripts/aitask_syncer.sh
```

**Python — extend `tests/test_syncer_rows.py`** (pure half for the row model and
the new `agent_launch_utils` helper; `run_test()` half for the app). `booted()`
gains patches for `resolve_latest_version`, `get_tmux_windows_result`,
`resolve_pane_id_by_pid`, **`get_tmux_sessions`, `is_tmux_available`**
(findings 4 + 12) and a `launch_in_tmux` spy. No test may reach real tmux or the
network.

1. **Active cross-repo target refuses and does not spawn** — a live session with
   a `board` window: the refusal names `board` and the spy records **zero**
   calls. Load-bearing: must fail if the gate is removed.
1b. **Failed enumeration refuses and does not spawn (finding 10)** —
   `get_tmux_windows_result` returns `([], "…")` for a live target: the action
   refuses with `unknown:tmux-enumeration-failed`, the spy records **zero**
   calls. Negative control: must fail if the reason is dropped and the empty
   list is fed to `detect_target_activity` (which would return `idle`).
1c. **The new helper itself (pure)** — with `agent_launch_utils._TMUX.run`
   mocked: `rc == 0` → parsed `(index, name)` tuples and `err is None`;
   `rc != 0` → `([], <reason>)`; `rc == 0` with empty output → `([], None)`, so
   a genuinely window-less session is still `idle`. Plus: `get_tmux_windows`
   returns exactly the first element for each case (existing callers unchanged).
2. **Registry-only target makes no tmux enumeration call** — a captured target
   built from an `is_live=False` session: the `get_tmux_windows_result` spy
   records **zero** calls, the flow reaches the confirmation as `idle`, and the
   spawn still resolves `new_session` from `get_tmux_sessions()` and targets
   `target.session_name` (populated from that project's `tmux.default_session`,
   finding 6). Also exercises the captured-target path end-to-end for a session
   object that is never re-read: pins that `is_live` and `session_name` are
   carried **on** the frozen target (finding 11) rather than dereferenced off an
   `AitasksSession` in a callback.
3. **Idle live target spawns once** with `cwd` equal to the target root, the
   command from `build_upgrade_command`, and `new_window=True`.
4. **Self-target never spawns** — zero spy calls; the handoff file exists and
   contains exactly `{"root": …, "version": …}`.
5. **Self-target with `AIT_SYNCER_HANDOFF` unset refuses** — zero spawns, zero
   files written, refusal message shown.
6. **Self-target advisory, not refusal (pins finding 1)** — a self target whose
   windows include `board` still reaches the handoff confirmation, the dialog
   body lists `board` verbatim, and confirming writes the request. Negative
   control: must fail if the self path is routed through the refusal screen.
7. **Force-override freshness** — a refusal displaying `busy:board` whose
   re-enumeration returns `busy:board,monitor` **aborts** the force: zero
   spawns, refusal re-shown with the new names.
8. **Lifecycle** — after a spawn the State cell renders `upgrading…` while
   Installed still shows the *old* version with a stale marker; with the pane
   gone it renders `re-check needed`; **no state ever renders a success string**.
9. **Per-tab gating** — `upgrade` / `recheck_version` are `False` on
   `tab_branches` and `tab_settings`, `True` on `tab_versions`; and on an app
   with no running query (`_active_tab()` degrade path) `upgrade` is `False` —
   fail-closed (finding 5).
10. **Lazy load negative control** — booting and staying on Branches makes
    **zero** `resolve_latest_version` calls; activating `tab_versions` makes
    exactly **one**, shared across N rows (not N).
11. **Fetch-off** — with `no_fetch=True`, activating the tab makes zero network
    calls and renders the last known latest with the stale marker.
12. **Row model (pure)** — `build_version_rows` yields one row per repo with
    keys `v0…vN` and collision-safe labels; `_version_rows_by_key` round-trips.
12b. **Captured target survives mid-flow mutation (finding 11)** — start the
    upgrade on repo A, then, while the confirmation is open, move the DataTable
    cursor to repo B **and** reorder/repoint `_version_rows_by_key`; confirming
    must still spawn with `cwd == A`. Load-bearing: fails the moment any
    callback re-resolves the target from the table or the lookup map, and stands
    as the forward guard for t1223_5 making the row set rebuildable.
13. **Placeholder test updated (finding 3)** — `#settings_placeholder` still
    renders its text; `#versions` resolves as a `DataTable`.

**Bash — new `tests/test_syncer_upgrade_handoff.sh`** (template:
`tests/test_setup_find_modern_python.sh` for the stub/`mktemp -d`/`trap` shape;
`tests/lib/asserts.sh` for the helpers). Seam: `AIT_PYTHON=<stub>`, where the
stub delegates real `-c` work to the system `python3`, short-circuits the
`import textual` / `import yaml` probes to exit 0, and simulates the app when
invoked with `syncer_app.py`. A stub `ait` sits in a fake repo carrying
`aitasks/metadata/project_config.yaml`.

14. An inbound `AIT_SYNCER_HANDOFF=/tmp/attacker.json` is **overwritten** — the
    wrapper never reads that path.
15. A request whose `root` lacks `aitasks/metadata/project_config.yaml` ⇒
    refused, stub `ait` never invoked, exit non-zero.
16. A request whose `version` is `"; touch /tmp/pwned"` ⇒ refused, no file
    created.
17. Request content is **never executed as code** — a `root` value crafted so
    that sourcing/eval would create a canary; assert the canary is absent
    **and** that the wrapper exited non-zero with `ait` never invoked (finding
    13: proving nothing ran is not the same as proving the input was refused).
17b. **Exact-shape enforcement (finding 13)** — each of these is refused with a
    non-zero exit, a printed reason, and `ait` never invoked: an extra member
    (`{"root":…,"version":…,"extra":1}`); a missing member; a duplicate `root`
    key in the raw JSON text; a non-string `version` (`{"version": 1.2}`); a
    `root` containing an embedded newline. Positive control: the exact
    two-member object is accepted.
18. The request file is **unlinked before** the upgrade runs (the stub `ait`
    asserts it is already gone when it executes).
19. The temp dir is removed on normal exit, after `SIGINT` during the app,
    **and** on the upgrade path (pins the pre-`exec` cleanup, finding 2).
20. With no request file, the wrapper exits cleanly, never invokes `ait`, and
    propagates the app's exit status.
21. Ordering: the stub `ait` records a marker proving it ran **after** the
    Python process exited.

**Harness falsifiability** (repo convention): after green, mutate and re-run —
drop the cross-repo activity gate (test 1 must fail); make `_probe_activity`
ignore the enumeration error and pass the empty list through (test 1b must
fail); route the self path through the refusal screen (test 6 must fail); drop
the pre-launch re-probe (test 7 must fail); make the `launched` state render a
success string (test 8 must fail); remove the `VERSION_TAB_ACTIONS` gate (test 9
must fail); make the version load eager (test 10 must fail); re-resolve the
target from the table in the confirm callback (test 12b must fail); drop
`is_live` / `session_name` from `UpgradeTarget` and dereference the originating
session object in `_probe_activity` or the lifecycle re-poll instead (test 2
must fail); relax the wrapper's key-set check to "contains root and version"
(test 17b must fail);
drop the wrapper's `export` of `AIT_SYNCER_HANDOFF` (test 14 must fail); move
the `rm -f` after the upgrade (test 18 must fail). Restore by undoing **only**
the mutation — never `git checkout --`.

No test manipulates tmux destructively (the Python tests spy on
`launch_in_tmux`; the bash tests stub `$PYTHON` and `ait`), so the
"tmux-stress tasks run outside the main aitasks tmux" rule does not apply — but
findings 4 and 12 are what keep the suite off the live session and the network:
every impure seam on the new paths (`resolve_latest_version`,
`get_tmux_windows_result`, `get_tmux_sessions`, `is_tmux_available`,
`resolve_pane_id_by_pid`, `launch_in_tmux`) is patched in `booted()`.

Manual/live coverage: t1223_7.

## Risk

### Code-health risk: medium
- `aitask_syncer.sh` loses `exec` and gains post-exit parsing that ends in a
  framework-rewriting command — a small but security-relevant launcher change
  in a script every `ait syncer` invocation runs · severity: medium ·
  → mitigation: contract **B** (wrapper-owned path, data-only JSON, independent
  revalidation, positional-arg command construction, `trap` + pre-`exec`
  cleanup) proven by bash tests 14–21 + `shellcheck`
- `syncer_app.py` (already 1058 lines, load-bearing for daily git sync) gains a
  second table, a second worker group and new gating; a regression breaks a
  workflow the user relies on · severity: medium · → mitigation: modals split
  into `syncer/upgrade_screens.py`, the row model kept pure (test 12), a
  separate worker group so the Branches tick is untouched, and t1223_1's
  Branches regression tests left intact
- The new code paths call tmux and the network from a TUI the existing test
  fixture boots for unrelated assertions; an unpatched seam would make the whole
  suite hit the user's live tmux session and GitHub · severity: medium ·
  → mitigation: finding 4 — `booted()` patches all three seams, with test 10 as
  the zero-call negative control
- `get_tmux_windows` is refactored to wrap a new checked variant, touching a
  helper with ~10 existing callers across monitor / switcher / agent launch ·
  severity: low · → mitigation: purely additive — the old function keeps its
  exact signature and returns `…_result(session)[0]`; test 1c pins both halves
- `_active_tab()` is fail-open by design, so the new gate's fail-closed
  behaviour is a consequence rather than a structural guarantee · severity: low
  · → mitigation: test 9's degrade-path assertion pins it explicitly

### Goal-achievement risk: medium
- The self-target ordering deviation changes a pinned contract-C interaction; if
  the advisory is wrong, a self-upgrade proceeds while live agents are running
  · severity: medium · → mitigation: user-confirmed decision (finding 1),
  advisory lists the live windows verbatim, test 6 pins advisory-not-refusal,
  and t1223_7 verifies it live
- The activity gate's inputs are best-effort: contract C's declared bound
  (tmux-session-scoped only) still holds, and an enumeration failure now
  refuses rather than passing — but a `busy` classification remains only as
  good as the window names tmux reports · severity: low · → mitigation:
  finding 10's checked enumeration + test 1b; the residual bound is stated in
  `framework_version`'s module docstring and documented by t1223_6
- The `exec`-based handoff is proven only against stubs in-task; the real
  exit-then-upgrade sequence is not demonstrated end-to-end here · severity:
  medium · → mitigation: bash tests 18–21 pin unlink-before-run, cleanup and
  ordering; the real scratch-repo self-upgrade is owned by t1223_7
- "Pane gone" is inferred from `resolve_pane_id_by_pid` returning `None`, which
  also happens on tmux failure · severity: low · → mitigation: the inferred
  label is `re-check needed` — never a success claim — so a false positive is
  benign; stated in Step 4 rather than hidden
- Lazy loading means a user who never opens the Versions tab never learns their
  repos have drifted · severity: low · → mitigation: accepted by design
  (user-confirmed bounded-polling trade-off); `ait`'s existing 24 h
  update-available hint still covers the local repo

No before/after mitigation tasks were confirmed — each risk is owned by an
in-task test, a binding contract, or t1223_7.

## Post-Review Changes

### Change Request 1 (2026-07-26 17:52)

- **Requested by user:** The wrapper's shared `trap … EXIT INT TERM` only removes
  the handoff directory and returns. A `SIGINT`/`SIGTERM` arriving after the
  request has been copied into `_request` cannot be undone by deleting the file,
  and bash resumes at the next statement — so a cancellation would continue
  through parsing and `exec` the upgrade. Use separate signal traps that clean up
  and exit 130/143, and add a valid-request test that interrupts after the read.
  Disposition: blocking.

- **Verified:** CONFIRMED, by probe rather than by reading: a minimal script with
  `trap "rm -rf '$d'" EXIT INT TERM` that reads a payload into a variable and is
  then sent `SIGTERM` printed `CONTINUED_AFTER_SIGNAL with payload=start` and
  exited **0**. The window is reachable in the real wrapper because the handoff
  parse spawns a Python process between the read and the `exec`.

- **Changes made:**
  1. `.aitask-scripts/aitask_syncer.sh` — replaced the shared handler with a
     `_cleanup_handoff` function plus three traps: `EXIT` tidies, while `INT` and
     `TERM` tidy **and exit** 130 / 143 (the conventional 128+signal statuses).
     The pre-`exec` teardown now calls `_cleanup_handoff` and still clears all
     three traps. Using a function also drops the `SC2064` disable.
  2. `tests/test_syncer_upgrade_handoff.sh` — the stub interpreter gained an
     `AIT_TEST_PARSE_SLEEP` pause inside the handoff parse (identified by the
     `no_dupes` hook in the code string) plus a `parsing` marker, which makes the
     post-read window deterministically reachable. New case 9 sends `SIGTERM` to
     the **wrapper alone** — not the process group, so the parse it is waiting on
     completes normally and the request genuinely is in memory — then asserts
     `ait` was never invoked, the exit status is 143, and the handoff dir is gone.
  3. Task file — recorded as an AC deviation under the wrapper requirements and
     as verification step 13b.

- **Negative control:** reverting only the trap change (back to
  `trap '_cleanup_handoff' EXIT INT TERM`) makes case 9 fail with `ait` invoked
  and the wrapper exiting 0 — the reported hazard, reproduced. Restored by
  undoing the mutation alone; suite back to 48/48.

- **Files affected:** `.aitask-scripts/aitask_syncer.sh`,
  `tests/test_syncer_upgrade_handoff.sh`,
  `aitasks/t1223/t1223_3_version_tab_upgrade_action_and_handoff.md`.

## Out of scope

Settings content (t1223_4 / t1223_5), documentation (t1223_6), and live
end-to-end verification (t1223_7). No change to the Branches tab's behaviour.
