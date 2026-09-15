---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [tmux]
gates: [risk_evaluated]
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-15 09:14
updated_at: 2026-09-15 09:14
---

## Origin

Spawned from t1800 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_ide.sh:52 — echo "$SESSION_OVERRIDE" swallows an option-like --session value (e.g. --session -n), so ait ide resolves an empty session name; needs printf plus a test seam (the script runs the IDE at top level)`
- `.aitask-scripts/aitask_setup.sh:4140 — setup_tmux_default_session's "already configured?" probe (grep | sed) treats a null, comment-only or quoted-empty default_session (# note, "", null, ~) as configured, prints e.g. "already configured: # note" and skips the prompt`
- `.aitask-scripts/lib/agent_launch_utils.py:747 / .aitask-scripts/lib/tmux_bootstrap.sh:68 — the line parsers cannot read YAML-only default_session shapes that load_tmux_defaults accepts: a flow mapping resolves to aitasks, a block scalar (>- or |) to its literal indicator (ait ide would name its session '>-'), a typed scalar (yes, 0123) to its source text instead of True/83`

## Diagnostic context

t1800 (code commit `d146a440c`) made the four tmux session-name resolvers agree
on blank, null and commented `tmux.default_session`: `load_tmux_defaults`, both
monitors' `main()` (now reading through it), `_read_default_session` and the
bash `_tmux_bootstrap_resolve_session`. Its contract is pinned by
`tests/test_tmux_default_session_resolvers.py`. Three adjacent defects were left
out of that contract on purpose:

- **`ait ide --session <name>`.** `aitask_ide.sh:16` accepts the value
  (`SESSION_OVERRIDE="${2:-}"`), and `:52` prints it with `echo`.
  - Measured: bash's builtin `echo` prints nothing for `-n`, `-e`, `-E` and
    `-neE`; `printf '%s\n'` preserves all four. t1800 applied the `printf` fix
    to `_tmux_bootstrap_resolve_session` only.
  - The override never reads `tmux.default_session`, and the script runs the
    IDE at top level, so there is no test seam. That is why it was split out.
- **The setup probe** never resolves a session name; it only decides whether
  to offer an optional prompt (default `aitasks`). After t1800 every resolver
  reads the skipped-prompt blank value as `aitasks`, so no launch path diverges.
  Only the message and the skipped prompt are wrong.
- **YAML-only shapes.** `LegacyYamlFormsPreservedTests` pins the YAML-backed
  side (`flowsess`, `blocksess`, `blocksess\n`, `True`, `83`), and deliberately
  does **not** assert the line parsers on those rows, so this fix will not be
  mistaken for a regression. A companion test requires every legacy row to be
  a shape the line parsers cannot read.

## Suggested fix

- **ide override:** `printf '%s\n' "$SESSION_OVERRIDE"`, plus a test seam. For
  example, move `resolve_session` into `lib/tmux_bootstrap.sh`, or guard the
  top-level run. Then add a committed test for `--session -n`.
- **setup probe:** decide "configured" with the same scalar rule the resolvers
  use (e.g. a raw-value helper in `tmux_bootstrap.sh` that prints empty for
  blank/null/comment-only) instead of `grep | sed`.
- **YAML-only shapes:** either support them in both line parsers or warn and
  fall back explicitly. Once decided, add line-parser assertions to
  `LegacyYamlFormsPreservedTests`, keeping the parity matrix's oracle
  discipline.
