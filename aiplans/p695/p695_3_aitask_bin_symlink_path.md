---
Task: t695_3_aitask_bin_symlink_path.md
Parent Task: aitasks/t695_install_python_if_sys_python_old.md
Sibling Tasks: aitasks/t695/t695_1_python_resolve_helper.md, aitasks/t695/t695_2_venv_python_upgrade.md, aitasks/t695/t695_4_refactor_python_callers.md
Archived Sibling Plans: aiplans/archived/p695/p695_*_*.md
Worktree: aiwork/t695_3_aitask_bin_symlink_path
Branch: aitask/t695_3_aitask_bin_symlink_path
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-28 13:18
---

# Plan — t695_3: ~/.aitask/bin/python3 symlink + scoped PATH integration

## Context

Third child of t695. After t695_2 builds the venv on a modern interpreter,
this child exposes that interpreter via `~/.aitask/bin/python3` and makes
it findable on PATH **only when aitasks scripts run** — not in the user's
interactive shell or for unrelated tools. The original plan (and the
t695_3 task description) proposed appending a `~/.aitask/bin` line to the
user's shell rc, which would silently override system `python3` for every
program the user runs. That is too broad. This revision scopes the PATH
change to aitasks subprocesses by sourcing a small lib that exports
PATH inside each invocation chain.

The remote-sandbox case is still handled by t695_4's helper-based
migration — the symlink + scoped PATH only fixes the local case.

## Design — why a sourced lib, not a shell rc edit

`export PATH="$HOME/.aitask/bin:$PATH"` placed in `~/.zshrc` / `~/.bashrc`
affects the user's interactive shell and every child process they ever
launch — including unrelated tools that depend on system `python3`. We
do NOT want that.

Instead, ship the PATH prepend in `.aitask-scripts/lib/aitask_path.sh`,
sourced from:
1. The `ait` dispatcher at the project root — covers every `./ait <cmd>`
   flow.
2. (Future, in t695_4) every `.aitask-scripts/aitask_*.sh` that invokes
   Python — covers skill-direct invocations of the helper scripts that
   bypass `./ait`.

Subprocesses spawned from aitasks scripts inherit the prepended PATH; the
user's shell never does. `ensure_path_in_profile()` is left untouched and
continues to manage only `~/.local/bin` (the global `ait` shim) — that's
intentional because the shim entry-point is the only thing the user
benefits from having on their interactive PATH.

## Pre-flight verification (done now, 2026-04-28)

- `setup_python_venv()` lives at `.aitask-scripts/aitask_setup.sh:513-575`
  (post-t695_2). Pip-install ends at line 572; `success "Python venv
  ready..."` is line 574 — natural insertion point for the symlink block.
- `ensure_path_in_profile()` lives at lines 580-616. **Untouched by this
  child.** It will continue to manage only `~/.local/bin`.
- `ait` dispatcher at the repo root: 6-line preamble at the top
  (shebang, `set -euo pipefail`, `AIT_DIR`, `cd "$AIT_DIR"`, blank,
  `SCRIPTS_DIR`). Adding a single `source` line directly after `cd` fits
  cleanly without disturbing anything else.
- Sourced libs already exist under `.aitask-scripts/lib/`:
  `task_utils.sh`, `terminal_compat.sh`, `python_resolve.sh` — all use
  the `_AIT_*_LOADED` double-source guard pattern. We mirror that.
- Per CLAUDE.md "Adding a New Helper Script": **sourced libs do NOT
  require whitelist entries** (they are not invoked directly by skills).
  Only executable scripts need the 5-touchpoint allowlist — confirmed
  by t695_1's `lib/python_resolve.sh` precedent.
- `tests/test_setup_python_install.sh` already exists from t695_2
  (`AIT_RUN_INTEGRATION_TESTS=1`-gated). Natural place to add symlink +
  scoped-PATH assertions.

## Files

- `.aitask-scripts/lib/aitask_path.sh` — **NEW.** Sourced lib that
  prepends `~/.aitask/bin` to PATH idempotently.
