---
priority: medium
effort: high
depends: [t1223_2]
issue_type: feature
status: Ready
labels: [tui, auto-update]
gates: [risk_evaluated]
anchor: 1223
created_at: 2026-07-23 18:31
updated_at: 2026-07-23 18:31
---

## Context

Third child of t1223. Wires the headless model from **t1223_2** into the tab
shell from **t1223_1**, and adds the only repo-mutating action in this feature:
launching `ait upgrade` + `ait setup` for a target repo. This is the
safety-critical child — it includes a change to the launcher
`.aitask-scripts/aitask_syncer.sh` that ends in a command which rewrites
framework files.

Parent plan: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.
**Contracts A, B, C, F and G are binding**; the ones this child owns are
restated inline below.

Depends on t1223_1 (`tab_versions` pane id exists) and t1223_2
(`lib/framework_version.py` exists).

## Key files to modify

- `.aitask-scripts/syncer/syncer_app.py` — fill `TabPane(id="tab_versions")`,
  add the version row model, upgrade + re-check actions, lifecycle state.
- `.aitask-scripts/aitask_syncer.sh` — drop `exec` (currently line 23), own the
  handoff request path, post-exit upgrade run.
- `tests/test_syncer_rows.py` — extend.
- **New:** `tests/test_syncer_upgrade_handoff.sh`.

## Reference files for patterns

- `.aitask-scripts/syncer/syncer_app.py:909-948` — `_launch_resolution_agent`, the
  existing in-file precedent for building a launch and spawning it.
- `.aitask-scripts/lib/agent_launch_utils.py:1188` — `launch_in_tmux(command, config)`
  → `(pane_pid, error)`; `:65-95` — `TmuxLaunchConfig` (**`cwd` field is what
  roots the spawn in the target repo**); `:1254` — `resolve_pane_id_by_pid`;
  `:1296` — `unique_window_name`; `:267` — `get_tmux_windows`.
- `.aitask-scripts/lib/tmux_exec.py` — the **only** sanctioned raw-tmux call site.
  `tests/test_no_raw_tmux.sh` enforces this; read
  `aidocs/framework/tmux_gateway.md` before writing any tmux code.
- `.aitask-scripts/syncer/sync_failure_screen.py` — a compact `ModalScreen`
  precedent for the confirm/refuse dialogs.
- `.aitask-scripts/aitask_project_resolve.sh:207-211` — `path_is_aitasks_project`,
  the canonical root marker check the wrapper must replicate.
- `.aitask-scripts/lib/aitask_path.sh`, `lib/python_resolve.sh` — already sourced
  by `aitask_syncer.sh`; `require_ait_python` gives the interpreter for JSON
  parsing.
- `aidocs/framework/shell_conventions.md` — required reading for the `.sh` change.

## Implementation plan

### 1. Version tab (read-only first)

One row **per repo** (not per repo×ref): Project · Installed · Latest · Status ·
State. Build it from `self.sessions` — reuse `build_labels()`
(`syncer_app.py:149`) for collision-safe labels; use **opaque positional row
keys** (`v0`, `v1`, …) recovered through a `_version_rows_by_key` map, exactly as
`RowSpec` does (`:90-105`) — never parse a filesystem path out of a row key.

`Latest` is resolved **once per refresh, shared by all rows** (one network call,
not N). Honor the existing `f` fetch-off toggle: with fetch off, show the last
known latest with a stale marker and make no network call. Run resolution in a
thread worker and reuse the generation-guard/coalescing pattern already in the
file (`coalesce_request`, `:240-260`) rather than inventing a second one.

### 2. Upgrade action

Bound to a new key on the Versions tab, gated through `check_action` +
`_active_tab()` (from t1223_1) and routed through `ShortcutsMixin` (scope
`"syncer"`, `:317`) so it is remappable. Flow:

