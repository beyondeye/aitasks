---
Task: t1379_atomic_task_file_writes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1379 — Atomic task/plan file writes

## Context

t1365 moved `ait board`'s By-Trail discovery to a live disk read, which exposed
the write side: a board scan racing `ait artifact new` saw the owning task file
either cut mid-YAML (`parse_frontmatter` raises) or truncated to zero bytes (it
returns `None`). `open(path, "w")` / `> "$file"` truncates **before** any bytes
are written, so the empty-file case is the likelier one.

t1365 hardened the *reader*. t1371 fixed exactly one *writer*
(`lib/frontmatter_patch.py`) and created the shared seam
`.aitask-scripts/lib/atomic_write.py`, recording the rest as upstream defects.
This task converts that remainder:

- **4 Python truncate-then-write sites** → route through `lib/atomic_write.py`,
  which already handles resolution, mode preservation and failure cleanup.
- **4 shell sites** that `mv` a `$TMPDIR` temp onto a repo file — a cross-device
  rename degrades into a non-atomic copy, and none of them clean up on failure.
- **Shell sites with no temp file at all**: `aitask_update.sh`'s
  `write_task_file` (the framework's highest-traffic task-file writer), plus two
  sites a fresh sweep found that the task's own survey missed —
  `aitask_create.sh` (3×, writing a brand-new task file, which a concurrent
  `aitasks/*.md` scan can catch at zero bytes) and `aitask_gate_pass.sh:94`
  (re-signing an existing gate witness the orchestrator reads).

That sweep also **cleared** the rest: `aitask_archive.sh:158,163` and
`aitask_gate.sh:280,297` already stage their temp in the destination directory,
so their renames are same-filesystem and atomic. Nothing else under
`.aitask-scripts/` truncates a file under `aitasks/` / `aiplans/`.

Intended outcome: every in-tree writer of a file under `aitasks/` / `aiplans/`
replaces it atomically, so a concurrent reader observes the whole old file or
the whole new one — never a partial state.

### Scope decisions (confirmed with the user)

| item | decision |
|---|---|
| Shell helper home | **New `lib/atomic_write.sh`** — a named shell sibling of `lib/atomic_write.py`, not a bolt-on to `terminal_compat.sh`. |
| `aitask_projects.sh:195` local `atomic_write` | **Re-point** onto the shared helper and delete the local copy (6 call sites). |
| `gate_ledger.py:357`, `skill_template.py:258` | **Out of scope — t1281 owns them.** Its migration table already names both; re-pointing them onto `atomic_write.py` fixes both defects as a side effect. *Remind the user at the end of implementation that t1281 still needs picking.* |
| Task-file-scoped **write lock** | **Out of scope — follow-up task**, created at Step 8b. Atomic writes make a lost update *clean* rather than *corrupt*; they do not prevent it. |

## Approach

### 1. New `.aitask-scripts/lib/atomic_write.sh`

Shell sibling of `lib/atomic_write.py`, same contract stated in its header:
**reader-visible atomicity, not writer serialization; no fsync.** Guarded with
`_AIT_ATOMIC_WRITE_LOADED` per `aidocs/framework/shell_conventions.md`.

```bash
# ait_atomic_resolve <path> — realpath equivalent: `pwd -P` on the directory,
#   then follow a FILE symlink chain via readlink (bounded at 40 hops, then
#   fails). `readlink -f` is GNU-only — macOS lacked it until 12.3.
ait_atomic_resolve() { … }

# ait_file_mode <path> — octal mode of an existing file, empty when absent.
#   `stat -c` is GNU, `stat -f` is BSD; the fallback chain is the repo idiom
#   (aitask_gate.sh:108, aitask_create.sh:334).
ait_file_mode() { stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null || true; }

# ait_atomic_tmp <resolved_dest> — create and print a staging temp beside it:
#   dot-prefixed (invisible to task globs / archive scans), in the file's own
#   directory (same-filesystem rename), chmod'd to the destination's current
#   mode — or, when it does not yet exist, to `0666 & ~umask`. Rejects a
#   directory destination. Discards the temp if the chmod fails.
#   <resolved_dest> MUST already be resolved — like atomic_write.py's `prepare`,
#   this does not follow symlinks itself.
ait_atomic_tmp() { … }

# ait_atomic_commit <tmp> <resolved_dest> — reject a directory destination,
#   then mv -f into place; rm -f the temp on any failure.
# ait_atomic_discard <tmp> — best-effort removal; never fails.
# ait_atomic_render <dest> <fn> [args…] — resolve ONCE, stage, run `fn > tmp`,
#   reject an empty result, commit on success / discard on failure.
#   THE pattern every converted block uses.
# ait_atomic_write_text <dest> <content> — one-shot; exactly one trailing newline.
```

Four pinned design points, each verified against a prototype rather than assumed:

- **Umask-derived mode for a missing destination.** `mktemp` creates `0600`
  while the redirections being replaced create `0666 & ~umask` (normally
  `0644`), so without this every *newly created* task and plan file would
  silently become private. Mirrors `atomic_write.py`'s `_UMASK` default.
  Measured: `mktemp` → `600`, `> file` → `644`; the derived value follows a
  changed umask (`umask 0077` → `600`), which is what stops a hardcoded `0644`
  from passing the test under the usual `umask 022`.
- **Resolve exactly once, then carry the resolved path through both stages.**
  `> "$dest"` follows a file symlink; `mv -f` **replaces the link itself**.
  Measured: `mv -f staged link.md` turned `link.md` into a regular file and left
  the backing file on its old content — the exact orphaning `atomic_write.py`
  avoids with `realpath`. Resolving also makes "staged beside the destination"
  true for a path reached through a symlink, which is what guarantees the
  same-filesystem rename. Critically, resolution happens **once**, in
  `ait_atomic_render` / `ait_atomic_write_text`; `ait_atomic_tmp` and
  `ait_atomic_commit` take an already-resolved path, exactly as
  `atomic_write.py`'s `prepare`/`commit` do. Resolving twice would leave a TOCTOU
  window in which a retargeted symlink stages beside backing file A and renames
  onto backing file B — reintroducing the cross-device path and writing the wrong
  file. Verified: retargeting the link between stage and commit still lands the
  write on the originally resolved backing file and leaves the other untouched.
- **Reject a directory destination.** `mv -f "$tmp" "$dir"` **succeeds** by
  moving the temp *inside* the directory (measured: exit 0, `.name.XXXXXX` left
  in `dir/`), so a naive commit would report success while writing nothing —
  whereas the `> "$dest"` it replaces fails with `Is a directory`. Both
  `ait_atomic_tmp` and `ait_atomic_commit` reject it explicitly.
- **Render inside the helper (`ait_atomic_render`), not a `trap`.** Bash has a
  single EXIT trap and `lib/archive_utils.sh:118` already claims it globally at
  source time (reached by every script sourcing `task_utils.sh`), while
  `aitask_create.sh` and `aitask_projects.sh` install 5 traps each — so a
  library-installed trap would silently unregister someone's cleanup. Inline
  cleanup alone is not enough either: under `set -e` a render failure exits
  *before* reaching the commit and leaves a dot-prefixed residue. Putting the
  render under the helper's control closes that window. Bash's dynamic scoping
  lets a top-level render function read the caller's `local`s, so
  `write_task_file`'s 30 locals need no plumbing.

- **Renderers must not rely on `set -e` — this is a written contract, not an
  inference.** Because `ait_atomic_render` tests the renderer's status (and is
  itself called under `|| die`), bash disables errexit for everything inside, so
  a renderer of the shape `echo line1; false; printf partial` runs to completion
  and returns its *last* command's status — committing a partial file. **No
  construct inside the helper can restore errexit.** Measured, all four
  committed `line1|partial` and reported success:

  | attempted construct | mid-render failure detected? |
  |---|---|
  | `if ! fn > tmp` | no |
  | `( set -e; fn )` | no |
  | `( set -e; trap 'exit 1' ERR; fn )` | no |
  | `( trap 'exit 1' ERR; fn )` | no |

  So the contract is stated in the helper header and enforced per renderer:
  **every fallible command carries an explicit `|| return 1`.** Concretely —
  `aitask_plan_verified.sh`'s renderer ends with `[[ $inserted -eq 1 ]] || return 1`;
  `aitask_issue_import.sh`'s ends with an explicit `injected` check (its `grep -qE`
  returns 1 on a normal non-match and must not be conflated with an error);
  `aitask_plan_externalize.sh`'s main renderer guards `build_header || return 1`
  (its `awk`-only splice renderer is already a single command, so its status *is*
  the renderer's). The `echo`-sequence renderers (`write_task_file`,
  `aitask_create.sh` ×3, `aitask_gate_pass.sh`) contain no command that fails for
  any reason other than a broken output fd — which fails the trailing `echo` too.
  Each site gets a **failure-after-success** test, not just a
  "renderer returns non-zero" test.