- `ait` (project root dispatcher) — add one `source` line near the top.
- `.aitask-scripts/aitask_setup.sh` — append symlink-creation block
  inside `setup_python_venv()`.
- `tests/test_setup_python_install.sh` — extend with symlink +
  scoped-PATH assertions.
- `aitasks/t695/t695_4_refactor_python_callers.md` — append a
  one-paragraph "Notes for sibling tasks" entry instructing t695_4 to
  source `lib/aitask_path.sh` from each Python-invoking script it
  migrates (so skill-direct invocations also pick up the scoped PATH,
  not just `./ait <cmd>` flows).

**Explicitly NOT modified:** the user's shell rc files. `ensure_path_in_profile()`
is unchanged. No global PATH side-effects on the user's interactive
shell.

## Implementation Steps

### Step 1 — Create `.aitask-scripts/lib/aitask_path.sh`

```bash
#!/usr/bin/env bash
# aitask_path.sh — Prepend ~/.aitask/bin to PATH for aitasks subprocesses.
#
# Sourced (not executed) by the `ait` dispatcher and by individual
# `.aitask-scripts/aitask_*.sh` scripts. The export is scoped to the
# current bash process and its descendants; the user's interactive
# shell rc is intentionally left untouched.
#
# Idempotent: sourcing this multiple times does not duplicate the entry.

if [[ -n "${_AIT_PATH_LOADED:-}" ]]; then
    return 0
fi
_AIT_PATH_LOADED=1

case ":$PATH:" in
    *":$HOME/.aitask/bin:"*) ;;            # already prepended, no-op
    *) export PATH="$HOME/.aitask/bin:$PATH" ;;
esac
```

The `case` form avoids a duplicate prepend when the lib is sourced more
than once across nested aitasks scripts (e.g., `ait` sources it, then
calls a helper that also sources it).

### Step 2 — Source from the `ait` dispatcher

Insert one line in `ait` directly after the existing `cd "$AIT_DIR"`
(currently line 5):

```bash
#!/usr/bin/env bash
set -euo pipefail

AIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$AIT_DIR"  # CRITICAL: ensures TASK_DIR="aitasks" works in all scripts
# shellcheck source=.aitask-scripts/lib/aitask_path.sh
source "$AIT_DIR/.aitask-scripts/lib/aitask_path.sh"

SCRIPTS_DIR="$AIT_DIR/.aitask-scripts"
```

Subprocesses spawned by `ait` (i.e., the dispatched script + everything
it spawns) inherit the prepended PATH. The user's shell does not.

### Step 3 — Symlink creation in `setup_python_venv()`

Insert at the end of `setup_python_venv()`, between line 572 (last
pip-install line) and line 574 (`success "Python venv ready..."`):

```bash
# Expose venv-Python via stable symlinks (t695_3).
# These are picked up by lib/aitask_path.sh's PATH prepend and by
# lib/python_resolve.sh's candidate list (already references this path).
mkdir -p "$HOME/.aitask/bin"
ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python3"
ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python"
info "Created framework Python symlinks at ~/.aitask/bin/{python,python3}."
```

`ln -sf` overwrites stale symlinks if the venv was re-created on a newer
interpreter. Both names are written because callers use both; the venv
itself ships `python` as canonical with `python3` symlinked to it, so we
mirror that shape.

### Step 4 — Append "Notes for sibling tasks" to t695_4

t695_4 will refactor every Python-invoking `.aitask-scripts/*.sh` to
source `lib/python_resolve.sh`. While each is being touched, t695_4
should also `source "$SCRIPT_DIR/lib/aitask_path.sh"` near the top —
that closes the gap for skill-direct invocations of helper scripts
(which bypass `./ait`).

Append to `aitasks/t695/t695_4_refactor_python_callers.md` under
`## Notes for sibling tasks`:

```markdown
- **Source `lib/aitask_path.sh` in every migrated script.** t695_3 ships
  this lib and sources it from the `ait` dispatcher. Skill-direct calls
  to `.aitask-scripts/aitask_*.sh` bypass the dispatcher, so each
  Python-invoking script must source `lib/aitask_path.sh` explicitly
  near its top (right next to `lib/python_resolve.sh`). This keeps
  shebang-based `python3` resolution scoped to aitasks subprocesses
  without touching the user's interactive shell rc.
```

