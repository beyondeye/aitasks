---
Task: t1815_fix_test_leak_of_fixture_task_files_into_live_tree.md
Base branch: main
Output branch: main
---

# t1815 — Stop test fixtures leaking into the live `aitasks/` tree

## Context

Four fixture task files sit in the live task-data tree and are committed on
`aitask-data`: `aitasks/t1_alpha.md`, `t2_beta.md`, `t10_gamma.md` (0 bytes) and
`aitasks/t5_remote_task.md` (`---\nRemote task`, a frontmatter block that never
closes). Every By-Trail discovery toast reports "Trail scan skipped 4 unreadable
active task file(s)". The task named three files; the fourth came in with them in
the same sweep commit, which is why the toast says 4.

**Root cause (from git history evidence; re-proven by the negative control below):**

- Only `tests/test_data_branch_setup.sh` writes these names: Test 4 writes
  `t5_remote_task.md` (line 582) and Test 11 writes t1/t2/t10 (lines 779-781).
  `test_boardcol_update.sh` writes non-empty files, so it is not the source.
- Both tests write inside `( cd "$TMPDIR_N/local/.aitask-data"; … )`. Until
  `f408721ea` (t1631, 2026-08-27 12:28) that `cd` had **no `|| exit 1`**. When
  `setup_data_branch` failed (t1631 was rewriting it at the time), the `cd`
  failed, the subshell stayed in the **caller's cwd — the live repo root** — and
  wrote the fixtures through the live `aitasks → .aitask-data/aitasks` symlink.
- Proof: the live main checkout's reflog has three `commit: ait: Add remote task`
  entries (be08a217e / 8d06873ab / 259d5548a, 11:28-11:32 on 08-27). That is
  Test 4's own `git add . && git commit`, running against the live repo and
  sweeping t1631's in-progress edits into it. A `reset` at 11:53 undid those
  commits, but the fixture files stayed in the data worktree, and the syncer's
  auto-commit `2dabfae81` (14:22) committed them.
- `f408721ea` added the guards, and every `cd` in the file is guarded today.
  However, **`t1_alpha.md` was truncated again on 2026-09-02 09:09:18**, after
  the guards existed. There is no matching git reflog or stash entry, no sibling
  file changed at that moment, and no writer of that name exists anywhere else in
  `tests/` or `.aitask-scripts/`. That second event is **unexplained**.

What fixes the class: each guard protects one line, and the next unguarded `cd`
added to this 1500-line file brings the hazard back. The fallback for a failed
`cd` must stop being the invoking directory, which is usually the live repo root.

## Implementation

### 1. Scratch cwd for the whole test file — `tests/test_data_branch_setup.sh`

Right after the `asserts.sh` source (line 15), move the process into a throwaway
directory, **and prove it is outside every git repository before entering it**.
`mktemp -d` honors `$TMPDIR`, so a caller can place it under the live checkout
or a worktree; an exported `GIT_DIR` makes *any* directory resolve to a repo.
Location is therefore verified with git, never assumed:

```bash
# Run from a throwaway directory, never the invoking one (t1815). Every fixture
# write below is a relative path inside `( cd "$TMPDIR_N/…" || exit 1; … )`; when
# such a `cd` was unguarded, a failed setup_data_branch left the subshell in the
# caller's cwd — usually the live repo root — so fixture tasks landed in the real
# aitasks/ and `git add . && git commit` committed into the real repository.
# The guards fix each site; this makes the fallback harmless for any future one.
# mktemp honors $TMPDIR, and GIT_DIR in the environment makes every directory a
# repo, so "outside any repository" is checked with git rather than assumed.
# The fixture dirs come from the same mktemp, so this also covers them.
command -v git >/dev/null 2>&1 || { echo "FAIL: git not found"; exit 1; }
TEST_SCRATCH_CWD="$(mktemp -d)" || { echo "FAIL: mktemp for scratch cwd"; exit 1; }
trap 'rm -rf "$TEST_SCRATCH_CWD"' EXIT
if git -C "$TEST_SCRATCH_CWD" rev-parse --git-dir >/dev/null 2>&1; then
    echo "FAIL: scratch dir '$TEST_SCRATCH_CWD' resolves to a git repository" \
         "(TMPDIR='${TMPDIR:-}' GIT_DIR='${GIT_DIR:-}'); refusing to run fixtures there"
    exit 1
fi
cd "$TEST_SCRATCH_CWD" || { echo "FAIL: cannot enter scratch cwd"; exit 1; }
```

