---
Task: t2163_discovery_non_utf8_config_crash.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2163 — Non-UTF-8 registry/config: tolerant discovery, fail-closed registry writers

## Context

`aitasks/metadata/project_config.yaml` and `~/.config/aitasks/projects.yaml` are
read with `open(..., encoding="utf-8")`, but `_resolve_config_project_group` and
`_parse_registry_records` (both in `.aitask-scripts/lib/agent_launch_utils.py`)
catch only `OSError`. Invalid UTF-8 raises `UnicodeDecodeError` (a
`ValueError`), and that error escapes from `discover_aitasks_sessions` in every
mode: plain, `include_registered=True`, and `_checked`. This is reported upstream
by aitasks_go#t17_4, a task in the other repository. The registry is read on
every discovery call, so one bad byte breaks monitor, stats, the TUI switcher,
syncer and agent_restore.

Found during planning and reproduced in scratch: every mutating `ait projects`
verb reads the registry with `tsv=$(list_registry_entries || true)`. On a
non-UTF-8 registry, Python prints a traceback, stdout is empty, and `|| true`
swallows the failure. The verb then **rebuilds the registry from nothing**. For
example, `ait projects add` dropped two existing entries and wrote back only the
new one. Fixing the readers alone would also remove the traceback, which is
currently the only warning. The user chose to fix both in this task:
**discovery stays tolerant, registry writers abort when the read fails, and a
test proves invalid UTF-8 leaves the registry byte-for-byte unchanged.**

Working mode: current branch (`main`), profile `fast`, no worktree.

## Step 1 — Tolerant Python readers (`.aitask-scripts/lib/agent_launch_utils.py`)

1. `_resolve_config_project_group` (≈L690):
   - Decode the **whole file** up front: `text = cfg.read_text(encoding="utf-8")`
     inside `try`, `except (OSError, UnicodeDecodeError): return None`. Then loop
     over `text.split("\n")` with the existing line logic (same universal-newline
     translation as the old file iteration; `split("\n")` instead of
     `splitlines()` so the line boundaries match the old loop exactly).
   - Why the whole file: the old loop `break`s at `project_group:`, and the
     text reader decodes in ~8 KiB chunks. Whether a bad byte raised therefore
     depended on where it fell relative to the chunk boundary. With a full
     decode, a file with any invalid byte always reads as "no project group",
     the same rule as the Go port.
   - Docstring: "Never raises — an unreadable or non-UTF-8 config is None."
2. `_parse_registry_records` (non-strict wrapper, ≈L735):
   `except (OSError, UnicodeDecodeError): return []`. Update the docstring: any
   read failure, **including non-UTF-8 content**, yields `[]`. A caller that must
   rule an entry out uses the strict reader instead.
3. `_parse_registry_records_strict`: **unchanged**. It keeps raising, and its
   docstring already says non-UTF-8 raises `ValueError`.
   `_cli_list_registry(strict=True)` already maps `(OSError, ValueError)` → exit
   3 with `registry unreadable: …` on stderr.
4. Update the two docstring mentions of `aitask_projects.sh::list_registry_entries`
   (≈L741, ≈L3129) to name the new bash helper (Step 2).

Effect: `discover_aitasks_sessions*` treats a non-UTF-8 registry as empty and a
non-UTF-8 config as having no group. `_checked` returns `(sessions, True)`
because its completeness flag covers tmux queries only. `--list-registry`
(non-strict) prints nothing and exits 0.

## Step 2 — Fail-closed registry reads in `.aitask-scripts/aitask_projects.sh`

Replace `list_registry_entries` (stdout-based, so a `die` inside `$( )` could
never stop the caller) with a helper that loads the registry into a global and
dies **in the calling shell**:

