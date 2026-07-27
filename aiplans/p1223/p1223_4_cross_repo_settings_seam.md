---
Task: t1223_4_cross_repo_settings_seam.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_5_settings_tab_and_push_action.md, aitasks/t1223/t1223_6_syncer_scope_documentation.md, aitasks/t1223/t1223_7_manual_verification_expand_syncer_scope_version_and_settings.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_1_tabbed_syncer_shell.md, aiplans/archived/p1223/p1223_2_framework_version_and_upgrade_command_model.md, aiplans/archived/p1223/p1223_3_version_tab_upgrade_action_and_handoff.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-27 23:52
---

# p1223_4 — Cross-repo settings seam (headless)

## Context

`t1223` expands the syncer beyond branch sync to **version** and **settings**
sync across registered repos. `t1223_1` (tab shell), `t1223_2` (version model)
and `t1223_3` (version tab + upgrade handoff) have landed. This child builds the
**headless seam for cross-repo settings** — no Textual — that `t1223_5` renders.

The framework has **no path-parameterized settings writer**: `aitask_codeagent.sh`
is read-only, and every Python config writer resolves its path from cwd-relative
module constants. `config_utils.export_all_configs` / `import_all_configs` are
the only functions taking a caller-supplied `metadata_dir`, but they are
**whole-file replace**, which would clobber a destination's other operations.

This task extends that shared API by parameter (contract **E**) and adds a module
that reads / diffs / validates the default code agent per operation across repos
(contract **D**).

Parent plan: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.

---

## Verification findings — the existing plan drifted

Re-verified against the current tree. Corrections:

| Anchor in the task file | Reality |
|---|---|
| `settings_app._handle_agent_pick:2281-2310`, masked block `:2299-2306` | **2284-2313**, masked block **2299-2309** (t1219 added 3 lines above). Behavior intact. |
| `settings_app.save_codeagent:485-493` | **488-496**. Behavior intact. |
| `agent_launch_utils.resolve_agent_string:232-251` | exact ✓ — `(project_root: Path, operation: str) -> str \| None` |
| `agent_model_picker.load_all_models:44-56` | exact ✓, but `project_root` is **optional** (defaults to cwd) |
| `agent_string.sh:26` `DEFAULT_AGENT_STRING` | ✓, value is now **`claudecode/opus5`** (t1241), not `opus4_8` |
| `SUPPORTED_AGENTS` "at :48-66" | actually at **:28**, outside `parse_agent_string` |
| "the house atomic-write pattern" | **two different implementations** — `gate_ledger:357-373` vs `attachment_meta:65-78`. They differ on temp creation, cleanup trigger and resulting file mode; neither fsyncs. There is no single house pattern to copy. |
| `model_reference_locations.md:55-68` = "authoritative resolution order" | **wrong file** — those lines are audit tables whose own line refs are stale. The real chain is `aitask_codeagent.sh:645-649`. |

### The blocking finding: there is no `seed` resolution tier

The task file states the order is `local → project → seed/codeagent_config.json →
DEFAULT_AGENT_STRING`. The **ground-truth resolver**
(`aitask_codeagent.sh:53-88`, help text at `:645-649`) resolves:

```
--agent-string  →  codeagent_config.local.json  →  codeagent_config.json  →  DEFAULT_AGENT_STRING
```

`seed/` is a **setup-time copy source** (`aitask_setup.sh:1666` copies it into
`aitasks/metadata/` during setup); it is never read at runtime, and an installed
user project has no `seed/` at its root at all.

Implementing `seed` as an effective tier would make **every** seed-only operation
render `conflict` (layer-derived = seed value, `resolve_agent_string` = builtin
default) — a systematic false positive, not an edge case.

**Decision (user-confirmed): drop `seed`.** `provenance ∈ {local, project,
builtin}` plus `conflict`. Contract **D**, this task's AC, and `t1223_5`'s marker
table are amended accordingly.

### Other user-confirmed decisions

- **Atomic writer:** make the module's existing write funnel atomic rather than
  adding a second writer. `save_project_config`, `save_local_config`,
  `export_all_configs` and `import_all_configs` all gain crash-safety; the
  unchanged `tests/test_config_utils*.py` are the regression proof.
- **Model catalog:** move `MODEL_FILES` + `load_all_models` from
  `agent_model_picker` (which imports Textual at module level) into
  `config_utils`, re-exporting so existing callers are untouched. Keeps
  `cross_repo_settings` genuinely headless.

---

## Part 1 — `config_utils` (contract E)

**File:** `.aitask-scripts/lib/config_utils.py`

### 1.1 One atomic write helper

```python
_UMASK = os.umask(0); os.umask(_UMASK)        # module import, once — never per write
from os import replace as _os_replace          # module-local seam (see tests)

def _atomic_write(path: Path, render) -> None:
    """Write text produced by render(fh) atomically.

    Temp file in the same directory + os.replace: a concurrent reader never
    observes a partial file, and a failed write leaves the original intact.
    This is atomic *visibility*, not crash durability — there is no fsync,
    matching gate_ledger and attachment_meta.
    """
    path = Path(os.path.realpath(path))        # never replace a symlink itself
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = _target_mode(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            render(fh)
        _os_replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
```