- **Empty-output backstop.** Independently of the contract above,
  `ait_atomic_render` refuses to commit a zero-byte temp (override:
  `AIT_ATOMIC_ALLOW_EMPTY=1`). Every renderer here produces at least a
  frontmatter block, and an empty temp is the signature of the worst case — the
  output fd broken from the first write. It does not catch a *partial* file;
  the per-renderer guards do. Verified: guarded mid-render failure rejected,
  empty output rejected, original intact, zero residue in both cases.
- **`mktemp` template form only** (`…XXXXXX` last) — BSD `mktemp` has no
  `--suffix` (`aidocs/framework/sed_macos_issues.md`).

**Sourcing:** `aitask_update.sh`, `aitask_create.sh`, `aitask_plan_verified.sh`,
`aitask_plan_externalize.sh`, `aitask_issue_import.sh`, `aitask_gate_pass.sh`,
`aitask_projects.sh` each gain one
`source "$SCRIPT_DIR/lib/atomic_write.sh"` line. The lib is **not**
added to `./ait`'s source-on-startup chain (no `ait` subcommand needs it
directly), but it *is* added to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()`
so the 29 scaffolded tests that run these scripts pick it up; the ~10 tests that
build fake repos **without** the scaffold need an explicit `cp` line (identified
by running the suite, not by guessing).

### 2. Shell conversions

**Every converted block goes through `ait_atomic_render`** — no site is allowed
to hand-roll `tmp=…; { … } > "$tmp"; commit`, because that is precisely the shape
that leaks a temp when the render fails under `set -e`.

| site | change |
|---|---|
| `aitask_update.sh:613-801` `write_task_file` | lift the existing `{ … }` block verbatim into a top-level `_ait_write_task_file_body` (it reads `write_task_file`'s locals via dynamic scoping), then `ait_atomic_render "$file_path" _ait_write_task_file_body \|\| die …`. Also correct the comment at `:645-651`, which explains the `attachments:`/`artifacts:` capture as happening "BEFORE the truncating redirect" — the read must still come first, but the truncation hazard it names is gone. |
| `aitask_plan_verified.sh:117,187` | the line-by-line rewrite loop becomes the render function (writing to stdout instead of appending to `$tmp`), ending in `[[ $inserted -eq 1 ]] \|\| return 1`; `ait_atomic_render "$plan_file" …`. The helper then discards and the caller `die`s — replacing today's hand-rolled `rm -f`. |
| `aitask_plan_externalize.sh:534,544` (`splice_output_branch`) | the `awk` becomes the render function (a single command, so its status is the renderer's); a failed `awk` now returns non-zero and the helper discards, fixing today's leak-on-awk-failure. |
| `aitask_plan_externalize.sh:547,558` | the `has_frontmatter` branch becomes the render function over `$EXTERNAL_PLAN`, with `build_header \|\| return 1`; the helper's `mkdir -p` covers the first-ever externalize, which *creates* the file. |
| `aitask_issue_import.sh:94,103` | the `while IFS= read` injection loop becomes the render function over `$filepath`, ending in an explicit `injected` check — its `grep -qE` returns 1 on a normal non-match, which must not be read as an error. |
| `aitask_create.sh:569,699,1887` | the three creation blocks become three render functions. The helper's `mkdir -p` covers the child-task directory case, and the umask-derived mode is what keeps a newly created task file at `0644` rather than `mktemp`'s `0600`. |
| `aitask_gate_pass.sh:94` | witness-file block → render function; the existing `mkdir -p "$(dirname "$target")"` becomes redundant but is harmless. |
| `aitask_projects.sh:194-204` | delete the local `atomic_write`; source the lib; 6 call sites (394, 459, 508, 786, 810, 919) → `ait_atomic_write_text`. Gains the missing failure cleanup and a dot-prefixed temp name (the current `"${target}.XXXXXX"` is glob-visible in the registry dir). |

`aitask_update.sh` and `aitask_issue_import.sh` run under `set -e` only (no
`-u`, no `pipefail`). The prepare/commit split is chosen precisely so no
conversion depends on `pipefail`; turning on `-u` in those scripts is a separate,
larger change and is **not** bundled here.

### 3. Python conversions

All four use the t1371 reference idiom — `sys.path.insert(0, …/"lib")` already
present (or added, per each module's own established form) then a bare
`from atomic_write import …`.

| site | change |
|---|---|
| `board/aitask_board.py:250-253` `Task.save` | `atomic_write_text(str(self.filepath), content)`. Import goes with the other `lib/` imports below the existing `sys.path.insert` (line 15). ~12 call sites, all unchanged. |
| `board/aitask_merge.py:467` | `atomic_write_text(str(filepath), merged_content)`; import beside `import gate_ledger  # noqa: E402`. |
| `diffviewer/merge_screen.py:110-123` | The write is a **multi-`write()` + `writelines()`** block, so it needs the render-callback form. Extract it as `write_merged_plan(path, meta, merged_lines)` into `diffviewer/merge_engine.py` (the non-Textual module that already owns `suggest_directory`/`suggest_filename`), implemented with `atomic_write(path, render)`; `on_save` calls it inside its existing `try/except OSError`. This makes the site unit-testable without a Textual `Pilot`. Add the `sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))` bootstrap the package uses (`diffviewer/plan_loader.py:8`) — do **not** rely on a transitive insert. |
| `brainstorm/brainstorm_session.py:1537` | `atomic_write_text(str(out_path), new_text)`; add the `../lib` insert its siblings already use (`brainstorm/utils.py:7`). Target is `.aitask-crews/`, not `aitasks/` — converted for consistency, not for the board race. |