```bash
# Load the registry into REGISTRY_TSV (one name|path|git_remote|last_opened|
# project_group line per entry) through the strict Python reader. A missing
# registry is a definite empty answer; anything that exists but cannot be read
# — non-UTF-8 content, a directory, a dangling symlink, an I/O error — is fatal,
# because every mutating verb rebuilds the whole file from this read and an
# empty read would drop every entry. Pass --locked when the caller holds the
# registry mutex: it is released before dying.
load_registry_or_die() {
    local locked=0 rc=0 python_bin
    [[ "${1:-}" == "--locked" ]] && locked=1
    python_bin=$(resolve_python)
    REGISTRY_TSV=""
    if [[ -n "$python_bin" ]]; then
        REGISTRY_TSV=$(AITASKS_PROJECTS_INDEX="$REGISTRY_FILE" "$python_bin" \
            "$SCRIPT_DIR/lib/agent_launch_utils.py" --list-registry-strict) || rc=$?
    else
        rc=1
    fi
    if [[ "$rc" -ne 0 ]]; then
        [[ "$locked" -eq 1 ]] && registry_lock_release "$REGISTRY_LOCK_DIR"
        die "Cannot read the project registry $REGISTRY_FILE — left unchanged. Fix or remove it, then retry."
    fi
}
```

(The final code will avoid a trailing `[[ … ]] && …` as a function's last
command under `set -e`; the shape above is illustrative.) Python's own stderr
line (`registry unreadable: 'utf-8' codec can't decode byte …`) passes through
to the user unchanged.

Convert every reader in the script, writers and displays alike, so the old
helper disappears completely:

| site | change |
|---|---|
| `cmd_list` (`done < <(list_registry_entries)`) | **Call `load_registry_or_die` first**, then `done <<< "$REGISTRY_TSV"`. Move the friendly "No registered projects. Run `ait projects add` …" message to *after* the strict read, so it fires only when `REGISTRY_TSV` is empty **and** `[[ ! -e "$REGISTRY_FILE" && ! -L "$REGISTRY_FILE" ]]`. By then the strict reader has proven the path is either truly absent (`stat` and `lstat` both `FileNotFoundError`) or a readable regular file. A directory or dangling symlink can no longer pass the old `[[ ! -f ]]` early return and report success. |
| `cmd_add` (`tsv_in=…`, inside lock) | `load_registry_or_die --locked; tsv_in="$REGISTRY_TSV"` |
| `cmd_remove` pre-prompt read | `load_registry_or_die` |
| `cmd_remove` in-lock re-read | `load_registry_or_die --locked` |
| `cmd_update` (inside lock) | `--locked` |
| `cmd_prune`, `cmd_doctor` (pre-scan, no lock) | plain. Without this they would report "Found 0 stale entries." on an unreadable registry |
| `set_registry_group`, `rename_registry_group`, `group sync` (inside lock) | `--locked` |
| `group list` | plain |

Also refresh the comment block above the old helper (the t970 single-reader
note) so it describes the new helper.

Behaviour change to note: a registry path that exists but is not a regular,
UTF-8-readable file now makes every `ait projects` verb fail. Before, a
directory or dangling symlink silently read as empty. The bootstrap
`ait projects add` in `lib/tmux_bootstrap.sh` runs as `… >/dev/null 2>&1 || true`,
so it now just skips its refresh. The lock is released, so nothing is left
wedged.

## Step 3 — Tests

**Python**
- `tests/test_project_groups.py` `ConfigGroupReadTests`:
  - a config with an invalid byte before `project_group:` → `None`;
  - a valid `project_group: suite_a` line followed by more than 8 KiB of padding
    and then an invalid byte → `None`. This pins the whole-file rule; on the
    old code the early `break` returned `suite_a` (or raised, depending on the
    chunk boundary).
- `tests/test_discover_include_registered.py` (new test methods, existing
  fixture and tmux-mock pattern):
  - non-UTF-8 registry: `_parse_registry_records()` → `[]`;
    `_parse_registry_records_strict()` raises `UnicodeDecodeError`;
    `discover_aitasks_sessions(include_registered=True)` → `[]` and does not
    raise; `discover_aitasks_sessions()` and `discover_aitasks_sessions_checked()`
    do not raise (the latter returns `([], True)`);
  - a live session (using the existing mocked `list-sessions` pattern from the
    live-dedupe tests) whose repo config is non-UTF-8: the session is returned
    with `project_group is None`, through both plain and `_checked` discovery.