Four write sites adopt it — this is what makes the approved caller list true,
since two are **inline writes that never went through `_save_json`**:

| Site | Today |
|---|---|
| `_save_json` (124-129) → `save_project_config` / `save_local_config` | inline `open(...,"w")` |
| `save_yaml_config` (167-173) — reached by `import_all_configs`' shortcuts branch | inline |
| `export_all_configs` (317-319) — the bundle write | inline |
| `import_all_configs` (427-429) — the per-file write | inline; becomes `_save_json(target, data)` |

`save_yaml_config` matters most: `userconfig.yaml` holds `email` and
`last_used_labels`, which exist nowhere else, whereas JSON configs are
recoverable from a bundle.

Four details that are load-bearing, not polish:

- **Mode preservation.** `_target_mode` returns `stat.S_IMODE(os.stat(path).st_mode)`
  when the target exists, else `0o666 & ~_UMASK`. `mkstemp` creates `0600`, and
  today `models_claudecode.json` is `0644` while `codeagent_config.json` is
  already `0600` — without the chmod every settings save would silently
  downgrade the former.
- **Umask read once at import.** The `os.umask(0)`-then-restore probe is
  process-global and racy; `settings_app` is a Textual app with worker threads,
  so doing it per write could hand another thread a mode-0 window.
- **`realpath` before choosing the temp dir.** `open(path,"w")` *follows* a
  symlink; `os.replace` *replaces the link itself*. Without resolving first, a
  symlinked config file would be silently converted to a regular file and its
  real backing file orphaned — reads keep succeeding while writes stop landing.
  No config file is a symlink today (checked), but `aitasks/` itself is
  (→ `.aitask-data/aitasks`, same filesystem), so the parent chain already
  exercises symlink resolution and the rename stays same-directory.
- **`_os_replace` alias.** `config_utils` does `import os`, so `config_utils.os`
  *is* the `os` module and patching `config_utils.os.replace` would patch
  `os.replace` process-wide (verified). Binding the name at import makes the
  atomicity negative control genuinely module-local.

Two behavior changes to accept and note: `mkstemp` needs write permission on the
**directory** (previously only on the file), and a read-only target file now
succeeds instead of raising `PermissionError`.

### 1.2 `import_all_configs` — `bundle=` and `merge=`

```python
def import_all_configs(
    input_path: str | Path | None = None,
    metadata_dir: str | Path | None = None,
    overwrite: bool = False,
    selected_files: list[str] | None = None,
    *,
    bundle: dict | None = None,
    merge: bool = False,
) -> list[str]:
```

`input_path` must stay **first positional** and `metadata_dir` second: all 15
call sites pass both positionally (`settings_app.py:3869`,
`tests/test_config_utils.py:419/433/447/463/621`,
`tests/test_config_utils_shortcuts.py:99/114/125`). Since `input_path` now needs
a `None` default, `metadata_dir` takes one too and is validated as **required at
runtime**. Its default must **not** be `metadata_dir()` — that module function is
shadowed by the parameter name and reads `TASK_DIR` at call time, so a
def-time default would freeze `TASK_DIR` at import.

Validation runs **first, before any filesystem access** (`ValueError` for each):
`bundle` and `input_path` both set or neither; `merge=True` with
`overwrite=False`; `metadata_dir is None`; `"files"` missing from a `bundle=`
dict (same check the path branch already applies).

Per-file order — **the existing skip order is preserved exactly**, because the
traversal guard currently runs *before* the selection filter (`:411-413` vs
`:416-417`), so an unselected `../evil.json` raises today and must keep raising:

1. path-traversal guard — now applied to `bundle=` names too;
2. `selected_files` filter;
3. `_error`-entry skip;
4. destination probe (`exists`) — repurposed, not deleted: in merge mode it
   distinguishes "merge into existing" from "create fresh";
5. **merge mode only:** read the destination (missing → `{}`; existing but
   malformed → **raise, write nothing**), conflict-check, `deep_merge`;
6. plan the write.

The destination read **must** come after steps 2 and 3. Reading before the
selection filter would let a malformed `board_config.json` abort an import that
only ever intended to touch `models_*.json` — a file the caller never asked to
touch, with no workaround from the TUI. Reading before the `_error` skip would
abort when both the bundle entry and the destination are garbage, the one case
where doing nothing is obviously right.

**Three-stage commit.** The justification is the caller:
`settings_app._handle_import` (`:3865-3885`) catches `Exception`, reports the
failure, and **skips `config_mgr.load_all()` and every `_populate_*` refresh** —
so any raise that leaves files on disk makes the TUI re-render stale in-memory
config. "Prepare everything, then commit" is therefore not cosmetic.

`_atomic_write` splits into `_prepare_atomic(path, render) -> tmp` and
`_commit_atomic(tmp, path)` so the phases are:

1. **Plan** — read, conflict-check and `deep_merge` every selected file. Any
   failure here raises with **nothing written and no temp files left**.
2. **Prepare** — write every merged result to its temp file. A failure here
   unlinks all temps and raises, still with nothing committed.
3. **Commit** — `os.replace` each temp in sequence.

