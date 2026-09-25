---
Task: t1849_upgrade_leaves_session_hook_uninstalled.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1849 — Surface a missing Claude Code session hook after `ait upgrade`

## Context

`ait upgrade` runs the target release's `install.sh --force`, which stages
`aitasks/metadata/claude_settings.hooks.json` (`install_seed_claude_hooks`) but
never merges it into `.claude/settings.json` — only `ait setup`
(`aitask_setup.sh::setup_claude_hooks`, own consent prompt) does. A project set
up before the hook shipped and only upgraded since has no hook, so its agents
freeze into unrestorable records (observed: `thinking_app`, 4 frozen agents).

Goal: make the missing hook visible at the moments that matter and cheap to fix,
**without** silently installing executable hooks (the consent prompt stays).

## Design

One detector, three consumers, one cheap repair path.

### 1. Shared merge/check helper — `.aitask-scripts/lib/claude_hooks_merge.py` (new)

Move the Python currently inlined as a heredoc in
`aitask_setup.sh::merge_claude_hooks` (the `norm()` identity + SessionStart
merge) into this file, with two subcommands:

- `merge <dest> <seed>` → prints merged JSON (exactly today's behaviour;
  `SystemExit` messages preserved).
- `check <dest> <seed>` → exit **0** when merging would change nothing (hook
  installed), **1** when it would add something or `<dest>` does not exist
  (missing), **2** when `<dest>` is unreadable / not valid JSON / has a
  non-object `hooks` or non-array `SessionStart` (invalid — the same inputs on
  which `merge` raises). Implemented as `merge(deepcopy(existing)) == existing`,
  so "installed" means precisely "setup's merge is a no-op" — no second
  definition of identity to drift.

`merge_claude_hooks` keeps its python-resolution ladder (`$VENV_DIR/bin/python`
→ `python3`) and calls `"$python_cmd" "$SCRIPT_DIR/lib/claude_hooks_merge.py" merge "$dest_file" "$seed_file"`.
**It now returns non-zero on every failure branch** (no Python, merge error,
empty output) — today it warns and returns 0, which is what would let a repair
look successful while fixing nothing. Warnings unchanged.

### 2. Status lib — `.aitask-scripts/lib/claude_hook_status.sh` (new, sourced)

- `claude_session_hook_status <project_dir>` → echoes one word:
  1. no `aitasks/metadata/claude_settings.hooks.json` → `NO_SEED`
  2. no `.claude/settings.json` → `MISSING` (absence proves it; **no Python
     needed** — the common upgraded-only case)
  3. A usable Python (the `resolve_python` interpreter **passing the
     minimum-version predicate** below) →
     `claude_hooks_merge.py check`: 0 → `INSTALLED`, 1 → `MISSING`,
     2 → `INVALID`. Malformed settings are therefore never reported as a
     plain `MISSING`.
  4. No usable Python: `settings.json` never names `aitask_session_hook.sh` →
     `MISSING` (true either way; the repair will then fail loudly, see §3);
     otherwise `UNKNOWN`.
  Always returns 0 so callers under `set -e` are safe.
- `claude_session_hook_hint` → the canonical MISSING hint (verb per CLAUDE.md:
  repair/populate → `ait setup`). It is **Claude-specific and about future
  sessions**, because restore reads the session id already stored in each
  record (`agent_restore.py::resume_blocker` → `no_session`), which installing
  the hook cannot back-fill:
  "The Claude Code session hook is not installed in .claude/settings.json, so Claude Code agents started in this project record no session id and cannot be restored after a freeze. Run 'ait setup --hooks-only' to install it. It only helps Claude Code agents started afterwards: agents already frozen without a session id stay view-only (re-pick them if they have a task), and running ones need a restart."
