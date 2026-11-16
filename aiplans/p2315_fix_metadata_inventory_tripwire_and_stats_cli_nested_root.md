---
Task: t2315_fix_metadata_inventory_tripwire_and_stats_cli_nested_root.md
Base branch: main
Output branch: main
---

# t2315 — Fix the metadata-inventory tripwire and the stats CLI nested-root read

## Context

Two upstream defects were found while reviewing t1912_4:

1. `tests/test_metadata_writer_inventory.py::NewWriterTripwire::test_no_unclassified_file_writes_metadata`
   fails at HEAD and flags `.aitask-scripts/lib/sitrep_crash.py`.
2. `aitask_model_stats.py export` / `show`, run from a nested directory without
   `--root`, read the legacy `models_<agent>.json` registry under the raw cwd
   and show branch-only counters.

### Findings (verified during planning)

**Tripwire.** The scan works per file. A file is flagged when it both names a
metadata path (`_TARGETS_METADATA`) and contains any write primitive
(`_PY_WRITE`). In `sitrep_crash.py` the two hits are unrelated:
- metadata reference: `os.path.join(root, "aitasks", "metadata", "gates.yaml")`
  (lines ~726 and ~850). This is a **read** of the gate registry, passed to
  `gate_ledger.read_task_gate_state(registry_file=...)`.
- write: `pause_point()`, `open(fifo + ".reached", "w")`. This is a test-only
  pause seam (`AITASK_SITREP_CRASH_PAUSE_FIFO`) that writes a sidecar next to a
  caller-supplied fifo. Every durable write goes through the sitrep store
  (`.aitask-sitrep`, `sitrep_store`).

**The task got the culprit commit wrong.** Both lines already exist at
`f9b5888cd` (t2299_2, the commit that added the file). t2307 (`87ecc9799`)
changed only the status-validation helpers. So the tripwire has been red since
t2299_2. Neither archived plan (p2307, p2299_2) mentions the inventory.
Nothing under `aitasks/metadata` is written. The right fix is a
`PINNED_FILES` entry with a reason, the same as `lib/agent_freeze.py` and
`lib/relations_store.py`. The file needs no `WIRED` or `KNOWN_UNCOMMITTED`
entry and no move.

**Stats nested root.** `_branch_content`, `branch_state` and `update` already
resolve `project_root` to `ors.toplevel` (via the cached `_layout`). But
`legacy_models` and `load_all_stats` build `metadata_dir(project_root)` from the
raw path. From `<repo>/website` the branch therefore comes from the repository
but the legacy registry is looked for at `<repo>/website/aitasks/metadata`, and
there is no file there. This affects a defaulted `--root` (cwd) and an
explicit nested `--root` alike. The only production callers are `cmd_export` and
`cmd_show`. `overlay` is unaffected: its legacy counters are the rows of the
`--file` it was given. `effective_total` already passes the toplevel (fixed by
t1912_4).

## Approach

Fix it in the store, not only in the CLI's `main()`. The legacy registry is
read under the same root the branch read uses. That makes the loader
self-consistent for every caller and for explicit nested `--root` values, which
a defaulted-root-only fix in `main()` would miss. It also keeps the store
consistent with `update()` and with t1912_4's `effective_total` fix.

## Steps

### 1. Classify `sitrep_crash.py` — `tests/test_metadata_writer_inventory.py`

Add to the `PINNED_FILES` extra set, next to `lib/agent_freeze.py` /
`lib/relations_store.py`, with a reason comment:

```python
    # Reads `aitasks/metadata/gates.yaml` (the gate registry, passed to
    # gate_ledger.read_task_gate_state) and writes nothing under it. Its only
    # write primitive is pause_point()'s `<fifo>.reached` sidecar, a test-only
    # seam (AITASK_SITREP_CRASH_PAUSE_FIFO); every durable write goes through
    # the sitrep store (.aitask-sitrep). Unclassified since it was added in
    # t2299_2 (f9b5888cd); classified in t2315.
    ".aitask-scripts/lib/sitrep_crash.py",
```

### 2. Resolve the registry root in the store — `.aitask-scripts/lib/model_stats_store.py`

Add one helper next to `metadata_dir`:

```python
def _registry_root(project_root):
    """The root ``models_<agent>.json`` is read under: the same toplevel the
    branch read uses (``_layout``), so a nested directory reads its
    repository's registry, not ``<nested>/<TASK_DIR>/metadata``. Outside a git
    work tree there is no toplevel, so the raw root is used (legacy-only
    reads keep working there)."""
    try:
        return _layout(project_root)[0]
    except (ors.GitError, OSError):
        return project_root
```

Use it in the two places that derive the registry path from `project_root`.
An explicit `metadata_path` stays verbatim, because `metadata_dir` ignores
the root when it is given:
- `legacy_models`: `metadata_dir(_registry_root(project_root), metadata_path)`.
  Skip the resolve when `metadata_path is not None` so cross-repo callers make
  no git call.
- `load_all_stats`: same for `meta`.

`metadata_dir` itself stays a pure path function, and its docstring is
unchanged. `effective_total` already passes `top`. Resolving it again is a
cached no-op, and its strict-mode semantics are unchanged (an un-gitted root
cannot reach it, because `toplevel` is called first and raises
`TotalUnavailable`). Update the comment in `effective_total` to say the loader
now uses the same rule.

`_layout` resolves the toplevel and also `git_common_dir`. Both already run for
the branch read on every loader call, so this adds no new git subprocesses.

### 3. Docstring — `.aitask-scripts/aitask_model_stats.py`

