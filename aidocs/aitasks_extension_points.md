# Aitasks Extension Points

Specialist guidance for extending the aitasks framework: adding a new task
frontmatter field, adding a new `.aitask-scripts/` helper, modifying the
install flow, fixing OS-specific bugs symmetrically, or touching the
framework's PATH / binary shim.

## Adding a new frontmatter field

A new task frontmatter field must touch three layers, or the board silently
drops it:

1. **Write path:** `aitask_create.sh` (batch flags + interactive flow +
   `create_task_file` serialization) and `aitask_update.sh` (mirroring
   add/remove flags).
2. **Fold machinery:** `aitask_fold_mark.sh` — union folded tasks' values into
   the primary if the field is a list. `aitask_fold_content.sh` only merges
   body text; frontmatter lists are lost unless `fold_mark` is extended.
3. **Board TUI:** `aitask_board.py` `TaskDetailScreen.compose()` renders
   per-field widgets keyed on field name. Add a `<FieldName>Field` class
   mirroring `DependsField` / `ChildrenField`, wire it into `compose()`, and
   have it shell out to `aitask_update.sh --batch ... --<flag>`.

When splitting a plan that introduces a new field, surface any missing layer
as its own child task.

## Adding a new helper script

Any new script under `.aitask-scripts/` invoked by a skill must be allowlisted
for every code agent's permission system — **both runtime configs (this
project) AND seed configs (new projects bootstrapped via `ait setup`)**.
Missing any touchpoint causes users of the corresponding agent to be prompted
on every invocation.

| Touchpoint | Entry shape |
|-----------|------------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/<name>.sh:*)"` in `permissions.allow` |
| `.codex/rules/default.rules` | `prefix_rule(pattern = ["./.aitask-scripts/<name>.sh"], decision = "allow", ...)` |
| `seed/claude_settings.local.json` | mirror of `.claude/settings.local.json` entry |
| `seed/codex_rules.default.rules` | mirror of runtime Codex rules |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/<name>.sh *": "allow"` |

Codex command allow rules live in `.rules` files, not `.codex/config.toml`.
The feature is experimental in Codex CLI, so keep the rules format aligned
with the current OpenAI Codex Rules documentation.

When splitting a plan that introduces one or more new helper scripts, surface
this 7-touchpoint checklist as an explicit deliverable per helper.

## Test the full install flow for setup helpers

When adding or modifying helpers in `.aitask-scripts/aitask_setup.sh` that
touch `aitasks/metadata/project_config.yaml` (or any file expected to be in
place by prior install steps), the test harness must simulate the full
`install.sh → ait setup` flow in a scratch dir, not just feed a hand-crafted
seed to the helper in isolation.

`install.sh` deletes `seed/` at the end of install. A helper that reads from
`$project_dir/seed/...` will silently fail in a fresh user install even if it
passes when tested against a hand-copied seed file.

How to apply:
- For any setup-flow change, run `bash install.sh --dir /tmp/scratchXY` (or
  equivalent) into a fresh scratch dir, THEN run the new helper/flow, THEN
  grep/cat the expected output file to confirm. Do not stop at helper-level
  unit tests.
- When adding a helper that reads from `aitasks/metadata/X`, grep `install.sh`
  for `install_seed_X` or similar — if there isn't one, the helper will fail
  on fresh installs even if it passes isolated tests.

## Cross-platform audit for platform-specific bugs

When fixing a bug on one OS branch (e.g., a Linux-only `_install_pypy_linux`
failure), audit the parallel function on the other platform
(`_install_pypy_macos`) for the same bug class before finalizing the task
scope: hardcoded literals where a constant exists, missing layout symmetry,
same single-source-of-truth violations.

If the symmetric path has same-family issues, fold them into the same task (a
single coherent fix is better than two staggered ones); name a manual-
verification follow-up for the platform you can't test from your dev box.

Skip this only when the bug is genuinely OS-specific (kernel API quirk,
sandbox restriction) with no analog on the other platform.

## No global PATH override for framework-internal binaries

Do NOT append framework-internal directories (e.g., `~/.aitask/bin`) to the
user's interactive shell rc (`~/.zshrc` / `~/.bashrc` / `~/.profile`). That
globally overrides system tools (like `python3`) for every program the user
runs, not just aitasks subprocesses, and risks silent breakage of the user's
unrelated workflows.

Instead, ship a sourced lib (e.g., `.aitask-scripts/lib/aitask_path.sh`) that
exports `PATH="$HOME/.aitask/bin:$PATH"` idempotently, and source it from the
`ait` dispatcher and from every `.aitask-scripts/aitask_*.sh` that may invoke
the framework binary (covers skill-direct calls bypassing the dispatcher).

The exception is `~/.local/bin` — `ensure_path_in_profile()` correctly manages
only that directory because the global `ait` entry-point shim is meant to be
user-invocable.