### 4. Documentation

- `board/aitask_board.py` `_iter_active_task_frontmatter` docstring (~740-748)
  currently cites `write_task_file` and `Task.save` as the writers that keep
  both torn-read failure shapes reachable. After this task that is false.
  **Keep the guard**, but rewrite the rationale honestly: no in-tree writer
  produces a torn read any more, and the guard now defends against a malformed
  or hand-edited file (`parse_frontmatter` raises on any bad YAML) and against a
  future unconverted writer.
- `lib/atomic_write.py` docstring: note the shell sibling `lib/atomic_write.sh`
  and that the shell task/plan writers now route through it.
- `aidocs/framework/shell_conventions.md`: add a short **atomic file
  replacement** bullet naming `lib/atomic_write.sh`. The doc is currently silent
  on temp files, which is why the two in-tree patterns disagree (one cleans up,
  one does not; one dot-prefixes, one does not).

### 5. Tests

#### What each assertion actually proves

The hardlink probe is **not** a cross-device detector, and the plan must not
claim it is. Measured directly (tmpfs source → disk destination): a real
cross-device `mv` left the probe holding the OLD bytes, the destination holding
the NEW bytes, and the inodes different — i.e. it produces the *same* result as a
same-filesystem rename while still exposing a reader-visible window. So:

