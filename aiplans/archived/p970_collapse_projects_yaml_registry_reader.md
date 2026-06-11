---
Task: t970_collapse_projects_yaml_registry_reader.md
Base branch: main
plan_verified: []
---

# Plan: Collapse projects.yaml registry file-reader to a single Python authority (t970)

## Context

`~/.config/aitasks/projects.yaml` (the per-user cross-repo project registry) is
currently parsed by **four** near-identical hand-rolled parsers:

1. `aitask_projects.sh::list_registry_entries` (157-207) — full **4-field**
   reader (`name|path|git_remote|last_opened`); feeds the registry **read +
   write** round-trip (add/remove/update/prune/doctor) via `build_registry_yaml`.
2. `aitask_project_resolve.sh::index_lookup_path` (160-205) — single-name
   path lookup on the **resolve hot path**.
3. `aitask_project_resolve.sh::cmd_list` (77-119) — name+path reader for the
   `list` verb (emits `PROJECT:<name>:<path>:<status>`).
4. `agent_launch_utils.py::_read_registry_index` (258-317) — **3-field**
   `(name, path, status)` reader for `discover_aitasks_sessions`.

Four awk/python copies of the same YAML grammar = drift risk. The goal (split
out of t952_5, scope item 4) is **one Python file-reader authority**, exposed via
a thin CLI, with bash shelling out to it — **no behavior change**. Only the file
reader is duplicated; the live-tmux scan is already single-authority Python.

**Decisions locked (plan-time):**
- **Full Python authority** — Python parses and emits all 4 raw fields; both read
  AND write paths shell out; `build_registry_yaml` stays in bash. Maximal dedup.
- **Resolve hot path: measure-then-decide** — benchmark `index_lookup_path`
  before/after; keep a lean bash reader (guarded by a parity test) only if the
  Python shell-out measurably regresses resolve latency.

### The critical parity gap (main risk)

`_read_registry_index` **requires both name AND path** and emits a *computed*
`OK/STALE` status. Bash `list_registry_entries` **emits on name alone** with 4
*raw* fields, and that raw output round-trips through the registry **write** path
(add/remove/update re-serialize the whole file). A naive shell-out to the
existing 3-field Python reader would **drop `git_remote` + `last_opened` on every
mutation** (silent data loss) and **change emit semantics** for name-only
entries. So the CLI needs a *new* bash-parity raw parser, distinct from
`_read_registry_index` (which is preserved verbatim for the discover path).

## Approach

### 1. Python: new raw parser + CLI surface (`agent_launch_utils.py`)

**a. Add `_parse_registry_records()`** — the single bash-parity reader:

```python
def _parse_registry_records() -> list[tuple[str, str, str, str]]:
    """Parse projects.yaml into raw (name, path, git_remote, last_opened) tuples.

    Bash-parity reader for aitask_projects.sh::list_registry_entries: emits an
    entry as soon as a `- name:`/indented `name:` is seen (path/remote/last may
    be empty), matching the bash awk emit() rule. Honors AITASKS_PROJECTS_INDEX.
    Distinct from _read_registry_index(), which additionally requires a non-empty
    path and annotates OK/STALE for the discover path.
    """
```

Tracks `cur_name/cur_path/cur_remote/cur_last`; `_flush()` emits whenever
`cur_name` is non-empty. Reuses the existing `_unquote` + the same line grammar
(`- name:`, indented `name:`, `path:`, `git_remote:`, `last_opened:`, skip
comments/blanks). Index path from `AITASKS_PROJECTS_INDEX` or `~/.config/aitasks/projects.yaml`; missing file → `[]`.

**b. Refactor `_read_registry_index()` to delegate** — preserve its exact
contract (used by `discover_aitasks_sessions:426` and `test_discover_*`):

```python
def _read_registry_index() -> list[tuple[str, Path, str]]:
    out = []
    for name, path, _remote, _last in _parse_registry_records():
        if not (name and path):          # original required name AND path
            continue
        p = Path(path)
        status = "OK" if (p / "aitasks" / "metadata" / "project_config.yaml").is_file() else "STALE"
        out.append((name, p, status))
    return out
```

File order + name-AND-path filter + OK/STALE classification are identical to
today → `discover_aitasks_sessions` and its tests are unaffected.

**c. Add a thin CLI** (`if __name__ == "__main__":`, argparse, stdlib only):
- `--list-registry` → one `name|path|git_remote|last_opened` line per record
  (raw, empty fields preserved) — byte-identical to bash `list_registry_entries`.
- `--resolve-index NAME` → print the path of the **first** record whose name
  matches and whose path is non-empty, else nothing — matches `index_lookup_path`.

Naming note: task suggested `--resolve`, but the verb only does the **index-file**
lookup (not the full tmux→index→env resolve), so `--resolve-index` is the
scope-honest name. Running the module directly puts `lib/` on `sys.path[0]`, so
the top-level `tui_registry` / `tmux_exec` imports resolve; the CLI touches
neither tmux nor Textual.

### 2. Bash: shell out (`aitask_projects.sh`)

