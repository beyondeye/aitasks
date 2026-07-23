---
priority: medium
effort: medium
depends: [t1223_1]
issue_type: feature
status: Ready
labels: [auto-update]
gates: [risk_evaluated]
anchor: 1223
created_at: 2026-07-23 18:30
updated_at: 2026-07-23 18:30
---

## Context

Second child of t1223. This is the **headless model layer** for the version
feature — no Textual, no tmux calls, no TUI. Everything here is a pure function
over paths and strings so that the risky parts (shell-command construction,
self-target detection, active-target detection) are unit-testable before any UI
exists. t1223_3 consumes this module.

Parent plan: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.
**Contracts A, B, C and F of its `## Safety contracts` section are binding here**
and are restated inline below — implement them exactly.

## Key files to modify

- **New:** `.aitask-scripts/lib/framework_version.py`
- **New:** `tests/test_framework_version.py`

## Reference files for patterns

- `.aitask-scripts/lib/github_release.sh:36-123` — `github_latest_release_version`
  (REST), `github_latest_tag_version` (`git ls-remote` fallback),
  `github_resolve_latest_version`, `github_ratelimit_reset_minutes`. Shell out to
  this; do **not** reimplement release resolution in Python.
- `.aitask-scripts/aitask_upgrade.sh:83-89` — the authoritative version regex.
  `:120-123` reads `.aitask-scripts/VERSION`. `:152` shows the install invocation.
- `.aitask-scripts/lib/agent_launch_utils.py:232-251` — `resolve_agent_string`, the
  house pattern for "shell out to a repo-rooted script with `cwd=`, parse a
  prefixed line, return `None` on any failure".
- `.aitask-scripts/lib/agent_launch_utils.py:98-142` — `AitasksSession` (fields
  `session`, `project_root`, `is_live`, `is_stale`; `key` = `os.path.realpath`).
- `.aitask-scripts/lib/agent_launch_utils.py:267` — `get_tmux_windows(session)`
  returns `list[tuple[str, str]]`; `:1393` — companion prefixes
  `["agent-", "create-"]`.
- `.aitask-scripts/lib/tui_switcher.py:155` — `KNOWN_TUIS`.
- `.aitask-scripts/lib/attachment_meta.py:65-72` — `atomic_write` (temp +
  `os.replace`), the pattern for the handoff-request write.
- `tests/test_syncer_rows.py` — the test style to follow (pure helpers,
  `sys.path.insert` of `.aitask-scripts/lib`, `unittest`, no live state).

## API to implement

```python
# .aitask-scripts/lib/framework_version.py

VERSION_RE = r"^(latest|[0-9]+\.[0-9]+(\.[0-9]+)?)$"

def read_installed_version(root: str | Path) -> str | None:
    """Read <root>/.aitask-scripts/VERSION. None if missing/unreadable/blank.
    Strips whitespace and a leading 'v'. Never raises."""

def resolve_latest_version(timeout: float = 10.0) -> tuple[str | None, str | None]:
    """(version, error). Shells lib/github_release.sh's
    github_resolve_latest_version. Returns (None, reason) on network failure,
    rate limit, or missing tooling — never raises, never blocks forever."""

def version_status(installed: str | None, latest: str | None) -> str:
    """'unknown' | 'up_to_date' | 'behind' | 'ahead'. Semver-tuple compare;
    non-numeric components make it 'unknown' rather than crashing."""

def is_self_target(root: str | Path, cwd: str | Path) -> bool:
    """os.path.realpath on BOTH sides, then compare — matching
    AitasksSession.key semantics. Falls back to str() on OSError."""

def detect_target_activity(session: str, windows: list[tuple[str, str]]) -> str:
    """'idle' or 'busy:<comma-separated window names>'. PURE — the caller does
    the tmux enumeration."""

def build_upgrade_command(root: str | Path, version: str) -> tuple[str, list[str]]:
    """(command_string, [quoted_ait_path, version]). Raises ValueError on a
    version not matching VERSION_RE."""

def build_handoff_request(root: str | Path, version: str) -> dict:
    """{'root': <abs str>, 'version': <str>} — exactly these two keys.
    Raises ValueError on an invalid version."""

def write_handoff_request(path: str | Path, request: dict) -> None:
    """Atomic write (temp in the same dir + os.replace) of json.dumps(request)."""
```