| assertion | what it discriminates |
|---|---|
| hardlink probe | **truncate-in-place** writes only (`write_task_file`, `Task.save`, `aitask_create.sh`, witness re-sign, the Python sites) |
| staged path's dirname == `dirname(realpath(dest))` | the temp really is same-filesystem — the property a cross-device `mv` lacks |
| controlled `TMPDIR` stays **empty** after the write | the converted site no longer stages in `$TMPDIR` |
| `TMPDIR=/nonexistent…` still succeeds | the write path has no `$TMPDIR` dependency at all |
| no `.<name>.XXXXXX` sibling afterwards | cleanup, on both success and failure paths |

**`tests/test_atomic_write_sh.sh`** (new) — helper contract, direct:

- staged temp lands beside the **resolved** destination and is dot-prefixed;
- existing mode preserved (0640 stays 0640);
- **missing destination gets `0666 & ~umask`**, re-asserted under `umask 0077`
  so a hardcoded `0644` cannot pass;
- missing parent directory created;
- a **symlinked destination** keeps the link and updates the backing file
  (mirrors `test_symlinked_target_is_followed_not_replaced`); a symlink cycle
  fails rather than looping;
- **retarget race**: resolve, stage, retarget the symlink, commit → the write
  lands on the *originally resolved* backing file and the new target is
  untouched (this is what a resolve-twice implementation gets wrong);
- **directory destination** is rejected by both `ait_atomic_tmp` and
  `ait_atomic_commit`, and the directory is left empty — the concrete
  commit-stage failure case;
- **mid-render failure-after-success** (`echo line1; false || return 1;
  printf partial`) leaves the original intact with no residue — the shape a
  final-return-code-only test would miss;
- **empty renderer output** is rejected;
- `ait_atomic_write_text` round-trip with exactly one trailing newline.

**`tests/test_atomic_task_file_writes.sh`** (new) — per shell site, over a
scaffolded fake repo: hardlink probe (truncate-in-place sites only), controlled-
`TMPDIR`-stays-empty, `TMPDIR=/nonexistent` still succeeds, and no residue.

**All seven shell sites get a probe — including the two the first draft missed.**
`aitask_plan_externalize.sh` (copy path *and* `splice_output_branch`, which is a
separate renderer with its own former `$TMPDIR` temp — the copy-path probe uses a
frontmatter-less source, where the splice never fires) and `aitask_projects.sh`.
Reverting either was verified invisible to every pre-existing suite, including
`test_plan_externalize.sh`, whose 300-odd `TMPDIR` mentions are all scratch
directories, not atomicity probes.

