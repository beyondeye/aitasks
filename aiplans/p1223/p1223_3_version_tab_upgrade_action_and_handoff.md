---
Task: t1223_3_version_tab_upgrade_action_and_handoff.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_1_*.md, aitasks/t1223/t1223_2_*.md, aitasks/t1223/t1223_4_*.md, aitasks/t1223/t1223_5_*.md, aitasks/t1223/t1223_6_*.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_*_*.md
Worktree: (none — profile 'fast': current branch)
Branch: main
Base branch: main
---

# p1223_3 — Version tab, upgrade action, exit-handoff

> The task file `aitasks/t1223/t1223_3_version_tab_upgrade_action_and_handoff.md`
> carries the full flow, the wrapper skeleton, and the binding contract text.
> This plan is the execution view. Parent design:
> `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md` (contracts
> **A**, **B**, **C**, **F**, **G**).

## Goal

Fill the `tab_versions` pane with a per-repo version view and add the upgrade
action — the only framework-mutating action in this feature. Includes the
safety-critical launcher change in `.aitask-scripts/aitask_syncer.sh`.

**This is the highest-risk child.** Every refusal path must be proven by a
no-spawn test, not by inspection.

## Steps

1. Read `aidocs/framework/tmux_gateway.md` and
   `aidocs/framework/shell_conventions.md` before writing any tmux or shell code.
2. **Version rows** — one row per repo (not per repo×ref), built from
   `self.sessions` with `build_labels()` (`syncer_app.py:149`) and **opaque
   positional keys** (`v0`, `v1`, …) recovered via a lookup map, mirroring
   `RowSpec` (`:90-105`). Columns: Project · Installed · Latest · Status · State.
3. **Shared latest** — resolve once per refresh for all rows (never N network
   calls). Honor the `f` fetch-off toggle: no network call, last known value
   shown stale. Run in a thread worker reusing the existing
   `coalesce_request` / generation-guard machinery (`:240-260`).
4. **Upgrade action** — new key on the Versions tab, gated through
   `check_action` + `_active_tab()` (t1223_1), routed via `ShortcutsMixin`
   (scope `"syncer"`). Order of checks is binding:
   1. version prompt (`latest` or pinned, validated by `VERSION_RE` in the
      dialog);
   2. **active-target gate** — `is_live=False` short-circuits to `idle` with
      **no tmux call**; otherwise `get_tmux_windows(session)` →
      `detect_target_activity()`; on `busy` **refuse**, naming the windows;
   3. **self-target** — `is_self_target(root, Path.cwd())` → handoff (step 5),
      never a spawn; refuse if the wrapper env var is absent;
   4. otherwise confirm (naming project **and** resolved root), then
      `launch_in_tmux(build_upgrade_command(root, version)[0],
      TmuxLaunchConfig(..., cwd=str(root), new_window=True))` with
      `unique_window_name(existing, f"upgrade-{label}")`.
5. **Handoff (contracts A + B)** — app side: read
   `os.environ.get("AIT_SYNCER_HANDOFF")`, write the request atomically via
   t1223_2's helper, `self.exit()`. Wrapper side (`aitask_syncer.sh`): create a
   `mktemp -d` dir (`0700`, file `0600`), `trap 'rm -rf …' EXIT INT TERM`,
   **export `AIT_SYNCER_HANDOFF` unconditionally** (ignoring any inbound value),
   run Python **without `exec`**, then after it exits read the request, **unlink
   it before running anything**, parse the two scalars with `"$PYTHON" -c` +
   `json.load` (never `source`, never `eval`), **revalidate independently**
   (absolute existing dir containing `aitasks/metadata/project_config.yaml` per
   `path_is_aitasks_project`, executable `<root>/ait`, version regex), and build
   the quoted command wrapper-side. Removing `exec` makes the wrapper the parent
   process — capture the app's exit status so `set -euo pipefail` cannot abort
   before the handoff is handled.
6. **Lifecycle (contract G)** — `idle` / `launched` (store `pane_pid`, `pane_id`
   via `resolve_pane_id_by_pid`, timestamp; State reads `upgrading…`, version
   cells keep the last **read** value with a stale marker) / `finished (result
   unknown)` (State reads `re-check needed`). Add a re-check key. **The UI must
   never render a success it did not observe.**

## Verification

- `bash tests/test_syncer_rows.py`, `bash tests/test_syncer_upgrade_handoff.sh`, `bash tests/test_no_raw_tmux.sh` and `shellcheck .aitask-scripts/aitask_syncer.sh` all pass.
- Active target: a live session with a `board` window produces a refusal naming `board` and the `launch_in_tmux` spy records zero calls.
- A registry-only target (`is_live=False`) triggers zero `get_tmux_windows` calls.
- An idle live target spawns exactly once, with `cwd` equal to the target root and the command from `build_upgrade_command`.
- Self-target never spawns: the spy records zero calls and the handoff file contains exactly the keys `root` and `version`.
- Self-target with `AIT_SYNCER_HANDOFF` unset refuses: zero spawns, zero files written, a refusal message shown.
- Lifecycle: after a spawn the State cell renders `upgrading…` while the version cell still shows the old version; with the pane gone it renders `re-check needed`; no state ever renders a success string.
- The upgrade key is inert on `tab_branches`.
- Wrapper: an inbound `AIT_SYNCER_HANDOFF` pointing elsewhere is overwritten and never read.
- Wrapper: a request whose root lacks `aitasks/metadata/project_config.yaml` is refused and the stub `ait` is never invoked.
- Wrapper: a request whose version is `"; touch /tmp/pwned"` is refused and no file is created.
- Wrapper: request content is never sourced — a canary file that sourcing would create is absent afterwards.
- Wrapper: the request file is already unlinked by the time the stub `ait` executes.
- Wrapper: the temp directory is removed on normal exit and after a `SIGINT` during the app.
- Wrapper: with no request file present the wrapper exits cleanly and never invokes `ait`.
- Wrapper: a marker proves the stub `ait` ran only after the Python process exited.

## Out of scope

Settings content (t1223_5) and documentation (t1223_6).