### Contract F — command construction (binding)

`agent_launch_utils.launch_in_tmux(command: str, ...)` hands its argument to
tmux, which runs it **through a shell** (`:1188`, `split_args += [..., command]`).
So `&&` chaining works and quoting is entirely our responsibility.

- Validate `version` against `VERSION_RE` **before any interpolation**; raise
  `ValueError` otherwise. Never interpolate an unvalidated version.
- `shlex.quote()` the `<root>/ait` path.
- Return `f"{q_ait} upgrade {version} && {q_ait} setup"`. **The `&&` is
  load-bearing** — a failed upgrade must not be followed by `setup`.
- Return the parts alongside the string so tests assert structure, not text.

### Contract C — activity detection (binding)

A window marks the target **busy** when its name is in
`tui_switcher.KNOWN_TUIS` **or** starts with `agent-` or `create-`. Everything
else (plain shells, editors) is ignored. Import `KNOWN_TUIS` lazily/defensively
so a `tui_switcher` import failure degrades to prefix-matching rather than
crashing. The caller passes `is_live=False` sessions straight to `idle` without
ever calling this.

**Declared bound:** this only sees the target's tmux session. An `ait` process in
an unrelated terminal, a detached process, or another machine sharing the
checkout is undetectable. State this in the module docstring — it must not be
implied to be covered.

### Contracts A/B — handoff request (binding)

The request is **data only**: exactly `root` and `version`, no command string.
It is written atomically so the shell wrapper can never read a partial file.
The wrapper (t1223_3) owns the path and revalidates both fields independently —
this module's validation is UX, not the security boundary.

## Verification steps

```bash
python3 tests/test_framework_version.py
```

Required tests:

1. `read_installed_version` — valid file; missing file; missing
   `.aitask-scripts/` dir; blank file; whitespace/`v` prefix stripped; unreadable
   (chmod 000) returns `None` without raising. All against **fixture roots**
   under `tempfile.mkdtemp()`, never cwd.
2. `version_status` — up_to_date / behind / ahead / unknown (either side `None`,
   non-numeric component).
3. `resolve_latest_version` — success parsed from a stubbed helper; **offline
   degradation**: helper exits non-zero ⇒ `(None, reason)`, no raise; timeout ⇒
   `(None, reason)`.
4. `is_self_target` — same path; symlinked path resolving to the same realpath
   (**must be True**); different path; trailing-slash variant.
5. `detect_target_activity` **truth table**: no windows ⇒ idle; only plain shell
   names ⇒ idle; a `KNOWN_TUIS` name (e.g. `board`) ⇒ busy naming it; an
   `agent-syncfix-pull` window ⇒ busy; a `create-…` window ⇒ busy; mixed ⇒ busy
   listing only the offending names.
6. `build_upgrade_command` **quoting** — roots containing a space, `$`, `;`,
   `&&`, a single quote, a double quote, and a backtick each produce a command
   that a shell parses as the intended two invocations (assert via
   `shlex.split` on each `&&` side, not string equality).
7. `build_upgrade_command` **rejects** `""`, `"; rm -rf /"`, `"1.2.3; ls"`,
   `"$(id)"`, `"v1.2.3"` — each raises `ValueError`. Accepts `latest`, `1.2`,
   `0.28.0`.
8. **Failure-chain test (load-bearing).** Create a temp dir with a stub `ait`
   executable that appends its first argument to a log and exits **1**. Run the
   built command string with `subprocess.run(cmd, shell=True)`. Assert the log
   contains `upgrade` and **does not contain `setup`** — proving `&&` prevents
   `setup` after a failed upgrade. Repeat with a stub that exits 0 and assert
   both appear, in order.
9. `build_handoff_request` — exactly the keys `{'root','version'}`, absolute
   root, invalid version raises.
10. `write_handoff_request` — file contains valid JSON round-tripping the dict;
    no `.tmp` residue left in the directory.

## Notes for sibling tasks

- t1223_3 must call `detect_target_activity` with windows it enumerated itself,
  and must short-circuit on `is_live=False` before making any tmux call.
- The wrapper-side revalidation in t1223_3 is **independent** of
  `build_handoff_request`'s validation — do not skip it because this module
  already validated.