`aitask_projects.sh` is different in kind and its test says so: its former local
`atomic_write` already staged in the destination directory, so the rename was
already atomic and **the hardlink probe cannot discriminate the conversion**.
What the shared helper adds there — and what is asserted — is mode preservation
(the old `mktemp` left the registry 0600), symlink resolution (the old `mv -f`
replaced the link and orphaned the backing file), and a dot-prefixed temp name
invisible to a glob of the registry directory. Each
site additionally gets a **failure-after-success render** test — driven by making
that renderer's own guarded condition fail (e.g. an `aitask_plan_verified.sh`
plan whose header cannot take the insertion, so `inserted` stays 0 while the
trailing `printf` succeeds) — asserting the target file is byte-identical
afterwards. That is the assertion that proves the renderer does not lean on the
errexit the calling context has disabled.
`aitask_create.sh` and a *first* `aitask_gate_pass.sh` sign have no prior inode,
so they get the residue + `TMPDIR` assertions plus a **created-file mode**
assertion (`0644` under the default umask — the check that catches the
`mktemp`-0600 regression); re-signing an existing witness does have a prior
inode and gets the hardlink probe.

If a converted script turns out to touch `$TMPDIR` on the same code path for an
unrelated reason (`aitask_update.sh:926` uses it for the interactive description
editor), narrow that site's `TMPDIR` assertions to the write step rather than
dropping them — the staging-location and residue assertions stand regardless.

**`tests/test_atomic_task_writes.py`** (new) — hardlink probes for `Task.save`,
`aitask_merge.main`, and `merge_engine.write_merged_plan`, plus a mode-preservation
case. **`tests/test_brainstorm_module_ops_integration.py`** gains one hardlink-probe
case for `assign_inferred_module_node_ids` (it already imports the function and
patches `crew_worktree`).

**Negative controls — one mutation per test.** Each converted site's probe must
fail when that site alone is reverted to its old write. The helper tests each get
their own mutation:

| test | mutation that must make it fail |
|---|---|
| existing-mode preserved | drop `chmod "$mode"` from `ait_atomic_tmp` |
| missing-destination mode (both umasks) | replace the umask derivation with a literal `0644` — the `umask 0077` case is what fails it |
| staged beside resolved dest / `TMPDIR` empty | point `ait_atomic_tmp` at `${TMPDIR:-/tmp}` |
| symlinked destination | drop `ait_atomic_resolve` from `ait_atomic_render` |
| retarget race | move resolution back into `ait_atomic_tmp` + `ait_atomic_commit` (i.e. resolve twice) |
| directory destination | drop the `[[ -d "$dest" ]]` rejections |
| render-stage failure (residue) | replace `ait_atomic_render` with the hand-rolled `tmp=…; { … } > "$tmp"; commit` shape |
| mid-render failure-after-success (per site) | drop that renderer's explicit `\|\| return 1` guard |
| externalize copy path | restore its `$TMPDIR` temp + `mv` |
| externalize splice path | restore *its* `$TMPDIR` temp + `mv` (separate renderer, separate control) |
| projects registry | restore the local `atomic_write` |
| empty output | drop the `[[ -s "$tmp" ]]` check |
| commit-stage failure | drop `rm -f "$1"` from `ait_atomic_commit` | Mutate and restore **by hand**, never `git checkout` (a concurrent
session may have staged work in these files); run Python controls with
`PYTHONDONTWRITEBYTECODE=1` and confirm the failing test id is the expected one —
identical-size mutations otherwise collide in the pyc cache (the t1371 trap).

## Files touched

| File | Change |
|---|---|
| `.aitask-scripts/lib/atomic_write.sh` | **new** — ~50 lines |
| `.aitask-scripts/aitask_update.sh` | source + `write_task_file` prepare/commit + comment |
| `.aitask-scripts/aitask_create.sh` | source + 3 creation writes |
| `.aitask-scripts/aitask_gate_pass.sh` | source + witness write |
| `.aitask-scripts/aitask_plan_verified.sh` | source + temp location + commit |
| `.aitask-scripts/aitask_plan_externalize.sh` | source + 2 temps + commit + leak fix |
| `.aitask-scripts/aitask_issue_import.sh` | source + temp location + commit |
| `.aitask-scripts/aitask_projects.sh` | delete local `atomic_write`; source + 6 call sites |
| `.aitask-scripts/board/aitask_board.py` | `Task.save` + reader-guard docstring |
| `.aitask-scripts/board/aitask_merge.py` | merged-result write |
| `.aitask-scripts/diffviewer/merge_engine.py` | **new** `write_merged_plan` |
| `.aitask-scripts/diffviewer/merge_screen.py` | call the extracted writer |
| `.aitask-scripts/brainstorm/brainstorm_session.py` | `out_path` write |
| `.aitask-scripts/lib/atomic_write.py` | docstring: name the shell sibling |
| `aidocs/framework/shell_conventions.md` | atomic-replacement idiom |
| `tests/lib/test_scaffold.sh` | copy the new lib |
| `tests/*` | 3 new files, ~10 curated `cp` lists, 1 added case |