**Bash — new `tests/test_projects_unreadable_registry.sh`** (self-contained,
`tests/lib/asserts.sh`, scratch `AITASKS_PROJECTS_INDEX`, fake projects as in
`test_projects_cmd.sh`):
- Three unreadable-registry fixture shapes, each rebuilt fresh before every
  verb:
  - **non-UTF-8**: a file with two entries and one invalid byte
    (`printf '\xe9'`), plus a pristine copy kept for comparison;
  - **directory** at the registry path, holding a sentinel file;
  - **dangling symlink** at the registry path.
- For each shape × each verb (`add <proj>`, `remove <name> --force`,
  `update <name> <proj>`, `prune --yes`, `doctor` (stdin `k`), `group set`,
  `group unset`, `group rename`, `group sync`, `list`, `group list`):
  - the exit status is non-zero;
  - stderr contains `Cannot read the project registry`;
  - the path is unchanged, checked per shape: non-UTF-8 → `cmp` against the
    pristine copy (**byte-for-byte unchanged**); directory → still a directory
    whose only entry is the sentinel; dangling symlink → still a symlink with the
    same `readlink` target and still dangling;
  - no `projects.yaml.lockd` is left behind.
- **Mid-confirmation corruption for `cmd_remove`'s in-lock re-read.** A corrupt
  start dies at the first read, so the matrix above never reaches the second,
  locked read. Steps:
  - start from a **valid** registry and run `remove alpha` (no `--force`) in the
    background, with stdin from a FIFO and stderr to a file;
  - open the FIFO's write end, then poll the stderr file (bounded, ~10 s) for
    `Remove 'alpha' from registry? [y/N]:`;
  - only then overwrite the registry with the non-UTF-8 bytes (keeping a copy),
    write `y` and close the FIFO;
  - assert the process exits non-zero, stderr carries the cannot-read message,
    the registry `cmp`-equals the corrupted bytes (not rewritten), and the lock
    dir is gone (the `--locked` release ran).

  A timed-out poll is reported as a FAIL, never a skip.
- Python CLI contract: `--list-registry` exits 0 with empty stdout;
  `--list-registry-strict` exits 3.
- Positive control: the same registry without the bad byte → `add` succeeds
  and both old entries survive. This proves the fixture is not failing for some
  unrelated reason.
- **Red proof** (recorded in Final Implementation Notes, not committed): copy
  the new test to scratch, point it at `git show HEAD:` copies of the two
  changed files, and show that it fails there.

## Step 4 — Verification

```bash
python3 tests/test_project_groups.py
python3 tests/test_discover_include_registered.py
bash tests/test_projects_unreadable_registry.sh
for t in test_projects_cmd test_aitask_projects_remove test_aitask_projects_update \
         test_aitask_projects_prune test_aitask_projects_doctor test_registry_reader_parity \
         test_registry_concurrency test_registry_cas test_project_resolve test_project_resolve_list \
         test_create_project_flag; do bash tests/$t.sh || echo "FAILED: $t"; done
python3 tests/test_settings_project_groups_tab.py
shellcheck .aitask-scripts/aitask_projects.sh
bash tests/run_all_python_tests.sh --test-dir tests   # last line = verdict
```

Also grep `website/content/` for `ait projects` text that describes an
unreadable registry, and update it only if such text exists.

## Step 9 — Post-Implementation

Standard archival per task-workflow Step 9 (current branch, no merge).

## Risk

### Code-health risk: medium
- The bash change touches 11 call sites in `aitask_projects.sh`, including the
  hot bootstrap `add` path, and a missed or mis-flagged site would either keep
  the wipe or leak the mutex. · severity: medium · → mitigation: covered by the
  plan's own tests. The Step 3 shape × verb matrix reaches every converted site
  whose read comes **first** in its verb. `cmd_remove`'s second, in-lock read
  can only be reached by corrupting the registry after its first read, which is
  exactly what the dedicated mid-confirmation test does. The existing per-verb
  suites run in Step 4.
- Behaviour change: a directory or dangling-symlink registry, which used to read
  as empty, is now fatal for every verb. · severity: low · → mitigation: none
  needed (deliberate fail-closed choice; bootstrap callers already swallow the
  failure)

### Goal-achievement risk: low
- None identified. Discovery tolerance follows the task's suggested fix, and the
  writer requirement is pinned by a byte-for-byte test with a red proof.