This shrinks the partial-application window to the rename loop, which is the
best a POSIX filesystem offers. It cannot be eliminated, so it is made
**visible instead of assumed away**: a failure during stage 3 unlinks the
remaining temps and raises `ConfigImportPartialError(written=[...])` naming the
files that did land. Callers must reload from disk on that error rather than
assume nothing changed — and `settings_app._handle_import` is updated to do
exactly that (call `config_mgr.load_all()` and the `_populate_*` refreshes, then
report which files landed). That also repairs an existing latent bug: the legacy
non-merge path can already partially apply today, because its traversal
`ValueError` fires mid-loop after earlier files were written, and the TUI
currently mishandles it.

`apply_push` writes exactly **one** file, so this task's own use cannot reach
cross-file partial application; the guarantee is for the shared API's other
callers.

Remaining bounds, stated rather than implied:
- `meta_path.mkdir(parents=True, exist_ok=True)` still precedes stage 2, so a
  stage-1 raise can leave an empty metadata directory — same as legacy.
- In merge mode `written` means "file was in the plan", which includes a merge
  that changed nothing. Legacy `written` meant "bytes were written". Documented;
  the only consumer does `len(written)`.

**Distinguishable failures.** `json.JSONDecodeError` **is** a `ValueError`
subclass (verified), so a bare `assertRaises(ValueError)` cannot tell a malformed
destination from a type conflict. Define `ConfigMergeError(ValueError)` for
conflict/unsupported-shape rejections: still a `ValueError` (so contract E's
stated exception type holds), but assertable apart from a decode error.

**Type conflicts.** `deep_merge` recurses only when both sides are dicts and
otherwise lets the override win, so a dict-vs-scalar mismatch silently drops a
subtree. Two levels of rule are needed.

*Whole-file value* — a bundle file value is **not** always a dict:
`tests/test_config_utils.py:493` round-trips `models_claudecode.json` as a bare
**list**, and `export_all_configs` preserves it.

