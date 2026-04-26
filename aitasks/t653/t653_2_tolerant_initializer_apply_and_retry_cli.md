---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [agentcrew, ait_brainstorm, whitelists]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-26 14:31
updated_at: 2026-04-26 17:07
---

## Context

Bug at Layer C in the t653 chain (see `aiplans/p653_brainstorm_import_proposal_hangs.md`).

The brainstorm initializer agent's free-text descriptions sometimes contain em-dashes (`—`) followed by a colon — perfectly valid English, invalid YAML. Concrete failure on session 635 (re-confirmed by running `yaml.safe_load` against the on-disk output file):

```
mapping values are not allowed here
  in "<unicode string>", line 28, column 71:
     ... ata/gates.yaml — per-gate config: verifier skill name, type (mac ...
```

`apply_initializer_output()` (`brainstorm_session.py:264`) raises; `_poll_initializer()`'s `try/except` (`brainstorm_app.py:3194-3198`) shows a transient toast and moves on. The 794-line agent output sits on disk, untouched. There is no recovery path — no CLI to retry, no error log on disk, no clear instruction to the user.

This child does three things:
1. **Tighten the prompt** (`initializer.md`) so the agent quotes scalars containing problematic characters in the first place.
2. **Make the parser tolerant** — on `yaml.YAMLError`, run a regex pass that quotes the offending values and retry. If still failing, write a clear error log on disk.
3. **Add a retry CLI** — `ait brainstorm apply-initializer <session>` so the user can re-run apply manually after fixing the output (or after t653_1's auto-retry timer dropped the file).

## Key Files to Modify

- `.aitask-scripts/brainstorm/templates/initializer.md` — strengthen Phase 4 with a "YAML rules" subsection and a bad/good example
- `.aitask-scripts/brainstorm/brainstorm_session.py` — replace `yaml.safe_load(node_yaml_text)` with a new `_tolerant_yaml_load()`; add error-log-on-disk on permanent failure
- **NEW:** `.aitask-scripts/aitask_brainstorm_apply_initializer.sh` — helper script
- `ait` dispatcher — wire `ait brainstorm apply-initializer <session>` (find via `grep -n "brainstorm" ait`)
- **NEW:** `tests/test_apply_initializer_tolerant.sh`

### 5-touchpoint whitelist (mandatory, per CLAUDE.md "Adding a New Helper Script"):

| Touchpoint | Entry |
|-----------|-------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_brainstorm_apply_initializer.sh:*)"` in `permissions.allow` |
| `.gemini/policies/aitasks-whitelist.toml` | `[[rule]]` block with `commandPrefix = "./.aitask-scripts/aitask_brainstorm_apply_initializer.sh"` |
| `seed/claude_settings.local.json` | mirror of the runtime entry |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of the runtime gemini policy |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_brainstorm_apply_initializer.sh *": "allow"` |

Codex is exempt (prompt/forbidden-only model — no allow decision exists).

## Reference Files for Patterns

- `apply_initializer_output()` at `brainstorm_session.py:264-305` — current strict-load implementation
- `_extract_block()` in the same file — block-delimiter parser; reusable as-is
- Any sibling helper script in `.aitask-scripts/` that calls Python via `python3 -c "from brainstorm.brainstorm_session import …"` for the import path pattern
- `aitask_crew_addwork.sh` — example of an `ait` subcommand helper that resolves a crew/session arg
- For the dispatcher-wire pattern, look at how existing `ait brainstorm <subcmd>` cases are routed in `ait` (e.g. the dashboard subcommand)

## Pseudo-verb / coordination note

t650_2 (sibling task on parent t650) is rewriting Phase 4's pseudo-verb lines. Coordinate by **appending** the new "YAML rules" subsection to the end of Phase 4 (before the existing `### Checkpoint 4` block). The diffs do not collide.

## Implementation Plan

### 1. Tighten `initializer.md` Phase 4

Append a `### YAML rules` subsection inside `## Phase 4: Write Output`:

```markdown
### YAML rules for the NODE_YAML block

Every scalar value MUST be double-quoted when it contains any of:
  - em-dash (`—`) or en-dash (`–`)
  - hyphen-space (` - `)
  - a second `:` (the YAML key separator must be the only colon-space on the line)
  - `#` (which YAML treats as the start of a comment)

Bad (will fail to parse):
```yaml
component_gate_registry: aitasks/metadata/gates.yaml — per-gate config: verifier skill name
```

Good:
```yaml
component_gate_registry: "aitasks/metadata/gates.yaml — per-gate config: verifier skill name"
```

When in doubt, double-quote the value.
```

### 2. Add `_tolerant_yaml_load()` to `brainstorm_session.py`

```python
import re
import yaml

