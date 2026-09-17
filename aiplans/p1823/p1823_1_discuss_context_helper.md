---
Task: t1823_1_discuss_context_helper.md
Parent Task: aitasks/t1823_brainstorm_discuss_proposals_interactive_agent.md
Sibling Tasks: aitasks/t1823/t1823_2_*.md, aitasks/t1823/t1823_3_*.md, aitasks/t1823/t1823_4_*.md, aitasks/t1823/t1823_5_*.md
Archived Sibling Plans: aiplans/archived/p1823/p1823_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-17 11:36
---

# t1823_1 — Discuss context helper (read-only id → path resolver)

## Context

The `aitask-brainstorm-discuss` skill (t1823_2) receives only ids on argv
(`<task_num> <node_id>...`) and must self-fetch paths. No existing CLI emits a
brainstorm session path or node proposal paths (`ait brainstorm status` prints
counts only; `init` creates a session). This child adds the read-only resolver,
in the mould of `aitask_shadow_context.sh`: `KEY:value` lines, **exit 0 on every
resolution outcome**, malformed id is the one hard error.

Parent plan: `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.

## Verification notes (2026-09-17, against current main)

All referenced APIs confirmed: `crew_worktree` (`brainstorm_session.py:54`),
`load_session` (:201), `session_exists` (:218), `file_for_ref`/`OpDataRef`
(`brainstorm_op_refs.py:33-57`), `read_node` (:88), `list_nodes` (:102),
`get_parents` (:208), `_node_module` (:390), `get_node_lineage` (:435),
`lib/python_resolve.sh` `require_ait_python`, `aitask_audit_wrappers.sh`
`apply-helper-whitelist` / `audit-helper-whitelist`. Three gaps the original plan
did not cover, now folded into the steps:

1. `AGENTCREW_DIR = ".aitask-crews"` is **cwd-relative**
   (`agentcrew_utils.py:57`), so the helper would resolve nothing when invoked
   from a subdirectory. The wrapper `cd`s to the repo root (`$SCRIPT_DIR/..`)
   before exec, so every emitted path is repo-relative and cwd-independent.
2. `read_yaml` raises `FileNotFoundError` on a missing file, and `_node_module`
   / `get_parents` go through it — every per-node read in the CLI is guarded,
   not only the BFS.
3. A crew dir can exist without `br_session.yaml` (crew created, session not
   initialized). `SESSION_PATH` is emitted as found only when `session_exists()`
   is true; otherwise `SESSION_PATH:NOT_FOUND` and stop.

### Review findings folded in (user review, all three verified)

4. **Graph-derived ids reach the filesystem unvalidated.** `read_node`
   (`brainstorm_dag.py:88-91`) and `file_for_ref` build paths straight from the
   id, and `parents` values come from YAML (`brainstorm_schemas.py:115` checks
   only that it is a list). A parent `../../../x` would make the BFS read — and
   the CLI emit — paths outside the session. Fix: **one id validator applied to
   every id before any filesystem access**, argv-derived or graph-derived.
5. **`yaml` is not imported in `brainstorm_dag.py`** (imports at :12-20 are
   `os, sys, deque, datetime, Path, read_yaml/write_yaml`), so
   `except yaml.YAMLError` would raise `NameError` exactly on the error path.
   Fix: `import yaml` explicitly; the error path is exercised by tests.
6. **Unescaped YAML-derived values in a delimited grammar.** `module_label`,
   parent ids and `task_file` are unconstrained by the schema, so a `|`, `,` or
   newline could forge fields or whole records. Fix: a **constrained encoding** —
   no raw YAML-derived value is ever emitted; every field is either a value
   matching its field charset or a sentinel that the charset cannot produce
   (below). Real sessions are unaffected: all current node ids are
   `n###_agent`, and every `task_file` in `.aitask-crews/*/br_session.yaml`
   is a plain `aitasks/t<N>_<slug>.md`.

### Second review round (both verified)

7. **Missing imports.** `brainstorm_dag.py` has no `import re` (needed by
   `SAFE_NODE_ID_RE`), and `brainstorm_cli.py` imports only
   `argparse, os, sys, Path` (:9-12) — no `re` (path/task-file regexes) and no
   `yaml` (its `except yaml.YAMLError`). Fix: add `import re` + `import yaml`
   to `brainstorm_dag.py`, and `import re` + `import yaml` to
   `brainstorm_cli.py`; each error path is hit by a focused test (a module
   import alone proves `re`; the malformed-YAML session/node tests prove
   `yaml`).