Replace the `list_registry_entries` awk body with a Python shell-out:

```bash
list_registry_entries() {
    [[ -f "$REGISTRY_FILE" ]] || return 0
    local python_bin; python_bin=$(resolve_python) || return 0
    [[ -n "$python_bin" ]] || return 0
    AITASKS_PROJECTS_INDEX="$REGISTRY_FILE" "$python_bin" \
        "$SCRIPT_DIR/lib/agent_launch_utils.py" --list-registry
}
```

**Silent-wipe guard (deliberate, load-bearing).** Today the parser is pure bash;
shelling out makes a missing interpreter return empty, and because callers use
`tsv=$(list_registry_entries || true)`, an empty read would make `cmd_add`
rebuild the file with only the new entry and `cmd_remove/update` mis-fire —
**silent data loss**. Fix: add `require_python >/dev/null` as the **first line of
each mutating verb** (`cmd_add`, `cmd_remove`, `cmd_update`, `cmd_prune`,
`cmd_doctor`). `require_python` runs in the main shell (not a swallowed
subshell), so a missing interpreter **aborts loudly before any read-modify-write**
instead of wiping the registry. `cmd_list` (read-only display) degrades to empty
without dying. This is an intentional, documented behavior change: registry
*mutation* now requires Python — acceptable since resolve already hard-depends on
Python for the tmux scan. `build_registry_yaml` and `atomic_write` are untouched.

### 3. Bash: shell out (`aitask_project_resolve.sh`)

- **`cmd_list` (77-119)** → consume `--list-registry`, compute `RESOLVED/STALE`
  in bash via the existing `path_is_aitasks_project`, emit the unchanged
  `PROJECT:<name>:<path>:<status>` lines. Removes the 3rd duplicate parser.
- **`index_lookup_path` (160-205) → measure-then-decide:**
  1. Benchmark first (see Verification). 2. If the shell-out adds no meaningful
  per-call latency, replace the awk body with `--resolve-index`. 3. If it
  measurably regresses resolve, **keep the lean bash awk reader** and add a
  parity test pinning it byte-identical to `--resolve-index`. Record the numbers
  in the plan's Final Implementation Notes either way — do not regress silently.

Resolver output contracts (`RESOLVED:`/`STALE:`/`NOT_FOUND:`/`PROJECT:`) stay
byte-identical — they are consumed by `aitask_update.sh:1844`, `cmd_exec`, etc.

### 4. Golden-corpus parity test (`tests/test_registry_reader_parity.sh`)

Fixture `projects.yaml` exercising every grammar case: double/single/unquoted
values, all-4-fields entry, name+path-only, name+path+remote (no last), `- name:`
list form vs indented `name:`, comment + blank lines, leading/trailing
whitespace, a stale-path entry (no marker), and a **name-only** entry (the
emit-on-name divergence). Set `AITASKS_PROJECTS_INDEX` to the fixture. Assert:
- `--list-registry` output == a **frozen golden block** captured from the
  *pre-change* bash `list_registry_entries` (byte-for-byte).
- `--resolve-index <name>` == `index_lookup_path <name>` for present / absent /
  stale-path / name-only names.
- **Round-trip:** `ait projects add` a new entry into a temp copy, then
  `remove`/`update` another — assert the untouched entries' `git_remote` +
  `last_opened` **survive** (the data-loss regression guard).
- `AITASKS_PROJECTS_INDEX` override honored.

The golden is generated by running today's bash readers against the fixture and
freezing their output as the expected literal (the "pre-change baseline").

## Files to modify

- `.aitask-scripts/lib/agent_launch_utils.py` — add `_parse_registry_records`,
  refactor `_read_registry_index` to delegate, add `__main__` CLI.
- `.aitask-scripts/aitask_projects.sh` — `list_registry_entries` shell-out +
  `require_python` guards in the 5 mutating verbs.
- `.aitask-scripts/aitask_project_resolve.sh` — `cmd_list` shell-out;
  `index_lookup_path` per measurement.
- `tests/test_registry_reader_parity.sh` — new golden-corpus + round-trip test.

## Out of scope / unaffected (verified)

`aitask_update.sh`, `aitask_query_files.sh`, `aitask_find_by_file.sh`,
`aitask_ls.sh` only call the **resolver** (no own parser). `tui_switcher.py` uses
`discover_aitasks_sessions` → `_read_registry_index` (semantics preserved). No
other production parser of `projects.yaml` exists.

## Verification

1. **Latency benchmark** (drives the §3 decision): `time` ~200 iterations of
   `aitask_project_resolve.sh <name>` for a name that misses the tmux scan (hits
   `index_lookup_path`), before vs. after. Record ms/call delta; threshold for
   keeping bash ≈ a measurable regression (>~20-30ms/call).
2. `bash tests/test_registry_reader_parity.sh` (new) — golden + round-trip pass.
3. Regression suite still green:
   `tests/test_project_resolve.sh`, `test_project_resolve_list.sh`,
   `test_projects_cmd.sh`, `test_aitask_projects_{update,remove,prune,doctor}.sh`,
   `test_discover_include_registered.py`, `test_discover_default_unchanged.py`.