- `claude_session_hook_invalid_hint` → "The Claude Code session hook cannot be checked: .claude/settings.json is not valid JSON (or its hooks section is malformed). Fix the file, then run 'ait setup --hooks-only'."
- `claude_session_hook_runtime_ok` → exit 0 only when the hook could actually
  record a session on this machine. Two explicit checks:
  1. `command -v python3` succeeds — the hook parses its payload with a bare
     `python3` (`aitask_session_hook.sh` step 1; any version parses JSON).
  2. The store writer's interpreter meets the minimum. `resolve_python`
     (`lib/python_resolve.sh`) only **locates** an executable (`AIT_PYTHON` →
     venv → `~/.aitask/bin/python3` → `python3`); the version gate lives in
     `require_modern_python`, which `die`s and so cannot be used as a probe.
     So the probe runs the **same predicate** itself, non-fatally:
     `p=$(resolve_python)`; `[[ -n "$p" ]] && "$p" -c "import sys; sys.exit(0 if sys.version_info >= ($major, $minor) else 1)"`
     with `major`/`minor` split from `AIT_VENV_PYTHON_MIN` exactly as
     `require_modern_python` does. This is the interpreter
     `aitask_agent_sessions.sh` will get from `require_ait_python`, so a pass
     here means the writer will accept it.
  The status check (step 3 above) uses the same resolved interpreter, and only
  when it passes this version predicate — otherwise it falls to step 4.