1. Prompt for target version: `latest` or a pinned value (free text, validated by
   `framework_version.VERSION_RE`; reject in the dialog, don't pass it on).
2. **Active-target gate (contract C).** If `session.is_live` is `False` →
   `idle`, make **no tmux call**. Otherwise call `get_tmux_windows(session)` and
   pass the result to `detect_target_activity()`. On `busy:<names>` → **refuse**,
   showing the offending window names. No override flag; the user closes them and
   re-tries.
3. **Self-target (contract A).** If `is_self_target(root, Path.cwd())`, do **not**
   spawn. Write the handoff request and `app.exit()` (see §3). If the wrapper
   path env var is absent, **refuse** with "relaunch via `ait syncer`, or run
   `ait upgrade` from a shell" — never spawn, never silently no-op.
4. Otherwise: confirmation modal naming the target project **and** its resolved
   root path, then
   `launch_in_tmux(build_upgrade_command(root, version)[0], TmuxLaunchConfig(..., cwd=str(root), new_window=True))`.
   Window name via `unique_window_name(existing, f"upgrade-{label}")`.

### 3. Self-target handoff (contracts A + B) — the launcher change

**App side.** Read the request path from `os.environ.get("AIT_SYNCER_HANDOFF")`.
If unset → refuse (step 2.3). Otherwise
`write_handoff_request(path, build_handoff_request(root, version))` (atomic, from
t1223_2), then `self.exit()`. **No framework file is touched while the TUI is
alive.**

**Wrapper side** — `.aitask-scripts/aitask_syncer.sh`:

```bash
# BEFORE the app runs:
_handoff_dir="$(mktemp -d)"; chmod 700 "$_handoff_dir"
trap 'rm -rf "$_handoff_dir"' EXIT INT TERM
export AIT_SYNCER_HANDOFF="$_handoff_dir/request.json"   # unconditional: ignores any inbound value

"$PYTHON" "$SCRIPT_DIR/syncer/syncer_app.py" "$@"        # NOT exec

# AFTER python has fully exited:
[[ -f "$AIT_SYNCER_HANDOFF" ]] || exit 0
_req="$(cat "$AIT_SYNCER_HANDOFF")"
rm -f "$AIT_SYNCER_HANDOFF"        # unlink BEFORE running, so a crash cannot re-trigger
# parse with "$PYTHON" -c 'import json,sys; ...' — NEVER source, NEVER eval
# revalidate, then run the upgrade
```

Binding wrapper requirements:
- **The wrapper owns the path.** `export` is unconditional — an externally
  supplied `AIT_SYNCER_HANDOFF` has no effect. Dir `0700`, file `0600`.
- **Data only.** Parse the two JSON scalars with `"$PYTHON" -c` + `json.load`.
  The file is **never** `source`d, `eval`ed, or interpolated unparsed, and it
  carries **no command string**.
- **Revalidate before constructing anything** (this is the security boundary,
  independent of the app's check): `root` must be an absolute existing directory
  containing `aitasks/metadata/project_config.yaml` (mirror
  `path_is_aitasks_project`) and an executable `<root>/ait`; `version` must match
  `^(latest|[0-9]+\.[0-9]+(\.[0-9]+)?)$`. Any failure ⇒ print the reason, run
  nothing, exit non-zero.
- **Build the command wrapper-side from the validated parts**, properly quoted.
- **Clear on every exit path** — unlink after read, `trap ... EXIT INT TERM`
  removes the directory on normal exit, error, and signal.
- Removing `exec` means the wrapper stays as the parent process: keep
  `set -euo pipefail` correct around the non-`exec` invocation (the app's exit
  status must not abort the script before the handoff is handled — capture it).

### 4. Lifecycle (contract G)

Per-repo `upgrade_state`:
- `idle` — normal row.
- `launched` — set at spawn; store `pane_pid` (from `launch_in_tmux`), `pane_id`
  (`resolve_pane_id_by_pid`), timestamp. While the pane is alive the State cell
  reads `upgrading…`; Installed/Latest keep the last **read** values with a stale
  marker — **never** an assumed new version.
- `finished (result unknown)` — pane gone. State reads `re-check needed`.

Add an explicit re-check key that re-reads `<root>/.aitask-scripts/VERSION`.
**The UI must never render a success it did not observe.** Self-target has no
state (the TUI is gone).

## Verification steps

```bash
bash tests/test_syncer_rows.py
bash tests/test_syncer_upgrade_handoff.sh
bash tests/test_no_raw_tmux.sh
shellcheck .aitask-scripts/aitask_syncer.sh
```

Python tests (`tests/test_syncer_rows.py`, mock `launch_in_tmux` with a spy):

1. **Active target refuses and does not spawn** — a live session with a `board`
   window: the action produces a refusal naming `board` and the spy records
   **zero** calls. (Load-bearing: must fail if the gate is removed.)
2. **Registry-only target makes no tmux enumeration call** — `is_live=False`
   spy on `get_tmux_windows` records zero calls.
3. **Idle live target spawns once** with `cwd` equal to the target root and the
   command from `build_upgrade_command`.
4. **Self-target never spawns** — spy records zero calls; the handoff file exists
   and contains exactly `{"root": ..., "version": ...}`.
5. **Self-target with `AIT_SYNCER_HANDOFF` unset refuses** — zero spawns, zero
   files written, a refusal message is shown.
6. **Lifecycle** — after spawn the state is `launched` and the State cell renders
   `upgrading…` while Installed shows the *old* version; with the pane gone the
   cell renders `re-check needed`; **no state ever renders a success string**.
7. **Per-tab gating** — the upgrade key is inert on `tab_branches`.

Bash tests (`tests/test_syncer_upgrade_handoff.sh`, stub `$PYTHON` and a fake
repo with a stub `ait`):

8. An inbound `AIT_SYNCER_HANDOFF=/tmp/attacker.json` is **overwritten** — the
   wrapper never reads that path.
9. A request whose `root` lacks `aitasks/metadata/project_config.yaml` ⇒ refused,
   stub `ait` never invoked.
10. A request whose `version` is `"; touch /tmp/pwned"` ⇒ refused, no file created.
11. A request containing shell metacharacters is **not executed as code** — write
    `{"root": "...", "version": "latest"}` plus a bogus extra member and assert
    nothing is sourced (e.g. a canary file the request text would create if
    sourced is absent).
12. The request file is **unlinked before** the upgrade runs (stub `ait` asserts
    the file is already gone when it executes).
13. The temp dir is removed on normal exit **and** after `SIGINT` during the app.
14. With no request file, the wrapper exits cleanly and never invokes `ait`.
15. Ordering: the stub `ait` records a timestamp/marker proving it ran **after**
    the Python process exited.

Manual: covered by t1223_7.

## Notes for sibling tasks

- The Versions row-key scheme (`v0`, `v1`, … + a lookup map) is the pattern
  t1223_5 should mirror for the settings matrix.
- The shared-`latest`-per-refresh rule exists to keep N-repo polling bounded —
  do not add a second per-row network call anywhere.