Header sentence "Every verb takes --root (default: the current directory)"
gains: "a directory inside a repository means that repository: the stats branch
and the legacy `models_<agent>.json` registry are both read at its toplevel."
No other user-facing docs mention this CLI (checked `website/content`,
`aidocs`).

### 4. Tests — `tests/test_model_stats_store.py`

In `TestLoader` (store level), add
`test_nested_root_reads_the_repository_registry`:
- `root = self.repo("p", remote=False)`, `write_legacy(root, …usage_entry(4))`,
  `self.bump(root)`, then `nested = root / "website" / "deep"; nested.mkdir(parents=True)`.
- Assert `self.runs(nested) == 5 == self.runs(root)`. Before the fix
  `runs(nested)` is `1` (branch only), which is the pre-fix control.
  This covers `legacy_models`.
- **`load_all_stats` listing: needs an agent reachable ONLY through the
  root-level registry listing.** `load_all_stats` discovers agents as branch
  agents ∪ markers ∪ the `models_*.json` listing, so `claudecode` (which is on
  the branch) is found even when the listing is unfixed. Add
  `write_legacy(root, [{"name": "gpt5", "usagestats": {"pick": usage_entry(7)}}], agent="codex")`
  with **no** codex branch data and no migration marker. Then assert
  `mss.load_all_stats(nested)["codex"]["gpt5"]["usagestats"]["pick"]["all_time"] == {"runs": 7}`
  and `set(mss.load_all_stats(nested)) == {"claudecode", "codex"}`. Pre-fix
  control: with only `legacy_models` fixed, `codex` is absent from the nested
  result. That fails this assertion, which is what makes it a real test of the
  listing.

In `TestEffectiveTotal` (CLI level, beside
`test_nested_cwd_without_root_reads_the_repository_registry`), add
`test_nested_cwd_export_and_show_read_the_repository_registry`:
- `root = self.repo(...)`, `self.legacy_rating(root)` (1 run, 20), one `self.rate(root, 5)`
  (`--root` given) so the branch has 1 run of 100.
- `chdir(nested)` (try/finally restore), then:
  - `export --agent claudecode` with no `--root`: the JSON's
    `models.opus.verifiedstats.pick.all_time == {"runs": 2, "score_sum": 120}`
    (pre-fix: `{"runs": 1, "score_sum": 100}`).
  - `show` with no `--root`: the output contains the line
    `claudecode/opus verifiedstats pick all_time=2 avg=60`.
  - Also seed a **legacy-only** agent in the root registry
    (`write_legacy(root, [{"name": "gpt5", "usagestats": {"pick": usage_entry(7)}}], agent="codex")`,
    no branch data, no marker). `show` from the nested cwd must contain
    `MARKER:codex:no` and `codex/gpt5 usagestats pick all_time=7`. This protects
    the visible behaviour of the `load_all_stats` listing. Pre-fix, both lines
    are missing.
- The `_layout_cache` keys are per realpath, so no cache reset is needed between
  the root and the nested reads.

The existing `test_git_failure_reads_as_legacy_only` (a non-git dir still
reads its own registry) keeps the fallback branch covered. It must stay green.

### 5. Verification

```bash
python3 -m pytest -q tests/test_metadata_writer_inventory.py      # was 1 failed → all pass
python3 -m pytest -q tests/test_model_stats_store.py              # new tests pass, existing unchanged
```
Pre-fix controls, attributed per assertion. Run the new tests in three states:
(a) no step-2 change: every new nested assertion fails. (b) only
`legacy_models` fixed: the claudecode runs/export/show assertions pass, and the
codex assertions (store `load_all_stats` and `show` lines) **still fail**.
(c) both fixed: everything passes. State (b) is what proves the codex
assertions really exercise the listing path. Make these checks with temporary
edits that are reverted by hand (never `git stash`/`git restore` in this shared
worktree).
Then the stats-adjacent suites that consume the loader or CLI:
```bash
grep -rl "aitask_model_stats\|model_stats_store" tests/ | xargs -n1 echo   # run each listed file
bash tests/run_all_python_tests.sh --test-dir tests 2>&1 | tail -3; echo "exit=${PIPESTATUS[0]}"
```
(Read only the final `PYTHON SUITE:` verdict. Pre-existing unrelated failures
are reported as such and not fixed here.)

### 6. Step 8e: note

t2299 (parent Ready, children t2299_3/t2299_4 pending) owns `sitrep_crash.py`'s
area. Offer a note at Step 8e. If a later child adds a real write under
`aitasks/metadata` to `sitrep_crash.py`, the new `PINNED_FILES` entry would hide
it, so that child must reclassify it as `WIRED` or `KNOWN_UNCOMMITTED`.

### Step 9 (Post-Implementation)

Commit the code (`bug: … (t2315)`) and then the plan via the scoped helpers.
Archive per the workflow.

## Risk

### Code-health risk: low
- Loader semantics change for a non-toplevel `project_root`. A non-git
  directory nested inside some enclosing repo now reads that repo's registry,
  not its own. This matches where the branch was already read from, so the
  result is now self-consistent, not newly wrong. Non-git roots outside any
  repo keep the raw-root fallback. · severity: low · → mitigation: covered in-plan (step 4 tests + existing `test_git_failure_reads_as_legacy_only`)
- A `PINNED_FILES` entry is file-scoped. A future real metadata write added to
  `sitrep_crash.py` would not trip the wire (the residue the inventory's own
  docstring names). · severity: low · → mitigation: covered in-plan (reason comment + Step 8e note to t2299)

### Goal-achievement risk: low
None identified.