- `rev-parse --git-dir` succeeds inside a work tree, inside a `.git` dir, inside a
  bare repo, and whenever `GIT_DIR` is exported — every case where a failed `cd`
  could reach real history. It **fails closed**: the file exits 1 before any
  fixture work rather than running somewhere unsafe. (Only the invoking
  environment is refused; the check does not `unset GIT_DIR` itself, because
  silently rewriting the caller's git environment would hide the condition.)
- The file uses only absolute paths (`$PROJECT_DIR`, `$TMPDIR_N`); sourcing at
  lines 15 and 295 is absolute. No `trap … EXIT` exists in the file (the only
  `trap` in scope is a comment in `tests/lib/asserts.sh`), so nothing is
  overwritten.

### 2. Remove the four leaked files from `aitask-data` — with a last-moment preflight

The data worktree is shared, dirty and unreconciled, so what the investigation
saw is not proof of what is there at removal time. **Immediately before** the
`git rm`, in the **same** Bash invocation (chained so any mismatch stops it),
verify for each path that it is still exactly the known junk:

| path | expected blob (HEAD, index and working tree) |
|---|---|
| `aitasks/t1_alpha.md`, `aitasks/t2_beta.md`, `aitasks/t10_gamma.md` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` (empty) |
| `aitasks/t5_remote_task.md` | `848e683c98f73faa7b0a43e6d5153fc491380484` (`---\nRemote task\n`) |

```bash
preflight_ok=1
while read -r path want; do
    [ -z "$(./ait git status --porcelain -- "$path")" ]        || { echo "MISMATCH:$path:dirty (staged or unstaged)"; preflight_ok=0; continue; }
    [ "$(./ait git rev-parse "HEAD:$path" 2>/dev/null)" = "$want" ] || { echo "MISMATCH:$path:HEAD blob"; preflight_ok=0; continue; }
    [ "$(./ait git rev-parse ":$path" 2>/dev/null)" = "$want" ]    || { echo "MISMATCH:$path:index blob"; preflight_ok=0; continue; }
    [ "$(git hash-object ".aitask-data/$path")" = "$want" ]     || { echo "MISMATCH:$path:worktree content"; preflight_ok=0; continue; }
done <<'EOF_PATHS'
aitasks/t1_alpha.md e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
aitasks/t2_beta.md e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
aitasks/t10_gamma.md e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
aitasks/t5_remote_task.md 848e683c98f73faa7b0a43e6d5153fc491380484
EOF_PATHS
[ "$preflight_ok" = 1 ] &&
./ait git rm -q -- aitasks/t1_alpha.md aitasks/t2_beta.md aitasks/t10_gamma.md aitasks/t5_remote_task.md &&
./ait git commit -q -m "ait: Remove test fixture task files leaked into the live tree (t1815)" -- \
    aitasks/t1_alpha.md aitasks/t2_beta.md aitasks/t10_gamma.md aitasks/t5_remote_task.md
```

- **Any `MISMATCH:` → stop, remove nothing, and investigate/report** — a changed
  name is no longer known junk (another session or a new leak touched it).
- `git rm` runs **without `-f`**, so git's own up-to-date check is a second
  backstop against removing content that differs from HEAD.
- The commit names its paths, so nothing else in the shared data index rides
  along; confirm with `./ait git show --stat <sha>` (by the reported sha, not
  `HEAD`) that it contains exactly these four deletions and nothing else.
- Then `./ait git push`. The data branch has 7 unpushed commits and unstaged
  changes blocking rebase; if the push fails, report it — never force.

## Verification

1. **Suite still green:** `bash tests/test_data_branch_setup.sh`, with
   `ALL TESTS PASSED` and the same PASS count as a run before the edit. Run the
   baseline in a scratchpad copy of the file: never stash, never git-restore.
2. **Negative controls (scratchpad copies, not committed; sentinel = a throwaway
   git repo in the scratchpad, never the live tree):**
   - *Failed-`cd` fallback:* copy the test file, delete Test 11's `|| exit 1`, and
     override `setup_data_branch() { return 1; }` after the `source`. Run it with
     cwd = sentinel. **Without** step 1 → `aitasks/t1_alpha.md` appears in the
     sentinel (reproduces the leak). **With** step 1 → sentinel untouched, `git log`
     unchanged.
   - *Unsafe `TMPDIR`:* run the fixed file with `TMPDIR=<sentinel>/tmp` →
     exits 1 with the "resolves to a git repository" message before any fixture
     work; sentinel `git status` / `git log` unchanged.
   - *Exported `GIT_DIR`:* run the fixed file with `GIT_DIR=<sentinel>/.git` →
     same refusal, sentinel unchanged.
   - *Removal preflight:* run the preflight loop body against a sentinel data
     repo holding the same four fixture files, once clean (no `MISMATCH`) and once
     after appending a byte to one file / staging an edit to another → each
     reports its `MISMATCH:` reason and the `git rm` never runs.
3. **Live tree:** after step 2, `./ait git ls-files aitasks/ | grep -E
   't(1_alpha|2_beta|10_gamma|5_remote_task)\.md'` is empty. `ls` shows no files.
   Also, the full `bash tests/test_data_branch_setup.sh` run leaves the file
   mtimes and `git status` of the live `aitasks/` unchanged: record a snapshot
   before the run and compare after.
4. `shellcheck tests/test_data_branch_setup.sh`: no new findings.

## Step 9 (Post-Implementation)

Current branch (profile fast), so no merge is needed. Commit the code as
`bug: Isolate data-branch setup tests from the invoking directory (t1815)`.
Commit the plan with `aitask_task_commit.sh`. Then run the gates (`risk_evaluated`)
and archive.

## Risk

### Code-health risk: low
- The scratch-cwd `cd` could break a test that silently relies on the starting cwd · severity: low · → mitigation: none needed (covered by Verification 1, same PASS count)
- The fail-closed repository check refuses to run the file when the caller exports `GIT_DIR` (e.g. from inside a git hook) or sets `TMPDIR` inside a repo — a deliberate behavior change for such invocations, with an explicit message naming both variables · severity: low · → mitigation: none (intended; pinned by the Verification 2 negative controls)

### Goal-achievement risk: medium
- The 2026-09-02 truncation of `t1_alpha.md` happened after the guards landed and remains unexplained. If some process other than this test file writes that name, deleting the files is temporary and the toast returns · severity: medium · → mitigation: audit_unguarded_test_cds
- Other test files have unguarded `cd` lines (about 435 across `tests/*.sh`). Most are harmless (`set -e`, or nothing written), but any one that writes relative paths after a failed `cd` can leak the same way · severity: low · → mitigation: audit_unguarded_test_cds

### Planned mitigations
- timing: after | name: audit_unguarded_test_cds | type: bug | priority: low | effort: medium | inline_risk: low | added_complexity: high | addresses: unguarded cd in other tests can leak fixtures into the live tree (and may explain the 2026-09-02 t1_alpha.md truncation) | desc: Audit tests/*.sh for unguarded cd followed by relative writes or git add/commit, and guard them or give the file a scratch cwd