This is a content-only edit (no frontmatter changes) and does not need a
separate `aitask_update.sh --batch` invocation — bundle it with the
plan-file commit during Step 8.

### Step 5 — Extend the existing integration test

Path: `tests/test_setup_python_install.sh` (existing).

Add assertions just before the final `echo "=== PASS: integration
test ==="` line:

```bash
echo ""
echo "--- Verifying ~/.aitask/bin symlinks (t695_3) ---"
[[ -L "$FAKE_HOME/.aitask/bin/python3" ]] || { echo "FAIL: ~/.aitask/bin/python3 missing"; exit 1; }
[[ -L "$FAKE_HOME/.aitask/bin/python"  ]] || { echo "FAIL: ~/.aitask/bin/python missing"; exit 1; }
target="$(readlink "$FAKE_HOME/.aitask/bin/python3")"
[[ "$target" == "$FAKE_HOME/.aitask/venv/bin/python" ]] \
    || { echo "FAIL: symlink target is $target (expected $FAKE_HOME/.aitask/venv/bin/python)"; exit 1; }
"$FAKE_HOME/.aitask/bin/python3" -V >/dev/null \
    || { echo "FAIL: ~/.aitask/bin/python3 not executable"; exit 1; }
echo "PASS: ~/.aitask/bin/{python,python3} symlinks created"

echo ""
echo "--- Verifying scoped PATH (sourced lib, NOT shell rc) ---"
# The user's shell rc must NOT contain a .aitask/bin entry.
for rc in "$FAKE_HOME/.zshrc" "$FAKE_HOME/.bashrc" "$FAKE_HOME/.profile"; do
    if [[ -f "$rc" ]] && grep -q '.aitask/bin' "$rc"; then
        echo "FAIL: $rc contains .aitask/bin (must be scoped via lib, not rc)"
        exit 1
    fi
done
echo "PASS: no .aitask/bin entry in shell rc files (scoped via lib)"

# Sourcing the lib must put .aitask/bin first in PATH.
out="$(HOME="$FAKE_HOME" bash -c '
    source "'"$PROJECT_DIR"'/.aitask-scripts/lib/aitask_path.sh"
    echo "$PATH"
' )"
case "$out" in
    "$FAKE_HOME/.aitask/bin:"*) echo "PASS: lib prepends .aitask/bin to PATH" ;;
    *) echo "FAIL: lib did not prepend .aitask/bin (got: ${out:0:80}...)"; exit 1 ;;
esac

# Idempotency: sourcing twice does not duplicate the entry.
out2="$(HOME="$FAKE_HOME" bash -c '
    source "'"$PROJECT_DIR"'/.aitask-scripts/lib/aitask_path.sh"
    source "'"$PROJECT_DIR"'/.aitask-scripts/lib/aitask_path.sh"
    echo "$PATH"
' )"
count="$(echo "$out2" | tr ':' '\n' | grep -c "^$FAKE_HOME/.aitask/bin$")"
[[ "$count" == "1" ]] || { echo "FAIL: duplicate .aitask/bin in PATH after double source ($count)"; exit 1; }
echo "PASS: lib sourcing is idempotent"

# `./ait` dispatcher must propagate the prepended PATH to its subprocess.
dispatched="$(HOME="$FAKE_HOME" "$SCRATCH/ait" --version 2>&1 || true)"
# We can't assert PATH directly from a dispatcher subprocess output, but
# we CAN assert the dispatcher source line by inspecting the file:
grep -q 'lib/aitask_path.sh' "$SCRATCH/ait" \
    || { echo "FAIL: $SCRATCH/ait does not source lib/aitask_path.sh"; exit 1; }
echo "PASS: ait dispatcher sources lib/aitask_path.sh"
```

Tests use `grep -c` (clean integer output) and avoid `wc -l` per
CLAUDE.md macOS portability notes.

### Step 6 — Manual sanity check

