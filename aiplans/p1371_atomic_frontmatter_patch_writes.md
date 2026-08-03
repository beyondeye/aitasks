---
Task: t1371_atomic_frontmatter_patch_writes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1371 — Atomic frontmatter patch writes

## Context

`.aitask-scripts/lib/frontmatter_patch.py` rewrites a task file with a plain
`open(path, "w")` in both `cmd_append` (:214) and `cmd_remove` (:238).
`open(…, "w")` **truncates before any bytes are written**, so a concurrent
reader can observe the file empty or cut mid-YAML.

This is not theoretical. t1365 moved `ait board`'s By-Trail discovery from the
board-startup snapshot to a live disk read, and a board scan racing `ait
artifact new` (which patches the owning task's `artifacts:` block through this
script) sees one of two broken states — `parse_frontmatter` **raises** on a
mid-YAML cut, and returns **`None`** on a zero-byte/delimiter-truncated one.
t1365 hardened that one *reader*; the *write* site is still non-atomic and every
other frontmatter reader remains exposed with no such guard.

Intended outcome: a reader of a task file patched by `frontmatter_patch.py`
observes either the complete old file or the complete new one — never a partial
state.

**Scope decision (confirmed):** fix `frontmatter_patch.py` only. A survey found
several other non-atomic task/plan writers; they are recorded as upstream
defects for the Step 8b follow-up offer, not fixed here.

**Coordination with t1281.** t1281 (`Ready`, refactor) already exists to unify
the framework's duplicated atomic-write implementations. Rather than add yet
another copy, this task creates the shared seam t1281 will consolidate onto, and
updates t1281 to match. t1371 does **not** depend on t1281 — it lands first and
shrinks it.

## Approach

### 1. New `.aitask-scripts/lib/atomic_write.py` (stdlib only)

Semantics copied from `config_utils._prepare_atomic` / `_commit_atomic` /
`_atomic_write` (`lib/config_utils.py:175-226`), which t1281 already names "the
natural base". Stdlib-only on purpose: `frontmatter_patch.py` is deliberately
yaml-free (it is line-based precisely to avoid a YAML round-trip), so importing
`config_utils` — which does `import yaml` at module level — is not acceptable.

```python
#!/usr/bin/env python3
"""atomic_write.py - temp-file + os.replace file writes (t1371)."""
import os
import stat
import tempfile
from os import replace as _os_replace   # aliased so tests can patch the seam

# Probed once at import: reading the umask needs os.umask(0) + restore, which is
# process-global — doing it per write would hand another thread a mode-0 window
# in the Textual TUIs. Mirrors config_utils.
_UMASK = os.umask(0)
os.umask(_UMASK)

def target_mode(path):      # the target's own mode, else 0o666 & ~umask
def discard(tmp):           # best-effort unlink
def prepare(path, render):  # makedirs; mkstemp beside target; fchmod to
                            # target_mode; render(fh); discard+raise on
                            # BaseException; returns tmp path
def commit(tmp, path):      # _os_replace, discard+raise on BaseException
def atomic_write(path, render):
    resolved = os.path.realpath(path)
    commit(prepare(resolved, render), resolved)
def atomic_write_text(path, text):
    atomic_write(path, lambda fh: fh.write(text))
```

Four properties are load-bearing and each gets a test:

- **`realpath` first.** `open(path, "w")` follows a symlink; `os.replace` would
  replace the *link*, orphaning the real backing file while reads keep
  succeeding. (`aitasks/` is a symlink into `.aitask-data/` on data-branch
  checkouts.)
- **Mode preservation** via `os.fchmod`. `mkstemp` creates 0600; without this a
  rewrite silently downgrades a 0644 task file.
- **Temp beside the target**, so the rename is same-filesystem and cannot
  degrade to copy+rename.
- **`discard` on `BaseException`**, so a failed write leaves the original intact
  and no `.tmp` residue.

**Explicitly no `fsync`** — this is atomic *visibility*, not crash durability,
matching all existing implementations. Said so in the docstring rather than
leaving "atomic" ambiguous (t1281 asks for exactly this).

#### Stable API contract (what t1281 migrates onto)

Pinned now so the later migration targets a fixed shape rather than a moving
one. `prepare` / `commit` are public because
`config_utils.import_all_configs` stages several files before any becomes
visible and needs that split when it is re-pointed here.

