---
Task: t653_2_tolerant_initializer_apply_and_retry_cli.md
Parent Task: aitasks/t653_brainstorm_import_proposal_hangs.md
Sibling Tasks: aitasks/t653/t653_3_*.md, aitasks/t653/t653_4_*.md, aitasks/t653/t653_5_*.md
Archived Sibling Plans: aiplans/archived/p653/p653_1_brainstorm_tui_self_heal_apply.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-26 (verify path)
  - claudecode/opus4_7_1m @ 2026-04-26 17:27
---

# Plan: t653_2 — Tolerant initializer apply + prompt hardening + retry CLI

## Context

`apply_initializer_output()` in `.aitask-scripts/brainstorm/brainstorm_session.py` calls `yaml.safe_load()` on the agent's `NODE_YAML` block. Em-dashes followed by a colon (perfectly natural English the agent emits) make YAML reject the line. Confirmed verbatim against the on-disk session-635 output:

```
mapping values are not allowed here
  in "<unicode string>", line 28, column 71:
     ... ata/gates.yaml — per-gate config: verifier skill name, type (mac ...
```

Sibling t653_1 (already merged) added a self-healing TUI: on every session load (and after Error/Aborted) the TUI calls `_try_apply_initializer_if_needed()`, which surfaces failures via a persistent banner that already references `ait brainstorm apply-initializer <session>`. **That CLI does not exist yet — the banner message is informative but currently a dead pointer.** This task makes it real and stops the underlying parse failure from happening in the first place.

Three layers of defense (cheapest first):
1. **Prompt** — tighten `initializer.md` Phase 4 so the agent quotes scalars containing problematic characters.
2. **Parser fallback** — `_tolerant_yaml_load()`: on `YAMLError`, run a regex pass that quotes the offending values and retry. On permanent failure, write a structured error log to disk before re-raising.
3. **Retry CLI** — `ait brainstorm apply-initializer <session>` for manual recovery when the auto-retry path can't run (or didn't run in time).

## Verified codebase state (from Phase 1 exploration)

**`.aitask-scripts/brainstorm/brainstorm_session.py`** (line numbers shifted by t653_1):
- `apply_initializer_output()` is at **line 283** (not 264 as the original task body claimed).
- `yaml.safe_load(node_yaml_text)` is at **line 309**.
- `import yaml` is **inside** `apply_initializer_output()` at line 305 — not at module top.
- `re` is **not imported anywhere** — must be added.
- `now_utc` does **not exist** in this module. The module uses `datetime.now().strftime(...)` (`datetime` is imported at module top, line 15). The plan will use `datetime.now()` rather than the non-existent `now_utc()`.
- `wt` (Path) is in scope inside `apply_initializer_output()` at line 296.
- `n000_needs_apply()` (added by t653_1) lives at line 264 and is unrelated to this task — leave alone.
- `_extract_block()` at line 250 — reused as-is.
- Placeholder string at line 120 — reused as-is.

**`.aitask-scripts/brainstorm/templates/initializer.md`:**
- `## Phase 4: Write Output` at line 122. Block-delimiters paragraph at lines 124–133. `### Checkpoint 4` at line 135. **No existing YAML-rules subsection.** The new subsection inserts between line 133 and line 135.
- t650_2's pseudo-verb rewrite touched the `### Checkpoint N` blocks — diffs do not collide with the new subsection.

**`.aitask-scripts/brainstorm/brainstorm_app.py`** (post-t653_1):
- Persistent banner widget `#initializer_apply_banner` exists in `compose()` at line 1345.
- `_try_apply_initializer_if_needed()` at lines 1808–1838.
- Notify/banner messages at lines 1830 and 3280 already reference `` `ait brainstorm apply-initializer {self.task_num}` ``. Once this task lands, those messages become correct (they are dead pointers today). **No `brainstorm_app.py` changes needed in this task.**

**`ait` dispatcher (lines 218–244):**
- Brainstorm subcommand uses script-per-subcommand pattern: `<subcmd>) exec "$SCRIPTS_DIR/aitask_brainstorm_<name>.sh" "$@" ;;`. Insert new sub-case in alphabetical position between `archive` and `delete` (or near them — match surrounding style).
- Update the `--help|-h|""` help text to list `apply-initializer`.
- Update the unknown-subcommand error message's `Available:` list.