4. `shellcheck .aitask-scripts/aitask_projects.sh .aitask-scripts/aitask_project_resolve.sh`.
5. Manual smoke: `ait projects list/add/remove/update` against a scratch
   `AITASKS_PROJECTS_INDEX`, confirming `git_remote`/`last_opened` round-trip and
   identical user-facing output.

Step 9 (Post-Implementation) handles cleanup, archival, and merge.

## Risk

### Code-health risk: medium
- Byte-parity divergence between the new Python reader and the bash awk parsers (quoting, emit-on-name-only, whitespace handling) would silently change registry read behavior · severity: medium · → mitigation: golden-corpus byte-for-byte test (in-plan deliverable §4)
- Shell-out makes a missing Python interpreter return empty; with the `tsv=$(... || true)` callers this could silently wipe the registry on mutation · severity: medium (high impact, but guarded) · → mitigation: `require_python` abort-loud guard at the top of every mutating verb (in-plan §2)

### Goal-achievement risk: low
- None identified. The one open variable (resolve-hot-path latency) is bounded by the measure-then-decide branch — both outcomes (shell-out or keep-bash-with-parity-guard) deliver "single authority" without regressing resolve.

_Mitigations for the code-health risks are intrinsic deliverables of this task
(the golden-corpus/round-trip test and the `require_python` guard), not separate
before/after follow-up tasks — so no standalone risk-mitigation tasks are
proposed._

## Final Implementation Notes

- **Actual work done:**
  - `lib/agent_launch_utils.py`: added `_parse_registry_records()` — the single
    bash-parity raw 4-field reader (the registry-file authority); refactored
    `_read_registry_index()` into a thin delegating annotator over it (kept its
    exact name-AND-path + OK/STALE contract); added a stdlib `__main__` CLI with
    `--list-registry` (raw `name|path|git_remote|last_opened`) and
    `--resolve-index NAME` (first-match path).
  - `aitask_projects.sh`: `list_registry_entries` now shells out to
    `--list-registry`; added `require_python >/dev/null` guard to all 5 mutating
    verbs (add/remove/update/prune/doctor).
  - `aitask_project_resolve.sh`: `cmd_list` shells out to `--list-registry`;
    `index_lookup_path` kept as lean bash (see Key decisions) with a parity-lock
    comment.
  - `tests/test_registry_reader_parity.sh`: new golden-corpus + round-trip test
    (27 assertions).

- **Deviations from plan:** None in shape. The plan's "measure-then-decide" for
  the resolve hot path resolved to **keep bash** (numbers below). Also collapsed
  the third duplicate (`aitask_project_resolve.sh::cmd_list`, not named in the
  original task scope) to the Python authority, as anticipated in plan §3 — it is
  not on the resolve hot path (backs the one-shot project picker in
  `aitask_create.sh:825`).

- **Issues encountered:** During guard verification, an initial `env -i
  PATH=/nonexistent` simulation hid `bash` itself (exit 127) rather than just
  `python3`; re-ran with a curated PATH (coreutils symlinks, no `python3`) and an
  empty `HOME` to genuinely exercise the missing-interpreter path. Confirmed:
  loud abort (exit 1, "No Python interpreter found"), registry left intact.

- **Key decisions:**
  - **Full Python authority** (chosen at plan time): both read and write paths
    read through Python; `build_registry_yaml` stays in bash. The critical parity
    gap (Python's `_read_registry_index` returned only 3 fields and *skipped*
    name-only entries; bash emitted 4 raw fields and emits on name alone) is why
    `_parse_registry_records` is a *new* parser, not a reuse of
    `_read_registry_index`.
  - **Silent-wipe guard:** because the shell-out makes a missing interpreter
    return empty and callers use `tsv=$(... || true)`, an empty read could wipe
    `git_remote`/`last_opened` on mutation. Closed by an up-front `require_python`
    in each mutating verb (runs in the main shell, so it aborts loudly before any
    read-modify-write). This is an intentional behavior change: registry
    *mutation* now requires Python (resolve already hard-depends on it).
  - **Resolve hot path kept in bash (latency):** measured (N=100) Python
    `--resolve-index` ≈ **53.3ms/call** vs bash awk ≈ **3.8ms/call** (incl. bash
    startup; sub-ms within an already-running resolve); end-to-end resolve ≈
    **59.6ms/call**. A shell-out would add a second interpreter startup and ~double
    resolve latency, so `index_lookup_path` stays bash, pinned byte-identical to
    `--resolve-index` by the new parity test.

- **Upstream defects identified:** None.

- **Verification results:** new parity test 27/27; regression suites
  (`test_project_resolve{,_list}`, `test_projects_cmd`,
  `test_aitask_projects_{update,remove,prune,doctor}`, 9 cross-repo/xdeps tests,
  `test_discover_include_registered`, `test_discover_default_unchanged`) all pass;
  `shellcheck` clean (only benign SC1091 source-info); `py_compile` OK;
  missing-interpreter guard verified (abort, no wipe).