No whitelist touchpoints — a lib sourced by other `.aitask-scripts/` scripts is
not a skill-invoked helper (`aidocs/framework/aitasks_extension_points.md:95-104`).
`seed/` ships no shell or Python, so no seed mirror.

## Verification

```bash
shellcheck .aitask-scripts/aitask_*.sh .aitask-scripts/lib/atomic_write.sh

bash tests/test_atomic_write_sh.sh
bash tests/test_atomic_task_file_writes.sh
bash tests/test_update_risk.sh
bash tests/test_update_multiline_yaml.sh
bash tests/test_plan_verified.sh
bash tests/test_plan_externalize.sh
bash tests/test_issue_import_contributor.sh
bash tests/test_create_silent_stdout.sh
bash tests/test_parallel_child_create.sh
bash tests/test_gate_frontmatter_roundtrip.sh
bash tests/test_gate_guarded_archival.sh
bash tests/test_projects_cmd.sh
bash tests/test_aitask_projects_update.sh
bash tests/test_aitask_projects_remove.sh
bash tests/test_terminal_compat.sh

python3 tests/test_atomic_write.py
python3 tests/test_atomic_task_writes.py
python3 tests/test_aitask_merge.py
python3 tests/test_diff_engine.py
python3 tests/test_brainstorm_module_ops_integration.py
```

Then the full Python suite — read **only** the final `PYTHON SUITE:` line, and
use `set -o pipefail` if piping (piping discards the status):

```bash
set -o pipefail; bash tests/run_all_python_tests.sh
```

Narrow with `--test-dir`, never a positional path or `-k` filter (without the
opt-in pytest dev tier the runner falls back to `unittest discover`, where `-k`
runs 0 tests and still exits 0).

Because ~39 bash tests exercise these scripts through scaffolded fake repos, the
bash sweep is part of verification, not optional:

```bash
for t in tests/*.sh; do bash "$t" >/dev/null 2>&1 || echo "FAIL $t"; done
```

End-to-end, against the real CLIs:

```bash
./ait update --batch <id> --status Postponed   # write_task_file path
./ait artifact new …                           # frontmatter_patch (already atomic)
ls -a aitasks/ | grep -E '^\.t.*\.[A-Za-z0-9]{6}$'   # expect nothing
git diff --stat                                 # modes unchanged
```

Step 9 archival then runs the `risk_evaluated` gate.

## Deferred out of this task

- **Task-file-scoped write serialization** — `aitask_update.sh`, board
  `Task.save` and `aitask_archive.sh` mutate task files without taking the global
  attach lock (`lib/attachment_lock.sh`), so they can lost-update a concurrent
  `ait artifact` / `ait attach` frontmatter write, and vice versa. Atomic writes
  make that loss **clean rather than corrupt**; they do not prevent it. A
  standalone design task is created at Step 8b.
- **`gate_ledger.py:357` / `skill_template.py:258`** — owned by **t1281**, which
  re-points them onto `lib/atomic_write.py` and fixes both defects as a side
  effect. *Remind the user at the end of implementation that t1281 still needs
  picking.*

## Risk

### Code-health risk: medium

- Touches the framework's highest-traffic file writers — `write_task_file`
  (3 call sites), `aitask_create.sh`'s 3 creation paths, and board `Task.save`
  (~12 call sites). A defect in the new helper breaks every task mutation *and*
  every task creation at once. Bounded by each edit being mechanical and
  behaviour-preserving, and by a per-site behavioural probe with its own negative
  control. · severity: medium · → mitigation: none needed
- The new lib must be added to `tests/lib/test_scaffold.sh` **and** to ~10
  hand-curated per-test `cp` lists. Those lists are a known-stale surface (t658
  found three already broken), and a missed entry fails with a bare
  `No such file or directory` far from its cause. · severity: medium ·
  → mitigation: test_scaffold_lib_drift_guard
