# Aitasks Extension Points

Specialist guidance for extending the aitasks framework: adding a new task
frontmatter field, adding a new `.aitask-scripts/` helper, modifying the
install flow, fixing OS-specific bugs symmetrically, or touching the
framework's PATH / binary shim.

## Adding a new frontmatter field

A new task frontmatter field must touch the layers below, or the board (or a
cross-PC sync) silently drops or mangles it:

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
4. **Sync/merge rule:** `board/aitask_merge.py` `merge_frontmatter()`. A field
   with no explicit rule falls into the generic `else` and can be dropped to the
   unresolved/PARTIAL path on a concurrent edit. Add a branch: list fields go in
   `_LIST_UNION_FIELDS` (union), per-checkout **board-layout** fields in
   `BOARD_LAYOUT_KEYS` (from which `_KEEP_LOCAL_FIELDS` is derived), and a scalar
   that must survive concurrent edits gets a newer-`updated_at`-wins branch
   (mirror `updated_at` / `anchor`). Keep a semantic scalar OUT of
   `_LIST_UNION_FIELDS` / `BOARD_LAYOUT_KEYS`.
4b. **Board save path (board-owned fields only):** `Task.reload_and_save_board_fields`
   in `board/aitask_board.py` takes a **required** `fields` set and persists only
   what the caller names — so no key is ever written back by a move that did not
   name it, whichever set it is in. A new board key goes in `BOARD_KEYS` (making
   it nameable and validated) but **not** in `BOARD_LAYOUT_KEYS` unless it is
   per-checkout layout. `BOARD_LAYOUT_KEYS` membership carries two policies a
   shared key must not inherit: its merge conflicts resolve **silently
   local-wins** (via `_KEEP_LOCAL_FIELDS`, layer 4), and writes naming only those
   keys are treated as layout so they **do not record `updated_at`**. Naming a
   non-layout key is what makes a write semantic. Guarded by
   `tests/test_board_persistence_seam.py`.
5. **Documentation surfaces:** the field's existence + meaning is enumerated in
   several places that drift independently — update **all** of them:
   - `seed/aitasks_agent_instructions.seed.md` "## Task File Format" YAML block,
     then regenerate the **AGENTS.md** mirror via the `ait setup` path
     (`update_agentsmd`, which uses the `>>>aitasks` markers). The
     `.codex/instructions.md` / `.opencode/instructions.md` mirrors currently use
     a markerless full-file format and are updated by hand to match the seed (do
     not run `insert_aitasks_instructions` on them — lacking the markers it
     appends a duplicate block).
   - `CLAUDE.md` "### Task File Format" YAML block (hand-maintained — it has no
     `>>>aitasks` markers; edit directly).
   - `website/content/docs/development/task-format.md` "### Frontmatter Fields"
     table.
   - The canonical creation contract
     `.claude/skills/task-workflow/task-creation-batch.md` (Input table + prose)
     and the inline flag list in `.claude/skills/aitask-create/SKILL.md` — define
     semantics once in the canonical contract; other surfaces point to it.
   - This checklist, and (when the board renders the field) the board
     `tuis/board/reference.md` row.

When splitting a plan that introduces a new field, surface any missing layer
as its own child task.

**Worked example — `anchor` (t1016):** a scalar topic-group key. Write path =
`--anchor` / `--followup-of` in `aitask_create.sh` + editable `--anchor` in
`aitask_update.sh` (shared `normalize_anchor_id` in `lib/task_utils.sh`); fold =
no-op comment in `aitask_fold_mark.sh` (scalar, primary wins); merge =
newer-wins scalar branch (NOT in `_LIST_UNION_FIELDS`/`BOARD_KEYS`); docs =
every surface in layer 5 above. (Board layer 3 + reference row ship separately.)

**Worked example — `boardgroup` (t1243_8):** the first **shared** board key
(in-column group membership, keyed by slug). It shows the two ways a board key
differs from an ordinary scalar:

- **Layer 4b:** added to `BOARD_KEYS` but deliberately **not** to
  `BOARD_LAYOUT_KEYS`, so it inherits neither silent local-wins nor
  timestamp-neutral writes.