| symbol | signature | guarantee |
|---|---|---|
| `atomic_write(path, render)` | `render` is called with an open text-mode fh | after return, `path` holds exactly what `render` wrote; on any exception `path` is byte-identical to before and no temp survives |
| `atomic_write_text(path, text)` | — | one-shot wrapper over `atomic_write` |
| `prepare(path, render)` | → temp path | temp is beside `path`, mode already `target_mode(path)`; raises with no residue |
| `commit(tmp, path)` | — | `os.replace`; raises with no residue |
| `target_mode(path)` | → int | `path`'s own mode, else `0o666 & ~umask` |
| `discard(tmp)` | — | best-effort unlink, never raises |

Not in the contract: `fsync`/durability, writer serialization (see *Concurrency
contract* below), and directory-entry durability.

#### This is intentional transitional duplication

Until t1281 runs, `lib/atomic_write.py` is a **new, independently maintained
implementation alongside the 7+ existing ones** — the count of distinct atomic
-write semantics in the tree goes *up* by one, not down. Nothing enforces that
the others converge on it. That is accepted deliberately:

- The alternative (importing `config_utils`) forces pyyaml onto a
  deliberately stdlib-only CLI; the other alternative (a private copy inside
  `frontmatter_patch.py`) produces the same +1 with no migration target.
- Consolidation is real work with its own decisions (fsync policy,
  `gate_ledger`'s non-`O_EXCL` temp naming, `skill_template`'s missing cleanup)
  and belongs to t1281, which already owns it.
- The API above is pinned so t1281 is a re-pointing exercise, not a redesign.

Step 4 records the link in t1281 so the duplication has a named owner rather
than relying on someone rediscovering it.

### 2. Route `frontmatter_patch.py` through it

Add the standard lib-dir bootstrap used across `.aitask-scripts/lib/` (e.g.
`lib/gate_registry_sync.py:39-41`) — the module currently imports only `re` and
`sys` and has no bootstrap:

```python
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atomic_write import atomic_write_text  # noqa: E402
```

Then replace both write blocks (`:214-215`, `:238-239`) with:

```python
atomic_write_text(path, "".join(lines))
```

Add a line to the module docstring recording that writes are atomic and why.

### 3. Correct the now-stale board docstring

`.aitask-scripts/board/aitask_board.py:735-745` currently asserts as present-tense
fact that "`frontmatter_patch` rewrites task files in place with a plain
`open(path, "w")`". After this change that is false, and it is the stated
rationale for the reader guard.

**Keep the guard** — rewrite only the rationale: the `frontmatter_patch` window
is closed (t1371), but the guard remains because other task-file writers are
still non-atomic (`aitask_update.sh:800 write_task_file`, `aitask_board.py:252
Task.save`), and both failure shapes (raise vs `None`) remain reachable.

### 4. Update t1281's task body

Its inventory says "three atomic-write implementations"; the survey found **7+**
Python ones (`gate_ledger:357`, `attachment_meta:65`, `artifact_manifest:132`,
`config_utils:175-226`, `skill_template:258`, `userconfig_persist:93`,
`agent_marks:243`, plus inline sites in `framework_version` and `chatlink/`).
Restate the goal as "re-point the remaining implementations onto
`lib/atomic_write.py`", note t1371 created it, and carry over the two extra
defects the survey surfaced (`gate_ledger`'s PID-named temp is not `O_EXCL`;
`skill_template._atomic_write` has no cleanup on failure).

Edit via `./.aitask-scripts/aitask_update.sh --batch 1281 --desc-file -` and
commit with `./ait git`.

### 5. Tests — `tests/test_atomic_write.py` (new)

Python `unittest`, `sys.path` bootstrap from `__file__` (the runner unsets
PYTHONPATH — `tests/run_all_python_tests.sh:40-43`), modelled on
`tests/test_agent_marks.py` (fixture) and the `AtomicWriteTests` class in
`tests/test_cross_repo_settings.py:311-396` (assertion style).

Helper-level:
1. `test_failed_replace_leaves_original_and_no_residue` — patch `_os_replace` →
   `OSError`; original bytes unchanged, no `.tmp` left.