**Whitelist patterns** (verified against `aitask_archive.sh` / `aitask_create.sh`):
- `.gemini/policies/aitasks-whitelist.toml` uses `[[rule]]` (singular), not `[[rules]]`.
- The 5-touchpoint pattern matches the existing helpers' format exactly.

## Files to modify

| File | Change |
|------|--------|
| `.aitask-scripts/brainstorm/templates/initializer.md` | + `### YAML rules for the NODE_YAML block` subsection (~15 lines) between line 133 and line 135 |
| `.aitask-scripts/brainstorm/brainstorm_session.py` | + module-top `import yaml`, `import re`; + `_tolerant_yaml_load()` (~30 lines); replace `yaml.safe_load(node_yaml_text)` at line 309 with try/except using tolerant load + error log |
| `.aitask-scripts/aitask_brainstorm_apply_initializer.sh` | NEW (~25 lines) |
| `ait` | + `apply-initializer` sub-case (~1 line) + help text + Available list (~3 lines total) |
| `.claude/settings.local.json` | + `"Bash(./.aitask-scripts/aitask_brainstorm_apply_initializer.sh:*)"` |
| `.gemini/policies/aitasks-whitelist.toml` | + `[[rule]]` block |
| `seed/claude_settings.local.json` | + same as runtime claude entry |
| `seed/geminicli_policies/aitasks-whitelist.toml` | + same as runtime gemini entry |
| `seed/opencode_config.seed.json` | + `"./.aitask-scripts/aitask_brainstorm_apply_initializer.sh *": "allow"` |
| `tests/test_apply_initializer_tolerant.sh` | NEW (~100 lines) |

Codex (`.codex/`, `seed/codex_config.seed.toml`) is intentionally exempt per CLAUDE.md.

## Step-by-step

### S1. Prompt hardening — `initializer.md` Phase 4

Insert between line 133 (end of fenced delimiters block) and line 135 (`### Checkpoint 4`):

```markdown
### YAML rules for the NODE_YAML block

Every scalar value MUST be double-quoted when it contains any of:
- em-dash (`—`) or en-dash (`–`)
- hyphen-space (` - `)
- a second `:` on the same line (the YAML key separator must be the only colon-space)
- `#` (which YAML treats as a comment marker)

Bad (will fail to parse):
`component_gate_registry: aitasks/metadata/gates.yaml — per-gate config: verifier skill name`

Good:
`component_gate_registry: "aitasks/metadata/gates.yaml — per-gate config: verifier skill name"`

When in doubt, double-quote the value.
```

### S2. `_tolerant_yaml_load()` in `brainstorm_session.py`

**Module-top imports** — add `import yaml` and `import re` to the existing import block (after `from pathlib import Path` at line 16). The previous in-function `import yaml` at line 305 becomes redundant; remove it.

**New helper** — place immediately above `apply_initializer_output()` (i.e., right after `n000_needs_apply()` which ends at line 280):

```python
_PROBLEM_VALUE_RE = re.compile(r'^(\s*[A-Za-z_][\w]*:\s+)((?!["\'\[\{]).+?)\s*$')
_PROBLEM_CHARS_RE = re.compile(r'(—|–| - |#|: )')


def _tolerant_yaml_load(text: str) -> dict:
    """yaml.safe_load with a one-shot quote-the-bad-values fallback.

    On YAMLError, walk lines whose value (after the first ': ') contains an
    em-dash, en-dash, hyphen-space, '#', or a second ': ', and is not already
    quoted or starting a flow collection. Wrap such values in double quotes
    (escaping any embedded "). Retry parsing. Re-raise the ORIGINAL error if
    the fixed text still fails — keeping the original line number is more
    useful for debugging than the line number after auto-quoting.
    """
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as orig_err:
        fixed_lines = []
        for line in text.splitlines():
            m = _PROBLEM_VALUE_RE.match(line)
            if m and _PROBLEM_CHARS_RE.search(m.group(2)):
                value = m.group(2).replace("\\", "\\\\").replace('"', '\\"')
                fixed_lines.append(f'{m.group(1)}"{value}"')
            else:
                fixed_lines.append(line)
        fixed_text = "\n".join(fixed_lines)
        try:
            return yaml.safe_load(fixed_text)
        except yaml.YAMLError:
            raise orig_err