- **Layer 4:** it needed a merge rule of its own, because *neither* generic rule
  can decide shared membership. One-sided presence resolves first and
  unconditionally, so a side that CLEARS the field loses to a side still
  carrying it — membership resurrects on sync. And `updated_at` is task-wide and
  minute-resolution, so an unrelated edit on a stale checkout wins a field it
  never touched. The rule is therefore **base-aware change detection**
  (`_BASE_AWARE_FIELDS`), resolved in a pre-loop block ahead of the one-sided
  branch, with the merge base read from **git's conflicted index** (stage 1) and
  passed by `aitask_sync.sh` as `--base-file`. It fails closed to PARTIAL when
  both sides changed it differently or no base exists. *The diff3 marker base is
  not a usable source: `merge.conflictStyle` is configured nowhere, so git emits
  2-way markers and the parser has no ancestor to read.*
- **Deletion needs a value, not an absence:** clearing writes the `""`
  **tombstone** rather than removing the key (omit ≠ clear). Note
  `write_task_file` skips empty board fields, and a bare `echo "key: $v"` emits
  `key: ` which the YAML loader reads back as `None` — so the tombstone is
  written as the quoted literal and carries a `_PRESENT` flag.
- **Persisted values are not trusted:** every consumer reads through
  `lib/board_groups.normalize_group_slug`, because a hand edit or another
  checkout can legally supply `None`, a list (unhashable — it would crash a
  keyed derivation), an int or a bool.
- Write path = `--boardgroup` in `aitask_update.sh` **only** (update-only,
  mirroring `--boardidx`, which `aitask_create.sh` also lacks); fold = no-op
  comment (scalar, primary wins); docs = layer 5 + the `sync.md` merge-rules
  table. (Board layer 3 `BoardGroupField` ships separately in t1243_12.)

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

**This whitelist applies ONLY to helpers invoked from a skill.** A helper whose
only callers are Python TUIs (via `subprocess.run([...])`), other
`.aitask-scripts/` shell scripts (via `"$SCRIPTS_DIR/foo.sh"`), or manual shell
invocation runs under the user's normal process — no sandbox approval is
involved, so adding allow-list entries for it is dead weight that pollutes the
policy files and falsely advertises a skill-facing surface. Whitelist only when
the script's path appears (literally or via `ait <subcommand>` dispatch) inside
a `*/SKILL.md` closure, or inside a helper that such a skill invokes. Example:
`aitask_skill_invalidate.sh` is run only by Python save-hooks (Settings TUI /
AgentCommandScreen), so it needs zero whitelist entries.

## The `ait` dispatcher is user-facing only

The `ait` dispatcher (`./ait`) is the user-facing CLI surface. Only add a new
top-level `ait <name>` case when a real human would plausibly type that command
at a shell prompt. Helpers that exist solely to be shelled out from other
scripts, Python TUIs, or hooks stay invoked via their full path
(`./.aitask-scripts/aitask_<name>.sh …`) — wrapping them in `ait <foo>` adds
zero capability, clutters `ait --help`, leaks implementation detail, and tempts
accidental manual misuse. When in doubt, default to "no dispatcher entry":
adding the case later is trivial, removing it is a breaking change. Example:
`aitask_skill_invalidate.sh` was planned with an `ait skill invalidate` surface;
that was rejected because only Python save-hooks call it, and the final design
has no dispatcher entry.

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

## Framework constants live in source, not `project_config.yaml`

When adding a lookup table the framework consults at runtime (known TUI window
names, code-agent window prefixes, agent prompt-pattern regexes, similar
enumerations), put it in a Python module under the relevant `.aitask-scripts/`
subdirectory — NOT in `aitasks/metadata/project_config.yaml`. That YAML is a
user-facing config surface; framework constants are not user choices — they
evolve with the framework. Adding a YAML key for every internal table bloats the
config surface, creates a migration burden across downstream repos, and invites
stale overrides. The agent-prefix / prompt-pattern tables under
`.aitask-scripts/monitor/` set the precedent. Only add a YAML surface when the
user *explicitly* asks for that specific item to be user-configurable. For
multi-category lists (e.g. prompt patterns per code-agent), organize the module
by category (one dict keyed by `claude` / `codex` / `opencode` / `all`) even if
today every category merges into one flat list — the per-category shape is cheap
and pays off when differentiation lands.
