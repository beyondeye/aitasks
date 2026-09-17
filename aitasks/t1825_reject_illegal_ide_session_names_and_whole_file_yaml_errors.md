---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tmux]
gates: [risk_evaluated]
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-17 09:11
updated_at: 2026-09-17 09:11
---

## Origin

Spawned from t1811 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_ide.sh:16 — ait ide --session accepts tmux-illegal session names (containing '.' or ':'), which ait setup rejects for the configured value; tmux then fails with a less helpful error`
- `.aitask-scripts/lib/tmux_bootstrap.sh:141 — the line-oriented default_session reader cannot see YAML errors elsewhere in project_config.yaml (an invalid line or non-UTF-8 byte on another line, a NUL byte): load_tmux_defaults falls back to aitasks while the bash reader still returns default_session (the Python twin reports only the encoding case)`

## Diagnostic context

t1811 (code commit `bc97800ee`) made both tmux.default_session line parsers
(`agent_launch_utils.read_default_session_status` and
`tmux_bootstrap.sh::_tmux_bootstrap_default_session_scan` / `_raw`) read a
value only when PyYAML would read back the same string. Otherwise they fall
back to `aitasks` and report a shape: a return value in Python, exit 2 plus a
`DEFAULT_SESSION_UNREADABLE:<shape>:<cfg>` stderr sentinel in bash. The rule is
pinned by `tests/test_tmux_default_session_resolvers.py`: oracle rows, a
28-token tmux header matrix, and a seeded 2000-value corpus asserting "read
like YAML or announced" and bash == Python.

Two adjacent gaps were deliberately left out:

- **`ait ide --session`:**
  - The value is now carried verbatim (printf, so `-n` survives) but is not
    validated.
  - `aitask_setup.sh::setup_tmux_default_session` rejects names containing `.`
    or `:`, because tmux treats them as target separators. `aitask_ide.sh`
    applies no such check to `--session`, so `ait ide --session a.b` reaches
    tmux and fails there.
- **Whole-file YAML validity:**
  - The line-oriented readers classify only the `default_session` line and the
    `tmux` block structure. Examples they cannot see: a malformed line under
    another top-level key, an invalid UTF-8 byte on another line, or a NUL byte
    (bash cannot carry NUL, so the rule excludes it from both twins).
  - In all of those cases `yaml.safe_load` fails and `load_tmux_defaults`
    returns `aitasks`, while the line readers still return the configured name.
    That is a silent divergence between the YAML-backed readers (board,
    monitors, agentcrew) and `ait ide` / registry discovery.
  - The Python twin already reports `encoding` for a non-UTF-8 file, because it
    decodes the whole file (and no longer raises UnicodeDecodeError out of
    discovery). The bash twin does not detect it.

## Suggested fix

- **ide:** reuse setup's `.`/`:` rejection for `--session` (die with the same
  message), and add a row to `tests/test_ide_session_override.sh`.
- **Whole-file validity:** decide whether the line readers should detect file-level
  YAML invalidity (a bash-side UTF-8 check via a portable byte validator plus a
  cheap structural scan) or whether that divergence is accepted and documented.
  If detected, add it to `DEFAULT_SESSION_PROBLEM_SHAPES`, and extend the
  generated corpus with whole-file mutations, keeping the oracle discipline.