In a fresh shell after running `ait setup`:

```bash
# Verify NO change to interactive shell PATH:
echo "$PATH" | grep -c aitask/bin   # should print 0 (or 1 if previously installed)

# Verify scoped PATH inside dispatched commands:
./ait --help >/dev/null   # no error → dispatcher boots fine
./ait stats > /dev/null   # invokes Python; should resolve via venv

# Verify the symlink target:
ls -l ~/.aitask/bin/python3   # → $HOME/.aitask/venv/bin/python
~/.aitask/bin/python3 -c "import linkify_it"   # imports cleanly
```

Expected: user's interactive `python3` still resolves to system Python
(or whatever it resolved to before — unchanged). Inside `./ait <cmd>`,
`python3` resolves to the framework venv-Python.

## Verification

- `AIT_RUN_INTEGRATION_TESTS=1 bash tests/test_setup_python_install.sh`
  exits 0 and reports the new PASS lines.
- `bash tests/test_setup_find_modern_python.sh` still passes (no
  interaction with the new lib).
- `shellcheck .aitask-scripts/lib/aitask_path.sh` clean.
- `shellcheck .aitask-scripts/aitask_setup.sh` no worse than baseline.
- `shellcheck ait` clean (dispatcher diff is one source line).
- Re-running `ait setup` in a non-fresh sandbox does not duplicate any
  symlinks or modify the user's shell rc.
- Manual sanity checks above pass on a fresh shell.

## Dependencies / Sequencing

- t695_1 (`lib/python_resolve.sh`) — already merged. Its candidate list
  references `~/.aitask/bin/python3`; once this child lands, that
  becomes the first hit on local installs.
- t695_2 (`venv_python_upgrade`) — already merged. `$VENV_DIR/bin/python`
  is now guaranteed ≥ 3.11, so the symlink target is a usable modern
  interpreter.
- t695_4 (helper-based caller refactor) — lands after this child. With
  the symlink + scoped PATH in place, locally installed shells get the
  framework Python via PATH **inside** aitasks subprocesses; t695_4
  closes the skill-direct gap by sourcing both libs from each
  Python-invoking script.

## Step 9 — Post-Implementation

Standard archival flow per `task-workflow/SKILL.md` Step 9. No worktree
to remove (profile `fast` works on `main` directly). The PATH change is
intentionally **not** sticky in the user's shell rc — that's the whole
point of this revision.

The Final Implementation Notes section appended to this plan during
Step 8 should call out:
- **Notes for sibling tasks:** that `lib/aitask_path.sh` is the
  single source of truth for PATH scoping; that t695_4 must source it
  from every Python-invoking script it touches; that
  `ensure_path_in_profile()` was deliberately left alone — future PATH
  work should NOT touch the user's shell rc for framework-internal
  resolution; that the scoped-lib pattern is reusable for any future
  framework binary that needs aitasks-subprocess-only PATH
  participation.
- Any deviation from this plan (especially around the `ait` dispatcher
  source line — verify the exact insertion point survives any
  intervening edits to `ait` between plan time and implementation time).

## Final Implementation Notes

- **Actual work done:** Implemented all six steps of the plan as written.
  - `.aitask-scripts/lib/aitask_path.sh` (NEW): sourced lib that prepends
    `~/.aitask/bin` to `PATH` idempotently. Uses the project's standard
    `_AIT_*_LOADED` double-source guard plus a `case` statement to
    short-circuit if the entry is already present.
  - `ait` dispatcher: one-line `source ".aitask-scripts/lib/aitask_path.sh"`
    inserted directly after the existing `cd "$AIT_DIR"` line so
    subprocesses spawned by `./ait <cmd>` inherit the prepended PATH.
  - `.aitask-scripts/aitask_setup.sh` `setup_python_venv()`: symlink-creation
    block appended after the pip-install branch and before the closing
    `success "Python venv ready..."` line. Creates both
    `~/.aitask/bin/python3` and `~/.aitask/bin/python` via `ln -sf` so
    re-runs overwrite stale targets without erroring.
  - `tests/test_setup_python_install.sh`: appended a "Verifying ~/.aitask/bin
    symlinks" block + a "Verifying scoped PATH" block that asserts (a) the
    symlinks exist and resolve to `$VENV_DIR/bin/python`, (b) NO `.aitask/bin`
    entry has been written to any shell rc file, (c) sourcing the lib
    prepends PATH, (d) double-sourcing is idempotent, (e) the `ait`
    dispatcher contains the lib source line.
  - `aitasks/t695/t695_4_refactor_python_callers.md`: appended a
    "Source `lib/aitask_path.sh` in every migrated script" bullet under
    the `## Notes for sibling tasks` section, including the canonical
    sourcing pattern. `updated_at` bumped to 2026-04-28 13:19.
