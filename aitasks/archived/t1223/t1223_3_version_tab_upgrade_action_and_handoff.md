---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t1223_2]
issue_type: feature
status: Done
labels: [tui, auto-update]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1223
implemented_with: claudecode/opus5
created_at: 2026-07-23 18:31
updated_at: 2026-07-27 08:49
completed_at: 2026-07-27 08:49
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

0. **Capture the target.** Freeze the highlighted row into an immutable
   `UpgradeTarget(session_key, session_name, is_live, root, label, installed)`
   before anything else. The flow spans several modal callbacks and the table
   cursor is movable between them, so every later step reads this record — the
   table, the row map and the `AitasksSession` are touched exactly once.
   *(AC deviation, added during implementation.)*
1. Prompt for target version: `latest` or a pinned value (free text, validated by
   `framework_version.VERSION_RE`; reject in the dialog, don't pass it on).
2. **Self-target check (contract A) — runs FIRST.** *(AC deviation,
   user-confirmed: the original order put the active-target gate ahead of this.)*
   The syncer's own repo is where the user works, so it nearly always has live
   framework windows; gating it on contract C would refuse **every** self-upgrade
   and leave the exit-then-upgrade handoff — the only safe path for this repo —
   reachable solely through the destructive force-override. For a self target the
   activity result is therefore **advisory**: listed verbatim in the handoff
   confirmation, never a refusal and never force-gated. See step 3 below for the
   handoff itself.
3. **Active-target gate (contract C, as amended in t1223_2) — cross-repo targets
   only.** If `session.is_live` is `False` → `idle`, make **no tmux call**.
   Otherwise enumerate with `get_tmux_windows_result(session)` and pass the
   windows to `detect_target_activity()`. **The enumeration must be checked, not
   the lossy `get_tmux_windows()`** *(AC deviation, added during implementation)*:
   that helper returns `[]` on any tmux failure — timeout, vanished session,
   missing binary — and `detect_target_activity([])` reads that as `idle`, so a
   live target would be upgraded un-forced whenever the tmux query failed. A
   non-`None` error becomes `unknown:tmux-enumeration-failed` (a refusal), while
   a successful enumeration with zero windows is still, correctly, `idle`.
   Only a literal `idle` proceeds un-forced. On
   `busy:<names>` **or** `unknown:<reason>` → **refuse**, showing the offending
   window names (or the unknown reason). The refusal dialog additionally offers
   a **force-override** (user-directed, t1223_2 planning), specified exactly:
   - a separate **destructive confirmation** step, never the same dialog's
     default action; default focus = Cancel;
   - before launching, **re-enumerate** windows and re-run
     `detect_target_activity()` — if the fresh result differs from what the
     dialog displayed, **abort the force** and re-show the refusal with the
     new state;
   - the confirmation body lists the freshly-detected window names (or the
     `unknown` reason) verbatim;
   - the confirming option is labeled
     "Force upgrade anyway — I accept the listed windows may break";
   - no "don't ask again" state is ever persisted.
   The force-override applies only to this gate; the self-target rule
   (contract A, step 2) is never force-bypassable — and because that check now
   runs first, there is no code path on which a self repo reaches the refusal
   or force dialogs at all.
4. **Self-target handoff (contract A), reached from step 2.** Do **not** spawn.
   Show the handoff confirmation (naming the repo, the version, and — as an
   advisory — any detected live framework windows verbatim), then write the
   handoff request and `app.exit()` (see §3). If the wrapper path env var is
   absent, **refuse** with "relaunch via `ait syncer`, or run `ait upgrade` from
   a shell" — never spawn, never silently no-op.
5. Otherwise: confirmation modal naming the target project **and** its resolved
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
[[ -f "$AIT_SYNCER_HANDOFF" ]] || exit "$_rc"
_req="$(cat "$AIT_SYNCER_HANDOFF")"
rm -f "$AIT_SYNCER_HANDOFF"        # unlink BEFORE running, so a crash cannot re-trigger
# parse with "$PYTHON" -c 'import json,sys; ...' — NEVER source, NEVER eval
# revalidate, then:
rm -rf "$_handoff_dir"; trap - EXIT INT TERM   # exec skips the trap — clean up first
exec bash -c '"$1/ait" upgrade "$2" && "$1/ait" setup' bash "$_root" "$_version"
```

Binding wrapper requirements:
- **The wrapper owns the path.** `export` is unconditional — an externally
  supplied `AIT_SYNCER_HANDOFF` has no effect. Dir `0700`, file `0600`.
- **Data only, and the exact shape.** Parse with `"$PYTHON" -c` + `json.load`.
  The file is **never** `source`d, `eval`ed, or interpolated unparsed, and it
  carries **no command string**. *(AC deviation, added during implementation:)*
  "exactly two members" is **enforced**, not assumed — the payload must be a
  `dict` whose key set is exactly `{"root", "version"}` with both values `str`
  and no embedded newline, and `object_pairs_hook` rejects duplicate keys
  (`json.loads` otherwise silently keeps the last). Any deviation exits
  non-zero and nothing runs; proving nothing was *executed* is not the same as
  proving the input was *refused*.
- **Revalidate before constructing anything** (this is the security boundary,
  independent of the app's check): `root` must be an absolute existing directory
  containing `aitasks/metadata/project_config.yaml` (mirror
  `path_is_aitasks_project`) and an executable `<root>/ait`; `version` must match
  `^(latest|[0-9]+\.[0-9]+(\.[0-9]+)?)$`. Any failure ⇒ print the reason, run
  nothing, exit non-zero.
- **Build the command wrapper-side from the validated parts.** *(AC deviation,
  added during implementation:)* they are passed as **positional arguments** to
  `bash -c`, so the validated scalars never become shell text at all — strictly
  stronger than quoting them into a command string.
- **Clear on every exit path** — unlink after read; the `EXIT` trap removes the
  directory on normal exit and on `die`. *(AC deviation, review-driven:)* `INT`
  and `TERM` need **their own traps that exit** (130 / 143), not a shared
  tidy-only handler. A trap that returns hands control back to the next
  statement, so a signal arriving after the request has been read into memory
  would delete a file that is no longer the source of truth and let the script
  carry on into the upgrade — turning a cancellation into a framework rewrite.
- Removing `exec` for the *app* means the wrapper stays as the parent process:
  keep `set -euo pipefail` correct around the non-`exec` invocation (the app's
  exit status must not abort the script before the handoff is handled — capture
  it, and propagate it when there is no request).
- **`exec` the upgrade itself.** *(AC deviation, user-confirmed:)* the upgrade
  extracts over `.aitask-scripts/` — including `aitask_syncer.sh`, which bash is
  still reading. `exec`ing the final command means bash never reads another byte
  of the replaced file, and the upgrade's exit status becomes the wrapper's.
  Because `exec` skips the `EXIT` trap, the handoff dir is `rm -rf`'d explicitly
  immediately before it; the trap still covers every other path.

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
python3 tests/test_syncer_rows.py          # a Python file, not a bash one
bash tests/test_syncer_upgrade_handoff.sh
bash tests/test_no_raw_tmux.sh
bash tests/test_shortcuts_registry_coverage.sh   # the two new bindings
shellcheck .aitask-scripts/aitask_syncer.sh
```

Python tests (`tests/test_syncer_rows.py`, mock `launch_in_tmux` with a spy).
**Every impure seam on the new paths must be patched in the boot fixture** —
`resolve_latest_version`, `get_tmux_windows_result`, `get_tmux_sessions`,
`is_tmux_available`, `resolve_pane_id_by_pid`, `launch_in_tmux` — or the suite
issues real GitHub and `tmux list-windows` calls against the developer's live
session (several pre-existing tests activate the Versions tab):

1. **Active target refuses and does not spawn** — a live session with a `board`
   window: the action produces a refusal naming `board` and the spy records
   **zero** calls. (Load-bearing: must fail if the gate is removed.)
1b. **Failed enumeration refuses and does not spawn** *(AC deviation, added
   during implementation)* — `get_tmux_windows_result` returning an error for a
   live target refuses with `unknown:tmux-enumeration-failed` and spawns
   nothing. Negative control for the fail-open hole described in step 3 above.
2. **Registry-only target makes no tmux enumeration call** — `is_live=False`
   spy on `get_tmux_windows_result` records zero calls.
3. **Idle live target spawns once** with `cwd` equal to the target root and the
   command from `build_upgrade_command`.
4. **Self-target never spawns** — spy records zero calls; the handoff file exists
   and contains exactly `{"root": ..., "version": ...}`.
5. **Self-target with `AIT_SYNCER_HANDOFF` unset refuses** — zero spawns, zero
   files written, a refusal message is shown.
6. **Lifecycle** — after spawn the state is `launched` and the State cell renders
   `upgrading…` while Installed shows the *old* version; with the pane gone the
   cell renders `re-check needed`; **no state ever renders a success string**.
6b. **Self-target activity is advisory, not a refusal** *(AC deviation,
   user-confirmed)* — a self target whose windows include `board` still reaches
   the handoff confirmation, which lists `board` verbatim; confirming writes the
   request. Must fail if the self path is routed through the refusal screen.
7. **Per-tab gating** — the upgrade key is inert on `tab_branches` (and on
   `tab_settings`), and fail-closed with no running app.
7b. **Captured target survives mid-flow mutation** *(AC deviation, added during
   implementation)* — moving the table cursor and repointing the row map while
   the confirmation is open must not redirect the spawn at another repository.

Bash tests (`tests/test_syncer_upgrade_handoff.sh`, stub `$PYTHON` and a fake
repo with a stub `ait`):

8. An inbound `AIT_SYNCER_HANDOFF=/tmp/attacker.json` is **overwritten** — the
   wrapper never reads that path.
9. A request whose `root` lacks `aitasks/metadata/project_config.yaml` ⇒ refused,
   stub `ait` never invoked.
10. A request whose `version` is `"; touch /tmp/pwned"` ⇒ refused, no file created.
11. A request containing shell metacharacters is **not executed as code** — a
    canary the request text would create if sourced is absent, **and** the
    wrapper exits non-zero with `ait` never invoked *(AC deviation, added during
    implementation: the original wording only asserted nothing was executed,
    which does not prove malformed input was refused)*.
11b. **Exact-shape enforcement** *(AC deviation, added during implementation)* —
    an extra member, a missing member, a duplicate key, a non-string value, a
    newline-bearing root, a JSON array and malformed JSON are each refused with
    a non-zero exit and `ait` never invoked. Positive control: the exact
    two-member object is accepted.
12. The request file is **unlinked before** the upgrade runs (stub `ait` asserts
    the file is already gone when it executes) — and so is the private dir,
    since the upgrade is `exec`'d and the trap cannot fire.
13. The temp dir is removed on normal exit, after `SIGINT` during the app, and
    on the upgrade path.
13b. **A signal after the request is read CANCELS** *(AC deviation,
    review-driven)* — with the request already in memory (signal delivered to
    the wrapper alone, mid-parse, so the parse completes normally), `SIGTERM`
    must exit 143 with `ait` never invoked. Negative control: a tidy-only
    `trap … EXIT INT TERM` makes this run the upgrade and exit 0.
14. With no request file, the wrapper exits cleanly, never invokes `ait`, and
    propagates the app's exit status.
15. Ordering: the stub `ait` records a timestamp/marker proving it ran **after**
    the Python process exited.

Manual: covered by t1223_7.

## Notes for sibling tasks

- The Versions row-key scheme (`v0`, `v1`, … + a lookup map) is the pattern
  t1223_5 should mirror for the settings matrix.
- The shared-`latest`-per-refresh rule exists to keep N-repo polling bounded —
  do not add a second per-row network call anywhere.
- Any multi-modal action must **capture an immutable target when it starts**
  and thread it through every callback (see `UpgradeTarget`), rather than
  re-resolving from the table in a later callback.
- `agent_launch_utils.get_tmux_windows_result()` is the enumeration variant to
  use for any **safety** decision; the older `get_tmux_windows()` collapses a
  tmux failure into an empty list.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-26T14:29:46Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-27T05:49:06Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-27T05:49:26Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:48ca9a62ebbc9aab

> **✅ gate:risk_evaluated** run=2026-07-27T05:49:26Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1223_3/risk_evaluated_2026-07-27T05:49:26Z-risk_evaluated-a1.log`
