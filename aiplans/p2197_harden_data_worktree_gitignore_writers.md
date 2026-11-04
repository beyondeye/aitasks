---
Task: t2197_harden_data_worktree_gitignore_writers.md
Base branch: main
Output branch: main
---

# t2197 — Harden setup_data_branch's `.aitask-data/.gitignore` writers

## Context

`setup_data_branch` Step 3 (`.aitask-scripts/aitask_setup.sh:1920-1972`) appends
six blocks to the data worktree's `.gitignore`. Each block is a bare
`{ echo …; } >> "$data_gitignore"` with only a `grep -q[x]F` guard. `main()` runs
under `set -euo pipefail`, so a failed append aborts `ait setup` partway, and
each group's status comes from its last command only. This is the same bug class
t2185 and t2188 fixed for the main `.gitignore`. t2191's
`refuse_nonregular_gitignores` precheck cannot cover this path, because on a
fresh setup `.aitask-data/` does not exist yet when `main()` starts.

### Probe (done during planning)

Script: `/tmp/claude-1000/-home-ddt-Work-aitasks/763ba652-af3d-428c-88ce-7f66bfac6747/scratchpad/probe.sh`.
It runs the real `setup_data_branch` under `set -euo pipefail` in throwaway
repos. For the symlink cases it first creates a local `aitask-data` branch whose
`.gitignore` is a git symlink (git does store symlinks).