| destination | incoming | merge mode |
|---|---|---|
| missing | dict | write (merge from `{}`) |
| missing | list / scalar | **write verbatim** — round-trip parity; must *not* raise |
| dict | dict | recurse |
| list / scalar | same kind | replace whole file (`deep_merge`'s documented list rule) |
| dict | list / scalar, or the reverse | **`ConfigMergeError`**, naming the file |
| exists but is a directory / holds `null` | anything | **`ConfigMergeError`**, not a stray `IsADirectoryError` |

*Nested common key* — raise when exactly one side is a dict:

| existing | incoming | result |
|---|---|---|
| dict | dict | recurse |
| dict | list / scalar / `None` | **raise** — would drop a subtree |
| list / scalar / `None` | dict | **raise** — would clobber a value with a tree |
| list | list | pass — incoming replaces the list |
| scalar | scalar (any types) | pass — override wins, no type policing |
| absent on either side | anything | pass |

The conflict walk is invoked **only** when `merge=True`, so the non-merge path is
untouched. Error messages join the key path with a separator and quote each
segment, since config keys legitimately contain `.` (e.g. `models_claudecode.json`).

**Shortcuts.** The `shortcuts` → `userconfig.yaml` branch (`:436-457`) is folded
into the two-phase structure: its YAML read and validation happen in phase 1, its
write runs last in phase 2. Its **shallow** `scope_map.update(actions)` semantics
stay unchanged — unifying it with `deep_merge` would silently alter depth-3
behavior, and `tests/test_config_utils_shortcuts.py` only exercises depth 2, so
such a refactor would pass the suite while changing behavior. Out of scope here.

### 1.3 Relocate the model catalog — and make it genuinely root-relative

Move `MODEL_FILES` and `load_all_models` into `config_utils` (they use only
`metadata_dir()` / `_load_json`, both already there — no new import, no cycle).
In `agent_model_picker.py` replace the definitions with
`from config_utils import MODEL_FILES, load_all_models`, so `settings_app`,
`agent_command_screen` and `tests/test_task_dir_module_constants.py` (which
probes in a fresh subprocess) are unaffected.

**A verbatim move would carry a latent cross-root bug.** `MODEL_FILES` is a
static map built from `metadata_dir()` — i.e. from the **caller's** `TASK_DIR` —
and `load_all_models` composes `root / rel`. That breaks two different ways:

- `TASK_DIR` **absolute** → pathlib discards the left operand entirely (verified:
  `Path("/dest/repo") / Path("/abs/aitasks/metadata/x.json")` → `/abs/.../x.json`),
  so the lookup leaves the destination altogether.
- `TASK_DIR` **relative but non-default** (e.g. `mytasks`) → the lookup becomes
  `dest_root/mytasks/metadata`, while the layer files and the env-scrubbed
  subprocess both use `dest_root/aitasks/metadata`. The catalog is then read from
  a different tree than everything else in the same answer — quietly yielding a
  false `model_not_in_dest_catalog`.

Deriving the catalog path from *any* ambient caller state is the defect; a
"relative is fine" carve-out only narrows it. So the root-supplied path is made
**explicitly parameterized**:

```python
def load_all_models(project_root=None, *, metadata_path=None) -> dict[str, dict]:
    """metadata_path, when supplied, is used verbatim — no ambient TASK_DIR.
    project_root=None keeps today's cwd/TASK_DIR behavior for existing callers.
    """
```

(The keyword is `metadata_path`, not `metadata_dir`, so it cannot shadow the
module-level `metadata_dir()` function — the same trap §1.2 avoids.)

`cross_repo_settings` **always** uses the `metadata_path=` form, passing the very
same `_dest_metadata_dir(root)` it uses for the layer files. One helper answers
"where is this repo's metadata" for the layers, the catalog, and (via the env
scrub) the subprocess — so the three agree by construction, not by coincidence.

The `project_root=`-only path keeps today's semantics for
`agent_command_screen.py:776` (same-repo, where honoring `TASK_DIR` is correct),
with one defensive fix since the function is being moved anyway: if `task_dir()`
is absolute it falls back to `aitasks` rather than silently discarding the root.

---

## Part 2 — `lib/cross_repo_settings.py` (contract D)

**New file**, Textual-free: stdlib + `config_utils` + `agent_launch_utils`.

### 2.0 Cross-root isolation (prerequisite for everything below)

Every value in this module is claimed to describe **a specific repo**. Two
verified leaks would silently break that claim without failing an ordinary
fixture test:

1. **The resolver inherits the caller's environment.** `agent_string.sh:24`
   states outright that "caller may pre-set any of these to override":
   `DEFAULT_AGENT_STRING` (`:26`) and `METADATA_DIR` / `TASK_DIR` (`:27`).
   `resolve_agent_string` runs `subprocess.run(..., cwd=project_root)` with **no
   `env=`**, so the child inherits them. Proven: with `METADATA_DIR` pointed at
   an unrelated directory, `aitask_codeagent.sh resolve pick` read *that*
   directory and ignored `cwd`. In the syncer — one process resolving N
   destinations — a set `METADATA_DIR` would collapse every destination onto the
   same config, and the whole matrix would agree for the wrong reason.
2. **Absolute `TASK_DIR` defeats root composition** on the Python side (§1.3).

Both are closed explicitly:

- Add a keyword-only `env: dict[str, str] | None = None` to
  `resolve_agent_string` (`agent_launch_utils.py:232`), forwarded to
  `subprocess.run`. Additive — the default preserves today's behavior for its
  ten existing same-repo callers, where honoring the user's `TASK_DIR` is
  correct.
- This module always passes a **scrubbed** env: `os.environ` minus
  `METADATA_DIR`, `TASK_DIR`, `DEFAULT_AGENT_STRING` and `OPT_AGENT_STRING`
  (the last is read as `${OPT_AGENT_STRING:-}` and would act as a global
  `--agent-string` override). The destination then resolves with **its own**
  defaults.
- A single private `_dest_metadata_dir(root) -> Path(root)/"aitasks"/"metadata"`
  is the **only** place this module answers "where is this repo's metadata". It
  feeds the layer reads, the model catalog (via `load_all_models(metadata_path=…)`,
  §1.3) and matches what the env-scrubbed subprocess resolves — so all three
  agree by construction. No ambient `TASK_DIR` / `METADATA_DIR` reaches any of
  them.

Tests 28 and 28b pin this at the weakest surface, under **both** hostile shapes
(absolute *and* relative-but-non-default `TASK_DIR`, plus a misdirected
`METADATA_DIR`): 28 covers the read/provenance path, 28b covers **catalog
validation through `plan_push`** with divergent per-root catalogs — the path a
read-only test cannot reach.

### 2.1 Strict raw-layer probe (why `dest_config_unreadable` cannot come from the resolver)

The shell resolver **swallows a corrupt config**: `jq … 2>/dev/null` then
`|| true`, so a malformed `codeagent_config.json` falls through to the next
layer. Proven end-to-end: a destination whose project config is `{not json`
resolves to `AGENT_STRING:claudecode/opus5` with **exit 0**. Left as-is,
`plan_push` against a corrupt destination would return a confident `ok`/`noop`
and write into it.

`_load_json` is equally lossy at the edges (verified): a **directory** at the
config path returns `{}` (indistinguishable from absent), and a file containing
`null` returns `None`, not a dict.

So this module reads the raw layers with its own strict probe rather than
trusting either. Per layer file: absent → fine (`{}`); not a regular file (dir,
fifo) → `dest_config_unreadable`; unreadable (`OSError`) → `dest_config_unreadable`;
invalid JSON → `dest_config_unreadable`; valid JSON that is not a dict (`null`,
list, scalar) → `dest_config_unreadable`. The same probe covers the destination's
`models_<agent>.json` catalog, so a corrupt catalog is a typed outcome rather
than an uncaught `JSONDecodeError` escaping `plan_push`.

```python
AGENT_OPERATIONS_EXCLUDE_SUFFIX = "-launch-mode"

@dataclass(frozen=True)
class OperationValue:
    operation: str
    effective: str | None      # GROUND TRUTH from resolve_agent_string(root, op)
    project_value: str | None
    local_value: str | None
    provenance: str            # 'local' | 'project' | 'builtin' | 'conflict'
```

- **`read_operation_defaults(root)`** — reads the raw layers directly; operation
  set is `union(local keys, project keys)` minus the `-launch-mode` suffix.
  `effective` comes from `resolve_agent_string(root, op)`, an **independent
  path** (it shells the destination's own `aitask_codeagent.sh`), never our own
  merge. `provenance`: local key present → `local`; else project key present →
  `project`; else `builtin`. If the layer-derived value disagrees with
  `effective`, provenance is **`conflict`** and no value is guessed.
- **`diff_across_repos(roots)`** → `{operation: {repo_key: OperationValue}}`.
  `repo_key` is `os.path.realpath` with an `OSError` fallback to `str(root)` —
  matching `AitasksSession.key` (`agent_launch_utils.py:126-141`) **exactly**, so
  `t1223_5` indexes by `sess.key` with no mapping layer. Operations are unioned
  across roots; a root missing an operation still gets an entry (provenance
  `builtin`).
  `resolve_agent_string` spawns a subprocess per `(root, operation)` (~17 ops × N
  repos, 10s timeout each), so the fan-out runs in a bounded
  `ThreadPoolExecutor(max_workers=8)`. The workers are pure and read-only, share
  no mutable state, and the result dict is assembled only after join — so
  ordering is deterministic and independent of completion order.
- **`plan_push(value, dest_root, operation, layer)`** → typed outcome, never a
  bare bool. `layer ∈ {'project','local'}`:
  - `noop` — the destination's **effective** value already equals `value`.
  - `masked` — `layer == 'project'` **and** the destination has a local override
    for that operation; carries `masking_value` so the UI can name it.
  - `rejected(reason)`, each cause distinct: `malformed_agent_string` (fails the
    shape `^[a-z]+/[a-z0-9_]+$` or names an unsupported agent),
    `model_not_in_dest_catalog` (shape and agent fine, but the model `name` is
    absent from the destination's `models_<agent>.json`), `dest_config_unreadable`
    (destination config invalid/unreadable, or the root is not an aitasks repo —
    `resolve_agent_string` returns `None`).
  - `ok` otherwise.
- **`apply_push(value, dest_root, operation, layer, clear_mask=False)`** — writes
  via `import_all_configs(bundle={"files": {<name>: {"defaults": {operation:
  value}}}}, metadata_dir=dest_root/"aitasks"/"metadata", overwrite=True,
  merge=True)`. With `clear_mask=True` it additionally removes the local override
  for `operation`, dropping an emptied `defaults` and then an emptied local file
  — mirroring `settings_app._handle_agent_pick:2304-2308` + `save_codeagent:488-496`.

  **`clear_mask=True` touches two files, and that is not atomic.** The ordering
  is therefore chosen so the *failure* mode is safe, and is a binding part of
  the contract:

  1. write the **project** layer, then 2. clear the **local** override.

  If step 2 fails, the local override is still present, so the destination's
  **effective value is unchanged** — the repo behaves exactly as it did before
  the push. The residue is a project-layer value hidden behind the mask, and
  re-running converges: `plan_push` still reports `masked`, the same three-way
  prompt appears, and the project write is idempotent (a merge of the same key).
  The reverse order is rejected: clearing the mask first and then failing would
  drop the user's override and swing the effective value to something they never
  chose.

  Step 2 failing raises `PushPartialError(applied="project",
  failed="clear_local", masking_value=…)` so the UI can say precisely: *"the
  project layer was updated but the local override could not be cleared — this
  repo still uses `<masking_value>`; retry to finish."* Silence here is what
  would make retry behavior and reporting ambiguous.

There is **no Python `parse_agent_string`** (verified — only `agent_string.sh`,
plus four ad-hoc unvalidated `.split("/", 1)` call sites). The shape regex and
supported-agent set live here, with the agent set taken from
`config_utils.MODEL_FILES` keys rather than a fresh literal, plus a drift-guard
test pinning it against `agent_string.sh`'s `SUPPORTED_AGENTS`.

The `-launch-mode` literal has only one other production `endswith` site
(`settings_app.py:2132`), below `planning_conventions.md`'s "3+ files" extraction
threshold, so it stays a local constant.

---

## Verification

```bash
python3 tests/test_cross_repo_settings.py
python3 tests/test_config_utils.py                # MUST pass unchanged
python3 tests/test_config_utils_shortcuts.py      # MUST pass unchanged
python3 tests/test_task_dir_module_constants.py   # MODEL_FILES relocation
bash tests/run_all_python_tests.sh
```

**Baseline captured before any edit:** 67 + 6 + 8 = **81 tests green**. Any
post-change failure among them is a regression, not pre-existing.

New tests use **fixture repo roots under `tempfile.mkdtemp()`**, never cwd, and
stdlib `unittest` ending in `unittest.main()`. No `codeagent_config.local.json`
and no `-launch-mode` key exists on disk today, so both are fixture-only.

**Prove the suite can fail before relying on it** — run each load-bearing test
against its named mutation and confirm a non-zero exit.

### `config_utils` (contract E)

1. `bundle=` + `input_path=` together, and neither ⇒ `ValueError` — **and no
   file changed and no metadata dir created** (pins "validate before any FS access").
2. `merge=True, overwrite=False` ⇒ `ValueError`, same no-side-effect assertion.
3. `metadata_dir=None` ⇒ `ValueError`; `bundle=` without `"files"` ⇒ `ValueError`.
4. **Exact target-file diff** — bundle carries **all 10** files, `selected_files`
   names 1; the other 9 unchanged in **bytes and `st_ino`** (with `os.replace` a
   rewrite always changes the inode, so inode-stability is the sharp probe).
   *Mutation: drop the selection filter.* The 10-file bundle is essential — with
   a 1-file bundle the test passes even with the filter deleted.
5. **Unrelated-key negative control** — destination holds a top-level key absent
   from the payload; it survives verbatim. *Mutation: whole-file write.*
6. **Depth discrimination** — destination `{"a": {"x": 1, "y": 2}}`, incoming
   `{"a": {"x": 9}}`; assert `y == 2` survives. *Mutation: `dict.update()`
   instead of `deep_merge`.* Without this, a shallow implementation passes the
   whole suite.
7. **Fail closed** — destination is invalid JSON: raises `json.JSONDecodeError`
   (assert the specific type, **not** bare `ValueError`), file identical in bytes
   **and `st_ino`**. *Mutation: a swallowing reader (`except: return {}`), which
   would merge into `{}` and clobber the file.* Companion: destination malformed
   but **not selected** ⇒ must **not** raise.
8. **Type conflict** — both directions (dict-vs-scalar and scalar-vs-dict), each
   raising `ConfigMergeError` and *not* `json.JSONDecodeError`, file unchanged.
   A one-sided implementation passes a single-direction test.
9. **Whole-file shapes** — every row of the whole-file table, especially
   *list into a missing destination must NOT raise* (round-trip parity) and
   *list into a dict destination must raise*.
10. **Atomicity** — `mock.patch("config_utils._os_replace", side_effect=OSError)`:
    original bytes and `st_ino` unchanged, and `list(path.parent.iterdir())`
    contains no `.{name}.*.tmp` entry (enumerate — `mkstemp` randomizes the name).
    *Mutations: missing `unlink` in the except path; writing to `path` directly.*
11. **Stage-1 fail-closed** — a bundle with one good and one malformed
    destination writes **neither**; assert the good file's bytes are untouched
    and that **no `.tmp` residue** remains.
11b. **Stage-3 partial application is visible** — patch `_os_replace` to succeed
    once then raise, driving a two-file merge: assert `ConfigImportPartialError`
    is raised, that its `written` list names exactly the first file, that the
    first file really did land on disk, and that the second file is untouched
    with no temp residue. *Mutation: swallow the error, or report `written=[]` —
    either would tell the caller "nothing changed" while file 1 changed.*
12. **Mode preservation** — a `0644` target stays `0644`, a `0600` target stays
    `0600`. *Mutation: drop the `fchmod`.*
13. **Symlinked target** — a config file that is a symlink stays a symlink and its
    backing file receives the update. *Mutation: drop the `realpath`.*
14. **`selected_files` parity** — drive the **same bundle dict** through
    `bundle=` and `input_path=`; assert identical `written`, identical bytes, and
    that the **non-selected file does not exist**. Without the last assertion an
    implementation whose `bundle=` path ignores `selected_files` still passes.
15. **Traversal** — `../evil.json` ⇒ `ValueError`; placed **after** a good name in
    insertion order, assert the good file was **not** written (merge mode); and a
    traversal name **not** in `selected_files` **still raises** (current behavior,
    untested today — without this the guard/filter order can be silently reordered).
16. Merge into a **missing** destination creates it and appears in `written`.
17. Legacy regression: `test_config_utils.py` + `test_config_utils_shortcuts.py`
    pass untouched.

### `cross_repo_settings` (contract D)

18. Provenance truth table: project-only ⇒ `project`; local-only ⇒ `local`;
    both ⇒ `local` (effective equals the local value); neither ⇒ `builtin`.
    **No `seed` case** — per the amended contract.
19. `conflict` — stub `resolve_agent_string` to return something the layers do
    not imply; provenance is `conflict` and **no value is guessed**.
20. A `seed/codeagent_config.json` in the fixture root does **not** influence
    provenance or effective. *Negative control for the dropped tier.*
21. `-launch-mode` keys are excluded from the operation set.
22. `noop` when the destination's effective already matches.
23. **`masked`** — destination has a local override; `layer='project'` ⇒ `masked`
    carrying the masking value; `layer='local'` ⇒ `ok`.
24. Each `rejected` reason fires for its own cause and **only** its own cause
    (three fixtures, each triggering exactly one).
25. `apply_push(layer='project', clear_mask=True)` removes the local key, drops
    an emptied `defaults`, deletes an emptied local file, leaves other local keys
    intact.
26. `diff_across_repos` groups by operation across ≥3 fixture roots, flags
    divergence, and its `repo_key` equals `AitasksSession.key` for the same root
    (guards the two identities against drifting apart).
27. Supported-agent drift guard: the Python agent set equals `SUPPORTED_AGENTS`
    parsed out of `agent_string.sh`.
28. **Cross-root isolation — read path.** Two fixture roots holding *different*
    values for the same operation, resolved in one process while `TASK_DIR`
    **and** `METADATA_DIR` are set to a third, unrelated directory: each root
    must still report its own `effective` and `provenance`. *Mutation: drop the
    `env=` scrub.*
28b. **Cross-root isolation — catalog path.** The read path never touches the
    model catalog, so 28 alone would still pass with a static `MODEL_FILES`.
    This test drives **`plan_push`**, the only consumer of the catalog: give root
    A a `models_claudecode.json` containing only `alpha1` and root B one
    containing only `beta1`, then assert
    `plan_push("claudecode/beta1", A, …) == rejected(model_not_in_dest_catalog)`
    while `plan_push("claudecode/beta1", B, …)` is **not** rejected — and the
    mirror image for `alpha1`. Divergent catalogs are what make the assertion
    discriminating: with identical catalogs, reading the wrong repo's file gives
    the right answer by luck.
28c. **Both tests run under every hostile env shape**, parameterized: `TASK_DIR`
    **absolute** (the case where `root / rel` discards the root), `TASK_DIR`
    **relative but non-default** (e.g. `mytasks` — the case where the catalog
    would silently diverge from the layer files while still living under the
    destination), and a `METADATA_DIR` pointing elsewhere. *Mutations that must
    each make 28b fail: use static `MODEL_FILES`; use `metadata_dir()` or
    `task_dir()` instead of `_dest_metadata_dir(root)`; drop the
    `metadata_path=` argument and fall back to the `project_root=`-only path.*
    A relative-only or absolute-only fixture does not discriminate — the two
    shapes fail through different mechanisms.
29. **Corrupt destination is typed, not silently resolved.** Destination whose
    `codeagent_config.json` is `{not json` (with a valid catalog present, so the
    resolver really does exit 0 with the builtin default): `plan_push` returns
    `rejected(dest_config_unreadable)` — **not** `ok`, `noop`, `masked`, or an
    uncaught `JSONDecodeError`. Repeat for a **directory** at the config path
    (which `_load_json` reports as absent), a config containing `null`, and a
    corrupt `models_<agent>.json`. *Mutation: trust `resolve_agent_string`'s
    return instead of the strict probe.*
30. **`clear_mask` partial failure** — fault-inject a failure of the local-clear
    step after the project write succeeds: `PushPartialError` is raised naming
    both halves, the destination's **effective value is unchanged** (the mask
    still applies), and a retry converges (`plan_push` still reports `masked`;
    a second `apply_push` completes and leaves other local keys intact).
    *Mutation: reverse the write order — the effective value then changes to a
    value the user never chose, and the test must fail.*

---

## Risk

### Code-health risk: medium
- Making the module's write funnel atomic changes the mechanism behind **every**
  framework config write (settings TUI, board config, models, userconfig
  shortcuts), not only this task's writes; a defect there breaks config
  persistence broadly. · severity: medium · → mitigation: the 81 unchanged
  existing tests as regression proof, plus dedicated mode-preservation, symlink
  and atomicity negative controls (tests 10/12/13)
- `mkstemp` + `os.replace` silently changes two properties `open(path,"w")` had:
  the resulting file mode (0600) and symlink-following. Left unhandled, a
  settings save would downgrade `models_claudecode.json` from 0644, and a
  symlinked config would be orphaned while reads kept
  succeeding. · severity: medium · → mitigation: explicit `fchmod` to the
  preserved mode and `realpath` resolution, each with its own falsifiable test
- `import_all_configs` is shared with the settings TUI's export/import; a
  signature change plus a merge branch adds real complexity (two-phase planning,
  a conflict walk, a new exception type) to a load-bearing helper with 15 call
  sites. · severity: medium · → mitigation: contract **E** stated in full, the
  non-merge path left untouched and proven by the unchanged suites, and the
  conflict walk invoked only when `merge=True`
- The whole-file merge matrix has a non-obvious carve-out — a list-valued
  `models_*.json` into a missing destination must **not** raise — that a naive
  root-level conflict rule gets wrong. · severity: low · → mitigation: test 9
  covers every row of the whole-file table including the carve-out
- This task adds a **third** temp-file + `os.replace` implementation alongside
  `gate_ledger._atomic_write` and `attachment_meta.atomic_write`, which already
  differ from each other. · severity: low · → mitigation: unify_atomic_write_helpers

### Goal-achievement risk: medium
- **The cross-repo promise is defeated by inherited environment.** `METADATA_DIR`
  / `TASK_DIR` / `DEFAULT_AGENT_STRING` are documented caller overrides that the
  resolver subprocess inherits, and an absolute `TASK_DIR` makes `root / rel`
  discard the root. Either one silently makes every destination report the same
  (wrong) repo — and neither shows up in an ordinary fixture test, because
  fixtures normally leave those vars unset. · severity: medium · → mitigation:
  §2.0 env scrub + a single `_dest_metadata_dir(root)` feeding layers, catalog
  and subprocess alike, with the catalog path **explicitly parameterized**
  (`metadata_path=`) rather than derived from ambient state; pinned by tests
  28 / 28b / 28c across absolute *and* relative-non-default `TASK_DIR` plus a
  misdirected `METADATA_DIR`, with 28b driving `plan_push` against divergent
  per-root catalogs so a static-`MODEL_FILES` regression cannot pass
- **A corrupt destination resolves to a confident wrong answer.** The shell
  resolver swallows malformed JSON and exits 0 with the builtin default, and
  `_load_json` reports a directory as absent — so without a strict probe
  `plan_push` would return `ok` and write into a repo whose config is
  broken. · severity: medium · → mitigation: §2.1 strict raw-layer probe, pinned
  by test 29 across four corruption shapes
- `effective` requires one `resolve_agent_string` subprocess per
  `(repo, operation)` — ~17 × N with a 10s timeout each — so a slow or
  unreachable destination makes `diff_across_repos` sluggish even bounded at 8
  workers. · severity: low · → mitigation: bounded `ThreadPoolExecutor`;
  `t1223_5` already calls it from a thread worker behind the existing coalescing
  guard
- `clear_mask` writes two files non-atomically, so a failure between them can
  leave a hidden project value behind a live mask. · severity: low · →
  mitigation: write order fixed so the **effective value never changes on
  failure**, `PushPartialError` naming both halves, retry-converges, pinned by
  test 30 including the reversed-order mutation
- Stage-3 commit can still partially apply across files, and the settings TUI
  currently skips its reload on any exception. · severity: low · → mitigation:
  `ConfigImportPartialError` carrying the landed files + a `settings_app`
  handler that reloads from disk, pinned by test 11b
- Dropping the `seed` tier amends a contract written into the parent plan and
  two sibling task files; if the amendment is not propagated, `t1223_5` would
  render a marker that can never occur. · severity: low · → mitigation:
  propagated in-task (step below) and pinned by test 20's negative control

### Planned mitigations
- timing: after | name: unify_atomic_write_helpers | type: refactor | priority: low | effort: medium | addresses: three divergent temp+os.replace implementations | desc: Extract gate_ledger, attachment_meta and config_utils atomic writers into one shared helper with consistent mode/cleanup semantics.

## Contract-amendment propagation (in-scope step)

Because the `seed` tier is being removed from a **binding** contract, the
amendment lands with this task rather than being left implicit:

- `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md` — contract
  **D**'s provenance enum.
- `aitasks/t1223/t1223_4_cross_repo_settings_seam.md` — its own AC (the
  "Resolution order" block and required test 11).
- `aitasks/t1223/t1223_5_settings_tab_and_push_action.md` — the marker table
  loses its `seed` row.
- `aitasks/t1223/t1223_6_syncer_scope_documentation.md` — a note to document the
  three-tier chain.

Task/plan files are committed with `./ait git`, separately from code.

## Files

- `.aitask-scripts/lib/config_utils.py` — prepare/commit atomic writer,
  `bundle=`/`merge=`, conflict walk, `ConfigMergeError` /
  `ConfigImportPartialError`, relocated + root-relative `MODEL_FILES` /
  `load_all_models`.
- `.aitask-scripts/lib/agent_model_picker.py` — re-export the two moved names.
- `.aitask-scripts/lib/agent_launch_utils.py` — additive keyword-only `env=` on
  `resolve_agent_string` (default preserves current behavior).
- `.aitask-scripts/settings/settings_app.py` — `_handle_import` reloads from disk
  on `ConfigImportPartialError` instead of assuming nothing changed.
- **New:** `.aitask-scripts/lib/cross_repo_settings.py`
- **New:** `tests/test_cross_repo_settings.py`

**Commit hygiene:** 59 unrelated files are modified in this worktree by a
concurrent session (skills / goldens); none overlap the four above. Stage only
these explicit paths.

## Considered and rejected

Replacing the `merge=True` + `overwrite=True` handshake with a single
`mode="skip"|"overwrite"|"merge"` parameter would remove the invalid
combination by construction. Rejected: contract **E** binds the `ValueError`
handshake explicitly, and the change would touch every existing `overwrite=`
call site for no behavioral gain.

## Out of scope

Any UI (`t1223_5`); any setting other than the default code agent per operation;
unifying the shortcuts shallow-merge with `deep_merge`; fsync/crash durability.

## Notes for sibling tasks

- **t1223_5** must render `provenance` / `conflict` and never re-derive the
  effective value. Its marker table **loses the `seed` row** — provenance is
  `local` / `project` / `builtin` / `conflict`.
- `plan_push` returning `masked` is **not** an error; the UI resolves it via the
  three-way prompt, then calls `apply_push` with the chosen layer / `clear_mask`.
- `diff_across_repos` keys by the same value as `AitasksSession.key` — index by
  `sess.key` directly.
- `apply_push` gives **per-destination** atomicity only; a multi-destination push
  that fails partway leaves earlier destinations applied. t1223_5 already reports
  per-destination outcomes, which is the right surface for that bound. It must
  also handle **`PushPartialError`** (project written, local mask not cleared) as
  its own outcome — the destination still uses the masking value and the row
  should invite a retry, not report success or plain failure.
- Never call `resolve_agent_string` for a *foreign* root without the §2.0 env
  scrub. `METADATA_DIR` / `TASK_DIR` / `DEFAULT_AGENT_STRING` are documented
  caller overrides that the subprocess inherits and that silently outrank `cwd`.
  Go through `cross_repo_settings`, which already does this.
- **t1223_6** should document the **three-tier** chain (local → project → builtin
  default) and state that `seed/` is a setup-time source, not a runtime tier. On
  a repo with a separate aitask-data branch a "project layer" write lands under
  `.aitask-data/` (git-tracked on that branch), so `git diff` in the
  destination's main checkout shows nothing.