2. `test_render_failure_leaves_original_and_no_residue` — `render` raises; same.
3. `test_mode_is_preserved` — subTests over 0o644 / 0o600.
4. `test_new_file_mode_respects_umask` — target absent → `0o666 & ~umask`.
5. `test_symlinked_target_is_followed_not_replaced` — link survives, backing
   file receives the write.

`frontmatter_patch` integration — **the deterministic proof of the bug fix** is a
hardlink probe. `os.link(task, snapshot)` before patching: after an atomic
rename the task path is a new inode, so `snapshot` still holds the *original*
bytes. Under truncate-in-place both names share one inode and `snapshot` shows
the new content, so the test fails on the old code.

6. `test_append_does_not_mutate_the_original_file_object`
7. `test_remove_does_not_mutate_the_original_file_object`
8. `test_patch_preserves_mode` — a 0644 task file stays 0644.

Deliberately **not** a standalone test: "no `.tmp` residue after a *successful*
patch". A successful rename consumes the temp, so the assertion holds for any
implementation and would be vacuous. Residue is asserted in tests 1-2, where a
temp genuinely existed and had to be cleaned up; tests 6-7 keep the check only
as a cheap add-on.

#### Negative controls — one mutation per test

Each test gets its **own** mutation that must make it fail; there is no single
mutation that fails them all.

| test | mutation that must make it fail | what it defends |
|---|---|---|
| 6, 7 | restore `open(path, "w")` in `cmd_append` / `cmd_remove` | **the defect this task fixes** |
| 1 | delete `discard(tmp)` from `commit` | residue after a failed rename |
| 2 | delete `discard(tmp)` from `prepare` | residue after a failed render |
| 3, 8 | delete `os.fchmod(fd, mode)` from `prepare` | `mkstemp`'s 0600 downgrade |
| 4 | hardcode a mode in `target_mode`'s `except` branch | umask-correct new-file mode |
| 5 | drop `os.path.realpath` from `atomic_write` | replacing the symlink itself |

**Restoring `open(path, "w")` fails only tests 6-7.** The old in-place write
preserves an existing file's mode and creates no temp file, so tests 1-5 and 8
pass under it — they are not evidence about the old code at all. They defend the
*new* implementation against the specific ways a tempfile-based writer goes
wrong, and each is validated by its own row above. Any plan or notes claiming
the old code fails the residue/mode tests is asserting a result that cannot
occur.

Run each negative control by editing the source by hand and reverting it the
same way — **not** `git checkout` (a concurrent session may have staged work in
these files). Purge `__pycache__` between runs, and confirm the failing test id
is the expected one rather than a collateral import error.

## Concurrency contract — what this task does and does not guarantee

Temp-file + `os.replace` removes **torn reads**. It does *not* serialize the
read-modify-write cycle: `cmd_append` reads the file, splices a block, and
writes it back, so two concurrent mutations could each render from the same old
text and the second `os.replace` would silently discard the first. Atomicity
makes the loss clean rather than corrupt — it does not prevent it.

**Verified: every current caller already holds a mutation lock.** All three
sites wrap their *entire* transaction — including this frontmatter mutation — in
`with_attach_lock` (`lib/attachment_lock.sh:36-49`), a single global mutex at
`attachments/.attach.lock` that is fail-safe (it `die`s on a busy lock rather
than proceeding unlocked):

| caller | site |
|---|---|
| `aitask_artifact.sh` | `:229`, `:324`, `:389`, `:466` |
| `aitask_attach.sh` | `:228`, `:346` |
| `aitask_fold_mark.sh` | `:548` |

So lost updates **between** `frontmatter_patch` invocations are already
excluded, and this task does not weaken that.

What remains unguarded — **pre-existing, unchanged by this task, and out of
scope**: the attach lock is scoped to the attach/artifact ledgers, not to the
task file. A concurrent writer that does not take it (`aitask_update.sh:800
write_task_file`, board `Task.save`, `aitask_archive.sh`) can still lost-update
an `artifacts:` block, and vice versa.

The module docstring will state the boundary explicitly — *reader-visible
atomicity, not writer serialization* — so a future caller does not read
"atomic" as a mutual-exclusion guarantee. Task-file-scoped write serialization
is recorded as an upstream defect at Step 8 rather than folded in here.

## Files touched