- **The probe reports WHY, not just pass/fail**, because the right repair
  depends on it. `claude_session_hook_runtime` echoes one line (always rc 0;
  `claude_session_hook_runtime_ok` is the `== OK` test over it):
  - `OK`
  - `NO_PYTHON3` — no `python3` on `PATH` (hook payload parse would fail)
  - `NO_PYTHON` — `resolve_python` found nothing
  - `TOO_OLD:<path>` — the selected interpreter fails the predicate and did
    **not** come from the override
  - `OVERRIDE_TOO_OLD:<path>` — the selected interpreter is `$AIT_PYTHON`
    (`-n "$AIT_PYTHON" && -x "$AIT_PYTHON" && p == "$AIT_PYTHON"`, mirroring
    `resolve_python`'s first candidate) and fails the predicate. Full
    `ait setup` would **not** help: it installs a modern venv, but
    `resolve_python` keeps preferring the explicit override.
- **Repair advice per reason** — one function, `claude_session_hook_repair`,
  returns the instruction that the hints and `--hooks-only` print (single
  mapping, no per-caller wording):
  - `OK` → "run 'ait setup --hooks-only'"
  - `NO_PYTHON3` / `NO_PYTHON` / `TOO_OLD:` → "run the full 'ait setup', which installs the Python runtime the hook needs and then offers the hook"
  - `OVERRIDE_TOO_OLD:<path>` → "AIT_PYTHON=<path> is older than Python <min> and overrides every other interpreter, so the session store would keep using it — unset AIT_PYTHON or point it at Python >=<min>, then run 'ait setup --hooks-only'"
- The MISSING hint embeds `claude_session_hook_repair` in place of the literal
  `ait setup --hooks-only`, so the shortcut is only offered where it can work
  and an override problem is named as such.
- Load guard (`_AIT_CLAUDE_HOOK_STATUS_LOADED`) like `ide_frozen_offer.sh`.

### 3. `ait setup --hooks-only` (`aitask_setup.sh`)

- `main()` arg parse: `--hooks-only) HOOKS_ONLY=1` and `--yes) ASSUME_YES=1`.
  `--yes` without `--hooks-only` → `die` (only meaningful there).
- `setup_claude_hooks` gains a return contract: **0** installed (fresh, merged,
  or already present), **1** failed (merge/copy failure, invalid settings),
  **2** declined. It checks status **first**: `INSTALLED` → `info "Claude Code
  session hook already installed"`, return 0, **no prompt**; `INVALID` → warn
  the invalid hint, return 1, no prompt. (A declined hook still re-prompts every
  run — the E2 "decline is not remembered" contract is unchanged.) The full
  `ait setup` caller (`setup_code_agents`) calls it as
  `setup_claude_hooks || true`, so full setup stays non-fatal exactly as today.
- `--hooks-only` flow, in this order (status before consent):
  1. `status=$(claude_session_hook_status "$project_dir")`
  2. `INSTALLED` → "already installed", **exit 0** — no consent needed, no work,
     so a repeated non-interactive run succeeds.
  3. `NO_SEED` → "no hook seed at aitasks/metadata/claude_settings.hooks.json — run 'ait setup' to restore it", exit 1.
  4. `INVALID` → invalid hint, exit 1.
  5. `MISSING` / `UNKNOWN` and the runtime probe is not `OK` → print
     "The session hook cannot record sessions on this machine yet: " +
     `claude_session_hook_repair`, exit 1, **no write**. (This also removes the
     post-copy `UNKNOWN` re-check: past this point a usable Python is known to
     be present, so the re-check in step 7 is a real JSON check.)
  6. `MISSING` / `UNKNOWN` → **consent gate**: stdin not a terminal and no
     `--yes` → "ait setup --hooks-only needs an interactive answer to install an executable hook; re-run in a terminal or pass --yes to accept explicitly.", exit 2,
     **before any write**. (`setup_claude_hooks`' own non-interactive
     auto-accept remains only for full `ait setup`, unchanged; here the gate
     guarantees it is reached non-interactively only with `--yes`.)
  7. `snapshot_pre_setup_dirty`; `setup_claude_hooks`, keeping rc:
     rc 2 → "Session hook not installed.", exit 0; rc 1 → "Session hook installation failed — see above.", exit 1;
     rc 0 → **re-check** status (verify by re-read, not by the success line):
     not `INSTALLED` → failure, exit 1.
  8. `commit_framework_files` (baseline armed per its contract;
     `.claude/settings.json` is already in `_ait_framework_paths`); exit 0.
  No other setup step runs (no OS detection, venv, data branch, shim, …).
- `usage()`: document `--hooks-only` ("Only install / repair the Claude Code
  session hook, needed to restore Claude Code agents frozen later; skips every
  other step") and `--yes` ("With --hooks-only: accept the hook without a
  prompt, for non-interactive use"), plus an example line.

### 4. `ait upgrade` hint (`install.sh`)

- New global `EXISTING_INSTALL=false`; set `true` in `check_existing_install`
  on both paths that proceed over an existing install (`--force` and the
  interactive "y").
- New `report_claude_session_hook()`: returns early unless
  `EXISTING_INSTALL=true` and `$INSTALL_DIR/.aitask-scripts/lib/claude_hook_status.sh`
  exists (extracted from the same tarball); sources it; `MISSING` → `warn` the
  hint; `INVALID` → `warn` the invalid hint; anything else silent.
  Non-fatal in every branch.
- Called in `main()` after `commit_installed_data_files`, before the success
  banner. Fresh installs are skipped: their banner already says "run 'ait setup'".
- `ait upgrade` runs the **target** version's `install.sh`, so the hint shows
  on the first upgrade to a release carrying this change — exactly the
  upgraded-only population — and step 2 of the status order needs no Python.

### 5. `ait ide` startup (`lib/ide_frozen_offer.sh`)

The `GONE:` wire line (`agent_reopen.py::gone_line`) carries no agent kind, and
a `no_session` record may be a Codex agent whose id was not captured at freeze
— so the offer **cannot attribute** a view-only record to the missing Claude
hook. The warning is therefore printed as a **separate, explicitly
forward-looking note**, never as the cause of the listed records:

- When there is ≥1 gone record, source the status lib (via
  `$(dirname "${BASH_SOURCE[0]}")`); on `MISSING` print
  "Separately, about future Claude Code sessions: " followed by the hint
  (whose text already says it does not repair existing records); on `INVALID`
  print the invalid hint. Placement: non-interactive branch after the existing
  "Note:" line (stderr); interactive branch after the listing, before the
  V/R/P/S menu.
- Not printed when there are no gone records: anything written just before
  `exec tmux attach` is wiped from view, so a bare startup warning would be
  invisible. (Changing the wire format to carry `agent_kind` for a causal,
  per-record message is left out — it widens a shared wire contract for a
  hint.)

### Out of scope (suggest as follow-up)

- A note in the monitor's `FreezeConfirmDialog` ("this agent can only be viewed,
  not restored"). `monitor/` files currently carry uncommitted edits from a
  concurrent session, and the freeze engine has a per-record signal (no
  recorded session id) that is more accurate than a project-level check —
  worth its own task.
- Codex `.codex/config.toml` hook detection.

## Files

- new `.aitask-scripts/lib/claude_hooks_merge.py`
- new `.aitask-scripts/lib/claude_hook_status.sh`
- `.aitask-scripts/aitask_setup.sh` (`merge_claude_hooks`, `setup_claude_hooks`, `usage`, `main`)
- `install.sh` (`check_existing_install`, new `report_claude_session_hook`, `main`)
- `.aitask-scripts/lib/ide_frozen_offer.sh`
- `tests/test_session_hook_install.sh`, `tests/test_ide_frozen_offer.sh` (extend); `tests/test_frozen_agents_acceptance.sh` re-run unchanged
- new `tests/test_claude_hook_status.sh`, `tests/test_setup_hooks_only.sh`
- `website/content/docs/commands/setup-install.md` (Session Hooks section + flag list)

## Tests

- **Existing** `tests/test_session_hook_install.sh` must stay green — it drives
  the real `merge_claude_hooks` (groups B/C/C2), so it is the regression net
  for the Python move.
- Extend it: Group F — `setup_claude_hooks` on an already-installed fixture
  under the PTY prints "already installed" and does NOT show the prompt.
- New `tests/test_setup_hooks_only.sh` — **the real command path**: a temp
  project (`git init`, one commit; copies of `aitask_setup.sh`,
  `.aitask-scripts/lib/`, `VERSION`, and the hook seed in
  `aitasks/metadata/`), `HOME` pointed at a temp dir. Runs
  `bash <fixture>/.aitask-scripts/aitask_setup.sh --hooks-only …` and asserts:
  - non-TTY, no `--yes` → exit 2, refusal message, **no** `.claude/settings.json`;
  - PTY (`tests/lib/pty_drive.py`), answer `n` → nothing installed;
  - PTY, answer `Y` (+ `Y` to the commit prompt) → hook installed, committed
    (`git log -1 --name-only` shows only `.claude/settings.json`);
  - non-TTY with `--yes` → hook installed;
  - second run on an installed project → "already installed", no prompt;
  - skipped setup work: output lacks `Detected OS` / venv lines and
    `$HOME/.aitask` was not created;
  - **repeated non-interactive run without `--yes` on an installed project →
    exit 0, "already installed"** (status is checked before the consent gate);
  - invalid `settings.json` → exit 1, invalid hint, file byte-for-byte unchanged,
    **no** "installed" success line (under a PTY answering Y too — failure must
    not look like success);
  - `NO_SEED` fixture → exit 1 naming `ait setup`;
  - **Python hidden** (temp `HOME` with no venv, `PATH` = stub bin dir without
    `python3`), no `settings.json`, with `--yes` → exit 1, message names the
    full `ait setup`, **no `.claude/settings.json` written** (the old failure:
    copy, then an `UNKNOWN` re-check reporting failure after the write);
  - **older override** (`AIT_PYTHON` → the pre-minimum stub, `python3` still on
    `PATH`), with `--yes` → exit 1, message names `AIT_PYTHON` and says to
    unset/repoint it, and does **not** tell the user to run the full `ait setup`;
    no write. Then **the same fixture with `AIT_PYTHON` unset** → probe `OK`,
    `resolve_python` now selects the real `python3` (asserted: its path is not
    the stub), and `--hooks-only --yes` installs the hook — the advised action
    really changes the selected interpreter;
  - `--yes` without `--hooks-only` → non-zero, no writes;
  - `--help` lists `--hooks-only` and `--yes`.
- New `tests/test_claude_hook_status.sh` (fixture dirs, `HOME` pointed at a
  temp dir so the python ladder falls to `python3`):
  NO_SEED; MISSING (no settings.json) **with Python hidden from `PATH`**
  (proves the no-parse branch); MISSING (settings.json never naming the
  script, also Python-less); MISSING (settings.json without hook);
  MISSING (hook under a different matcher — merge would add it);
  INSTALLED (seed copied); INSTALLED (absolute-path spelling, C2 case);
  INVALID (invalid JSON; and `hooks` a list) — never MISSING;
  UNKNOWN (Python hidden, settings.json naming the script);
  hint text contains `ait setup --hooks-only` when the runtime probe passes,
  and names full `ait setup` (not `--hooks-only`) with Python hidden;
  `claude_session_hook_runtime` reports `NO_PYTHON3` with Python hidden;
  `OVERRIDE_TOO_OLD:<stub>` with `AIT_PYTHON` → a stub interpreter that execs
  the real `python3` for everything except the `sys.version_info` predicate
  (which it fails — a pre-minimum Python); `TOO_OLD:<stub>` with the same stub
  reached via the temp-HOME venv path (`$HOME/.aitask/venv/bin/python` → stub,
  `AIT_PYTHON` unset); and `OK` normally. `claude_session_hook_repair` maps
  each to its advice (the override case names `AIT_PYTHON` and never says
  "full ait setup").
  Plus `merge_claude_hooks` returns non-zero on invalid JSON and with Python
  hidden (previously 0).
  Plus `install.sh --source-only`: `report_claude_session_hook` prints the hint
  with `EXISTING_INSTALL=true` + missing hook, prints nothing with
  `EXISTING_INSTALL=false`, nothing when installed, the invalid hint on
  INVALID, and — with Python hidden — the MISSING hint for an absent
  settings.json that points to full `ait setup`.
  "Python hidden" = `PATH` set to a temp bin dir holding symlinks to only the
  tools the lib uses (`bash`, `grep`, `dirname`), and a temp `HOME`.
  Plus `ide_offer_frozen_agents` with a stub `frozen_sh` (in the existing
  `tests/test_ide_frozen_offer.sh`), non-interactive: with ≥1 gone record the
  "Separately, about future Claude Code sessions" note appears when MISSING and
  is absent when INSTALLED; with no gone records nothing is printed.
- Full `ait setup` stays non-fatal: a `set -e` driver calling
  `setup_code_agents`-style `setup_claude_hooks || true` on an invalid-JSON
  fixture continues (Group G in `test_session_hook_install.sh`).
- `shellcheck` on touched shell files; `bash tests/test_ide_frozen_offer*.sh`
  (whatever exists for t1847) and `tests/test_seed_manifest_drift.sh`.
- `cd website && python3 check_links.py --build` after the doc edit.

## Step 9

Post-implementation: commit code (`bug: … (t1849)`), plan via
`aitask_task_commit.sh`, archive per task-workflow Step 9.

## Risk

### Code-health risk: low
None identified. (Moving the merge Python into a file is covered by the
existing merge tests, groups B/C/C2. The new non-zero returns from
`merge_claude_hooks` / `setup_claude_hooks` reach only three call sites —
`setup_code_agents` (now `|| true`, pinned by Group G) and the tests in
`test_session_hook_install.sh` / `test_frozen_agents_acceptance.sh`, which
already ignore the status — so full `ait setup` behaviour is unchanged.)

### Goal-achievement risk: low
None identified. (The hint reaches the upgraded-only population because
upgrades run the target version's `install.sh`, and the absent-file / absent-
script cases are detected without Python, and the repair it names is chosen
by a runtime probe so a Python-less machine is sent to full `ait setup`
rather than a shortcut that would copy a non-functional hook; consent stays explicit on the new
path; the hint states that existing no-session records are not repaired. The
freeze-dialog note is deferred as a follow-up — the task only asked to
"consider" it.)