| trigger | result |
|---|---|
| no fault (umask 022) | rc 0, 496-byte file (saved as `baseline_data_gitignore`) |
| umask 0222 / 0277 (the task's guess) | **does not reach it**: setup fails earlier (rc 1, the branch is never even created) |
| `.gitignore` → symlink to a read-only regular file | **reaches it**: `Permission denied`, setup aborts under errexit |
| `.gitignore` → symlink to `/dev/full` | **reaches it**: `echo: write error: No space left on device` at `:1924`, abort |
| `.gitignore` → symlink to a FIFO | **reaches it and hangs** (the probe's 20 s timeout fired, rc 124) |

So the real triggers are an existing `aitask-data` branch (remote or local)
whose `.gitignore` is a symlink to a non-regular or unwritable file, plus
ENOSPC. Every abort leaves a half-built `.aitask-data` worktree with no
symlinks. A later `ait setup` then returns at "already configured" and never
finishes the setup.

**A symlinked `.gitignore` is worse than a write fault, and was already a hole
in the old code.** git's own docs (`git help gitignore`, 2.56) say: "Git does
not follow symbolic links when accessing a .gitignore file in the working
tree." So with a symlinked `.aitask-data/.gitignore` *no rule in it takes
effect*, even when every write and every grep read-back succeeds through the
link. Step 4's `git add .` then commits the migrated private files (a reviewer
reproduced this: writer rc 0, rule present, `git check-ignore` 1,
`git add --dry-run .` listed `userconfig.yaml`). A regular, non-symlink file is
therefore a **precondition** of this caller, not something the writer's `-f`
guard (which follows links) can establish. Materializing the link as a regular
file was rejected: it would silently rewrite the branch's tracked `.gitignore`
(symlink → file) in Step 4's commit.

**Why a failed write must stop setup rather than warn and continue.** Step 4
runs a blanket `git add .` in the data worktree and pushes. On the migration
path, `cp -a aitasks/.` has just copied the user's `userconfig.yaml`,
`*.local.json` and `chatlink_sessions/` / `applink_sessions/` secrets into the
worktree. If the rules are missing, those files get committed and pushed. So a
rule that cannot be written has to stop setup **before Step 4**. The
fail-closed route already exists: `abort_data_branch_setup` (`:1592`, the same
route Step 4's commit failure uses). It tears the worktree down and leaves the
legacy layout, so a later `ait setup` retries from scratch.

## Implementation

### 1. Rule table: add the data-worktree groups (`_ait_gitignore_group`, `:3433`)

Reuse the existing `drafts` group. Its comment and rule are byte-identical to the
first data block. Add five groups. The strings are copied verbatim from the
current Step 3 echoes, so the output stays byte-identical:

| group | comment | rule | `_ait_gi_what` | `_ait_gi_label` |
|---|---|---|---|---|
| `data_userconfig` | `Per-user config (local, not shared)` | `aitasks/metadata/userconfig.yaml` | `Per-user config (userconfig.yaml)` | `per-user config` |
| `data_local_json` | `Per-user overrides (*.local.json files, not shared)` | `aitasks/metadata/*.local.json` | `Per-user override files (*.local.json)` | `per-user overrides` |
| `data_local_profiles` | `Per-user execution profiles (local, not shared)` | `aitasks/metadata/profiles/local/` | `Per-user execution profiles` | `per-user profiles` |
| `data_chatlink` | `chatlink runtime state (per-PC: bot token + relay spools)` | `aitasks/metadata/chatlink_sessions/` | `chatlink runtime state` | `chatlink runtime state` |
| `data_applink` | `applink runtime state (per-PC: TLS cert/key + active bearer sessions)` | `aitasks/metadata/applink_sessions/` | `applink runtime state` | `applink runtime state` |

Add a short comment saying these five groups belong to the data worktree's own
`.gitignore`, are written only by `setup_data_branch` Step 3, and are never
written to the main `.gitignore` or by the upgrade loop.

### 2. Step 3: route the blocks through the per-rule writer (`:1920-1972`)

Replace the six echo blocks with a precondition, then one loop.

**Precondition (new, first):** if `$data_gitignore` is a symlink (`[[ -L ]]`,
which covers dangling links too), or exists and is not a regular file
(`[[ -e && ! -f ]]`, e.g. a `.gitignore/` tree entry checked out as a
directory), call `abort_data_branch_setup` and return. Nothing gets written
through the link and no target is touched. The reason text says what was found
(`is a symlink — git ignores a symlinked .gitignore, so its rules would not keep
private files out of the commit` / `is not a regular file`) and gives the fix:
"replace `.gitignore` on the aitask-data branch with a regular file (e.g. `git
show aitask-data:.gitignore` to inspect it), then re-run 'ait setup'". The
writer's own non-regular check stays as a backstop.

```bash
    # The data worktree's own .gitignore rules go through the per-rule writer
    # (_ait_add_gitignore_rules): checked writes, a read-back, and no `>>` that
    # blocks on a FIFO or aborts setup under errexit (t2197, as t2185/t2188 for
    # the main .gitignore). t2191's non-regular refusal cannot cover this file:
    # on a fresh setup .aitask-data/ does not exist when main() starts, and an
    # existing aitask-data branch can carry .gitignore as a symlink.
    # A rule that cannot be written stops setup HERE, before Step 4: Step 4's
    # `git add .` would otherwise commit (and push) exactly what these rules
    # keep out — on migration, the userconfig, *.local.json and chatlink/applink
    # secrets cp just copied in. abort_data_branch_setup leaves the legacy
    # layout, which the next `ait setup` retries from scratch.
    local data_gitignore="$project_dir/$AIT_DATA_DIR_NAME/.gitignore" gi_group gi_rc
    for gi_group in drafts data_userconfig data_local_json data_local_profiles \
                    data_chatlink data_applink; do
        _ait_gitignore_group "$gi_group"
        gi_rc=0
        _ait_add_gitignore_rules "$data_gitignore" "$_ait_gi_comment" \
            "${_ait_gi_rules[@]}" || gi_rc=$?
        if [[ "$gi_rc" -eq 2 ]]; then
            local gi_state="it is not a regular file, or the write failed — left unchanged"
            [[ -n "$_ait_gitignore_partial" ]] && \
                gi_state="the write stopped part-way, so the file it reached may now end in an incomplete entry"
            abort_data_branch_setup "$project_dir" "$branch_exists" "$needs_migration" \
                "Could not add ${_ait_gi_rules[*]} to $AIT_DATA_DIR_NAME/.gitignore ($gi_state). Stopping before the data branch commit, which would otherwise commit them: $_ait_gi_what."
            return
        fi
    done
```

(`$_ait_gi_what` is used as-is, with no `${,,}`, which bash 3.2 lacks. Since the
precondition guarantees a regular file inside the worktree, the partial bytes
vanish with the worktree on teardown. The "part-way" wording describes the
moment of failure, and the abort says the worktree was removed.)

Byte identity: on an absent file the writer writes `# comment\nrule\n` with no
leading blank line, and on an existing one `\n# comment\nrule\n`. That is
exactly what the old echoes produced on a fresh worktree. Test 41's control pins
this against the probe's baseline bytes.

**Accepted semantic narrowing (deliberate):** the old `*.local.json` and
`profiles/local/` guards were substring `grep -qF`. They counted *any* line that
contained the text, including their own comment line, as present. So a
`.gitignore` that kept the comment but lost the rule was never repaired. The
per-rule writer matches whole lines, in LF or CRLF form. This only matters on a
pre-existing data branch whose `.gitignore` has a broader or variant line, and
there the result is one extra, exact rule. Record this in the code comment.

### 3. Repoint the source-shape test (`tests/test_applink_setup_gitignore.sh`)

Part 1 currently greps the setup source for `grep -qxF "aitasks/metadata/applink_sessions/"`
and `echo "aitasks/metadata/applink_sessions/"`, so it breaks with this change.
Rewrite it to source `aitask_setup.sh --source-only` (with `task_utils.sh`, as
other tests do) and:
- Part 1: `_ait_gitignore_group data_applink` yields `_ait_gi_rules == (aitasks/metadata/applink_sessions/)`.
  Also assert that Step 3's loop names `data_applink`, by scanning the body of
  `declare -f setup_data_branch` for the group word. This keeps the original
  "the block was removed" guard.
- Part 2: take `SEEDED_PATH` from `_ait_gi_rules[0]` instead of parsing the
  source. The check-ignore positives and negative control stay as they are.

### 4. Regression test: Test 41 in `tests/test_data_branch_setup.sh`

Put it after Test 40b. It uses Test 40's harness shape: `run_bounded 30` and a
child `bash -c` that sources setup (errexit on, with an `ERREXIT_ON` control)
and runs `setup_data_branch`, then `echo SURVIVED`. Add a helper
`t41_seed_branch <dir> <symlink-target|regular:<content>>` that pre-creates a
local `aitask-data` branch with a `.gitignore` entry, built with
`hash-object` + `mktree` + `commit-tree` + `update-ref` as in the probe.

Shared "stopped before Step 4" assertions (`t41_assert_stopped`): the child
returns within 30 s (124 = hung), `ERREXIT_ON`, `SURVIVED`. `.aitask-data` is
gone, `aitasks` is not a symlink, the `aitask-data` branch tip is unchanged (no
Step 4 commit), and `Task data branch configured successfully` is absent.

Cases:
- **clean** (no pre-existing branch, fresh create): no-fault control. rc 0,
  `SURVIVED`, "configured successfully". `.aitask-data/.gitignore` matches a
  literal heredoc of the probe's 496 baseline bytes **byte for byte**, which
  proves the output is identical to the old code's. Goal-level check:
  `git -C .aitask-data check-ignore -q` succeeds for one representative path
  per rule (`aitasks/new/x.md`, `aitasks/metadata/userconfig.yaml`,
  `aitasks/metadata/x.local.json`, `aitasks/metadata/profiles/local/x.yaml`,
  `aitasks/metadata/chatlink_sessions/x`, `aitasks/metadata/applink_sessions/x`),
  and fails for `aitasks/metadata/labels.txt` (negative control).
- **regular** (pre-existing branch whose `.gitignore` is a regular file: `keep-me`
  with no trailing newline, then `aitasks/metadata/userconfig.yaml`): rc 0. The
  first appended block's separator ends `keep-me` (no `keep-me#` glue).
  `userconfig.yaml` appears exactly once. Each other rule appears exactly once.
- **writable-symlink + migration** (the reviewer's case, the high-severity one):
  legacy `aitasks/` holding `aitasks/metadata/userconfig.yaml` and
  `aitasks/metadata/applink_sessions/tls_key.pem`, plus a pre-existing branch
  whose `.gitignore` is a symlink to a **writable** regular file outside the
  fixture repo that already lists every rule. Fixture control: before running
  setup, assert that git really ignores nothing through it. In a scratch repo,
  a `.gitignore` symlink to that target gives `git check-ignore` rc 1 for
  `aitasks/metadata/userconfig.yaml`, which proves the premise on this git.
  Then: `t41_assert_stopped`. The reason names the symlink and git's
  no-follow. The target is byte-identical, `aitasks/` is still a real
  directory with both files, "Nothing was removed from the current branch"
  appears, and `git ls-tree -r aitask-data` lists neither file.
- **fifo-symlink** (symlink → a FIFO; the old code hung here): `t41_assert_stopped`
  (the 30 s bound is the point), and the FIFO is still a FIFO.
- **directory** (branch tree has `.gitignore/keep`, so it checks out as a
  directory): `t41_assert_stopped`, and the reason says "not a regular file".
- **late write fault + migration** (concern 2: a real failure after earlier
  groups landed, against a regular in-worktree file). Fresh branch, legacy
  `aitasks/` with `userconfig.yaml`. The child shadows `echo` as 27n does,
  failing only on `echo "# Per-user execution profiles (local, not shared)"`.
  That is the fourth group's comment, written after its separator and after
  `drafts`, `data_userconfig` and `data_local_json` have landed. Assert
  `t41_assert_stopped`, the partial diagnostic ("stopped part-way") naming
  `aitasks/metadata/profiles/local/`, and no `left unchanged` claim for it.
  Also assert migration originals intact and no `aitask-data` commit carrying
  `userconfig.yaml`. Binding check: the shadowed literal equals
  `_ait_gitignore_group data_local_profiles`'s comment, so the fault
  provably hits the group under test.

Red proof for the fix itself: before the code change, run Test 41 against the
unmodified `aitask_setup.sh` and record which cases fail. The expected result:
writable-symlink gets past Step 4 and commits `userconfig.yaml`; fifo-symlink
hangs to 124; the late fault lacks `SURVIVED`. Put the observed results in the
Final Implementation Notes.

### 5. Lint

`shellcheck .aitask-scripts/aitask_setup.sh` (no new warnings). Shellcheck the
two edited test files as well.

## Verification

- `bash tests/test_data_branch_setup.sh` (Test 41 green; Tests 1-40b unchanged)
- `bash tests/test_applink_setup_gitignore.sh`
- `bash tests/test_setup_git.sh` (27h/27k/27n rely on the table; the new groups must not change existing groups' bytes)
- `bash tests/test_data_branch_migration.sh`, `bash tests/test_init_data.sh`,
  `bash tests/test_ait_git_gateway_pull.sh`, `bash tests/test_gitignore_data_symlinks.sh`
  (other `setup_data_branch` drivers)
- Re-run the scratchpad probe against the fixed code: every fault case returns
  promptly with the abort message and leaves no `.aitask-data`. Also confirm
  the FIFO teardown (`git worktree remove --force`) does not block.

Then Step 9 (Post-Implementation): commit, archive.

## Risk

### Code-health risk: low
- The table gains five groups the main/upgrade routes never read. A future refactor could feed them into `upgrade_store_gitignore_rules` or the main `.gitignore` by mistake · severity: low · → mitigation: none (the table comment names their only writer)
- Substring → whole-line guard for the `*.local.json` / `profiles/local/` rules can add one redundant rule on a pre-existing branch with a variant line · severity: low · → mitigation: none (accepted, documented in the code comment)

- The new symlink refusal also stops a pre-existing data branch whose `.gitignore` is a symlink that previously "worked" (it never did: git ignored it). Such users now get an abort with a fix instead of a silent commit of private files · severity: low · → mitigation: none (intended, fail-closed)

### Goal-achievement risk: low
- Writes plus grep read-back alone would not prove git honours the rules (a symlinked `.gitignore`) · severity: low (residual: addressed in the plan by the regular-file precondition and the clean case's `git check-ignore` goal check) · → mitigation: none
- The abort's `git worktree remove --force` might read the FIFO-symlink `.gitignore` and block · severity: low · → mitigation: none (git does not follow symlinked `.gitignore`; Test 41 fifo-symlink is bounded at 30 s)

## Final Implementation Notes
- **Actual work done:** As planned. `setup_data_branch` Step 3 (`aitask_setup.sh`) now (1) refuses a `.aitask-data/.gitignore` that is a symlink (dangling included) or an existing non-regular file, via `abort_data_branch_setup`, before any write; (2) writes `drafts` + the five new `data_*` table groups through `_ait_add_gitignore_rules`, aborting on rc 2 with the part-way / left-unchanged wording. Fresh-setup output is byte-identical to the old echo blocks (Test 41 clean pins the captured bytes). `tests/test_applink_setup_gitignore.sh` reads the table group + `declare -f setup_data_branch` instead of grepping source shapes.
- **Deviations from plan:** (a) Test 32 (t1631) relied on `cp_ok_then_drop_worktree`, which deleted the data worktree right after the copy; the checked Step 3 now catches that vanished worktree first (correctly), so Step 4's `cd ... || exit 1` guard was no longer reached. Replaced it (only user) with `grep_last_readback_drop_worktree`: grep runs for real, and after Step 3's LAST read-back (the applink rule) succeeds the worktree is removed, so Step 4 is still the first step to meet it missing. (b) The symlink abort message reads ".aitask-data/.gitignore is a symlink — git does not follow a symlinked .gitignore, ... (it comes from the existing aitask-data branch)". (c) `_ait_gi_what` strings are lower-case phrases (used mid-sentence) instead of the planned capitalised ones.
- **Issues encountered:** Red proof against the unmodified code (Test 41 added first): writable-symlink + migration → "configured successfully" and `git ls-tree aitask-data` listed `aitasks/metadata/userconfig.yaml` and `applink_sessions/tls_key.pem` (secrets committed); fifo-symlink → rc 124 (hung); directory → rc 1 (errexit abort, worktree left); regular → `keep-me#` glue; late write fault (echo shadow on the profiles/local comment) → no SURVIVED, setup aborted under errexit with a half-written data .gitignore. Fixed code: 580/580 in test_data_branch_setup.sh. Mutants: dropping the `-L` precondition fails only the writable-symlink case (fifo/directory still stopped by the writer's own non-regular backstop); turning the rc-2 abort off fails only the late-fault case. Planning probe re-run: every fault case returns promptly with the abort and no `.aitask-data` left; FIFO teardown does not block. umask 0222/0277 do not reach Step 3 (setup fails earlier) — the task's guessed trigger is not the real one.
- **Key decisions:** Refuse rather than materialize a symlinked .gitignore (materializing would silently rewrite the branch's tracked file in Step 4's commit). Any failed rule write aborts (fail-closed) rather than warns, since Step 4's `git add .` would otherwise commit/push the very files the rule excludes. Accepted narrowing: `*.local.json` / `profiles/local/` presence is now whole-line, not substring (the old substring guard also matched its own comment line).
- **Upstream defects identified:** None
- **Verification:** test_data_branch_setup (580/0), test_applink_setup_gitignore (5/0), test_setup_git, test_data_branch_migration, test_init_data, test_ait_git_gateway_pull, test_gitignore_data_symlinks, test_install_create_data_dirs, test_install_upgrade_dirty_baseline, test_sync_fetch_exclusion, test_agent_instructions — all green. shellcheck: no new warnings in aitask_setup.sh (diffed against HEAD); the new test code adds only an SC2016 info identical to Test 40's.