```

The negative-lookahead `(?!["\'\[\{])` skips already-quoted values, flow lists (`field: [a, b]`), and flow maps (`field: {…}`).

### S3. Wire into `apply_initializer_output()`

Replace the current line 309 `node_data = yaml.safe_load(node_yaml_text)` with a try/except that invokes the tolerant loader and writes an error log on permanent failure:

```python
try:
    node_data = _tolerant_yaml_load(node_yaml_text)
except yaml.YAMLError as exc:
    err_log = wt / "initializer_bootstrap_apply_error.log"
    err_log.write_text(
        f"apply_initializer_output failed at "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Original YAML parse error:\n{exc}\n\n"
        f"NODE_YAML block (first 2000 chars):\n{node_yaml_text[:2000]}\n",
        encoding="utf-8",
    )
    raise
```

`datetime` is already imported at module top (line 15). The redundant in-function `import yaml` (was line 305) is removed since yaml moves to module-top.

### S4. New helper `aitask_brainstorm_apply_initializer.sh`

Mirror `aitask_brainstorm_archive.sh`'s Python-setup boilerplate (venv-aware) so the helper works under `ait setup`'s isolated venv. Place at `.aitask-scripts/aitask_brainstorm_apply_initializer.sh`:

```bash
#!/usr/bin/env bash
# aitask_brainstorm_apply_initializer.sh - Re-run apply on a brainstorm session.
#
# Usage: ait brainstorm apply-initializer <task_num>
#
# Re-parses initializer_bootstrap_output.md and rewrites n000_init.
# Useful when the TUI's auto-retry didn't run (or didn't get a chance).
#
# Output:
#   APPLIED:n000_init        Apply succeeded
#   APPLY_FAILED:<error>     Apply failed (stderr; see also
#                            initializer_bootstrap_apply_error.log in the crew worktree)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

VENV_PYTHON="$HOME/.aitask/venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
    if ! command -v "$PYTHON" &>/dev/null; then
        die "Python not found. Run 'ait setup' to install dependencies."
    fi
    if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
        die "Missing Python package: pyyaml. Run 'ait setup' or: pip install pyyaml"
    fi
fi

SESSION="${1:-}"
[[ -z "$SESSION" ]] && { echo "Usage: ait brainstorm apply-initializer <task_num>" >&2; exit 2; }

# Accept "635" or "brainstorm-635" — strip the optional prefix
NUM="${SESSION#brainstorm-}"

cd "$SCRIPT_DIR/.."
exec "$PYTHON" -c "
import sys
sys.path.insert(0, '.aitask-scripts')
from brainstorm.brainstorm_session import apply_initializer_output
try:
    apply_initializer_output('$NUM')
    print('APPLIED:n000_init')
except Exception as exc:
    print(f'APPLY_FAILED:{exc}', file=sys.stderr)
    sys.exit(1)
"
```

`chmod +x` after creation. Validate with `shellcheck`.

### S5. Wire `ait brainstorm apply-initializer <session>` into `ait`

In the `brainstorm)` block (around line 220), insert after `archive)` line:

```bash
apply-initializer) exec "$SCRIPTS_DIR/aitask_brainstorm_apply_initializer.sh" "$@" ;;
```

Update the `--help|-h|""` help text (around line 233) to add a line:
```
echo "  apply-initializer  Re-run apply on a session (recovers stuck imports)"
```

Update the unknown-subcommand `Available:` message (around line 244) to include `apply-initializer`.

### S6. 5-touchpoint whitelist

Mirror the existing `aitask_archive.sh` entries, with the new helper's filename:

| File | Entry |
|------|-------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_brainstorm_apply_initializer.sh:*)"` in `permissions.allow` (alphabetic order) |
| `seed/claude_settings.local.json` | mirror |
| `.gemini/policies/aitasks-whitelist.toml` | `[[rule]]` block: `toolName = "run_shell_command"`, `commandPrefix = "./.aitask-scripts/aitask_brainstorm_apply_initializer.sh"`, `decision = "allow"`, `priority = 100` |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_brainstorm_apply_initializer.sh *": "allow"` |

Codex is intentionally exempt.

### S7. Tests — `tests/test_apply_initializer_tolerant.sh`

Build a temporary synthetic crew worktree under `${TMPDIR:-/tmp}/aitask_test_apply_XXXXXX` (portable mktemp template per CLAUDE.md). The strategy: monkey-patch `crew_worktree()` via `AGENTCREW_DIR` (or by setting `AGENTCREW_DIR` env var — check `agentcrew_utils.AGENTCREW_DIR` for env-var support). Three cases:

1. **Em-dash YAML loads via tolerant fallback.** Create a fixture with `--- NODE_YAML_START ---` containing the verified-bad em-dash line. Build the surrounding session structure (`br_session.yaml`, `br_nodes/n000_init.yaml`, `br_proposals/n000_init.md`). Run `apply_initializer_output()` via `python3 -c`. Assert: returns successfully, n000_init.yaml contains the rewritten YAML.

2. **Truly malformed YAML fails AND writes error log.** Fixture with unbalanced bracket (no auto-fix possible). Assert: raises `yaml.YAMLError`; `initializer_bootstrap_apply_error.log` exists in the crew worktree and contains the original parse error message.

3. **Well-formed YAML loads normally.** Fixture with already-quoted values. Assert: returns successfully; **no** error log written.

Use `assert_eq` / `assert_contains` helpers from any neighboring test file (e.g., `tests/test_claim_id.sh`).

## Verification

1. **Unit tests:** `bash tests/test_apply_initializer_tolerant.sh` — all PASS.
2. **Whitelist consistency check:**
   ```bash
   grep -n "aitask_brainstorm_apply_initializer" \
     .claude/settings.local.json \
     seed/claude_settings.local.json \
     .gemini/policies/aitasks-whitelist.toml \
     seed/geminicli_policies/aitasks-whitelist.toml \
     seed/opencode_config.seed.json
   ```
   Exactly 5 matches.
3. **No-prompt sanity:** invoke `./.aitask-scripts/aitask_brainstorm_apply_initializer.sh nonexistent_session` directly. Should run without permission prompt; print `APPLY_FAILED:...` to stderr; exit 1.
4. **shellcheck:** `shellcheck .aitask-scripts/aitask_brainstorm_apply_initializer.sh` — clean.
5. **CLI surface:** `./ait brainstorm --help` lists `apply-initializer`. `./ait brainstorm apply-initializer` (no arg) prints usage to stderr and exits 2.
6. **End-to-end on session 635 (manual, after this child lands):**
   ```bash
   ./ait brainstorm apply-initializer 635
   ```
   Expected: `APPLIED:n000_init`. Then `ait brainstorm 635` shows the real proposal — recovers the user's stuck session. *(This is one of the tracking items inside the t653_4 manual-verification sibling.)*

## Notes for sibling tasks

- **t653_1 (already merged):** The banner messages and notify text added there reference `ait brainstorm apply-initializer {self.task_num}`. Those become correct (not just informative) once this task lands. No further changes needed in `brainstorm_app.py`.
- **t653_3 (agentcrew terminal push):** Independent code paths. Can land before or after.
- **t653_4 (manual verification aggregate):** End-to-end recovery of session 635 belongs in its checklist.
- **t650_2 (already merged):** Pseudo-verb rewrite touched the `### Checkpoint N` blocks. The new YAML-rules subsection sits between the delimiters paragraph and `### Checkpoint 4`, so it does not collide with t650_2's edits.

## Step 9 — Post-Implementation

Standard task-workflow archival. No `verify_build` configured (per `aitasks/metadata/project_config.yaml`). After commit:
- Append a "Final Implementation Notes" section to this plan covering: actual files touched, any deviations (especially around the regex pattern or tolerant-load edge cases), and whether session 635 recovery worked end-to-end.
- Run `./.aitask-scripts/aitask_archive.sh 653_2`. Push.

## Out of scope (intentionally)

- TUI changes — already done in t653_1.
- Heartbeat / agent-crew status push fixes — owned by t653_3 and parent t650.
- Polling activity indicator — owned by t653_5.
- Multi-language YAML auto-fix (only same-line scalar quoting; no rewriting block scalars or flow sequences).

## Final Implementation Notes

- **Actual work done:** All seven step blocks (S1–S7) implemented as planned:
  - `initializer.md` — appended `### YAML rules for the NODE_YAML block` between the delimiters paragraph and `### Checkpoint 4` in Phase 4.
  - `brainstorm_session.py` — added module-top `import yaml`, `import re`; added `_PROBLEM_VALUE_RE`, `_PROBLEM_CHARS_RE`, and `_tolerant_yaml_load()` immediately above `apply_initializer_output()`; replaced the line-309 `yaml.safe_load()` with a try/except using the tolerant loader and writing `initializer_bootstrap_apply_error.log` on permanent failure; removed the now-redundant in-function `import yaml`.
  - `aitask_brainstorm_apply_initializer.sh` — new helper, venv-aware Python detection mirroring `aitask_brainstorm_archive.sh`, prefix stripping for `brainstorm-NNN`, `chmod +x` applied. Output contract: `APPLIED:n000_init` / `APPLY_FAILED:<exc>`.
  - `ait` — added `apply-initializer)` sub-case adjacent to `archive)`; updated `--help|-h|""` text; added to unknown-subcommand `Available:` list. Realigned the existing arrows for readability.
  - 5-touchpoint whitelist — entries added to `.claude/settings.local.json`, `seed/claude_settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json`. Codex omitted per CLAUDE.md.
  - `tests/test_apply_initializer_tolerant.sh` — new, 15 assertions covering: em-dash tolerant fallback, malformed-YAML failure with error log, clean YAML happy path (no error log), and direct `_tolerant_yaml_load` unit assertions (em-dash auto-quote, already-quoted preservation, flow-list non-mangling, malformed re-raise).

- **Deviations from plan:** Two minor:
  - The helper script uses a `python3 - "$NUM" <<'PY' … PY` heredoc (passing the session number via `argv[1]`) instead of inline-substituting the variable into the script body. This avoids quoting issues when the session ID contains characters meaningful to the shell, and shellcheck is happier with it. Functionally identical — same APPLIED/APPLY_FAILED output.
  - The arrows in the brainstorm subcommand dispatch were realigned to accommodate the longer `apply-initializer` keyword. Pure formatting; no behavior change.

- **Issues encountered:** None. shellcheck info-level SC1091 on the `source "$SCRIPT_DIR/lib/terminal_compat.sh"` line matches the project standard for every other helper in `.aitask-scripts/` (e.g., `aitask_brainstorm_archive.sh` exits with the same info).

- **Key decisions:**
  - Promoted `yaml` to a module-top import (was lazy-imported inside `apply_initializer_output`). Tests need to call `_tolerant_yaml_load` directly without first running the full apply path; a top-level import is cleaner and the import cost is trivial since the module is already pulled in by the brainstorm TUI/CLI on every launch.
  - The negative-lookahead `(?!["\'\[\{])` in `_PROBLEM_VALUE_RE` skips already-quoted scalars **and** flow collections (`field: [a, b]` / `field: {…}`). Confirmed via the unit-test case `key: [a, b, c]` which must round-trip through tolerant load unchanged.
  - On permanent parse failure, `_tolerant_yaml_load` re-raises the **original** `YAMLError`, not the post-quoting one. The original line numbers are far more useful for debugging than line numbers shifted by auto-quoting.

- **Notes for sibling tasks:**
  - **t653_1 (already merged):** Banner/notify text at `brainstorm_app.py:1830` and `:3280` referenced `ait brainstorm apply-initializer {task_num}`. Those references are now backed by a real CLI subcommand; no further changes in `brainstorm_app.py` are needed.
  - **t653_3 (agentcrew terminal push):** Independent. The new error-log file `initializer_bootstrap_apply_error.log` lives in the crew worktree alongside `initializer_bootstrap_status.yaml` — t653_3's status-push logic doesn't need to know about it.
  - **t653_4 (manual verification aggregate):** End-to-end recovery of session 635 with `./ait brainstorm apply-initializer 635` is a candidate checklist item. Expected output: `APPLIED:n000_init`, then opening `ait brainstorm 635` shows the real proposal text.
  - **t653_5 (polling indicator widget):** No interaction with this task.

- **Build verification:** No `verify_build` configured in `project_config.yaml`. New tests pass (15/15). Existing `test_apply_initializer_output.sh` regression check passes (8/8).

- **Session 635 recovery (manual, post-archival):** Listed in t653_4's verification checklist; not exercised inside the implementation context to avoid mutating the user's live brainstorm session without explicit go-ahead.