8. **`TASK_FILE` needs an allowlist, not just a safe-path check.** A corrupt
   `task_file: .git/config` is safe, relative and exists. The value is written
   only by `aitask_brainstorm_init.sh:92-99` from
   `aitask_query_files.sh resolve <N>`, so its sole legitimate shape is the
   task's own file. Fix: accept only
   `^aitasks/t<N>_[A-Za-z0-9_-]+\.md$` (parent `<N>`), or
   `^aitasks/t<P>/t<P>_<C>_[A-Za-z0-9_-]+\.md$` when `<N>` is `<P>_<C>`, with
   `<N>`/`<P>`/`<C>` inserted via `re.escape` — checked **before** any
   `is_file()`. Anything else → `TASK_FILE:INVALID`. Correspondingly the
   task-num argv validator is tightened to `^[0-9]+(_[0-9]+)?$` (the task-number
   shape `resolve` accepts); node ids keep `SAFE_NODE_ID_RE`.

## Output grammar (the contract t1823_2 parses)

```
SESSION_PATH:<path>|NOT_FOUND
TASK_FILE:<path>|NOT_FOUND|INVALID
NODE:<id>|PROPOSAL:<path>|META:<path>|PARENTS:<tokens>
ANCESTOR:<node>|<token>|DEPTH:<n>|MODULE:<token>|PARENTS:<tokens>|PROPOSAL:<path>   # --lineage only
```

- **id / token field** — either an id matching `SAFE_ID` =
  `^[A-Za-z0-9_.-]+$` and not `.`/`..`, or a `!`-prefixed sentinel:
  `!INVALID` (value present but fails `SAFE_ID`, or is not a string) /
  `!MISSING` (value unknowable because the owning YAML is missing or
  unreadable; used for `MODULE`). `!` is outside `SAFE_ID`, so a node literally
  named `INVALID` can never be confused with a sentinel.
- **`<tokens>`** — comma-joined tokens (possibly empty). Tokens cannot contain
  `,` or `|`.
- **`TASK_FILE`** — additionally restricted to the task's own file shape
  (`aitasks/t<N>_<slug>.md`, or `aitasks/t<P>/t<P>_<C>_<slug>.md`); any other
  value is `INVALID`, even if it is a safe, existing path.
- **path field** — a repo-relative path matching `^[A-Za-z0-9_./-]+$` with no
  leading `/` and no `..` segment, or `NOT_FOUND` / `INVALID`. Every real path
  contains `/`; the sentinels do not, so they are unambiguous. `PROPOSAL` /
  `META` are always built from a `SAFE_ID` id, so they are `path|NOT_FOUND`.
- No field can contain `|`, `,` (except as the token separator) or a newline:
  every line is exactly one record with a fixed field count.
- `<node>` on an ANCESTOR line is the requested (argv-validated) node id.

## Steps

1. **`brainstorm_dag.py`**
   - add `import re` and `import yaml` (explicit, alongside the existing imports).
   - add public `SAFE_NODE_ID_RE = re.compile(r"[A-Za-z0-9_.-]+")` and
     `is_safe_node_id(value) -> bool` (`isinstance(value, str)`, fullmatch, not
     `.`/`..`). Single source for the CLI and the BFS.
   - add `_read_parents_safe(session_path, node_id) -> list | None`: returns
     `None` without touching the filesystem if `not is_safe_node_id(node_id)`;
     `try: data = read_node(...) except (OSError, ValueError, yaml.YAMLError):
     return None`; a non-list `parents` → `[]`; else the raw list (entries not
     yet validated — the caller decides).
   - **`get_node_ancestors(session_path, node_id) -> list[tuple[object, int]]`**
     (right after `get_node_lineage`). Do NOT reuse `get_node_lineage`
     (first-parent walk, confined to one module). BFS over **all** parents,
     crossing module boundaries:
     - `visited` keyed on the raw value (unhashable entries, e.g. a dict in YAML,
       are keyed by `repr`); a parent is emitted/queued only if unseen → diamond
       ancestors once at shortest depth; cycles (incl. back to the start) end;
     - an **unsafe** parent is emitted as an ancestor but **never traversed and
       never read** — its path is never constructed;
     - a safe parent whose YAML is missing/malformed is emitted, traversal stops
       there;
     - result sorted by `(depth, str(id))`, start node excluded.
     `get_node_lineage` and its callers stay untouched.