_PROBLEM_VALUE_RE = re.compile(
    r'^(\s*[A-Za-z_][\w]*:\s+)((?!["\']).+?)\s*$'
)
_PROBLEM_CHARS_RE = re.compile(r'(—|–| - |#|: )')

def _tolerant_yaml_load(text: str) -> dict:
    """yaml.safe_load with a one-shot quote-the-bad-values fallback.

    On YAMLError, walk lines whose value (after the first ': ') contains an
    em-dash, en-dash, hyphen-space, '#', or a second ': ', and is not already
    quoted. Wrap such values in double quotes (escaping any embedded ").
    Retry. Raise the original error if the fixed text still fails to parse.
    """
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as orig_err:
        fixed_lines = []
        for line in text.splitlines():
            m = _PROBLEM_VALUE_RE.match(line)
            if m and _PROBLEM_CHARS_RE.search(m.group(2)):
                value = m.group(2).replace('\\', '\\\\').replace('"', '\\"')
                fixed_lines.append(f'{m.group(1)}"{value}"')
            else:
                fixed_lines.append(line)
        fixed_text = "\n".join(fixed_lines)
        try:
            return yaml.safe_load(fixed_text)
        except yaml.YAMLError:
            raise orig_err  # surface the ORIGINAL error to the caller
```

### 3. Wire into `apply_initializer_output()`

Replace `node_data = yaml.safe_load(node_yaml_text)` with `node_data = _tolerant_yaml_load(node_yaml_text)`. If parsing still fails, write an error log before re-raising:

```python
err_log = wt / "initializer_bootstrap_apply_error.log"
err_log.write_text(
    f"apply_initializer_output failed at {now_utc()}\n\n"
    f"Original YAML parse error:\n{exc}\n\n"
    f"NODE_YAML block follows (first 2000 chars):\n{node_yaml_text[:2000]}\n",
    encoding="utf-8",
)
```

Implementation detail: wrap the parse call in try/except, write the log, then `raise`.

### 4. New helper `aitask_brainstorm_apply_initializer.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="${1:-}"
[[ -z "$SESSION" ]] && { echo "Usage: $0 <session>" >&2; exit 2; }

# Resolve session number (accept "635" or "brainstorm-635")
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

Make executable: `chmod +x .aitask-scripts/aitask_brainstorm_apply_initializer.sh`.

### 5. Wire `ait brainstorm apply-initializer <session>`

Locate the brainstorm dispatch in the top-level `ait` script (grep for `brainstorm`). Add a new case before the catch-all:

```bash
apply-initializer)
    shift
    exec ./.aitask-scripts/aitask_brainstorm_apply_initializer.sh "$@"
    ;;
```

(Adapt to the existing dispatch style — the file uses bash case statements.)

### 6. 5-touchpoint whitelist (mandatory)

Add the entries listed in the table above. Mirror the format of an adjacent existing helper (e.g., `aitask_archive.sh` or `aitask_create.sh`) in each file.

### 7. Tests — `tests/test_apply_initializer_tolerant.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
# Test 1: em-dash YAML loads via tolerant fallback
# Test 2: truly-malformed YAML fails AND writes the error log
# Test 3: well-formed YAML loads normally (no fallback)
```

Build a temporary synthetic session under `/tmp/`, mock `crew_worktree()` to point at it, run the apply, assert outputs.

## Verification Steps

1. **Unit test:** `bash tests/test_apply_initializer_tolerant.sh` → all PASS.

2. **Whitelist consistency check:**
   ```bash
   grep -n "aitask_brainstorm_apply_initializer" \
     .claude/settings.local.json \
     seed/claude_settings.local.json \
     .gemini/policies/aitasks-whitelist.toml \
     seed/geminicli_policies/aitasks-whitelist.toml \
     seed/opencode_config.seed.json
   ```
   Expect five matches, one per file.

3. **No-prompt sanity:** invoke `./.aitask-scripts/aitask_brainstorm_apply_initializer.sh nonexistent_session` in this very Claude Code session. Should run without a permission prompt.

4. **End-to-end on session 635 (manual):** after this child lands, run `ait brainstorm apply-initializer 635`. Expected: `APPLIED:n000_init`. Then open `ait brainstorm 635` and confirm n000_init shows the real description and proposal — recovering the user's actual stuck session.

5. **shellcheck:** `shellcheck .aitask-scripts/aitask_brainstorm_apply_initializer.sh` → clean.

## Out of scope (intentionally)

- TUI changes — owned by sibling t653_1.
- Status / transition / push changes — owned by sibling t653_3.
- Agent heartbeat fixes — owned by parent t650.
- Multi-language YAML auto-fix (we only quote scalars on the same line as the key; we do not try to rewrite block scalars or flow sequences).