- `ait_file_mode` depends on the `stat -c` / `stat -f` fallback and the BSD-safe
  `mktemp` template form. Both are the established repo idioms, but the helper
  will not be exercised on macOS in this session. · severity: low ·
  → mitigation: atomic_write_macos_portability
- `aitask_update.sh` and `aitask_issue_import.sh` run under `set -e` only (no
  `-u`, no `pipefail`). `ait_atomic_render` is chosen partly because it needs
  neither: it takes a function rather than a pipeline, and it owns the staging
  handle so no caller can redirect into an unset path. · severity: low ·
  → mitigation: none needed
- The render-function refactor reshapes 7 write blocks rather than just swapping
  a redirect target, and it leans on **bash dynamic scoping** for
  `write_task_file`'s 30 locals — correct and verified, but an implicit contract
  a reader may not expect. Bounded by naming each render function `_ait_*_body`,
  defining it immediately above its caller, and a comment stating the dependency.
  · severity: medium · → mitigation: none needed
- **"Renderers must not rely on `set -e`" is an unenforced invariant.** It cannot
  be made structural: the calling context disables errexit inside the renderer
  and no construct within the helper restores it (four were measured and all
  failed). A future renderer added without explicit `|| return 1` guards would
  silently commit a partial file. Bounded by stating the contract in the helper
  header, the zero-byte backstop, and a failure-after-success test per site —
  but a *new* site can be added without one. · severity: medium ·
  → mitigation: none needed
- `ait_atomic_resolve` is new bespoke code (`readlink -f` is GNU-only, so the
  chain is walked by hand) on the path of every task-file write. Bounded at 40
  hops with an explicit failure, and covered by symlink + cycle tests. ·
  severity: low · → mitigation: atomic_write_macos_portability

### Goal-achievement risk: low

- **Cross-device atomicity is proven by construction, not by observation.** A
  real cross-device `mv` was measured (tmpfs → disk) and it defeats the hardlink
  probe: probe old, destination new, inodes different — indistinguishable from a
  clean rename. So the tests cannot *detect* a cross-device copy; they instead
  assert the condition that makes one impossible — the temp is staged in the
  resolved destination's own directory, and `$TMPDIR` is provably unused. That
  is sound (a rename within one directory is always same-filesystem) but it is a
  structural argument, not an observed atomic window. · severity: low ·
  → mitigation: none needed
- The `TMPDIR=/nonexistent` discriminator assumes no converted script touches
  `$TMPDIR` for an unrelated purpose on the same code path — `aitask_update.sh:926`
  does use it, for the interactive description editor. If a probe path reaches
  that, the assertion must be narrowed to the write step rather than dropped,
  or that site loses its discriminator. · severity: low · → mitigation: none needed
- Delivers reader-visible atomicity only; writer serialization is explicitly
  deferred (above). After this task the *class* of torn reads from in-tree writers
  is closed, but two concurrent read-modify-writes can still silently discard one
  another. · severity: low · → mitigation: none needed

### Planned mitigations
- timing: after | name: atomic_write_macos_portability | type: manual_verification | priority: medium | effort: low | addresses: code-health — BSD `stat -f` / `mktemp` template paths in `lib/atomic_write.sh` are untested | desc: Run tests/test_atomic_write_sh.sh, tests/test_atomic_task_file_writes.sh and the converted scripts' bash tests on macOS and record the results.
- timing: after | name: test_scaffold_lib_drift_guard | type: test | priority: medium | effort: medium | addresses: code-health — hand-curated per-test `cp` lib lists rot silently | desc: Guard test that derives, for each bash test scaffolding a fake repo, the libs its copied scripts actually source, and fails when a curated cp list is missing one.

## Final Implementation Notes

