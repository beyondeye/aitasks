---
Task: t1223_2_framework_version_and_upgrade_command_model.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_1_*.md, aitasks/t1223/t1223_3_*.md, aitasks/t1223/t1223_4_*.md, aitasks/t1223/t1223_5_*.md, aitasks/t1223/t1223_6_*.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_*_*.md
Worktree: (none — profile 'fast': current branch)
Branch: main
Base branch: main
---

# p1223_2 — Framework version + upgrade-command model (headless)

> The task file `aitasks/t1223/t1223_2_framework_version_and_upgrade_command_model.md`
> carries the full API signatures, binding contracts, and reference anchors.
> This plan is the execution view. Parent design:
> `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.

## Goal

Create `.aitask-scripts/lib/framework_version.py` — pure functions over paths and
strings, no Textual and no tmux calls — so the risky logic (shell-command
construction, self-target detection, active-target detection, handoff request)
is fully unit-tested before any UI consumes it.

## Steps

1. `read_installed_version(root)` — read `<root>/.aitask-scripts/VERSION`, strip
   whitespace and a leading `v`, return `None` on missing/unreadable/blank.
   Never raises.
2. `resolve_latest_version()` — shell out to
   `lib/github_release.sh::github_resolve_latest_version` with a timeout,
   returning `(version, error)`. Follow the `resolve_agent_string`
   (`agent_launch_utils.py:232-251`) shape: prefixed-line parse, `None` on any
   failure. Do **not** reimplement release resolution in Python.
3. `version_status(installed, latest)` — semver-tuple compare →
   `unknown | up_to_date | behind | ahead`; non-numeric components yield
   `unknown` rather than crashing.
4. `is_self_target(root, cwd)` — `os.path.realpath` on **both** sides (matching
   `AitasksSession.key`), `str()` fallback on `OSError`.
5. `detect_target_activity(session, windows)` — **pure**. Busy when a window name
   is in `tui_switcher.KNOWN_TUIS` or starts with `agent-` / `create-`
   (`agent_launch_utils.py:1393`); everything else ignored. Import `KNOWN_TUIS`
   defensively so an import failure degrades to prefix matching. Record the
   **declared bound** (tmux-session-scoped only) in the module docstring.
6. `build_upgrade_command(root, version)` — validate `version` against
   `VERSION_RE` **before any interpolation** (raise `ValueError` otherwise),
   `shlex.quote()` the `<root>/ait` path, return
   `f"{q_ait} upgrade {version} && {q_ait} setup"` plus the parts. The `&&` is
   load-bearing.
7. `build_handoff_request(root, version)` / `write_handoff_request(path, request)`
   — exactly two keys (`root`, `version`), **no command string**, written
   atomically (temp in the same dir + `os.replace`, per
   `attachment_meta.py:65-72`).
8. Write `tests/test_framework_version.py` in the style of
   `tests/test_syncer_rows.py`, entirely against `tempfile.mkdtemp()` fixture
   roots — never cwd.

## Verification

- `python3 tests/test_framework_version.py` passes.
- `read_installed_version` handles valid / missing file / missing `.aitask-scripts` dir / blank / whitespace-and-`v`-prefixed / unreadable (chmod 000) without raising, against fixture roots rather than cwd.
- `version_status` returns up_to_date, behind, ahead and unknown for the corresponding inputs including a `None` side and a non-numeric component.
- `resolve_latest_version` degrades offline: a helper exiting non-zero and a timeout each yield `(None, reason)` with no exception raised.
- `is_self_target` is True for a symlinked path resolving to the same realpath, and for a trailing-slash variant; False for a different path.
- `detect_target_activity` truth table: no windows, plain shell names only, and an unknown-name window each yield `idle`; a `KNOWN_TUIS` name, an `agent-*` window and a `create-*` window each yield `busy` naming only the offending windows.
- `build_upgrade_command` produces a shell-safe command for roots containing a space, `$`, `;`, `&&`, a single quote, a double quote and a backtick — asserted via `shlex.split` on each side of the `&&`, not string equality.
- `build_upgrade_command` raises `ValueError` for `""`, `"; rm -rf /"`, `"1.2.3; ls"`, `"$(id)"` and `"v1.2.3"`, and accepts `latest`, `1.2` and `0.28.0`.
- Failure-chain test: running the built command with a stub `ait` that exits 1 logs `upgrade` and never logs `setup`; with a stub that exits 0 both are logged in order.
- `build_handoff_request` yields exactly the keys `root` and `version` with an absolute root, and raises on an invalid version.
- `write_handoff_request` produces valid round-tripping JSON and leaves no `.tmp` residue in the directory.

## Out of scope

Any tmux enumeration or spawning (t1223_3 does the impure wiring) and any UI.
