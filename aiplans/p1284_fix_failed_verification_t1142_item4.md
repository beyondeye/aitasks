---
Task: t1284_fix_failed_verification_t1142_item4.md
Base branch: main
Output branch: main
---

# t1284 — re-verify t1142 item #4 (unmounted dir share fails closed) on the current tree

## Context

t1142 item #4 failed in two ways on the `dir` artifact backend as it was at
640fc94f4 (t1076_3):

- **Clause 1:** after unmount, "is the share mounted?" was printed, but the
  `die` was swallowed inside `$( )` under `with_attach_lock`. `put` then went on
  to `mkdir`/`mktemp` at `/<2hex>`, and only the read-only `/` stopped it.
- **Clause 2:** a persistent mountpoint directory left behind after unmount was
  accepted as the store. The blob landed on the local disk, the manifest was
  committed, and the command exited 0.

Both clauses have since been fixed in code by sibling tasks:

- **t1283 (9d818998f):** the root is validated in the op's own shell, and a
  `.ait-artifact-store` marker is required. Only `ait artifact init-store dir`
  writes it. Pinned by `tests/test_artifact_share_resolution.sh` §J1 (missing
  path), §J2 (unmarked empty directory — the t1284 case is named there) and §J3
  (cold-cache get), and by `tests/test_artifact_dir_backend.sh` §E.
- **t1960 (86025fc28):** every op holds the store root as its cwd. Pinned by
  `tests/test_artifact_dir_backend.sh` §F/§G.

The pre-t1283 `dir.sh` is byte-identical to the t1076_3 version that t1142
tested.

The two notes received from t1283 and t1960 are advisory. They state that what
is left is a re-verification on a real mount. So this task **reproduces item #4
against the current tree on a real mount**, with the pre-fix tree as the
negative control. If the reproduction shows no defect, the task closes with no
code change and records the evidence here. If it shows a defect, stop and
revise this plan instead of improvising a fix.

Out of scope: a share unmounted **mid-operation** (EBUSY / `umount -l` while a
put holds the cwd). That is owned by the manual-verification task **t1968**.

## Implementation

### 1. Pre-fix tree for the negative control (scratch only)

```bash
S=/tmp/claude-1000/-home-ddt-Work-aitasks/cce294ba-8640-4cce-8851-59e6973f16da/scratchpad
mkdir -p "$S/old" && git archive 9d818998f^ .aitask-scripts | tar -x -C "$S/old"
```

This is a read-only export, so the repository is not touched.

### 2. Scenario script `$S/t1284_item4.sh <tree>`

Write the script in the scratchpad so it can be run. It is **not** a repo file,
but it is not throwaway either. The exact version that produced the evidence is
preserved verbatim in this plan's `## Reproduction script` appendix (Step 5),
which is archived with the plan.

The script must be self-contained so a later reader can rerun it from the
appendix alone:

- it takes the tree to test as `$1`;
- it embeds no scratchpad or session paths;
- its header comment states how to invoke it, including the `unshare` line and
  the pre-fix export command from Step 1.

The script runs entirely inside
`unshare --user --map-root-user --mount --propagation private`. That gives a real
mount and umount without sudo, and nothing leaves the namespace. Unprivileged
user namespaces are enabled here (`kernel.unprivileged_userns_clone=1`).

**Fixture.** The script copies the fixture of
`tests/test_artifact_share_resolution.sh`:

- `TMP=$(mktemp -d)`, with `XDG_CACHE_HOME=$TMP/xdg`;
- a legacy-mode git repo `$TMP/repo` containing `aitasks/t5_demo.md` and the
  `write_config <path>` helper;
- `ART=<tree>/.aitask-scripts/aitask_artifact.sh`.

**The share.** A backing directory `$TMP/backing` is bind-mounted on a
persistent mountpoint directory `$TMP/mnt`. That is a real VFS mount, so after
`umount` the mountpoint is the bare underlying directory, as in the NAS/fstab
case. The backing directory survives, so the remount round-trip can be checked.

**The checks.** Each check prints a `PASS:` / `FAIL:` line, and the script ends
with a count. The script captures `before=$(git rev-list --count HEAD)` and a
copy of the task file before the unmounted operations.

**R1 — the store is the mountpoint itself** (task body, clause 2):
1. `write_config "$MNT"`; `init-store dir` (its failure is tolerated, because
   the pre-fix tree has no such verb).
2. Positive control: `create 5 a.html --kind reportpre --backend dir` exits 0,
   and the blob is present under `$TMP/backing`.
3. `umount "$MNT"`; assert that `find "$MNT" -mindepth 1` is empty.
4. While unmounted, check each of:
   - `create 5 v3b.html --kind report3b --backend dir`;
   - `update art:t5-reportpre b.html`;
   - a cold-cache `get art:t5-reportpre --out got.html` (run
     `rm -rf "$XDG_CACHE_HOME"` first).

   Each must exit nonzero, and the output must contain
   `not an initialized artifact store`.
5. Assert all of these:
   - `find "$MNT" -mindepth 1` is still empty;
   - the commit count is unchanged;
   - there is no `artifacts/manifests/t5-report3b.json`;
   - the task file is byte-identical to the copy;
   - the `art:t5-reportpre` manifest still has one version.
6. Remount (`mount --bind`); the cold-cache `get art:t5-reportpre` succeeds and
   the bytes match `a.html`.