2. **`brainstorm_cli.py` — `paths` subcommand**: `--task-num N`, `--lineage`,
   positional `node_ids` (`nargs="*"`). Add `import re` and `import yaml` to
   the module imports. `cmd_paths`:
   - Validate `N` with `^[0-9]+(_[0-9]+)?$` and each argv node id with
     `is_safe_node_id`; on failure print
     `Error: invalid <what>` to stderr (value `repr`-escaped) and `sys.exit(2)`,
     before any stdout output.
   - Local encoders — the **only** way a value reaches stdout:
     `_tok(v)` → `v` if `is_safe_node_id(v)` else `!INVALID`;
     `_tokens(list|None)` → `,`.join of `_tok` (empty for `None`);
     `_path(p)` → `str(p)` if it matches the path charset, is relative and has no
     `..` part, else `INVALID`.
   - `if not session_exists(N)`: print `SESSION_PATH:NOT_FOUND`, return (exit 0).
   - `session = crew_worktree(N)`; print `SESSION_PATH:<_path(session)>`.
   - `TASK_FILE:` — `load_session(N).get("task_file")` guarded
     (`OSError, ValueError, yaml.YAMLError`); non-string, or not matching the
     **task-file allowlist** for `N` (finding 8) → `INVALID` (checked **before**
     `is_file()`, so no disallowed path is stat'ed); allowed and `is_file()` →
     the path; allowed but absent (e.g. task since archived) → `NOT_FOUND`.
     An unreadable/malformed `br_session.yaml` → `TASK_FILE:NOT_FOUND`
     (session path still emitted, nodes still resolved).
   - node ids empty → `list_nodes(session)`, each filtered through
     `is_safe_node_id` (a stray `br_nodes/` filename with odd chars is skipped,
     never emitted).
   - per node: `NODE:<id>|PROPOSAL:<p|NOT_FOUND>|META:<p|NOT_FOUND>|PARENTS:<_tokens>`
     via `file_for_ref(session, OpDataRef("node_proposal"|"node_metadata", id))`
     + `is_file()`.
   - `--lineage`: after each node's `NODE:` line, per `get_node_ancestors` entry:
     unsafe ancestor → `ANCESTOR:<node>|!INVALID|DEPTH:<n>|MODULE:!MISSING|PARENTS:|PROPOSAL:NOT_FOUND`;
     safe ancestor → `MODULE:` from its YAML `module_label` (absent/empty →
     `_umbrella`; present but unsafe → `!INVALID`; YAML unreadable → `!MISSING`),
     `PARENTS:<_tokens>`, `PROPOSAL:<p|NOT_FOUND>`. One node read per ancestor
     (read the YAML once, derive module + parents from it; do not call
     `_node_module`, which would re-read unguarded).
   - Never writes. Update the module docstring's subcommand list.

3. **`.aitask-scripts/aitask_brainstorm_context.sh`** (new, executable) —
   header comment documenting usage + output grammar (as shadow's does);
   `#!/usr/bin/env bash`, `set -euo pipefail`; source `lib/aitask_path.sh`,
   `lib/python_resolve.sh`, `lib/terminal_compat.sh` (same trio as
   `aitask_brainstorm_status.sh`); `-h/--help`; parse `--lineage` anywhere,
   first positional = task_num (required, else usage + die), rest = node ids;
   `PYTHON="$(require_ait_python)"`; `cd "$SCRIPT_DIR/.."`;
   `exec "$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" paths --task-num "$task_num" ${lineage flag} -- "${node_ids[@]}"`
   (guard the empty-array expansion for bash 3.2). Validation stays in Python
   (single source). No `ait` dispatcher entry.

4. **Permission touchpoints (5)**:
   `./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_brainstorm_context.sh`
   then `audit-helper-whitelist aitask_brainstorm_context.sh` → no `MISSING:`.
   Mirror the entry into `aitasks/metadata/opencode_config.seed.json` next to
   the shadow_context entry (commit that one via `aitask_task_commit.sh`, by path,
   separately from code).

5. **Tests**
   - `tests/test_brainstorm_node_ancestors.py` (reuse the `BrainstormTestBase`
     AGENTCREW_DIR-patching pattern from `tests/test_brainstorm_dag.py`, defined
     locally — no cross-test import): multi-parent synthesis (both branches
     present; `get_node_lineage` on the same fixture omits branch `b` —
     control); module-boundary ancestry (umbrella ancestors present,
     `_node_module` differs); diamond de-dup at shortest depth; hand-written
     cycle terminates; missing-parent YAML tolerated; **malformed-YAML parent**
     (unparseable file → emitted, not traversed, no `NameError` — the red proof
     for finding 5); start node excluded; order `(depth, id)`.
     **Traversal safety:** a node whose `parents` holds `../outside/n9`, with a
     *valid* YAML planted at that traversal target listing a parent `canary`:
     `../outside/n9` is returned (depth 1) but `canary` is **not** — the negative
     control proving the unsafe id was never read. Also `is_safe_node_id` table
     (`.`, `..`, `a/b`, `a|b`, `a,b`, `a\nb`, `""`, `1` (int), `None` → false;
     `n001_explorer` → true).
   - `tests/test_brainstorm_context_helper.sh`: fixture = tmp dir with copies of
     `.aitask-scripts/{aitask_brainstorm_context.sh, lib/, brainstorm/*.py,
     agentcrew/agentcrew_utils.py}`, session built by a python snippet calling
     `init_session` + `create_node` (with cwd = fixture root). Cases: found node
     (paths exist), unknown node (`PROPOSAL:NOT_FOUND`, exit 0), missing session
     (exit 0, only `SESSION_PATH:NOT_FOUND`), all-nodes listing, `--lineage` on a
     synthesis node lists both branches, invocation from a subdirectory still
     resolves, malformed id and `../x` and bad task num (exit 2),
     **delimiter-bearing fixture** (hand-written node YAML with
     `parents: ["a|b", "c,d", "e\nANCESTOR:x|forged", "../../x"]`,
     `module_label: "m|DEPTH:9"`, and a `task_file` containing a newline):
     assert every stdout line starts with a known record key, `ANCESTOR` lines
     have exactly 6 `|`-fields, the forged record never appears, unsafe values
     render as `!INVALID` / `INVALID`, and `TASK_FILE:INVALID`;
     **task-file allowlist**: `task_file: .git/config` (a real, existing file in
     the fixture) → `TASK_FILE:INVALID`; `aitasks/t998_other.md` (existing, wrong
     task) → `INVALID`; the correct `aitasks/t999_x.md` → emitted; correct shape
     but deleted → `NOT_FOUND`; task num `12a` / `1_` → exit 2;
     **malformed `br_session.yaml`** (unparseable) → `TASK_FILE:NOT_FOUND`,
     exit 0, no traceback on stderr (red proof for the CLI `yaml` import);
     and a
     **read-only proof** (sha of the fixture crew tree unchanged after all
     invocations). Tests run in the main shell (no `( … )` bodies) — if any
     subshell body is used, opt into `assert_counters_init`/`assert_counters_load`.

## Verification

- `bash tests/test_brainstorm_context_helper.sh` passes
- `bash tests/run_all_python_tests.sh --test-dir tests` — last line `PYTHON SUITE: PASSED`
  (plus the focused `python -m pytest tests/test_brainstorm_node_ancestors.py tests/test_brainstorm_dag.py tests/test_brainstorm_cli_python.py`)
- `bash tests/test_brainstorm_cli.sh` still passes (CLI module edited)
- `shellcheck .aitask-scripts/aitask_brainstorm_context.sh` clean
- `bash tests/test_touchpoint_count_contract.sh` passes; `audit-helper-whitelist` reports nothing missing
- On a real session if one exists under `.aitask-crews/`: `--lineage` run, and
  `git -C .aitask-crews/crew-brainstorm-<N> status` stays clean

## Post-implementation

Step 9 of the task workflow (review, commit, archive). In Final Implementation
Notes record the **final output grammar** — t1823_2's skill parses it. The
grammar now differs from the one quoted in t1823_2's task body (sentinels
`!INVALID` / `!MISSING` / `INVALID`), so after landing send t1823_2 a note via
`./ait note 1823_2 --from 1823_1` pointing at the archived plan's grammar.

## Risk

### Code-health risk: low
None identified. The change is additive (one new pure DAG function plus a
validator, one new CLI subcommand, one new wrapper, whitelist entries written by
the audit tooling); no existing function or caller is modified. The added
`import yaml` in `brainstorm_dag.py` is already a hard dependency via
`agentcrew_utils`.

### Goal-achievement risk: low
None identified. The output grammar is fixed here (with its encoding) and
consumed by a not-yet-written sibling, so it is pinned by tests now. The three
review findings (unvalidated graph ids, missing `yaml` import, unescaped
delimiters) are designed in with red-proof tests; the cwd-relative crew path is
handled in step 3.