- **Deviations from plan:** None of substance. The plan called out the
  `ait` dispatcher insertion point as "directly after `cd "$AIT_DIR"`";
  the actual file had a comment on that line, so the new `source` line
  was placed on the immediately-following line — same effect.
- **Issues encountered:** None. Initial smoke tests (lib double-source
  idempotency, `./ait --help`, existing `test_setup_find_modern_python.sh`
  pass) all worked first try.
- **Key decisions:**
  - **Scoped lib over shell-rc edit (user direction during planning).**
    The original plan draft proposed extending `ensure_path_in_profile()`
    to append `~/.aitask/bin` to the user's `~/.zshrc`/`~/.bashrc`. User
    rejected this as too broad — it would silently override system
    `python3` for the entire interactive shell and unrelated tools. The
    final plan ships a sourced lib instead, scoped to aitasks
    subprocesses only. `ensure_path_in_profile()` was left untouched
    and still manages only `~/.local/bin` (the user-facing `ait` shim).
  - **Per-script sourcing deferred to t695_4.** With ~9 Python-invoking
    `.aitask-scripts/aitask_*.sh` scripts in the framework, adding the
    `source` line to each here would have duplicated the file-level
    edits t695_4 will already make to those same scripts. Instead, the
    `ait` dispatcher source covers `./ait <cmd>` flows now, and a
    sibling-task note in t695_4 carries the per-script sourcing pattern
    for skill-direct flows (where `aitask_*.sh` is invoked without the
    dispatcher). Between t695_3 and t695_4 lands, skill-direct flows
    fall back to system `python3` via PATH, with the existing
    `${PYTHON:-python3}` import-check guards (e.g.,
    `aitask_board.sh:24`) catching missing-deps.
  - **Idempotency via runtime PATH check, not rc-file grep.** The lib
    inspects `$PATH` at sourcing time rather than diffing a file. This
    is naturally portable across all shells and avoids the question of
    "which rc file would I check" in a sourced-lib context. The
    `_AIT_PATH_LOADED` guard provides per-process double-source
    protection; the `case` statement protects against cross-shell
    re-entry where a child shell starts with a parent-prepended PATH.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - `lib/aitask_path.sh` is the single source of truth for "scope
    `~/.aitask/bin` to aitasks subprocesses". Any future framework
    binary that needs the same scoping should be added to the same lib
    (extend the case statement) rather than introducing a parallel
    PATH-management mechanism.
  - **Do NOT touch the user's shell rc** for any future framework PATH
    needs. `ensure_path_in_profile()` is reserved for `~/.local/bin`
    (the global `ait` shim, which IS user-facing) and should not be
    extended to handle framework-internal paths. The user-feedback
    memory `feedback_no_global_path_override.md` records this rule.
  - t695_4 must source `lib/aitask_path.sh` (next to
    `lib/python_resolve.sh`) in every Python-invoking script it
    migrates. The exact sibling-task pattern was added to
    `aitasks/t695/t695_4_refactor_python_callers.md` under "Notes for
    sibling tasks".
  - The `~/.aitask/bin/python3` symlink target is `$VENV_DIR/bin/python`
    (not `bin/python3`) — `python -m venv` makes `python` canonical
    with `python3` as a sibling symlink, so we mirror that shape one
    level up. Both names are written so callers using either shebang
    form resolve identically.
