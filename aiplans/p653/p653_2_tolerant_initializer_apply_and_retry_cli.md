---
Task: t653_2_tolerant_initializer_apply_and_retry_cli.md
Parent Task: aitasks/t653_brainstorm_import_proposal_hangs.md
Sibling Tasks: aitasks/t653/t653_1_*.md, aitasks/t653/t653_3_*.md
Archived Sibling Plans: (none yet)
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
---

# Plan: t653_2 — Tolerant initializer apply + prompt hardening + retry CLI

## Context (recap)

`apply_initializer_output()` (`brainstorm_session.py:264`) calls `yaml.safe_load()` on the agent's `NODE_YAML` block. Em-dashes followed by a colon (perfectly natural English) make YAML reject the line. Confirmed verbatim against the on-disk session-635 output:

```
mapping values are not allowed here
  in "<unicode string>", line 28, column 71:
     ... ata/gates.yaml — per-gate config: verifier skill name, type (mac ...
```

`brainstorm_app._poll_initializer()`'s try/except swallows the exception. The 794-line agent output sits on disk forever, and the user has no recovery CLI.

## Approach

Three layers of defense:

1. **Prompt** (cheapest fix; layered first): tighten `initializer.md` Phase 4 so the agent quotes scalars containing problematic characters.
2. **Parser fallback**: if `yaml.safe_load` raises, attempt one regex pass that quotes the offending values, retry, and on permanent failure write a structured error log.
3. **Retry CLI**: new `ait brainstorm apply-initializer <session>` that re-runs apply on demand. Required because the TUI auto-retry (sibling t653_1) only reaches the apply path while the TUI is open or on next session load — the CLI gives the user direct control.

## Step-by-step

### S1. Prompt hardening — `initializer.md`

Append a `### YAML rules for the NODE_YAML block` subsection inside `## Phase 4: Write Output`, between the existing block-delimiters paragraph and `### Checkpoint 4`. Coordinate with t650_2's pseudo-verb rewrite: t650_2 only edits the `### Checkpoint N` blocks themselves; this subsection sits between them so the diffs do not collide.

Subsection content:

> ### YAML rules for the NODE_YAML block
>
> Every scalar value MUST be double-quoted when it contains any of:
> - em-dash (`—`) or en-dash (`–`)
> - hyphen-space (` - `)
> - a second `:` on the same line
> - `#` (which YAML treats as a comment marker)
>
> Bad (will fail to parse):
> `component_gate_registry: aitasks/metadata/gates.yaml — per-gate config: verifier skill name`
>
> Good:
> `component_gate_registry: "aitasks/metadata/gates.yaml — per-gate config: verifier skill name"`
>
> When in doubt, double-quote the value.

### S2. `_tolerant_yaml_load()` in `brainstorm_session.py`

Add near the top of the file (after the existing imports of `yaml`, `re`):

```python
import re

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

Locate the line `node_data = yaml.safe_load(node_yaml_text)` (around line 280 of `brainstorm_session.py`) and replace with:

```python
try:
    node_data = _tolerant_yaml_load(node_yaml_text)
except yaml.YAMLError as exc:
    err_log = wt / "initializer_bootstrap_apply_error.log"
    err_log.write_text(
        f"apply_initializer_output failed at {now_utc()}\n\n"
        f"Original YAML parse error:\n{exc}\n\n"
        f"NODE_YAML block (first 2000 chars):\n{node_yaml_text[:2000]}\n",
        encoding="utf-8",
    )
    raise
```

`wt` and `now_utc` are already imported in this module — verify before editing.

### S4. New helper `aitask_brainstorm_apply_initializer.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="${1:-}"
[[ -z "$SESSION" ]] && { echo "Usage: $0 <session>" >&2; exit 2; }

# Accept "635" or "brainstorm-635" — strip the optional prefix
NUM="${SESSION#brainstorm-}"

cd "$SCRIPT_DIR/.."
exec python3 -c "
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

`chmod +x .aitask-scripts/aitask_brainstorm_apply_initializer.sh`. Test with `shellcheck`.

### S5. Wire `ait brainstorm apply-initializer <session>`