| File | Change |
|---|---|
| `.aitask-scripts/lib/atomic_write.py` | **new** — ~60 lines, stdlib only |
| `.aitask-scripts/lib/frontmatter_patch.py` | bootstrap + import; 2 write sites; docstring |
| `.aitask-scripts/board/aitask_board.py` (735-745) | correct the guard rationale; guard unchanged |
| `tests/test_atomic_write.py` | **new** — 9 tests |
| `aitasks/t1281_unify_atomic_write_helpers.md` | inventory + goal restated |

No whitelist touchpoints: a Python lib module imported by another Python module
is not a skill-invoked helper (`aidocs/framework/aitasks_extension_points.md:95-104`).
`seed/` ships no Python, so no seed mirror either.

## Verification

```bash
python3 tests/test_atomic_write.py          # new suite
bash    tests/test_attach_meta.sh           # existing frontmatter_patch coverage
bash    tests/test_artifact_cli.sh
bash    tests/test_artifact_fold_transfer.sh
python3 tests/test_cross_repo_settings.py   # unchanged atomic-write contract
```

Narrow a suite run with `--test-dir`, never a `-k` filter: without the opt-in
pytest dev tier the runner falls back to `unittest discover`, where `-k` runs 0
tests and still exits 0. Full suite if time allows:
`bash tests/run_all_python_tests.sh`, reading only the final `PYTHON SUITE:`
line (piping discards the status — use `set -o pipefail`).

End-to-end, against the real CLI that provoked the bug:

```bash
./ait artifact new …      # patches artifacts: via frontmatter_patch append
git diff --stat           # task file updated, mode unchanged, no .tmp residue
ls -la aitasks/ | grep '\.tmp'   # expect nothing
```

Step 9 archival then runs the `risk_evaluated` gate.

## Risk

### Code-health risk: low

- Adds an **8th independently maintained** atomic-write implementation, and
  t1281 (which would consolidate them) is only `Ready` and `low` priority — so
  the duplication is real for an unbounded period, not momentary, and the copies
  can drift. Bounded by the pinned API contract above, a single caller, and the
  named owning task. · severity: low · → mitigation: t1281 (already exists)
- `frontmatter_patch.py` gains its first sibling import, so a caller invoking it
  with `lib/` absent from `sys.path` would now fail at import. Mitigated by the
  explicit `__file__`-derived bootstrap, which is the repo-wide convention and
  does not rely on the caller. · severity: low · → mitigation: none needed

### Goal-achievement risk: low

- Closes the `frontmatter_patch` window only; `aitask_update.sh:800` and
  `Task.save` still truncate in place, so the *class* of torn reads survives
  this task. This is the confirmed scope, and the board's reader guard stays in
  place to cover it. · severity: low · → mitigation: Step 8b upstream-defect
  follow-up
- Delivers reader-visible atomicity, not writer serialization: a task file can
  still be lost-updated by a writer that does not take the attach lock. Verified
  that all present `frontmatter_patch` callers do take it, so no regression — but
  "atomic" must not be read as mutual exclusion. · severity: low · → mitigation:
  documented in the module docstring + recorded as an upstream defect

## Upstream defects to record at Step 8 (not fixed here)

- `aitask_update.sh:800` — `write_task_file` rebuilds an existing task file with
  `} > "$file_path"`; the framework's highest-traffic task-file writer.
- `board/aitask_board.py:252` — `Task.save` truncate-then-write, ~10 call sites.
- `board/aitask_merge.py:467`, `diffviewer/merge_screen.py:113`,
  `brainstorm/brainstorm_session.py:1537` — same primitive on task/plan files.
- `aitask_plan_verified.sh:187`, `aitask_plan_externalize.sh:544,558`,
  `aitask_issue_import.sh:103` — `mv` from `$TMPDIR`, cross-device risk degrades
  the rename to copy+rename.
- `gate_ledger.py:357` — PID-named temp without `O_EXCL`, collision-prone across
  threads.
- `skill_template.py:258` — `_atomic_write` leaves `.tmp` residue on failure.
- No task-file-scoped write lock: `aitask_update.sh`, board `Task.save` and
  `aitask_archive.sh` mutate a task file without taking the attach lock, so they
  can lost-update a concurrent `ait artifact` / `ait attach` frontmatter write
  (and vice versa). Atomic writes make the loss clean, not absent.