**R2 — the store is a subdirectory of the share** (the original t1142 layout,
`<mount>/store`; clause 1's code path). Unmounting removes the store path, just
as udisks removes `/run/media/<user>/<label>`:
1. `mkdir "$MNT/store"` while mounted, then `write_config "$MNT/store"`, then
   `init-store dir`.
2. Positive control: `create` exits 0.
3. `umount "$MNT"`, then repeat the step-4 operations. Each must exit nonzero,
   and the output must contain `is the share mounted`. The output must contain
   neither `mktemp` nor `cannot create directory '/`.
4. Assert all of these:
   - `$MNT/store` was not created;
   - `find "$MNT" -mindepth 1` is empty;
   - there is no new commit and no new manifest.

At the end, the script unmounts whatever is still mounted and runs
`rm -rf "$TMP"`. Nothing outlives the namespace.

### 3. Run it

```bash
unshare --user --map-root-user --mount --propagation private bash "$S/t1284_item4.sh" /home/ddt/Work/aitasks
unshare --user --map-root-user --mount --propagation private bash "$S/t1284_item4.sh" "$S/old"
```

Expected results:

| Tree | Expected | Why |
|---|---|---|
| current | all PASS | |
| pre-fix | R1 step 4/5 FAIL | `create` exits 0 and a blob lands in `$MNT` (clause 2 reproduced) |
| pre-fix | R2 step 3 FAIL | `mktemp`/`mkdir` at `/` in the output (clause 1 reproduced) |

If the pre-fix run does **not** fail those checks, the script is not
reproducing the defect. In that case, fix the script before drawing any
conclusion.

### 4. Existing pinned tests

```bash
bash tests/test_artifact_dir_backend.sh
bash tests/test_artifact_share_resolution.sh
bash tests/test_artifact_cli.sh
```

### 5. Outcome

- **Current tree all PASS, and the pre-fix tree reproduces both clauses:** item
  #4 is satisfied. There is no code change. Make the evidence durable in the
  plan file, which is committed and then archived:
  - **`## Reproduction script` appendix:** the script verbatim, in a fenced
    block. After the final run, confirm the appendix is byte-identical to the
    file that ran:
    `diff <(sed -n '/^## Reproduction script/,$p' <plan> | awk '/^```bash$/{f=1;next} f&&/^```$/{exit} f') "$S/t1284_item4.sh"`
    must print nothing. The extraction takes the first `bash` fence under the
    heading and stops at its closing fence. The evidence section uses `text`
    fences.
  - **`## Reproduction evidence` section:** the **complete** per-check output of
    both runs, meaning every `PASS:`/`FAIL:` line and the counts, not only the
    tails. Add the facts that date the evidence: the tested tree's
    `git rev-parse HEAD`, the pre-fix tree (`9d818998f^`), `uname -r`,
    `unshare --version`, and the run date.
  - **Final Implementation Notes:** a short summary pointing at those two
    sections.

  Then commit only the plan. Archive t1284 in Step 9 as fixed by t1283 + t1960,
  and re-verified here.
- **Any current-tree FAIL:** stop. Report the failing check and its output, and
  revise this plan with a root-caused fix before writing any code.

### 6. Note to t1968 (Step 8e, after the plan commit)

Send the note only once the plan carrying the appendix is committed, so the
reference resolves. Send `./ait note 1968 --from 1284` (via `/aitask-note`),
stating that:

- `unshare --user --map-root-user --mount --propagation private` gave a real
  bind mount and umount of a dir store without sudo here;
- the reference script and its evidence are the `## Reproduction script` and
  `## Reproduction evidence` sections of t1284's plan.
  - Name the path `aiplans/p1284_fix_failed_verification_t1142_item4.md`, which
    moves to `aiplans/archived/` on archival.
  - Name the plan commit SHA, so `git show <sha>:<path>` retrieves it
    regardless of where the file later lives.
- this may let t1968 run its real `umount` / `umount -l` probes unprivileged;
- this run did **not** exercise the mid-put windows (EBUSY, a lazy detach),
  which stay t1968's to verify.

Mark the note advisory and hedged.

## Verification

- Step 3 table: the current tree is all PASS, and the pre-fix tree FAILs exactly
  the clause-1 and clause-2 checks.
- Step 4 tests pass.
- `git status --porcelain` shows no code changes (only the plan and task data
  under `./ait git`).
- The committed plan contains the `## Reproduction script` appendix, and the
  appendix is byte-identical to the script that ran (the `diff` in Step 5 prints
  nothing). It also contains the full `## Reproduction evidence` for both trees.

## Step 9

Post-implementation: there is no code commit. Commit the plan via
`aitask_task_commit.sh`, then archive per task-workflow Step 9.

## Risk

### Code-health risk: low
- No framework code is changed. The scenario script and the pre-fix export live
  in the scratchpad, and the mounts exist only inside a private mount namespace
  · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The real-mount reproduction uses a bind mount in a user namespace rather than
  the udisks loop mount of the original run. To the code, an unmounted
  mountpoint is the bare underlying directory either way. The udisks variant
  (the mountpoint is removed) is the R2 layout, where the store path is missing
  after unmount. · severity: low · → mitigation: none needed (R1 + R2 cover both
  layouts)
- Closing a bug task with no code change rests on the reproduction being able to
  detect the defect. The pre-fix tree must fail the clause checks, or no
  conclusion is drawn. · severity: low · → mitigation: none needed (in plan,
  step 3 negative control)
- Mid-operation unmount is not exercised · severity: low · → mitigation: t1968
  (existing task; out of scope here)
- The closure evidence could be unreproducible if the script lived only in the
  session scratchpad · severity: low (residual — the script is preserved
  verbatim in the archived plan, with a byte-identity check against the
  version that ran, and the full per-check output is recorded) · → mitigation:
  none needed (in plan, Step 5)