Locate the `brainstorm` case in the top-level `ait` script (`grep -n "brainstorm)" ait`). Add a sub-case:

```bash
apply-initializer)
    shift
    exec ./.aitask-scripts/aitask_brainstorm_apply_initializer.sh "$@"
    ;;
```

Place it adjacent to the existing brainstorm sub-cases. Match the indentation style and quoting used by the surrounding cases.

### S6. 5-touchpoint whitelist

Mirror the format of an existing helper entry (e.g., `aitask_archive.sh`) in each file:

| File | Entry |
|------|-------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_brainstorm_apply_initializer.sh:*)"` in `permissions.allow` |
| `seed/claude_settings.local.json` | mirror |
| `.gemini/policies/aitasks-whitelist.toml` | `[[rules]]` block with `commandPrefix = "./.aitask-scripts/aitask_brainstorm_apply_initializer.sh"` (look at any existing block for the exact key set) |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_brainstorm_apply_initializer.sh *": "allow"` |

Codex (`.codex/`, `seed/codex_config.seed.toml`) is intentionally exempt per CLAUDE.md.

### S7. Tests — `tests/test_apply_initializer_tolerant.sh`

Build a tmpdir under `${TMPDIR:-/tmp}/aitask_test_apply_XXXXXX` (use the portable `mktemp` template per CLAUDE.md). Three cases:

1. **Em-dash YAML loads via tolerant fallback.** Build a fixture file with a `NODE_YAML_START..END` block containing the verified-bad em-dash line. Mock `crew_worktree()` (or set up a real synthetic crew dir) so `apply_initializer_output()` resolves to the fixture. Assert: returns successfully; `n000_init.yaml` description matches the agent's intent.

2. **Truly malformed YAML fails AND writes the error log.** Fixture with broken YAML (e.g., unbalanced bracket). Assert: raises; `initializer_bootstrap_apply_error.log` exists with the original parse error.

3. **Well-formed YAML loads normally.** Fixture with already-quoted values. Assert: returns successfully without any error log written.

Each test uses `assert_eq` / `assert_contains` from any neighboring test file.

## Files touched

- `.aitask-scripts/brainstorm/templates/initializer.md` — +YAML-rules subsection (~15 lines)
- `.aitask-scripts/brainstorm/brainstorm_session.py` — +`_tolerant_yaml_load`, +error-log on apply failure (~50 lines)
- `.aitask-scripts/aitask_brainstorm_apply_initializer.sh` — new (~20 lines)
- `ait` — +`apply-initializer` sub-case (~3 lines)
- 5 whitelist files — one entry each
- `tests/test_apply_initializer_tolerant.sh` — new (~80 lines)

## Verification

1. **Unit test:** `bash tests/test_apply_initializer_tolerant.sh` — all PASS.
2. **Whitelist consistency:**
   ```bash
   grep -n "aitask_brainstorm_apply_initializer" \
     .claude/settings.local.json \
     seed/claude_settings.local.json \
     .gemini/policies/aitasks-whitelist.toml \
     seed/geminicli_policies/aitasks-whitelist.toml \
     seed/opencode_config.seed.json
   ```
   Exactly 5 matches.
3. **No-prompt sanity:** invoke `./.aitask-scripts/aitask_brainstorm_apply_initializer.sh nonexistent_session` directly. Should not trigger a permission prompt; should print `APPLY_FAILED:...` to stderr and exit 1.
4. **shellcheck:** `shellcheck .aitask-scripts/aitask_brainstorm_apply_initializer.sh` — clean.
5. **End-to-end on session 635 (manual, after this child lands):**
   ```bash
   ait brainstorm apply-initializer 635
   ```
   Expected: `APPLIED:n000_init`. Then opening `ait brainstorm 635` shows the real proposal — recovers the user's stuck session.

## Notes for sibling tasks

- The persistent banner in t653_1 references the CLI added here. If t653_1 lands first, the banner message points at a not-yet-existing command; the message is still informative and becomes correct once t653_2 lands. No coordination beyond awareness needed.
- t653_3 (push) does not interact with this child's code paths. The two can land in any order.

## Final Implementation Notes

(Filled in at archival time per task-workflow Step 9.)