- **Actual work done:** Implemented as planned, with the scope extended once
  during review (below).
  - New `.aitask-scripts/lib/atomic_write.sh`: `ait_atomic_resolve`,
    `ait_file_mode`, `ait_atomic_tmp`, `ait_atomic_commit`, `ait_atomic_discard`,
    `ait_atomic_render`, `ait_atomic_write_text`. Resolve happens once in the
    entry points; the primitives take a resolved path. Umask-derived mode for a
    missing destination, mode preservation for an existing one, dot-prefixed temp
    staged beside the resolved target, directory-destination rejection,
    zero-byte-output backstop, inline cleanup (no EXIT trap).
  - Eight shell writers converted to `ait_atomic_render`: `write_task_file`,
    `aitask_create.sh` ×3 (`create_task_file`, `create_child_task_file`,
    `create_draft_file`), `aitask_gate_pass.sh`'s witness,
    `aitask_plan_verified.sh`'s `cmd_append`, `aitask_plan_externalize.sh`'s copy
    and splice paths, and `aitask_issue_import.sh`'s
    `inject_merge_frontmatter`. `aitask_projects.sh`'s local `atomic_write` was
    deleted and its 6 call sites re-pointed at `ait_atomic_write_text`.
  - Four Python writers routed through `lib/atomic_write.py`: board `Task.save`,
    `aitask_merge`, `brainstorm_session`, and a new
    `diffviewer/merge_engine.write_merged_plan` extracted out of the Textual
    `SaveMergeDialog.on_save` so the write is testable without a `Pilot`.
  - Docs: the board reader-guard docstring's rationale (no in-tree writer
    produces a torn read any more — the guard now defends malformed/externally
    written files), `lib/atomic_write.py`'s docstring naming the shell sibling,
    and a new atomic-file-replacement bullet in `shell_conventions.md`.
  - Tests: `tests/test_atomic_write_sh.sh` (30), `tests/test_atomic_task_file_writes.sh`
    (62), `tests/test_atomic_task_writes.py` (8), plus a hardlink case in
    `tests/test_brainstorm_module_ops_integration.py`. `tests/lib/test_scaffold.sh`
    now copies both `atomic_write.sh` and `atomic_write.py`.

- **Deviations from plan:** Two, both scope additions agreed during review.
  - A pre-implementation sweep found two truncate-then-write sites the task's own
    survey missed — `aitask_create.sh` (×3) and `aitask_gate_pass.sh:94` — and the
    user chose to include both. The same sweep cleared `aitask_archive.sh:158,163`
    and `aitask_gate.sh:280,297`, which already stage in the destination directory.
  - Review caught that `aitask_plan_externalize.sh` (both paths) and
    `aitask_projects.sh` had no atomicity probe. Verified by reverting each: the
    reverts were invisible to every pre-existing suite. Probes and per-site
    negative controls were added for all three.

- **Issues encountered:**
  - **No construct can restore `errexit` inside a renderer.** `ait_atomic_render`
    tests its renderer's status, which disables errexit for everything inside, so
    `echo a; false; printf b` commits a partial file. `if ! fn`, `( set -e; fn )`,
    `( set -e; trap 'exit 1' ERR; fn )` and `( trap 'exit 1' ERR; fn )` were all
    measured and all committed the partial output. The contract is therefore
    explicit `|| return 1` guards per renderer, documented in the helper header
    and backed by a failure-after-success test per site.
  - **The hardlink probe does not detect a cross-device `mv`.** Measured tmpfs →
    disk: probe holds the old bytes, destination the new, inodes differ —
    identical to a clean rename. Three sites (`issue_import`, externalize copy,
    externalize splice) were consequently blind until a `TMPDIR=/nonexistent`
    discriminator was added; `aitask_projects.sh` needed mode/symlink assertions
    instead, since its old writer already staged in the destination directory.
  - **`mv -f tmp somedir` succeeds** by moving the temp inside the directory,
    reporting success while writing nothing — hence the explicit directory guard.
  - **Three negative controls initially passed**, which meant the tests were
    wrong, not the code: the symlink control missed `ait_atomic_write_text`'s own
    resolve; the retarget test handed both stages a pre-resolved path so it could
    not detect double resolution; and the directory guard short-circuits before
    `mv`, leaving the commit-cleanup branch unreachable (now driven by an `mv`
    function override). A fourth was a driver bug: grepping only for `FAIL:` lines
    missed aborts, because `set -e` kills the suite before any assertion prints.
  - `aitask_gate_pass.sh`'s witness block ended in `[[ -n "$digest" ]] && echo …`,
    which returns 1 when the digest is empty — as a renderer's last command that
    would have discarded a valid witness. Rewritten as an `if`, with a test.
  - The concurrent session in this checkout was editing `board/aitask_board.py`
    (8 unrelated hunks) plus five test files. Only my three hunks in that file
    were staged, via a hunk-filtered patch applied with `git apply --cached`;
    every other path was staged explicitly.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_archive.sh:158,163 — task-file rewrite uses a FIXED temp name ("$file_path.tmp") instead of mktemp, so two concurrent archives of the same task collide, and the temp is visible to a *.md.tmp glob`
  - `.aitask-scripts/aitask_gate.sh:280 — ledger temp name is PID-derived with no O_EXCL (same defect class as gate_ledger.py:357, which t1281 owns)`
  - `.aitask-scripts/aitask_update.sh:6 — `set -e` only, no `-u`/`pipefail`, contrary to aidocs/framework/shell_conventions.md; same at aitask_issue_import.sh:6`

- **Notes for sibling tasks:** n/a (not a child task).
