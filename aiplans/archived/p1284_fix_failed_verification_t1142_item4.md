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

## Reproduction evidence

Produced by the `## Reproduction script` below (its sha256 is in the environment block). Run as:
`unshare --user --map-root-user --mount --propagation private bash t1284_item4.sh <tree>`.
The `== tree:` line names the session scratch location each tree was run from: the
checkout for the current tree, and a `git archive 9d818998f^ .aitask-scripts` export for the pre-fix tree.
The artifact code (`aitask_artifact.sh`, `lib/artifact_backend*.sh`, `lib/artifact_backends/`,
`lib/attachment_lock.sh`, `lib/txn_snapshot.sh`) is identical between the plan-time HEAD 6a3a81efc and the tested HEAD.

### Environment

```text
date: 2026-10-13 21:02 UTC
tested tree HEAD: 8718afa0877d3e336f05c95d4b4dc37b30c5f6a5
pre-fix tree: 13a8751d59fde438d0a871bd130bc70fb4df23eb (9d818998f^)
kernel: 7.2.4-arch1-2
unshare from util-linux 2.42.3
script sha256: ad7592514d5949ce4e8b73fca58bd655822e61a979a9d8e3cbca9f6bc1251652
```

### Current tree: 39 passed, 0 failed

```text
== tree: /home/ddt/Work/aitasks
== R1: store root is the mountpoint itself
PASS: R1 positive control: create while mounted exits 0
PASS: R1 positive control: blob landed in the share
PASS: R1 unmounted mountpoint is an empty directory
PASS: R1 create exits nonzero (rc=1)
PASS: R1 create says 'not an initialized artifact store'
PASS: R1 create derives no root-level path
PASS: R1 update exits nonzero (rc=1)
PASS: R1 update says 'not an initialized artifact store'
PASS: R1 update derives no root-level path
PASS: R1 cold-cache get exits nonzero (rc=1)
PASS: R1 cold-cache get says 'not an initialized artifact store'
PASS: R1 cold-cache get derives no root-level path
PASS: R1 nothing written into the unmounted mountpoint
PASS: R1 no commit
PASS: R1 no manifest for the refused create
PASS: R1 task file untouched
PASS: R1 existing handle still has 1 version
PASS: R1 attach lock released
PASS: R1 after remount: cold-cache get exits 0
PASS: R1 after remount: bytes match the original
== R2: store root is a subdirectory of the share
PASS: R2 positive control: create while mounted exits 0
PASS: R2 positive control: blob landed in the share
PASS: R2 unmounted mountpoint is an empty directory
PASS: R2 create exits nonzero (rc=1)
PASS: R2 create says 'is the share mounted'
PASS: R2 create derives no root-level path
PASS: R2 update exits nonzero (rc=1)
PASS: R2 update says 'is the share mounted'
PASS: R2 update derives no root-level path
PASS: R2 cold-cache get exits nonzero (rc=1)
PASS: R2 cold-cache get says 'is the share mounted'
PASS: R2 cold-cache get derives no root-level path
PASS: R2 store root was not created
PASS: R2 nothing written into the unmounted mountpoint
PASS: R2 no commit
PASS: R2 no manifest for the refused create
PASS: R2 task file untouched
PASS: R2 existing handle still has 1 version
PASS: R2 attach lock released
RESULT: 39 passed, 0 failed
```

### Pre-fix tree (negative control): 24 passed, 15 failed

Each FAIL is one of the defects t1142 item #4 observed:

- **R1 (clause 2):** `create` and `update` exit 0 into the bare unmounted
  mountpoint and commit. After remount those blobs are hidden, and the cold-cache
  `get` of the updated handle fails. That is the "blob not found on every other
  checkout" symptom. The R1 cold-cache `get` *succeeds* while unmounted only because
  the pre-fix `update` had just written v2 into the bare mountpoint.
- **R2 (clause 1):** the message is printed, but `put` goes on to `mkdir`/`mktemp` at
  `/<2hex>`.

```text
== tree: /tmp/claude-1000/-home-ddt-Work-aitasks/cce294ba-8640-4cce-8851-59e6973f16da/scratchpad/old
== R1: store root is the mountpoint itself
note: init-store unavailable or failed (expected on the pre-fix tree)
PASS: R1 positive control: create while mounted exits 0
PASS: R1 positive control: blob landed in the share
PASS: R1 unmounted mountpoint is an empty directory
FAIL: R1 create exits nonzero -- rc=0: Created artifact art:t5-v3b (v1 sha256:ad9e8874a91eb131bb5b767dffe0140c4c1406f7658c3f7222b0b6f3640843f4) on t5 HANDLE:art:t5-v3b 
FAIL: R1 create says 'not an initialized artifact store' -- Created artifact art:t5-v3b (v1 sha256:ad9e8874a91eb131bb5b767dffe0140c4c1406f7658c3f7222b0b6f3640843f4) on t5 HANDLE:art:t5-v3b 
PASS: R1 create derives no root-level path
FAIL: R1 update exits nonzero -- rc=0: Updated artifact art:t5-pre1 — current is now sha256:f0bb9a80dfd9312e4d8c3229a955eec8a5e7e86a310be74f6a81fcd93480c3c3 
FAIL: R1 update says 'not an initialized artifact store' -- Updated artifact art:t5-pre1 — current is now sha256:f0bb9a80dfd9312e4d8c3229a955eec8a5e7e86a310be74f6a81fcd93480c3c3 
PASS: R1 update derives no root-level path
FAIL: R1 cold-cache get exits nonzero -- rc=0: Wrote got1.html 
FAIL: R1 cold-cache get says 'not an initialized artifact store' -- Wrote got1.html 
PASS: R1 cold-cache get derives no root-level path
FAIL: R1 nothing written into the unmounted mountpoint
FAIL: R1 no commit
FAIL: R1 no manifest for the refused create
FAIL: R1 task file untouched
FAIL: R1 existing handle still has 1 version
PASS: R1 attach lock released
FAIL: R1 after remount: cold-cache get exits 0
FAIL: R1 after remount: bytes match the original
== R2: store root is a subdirectory of the share
note: init-store unavailable or failed (expected on the pre-fix tree)
PASS: R2 positive control: create while mounted exits 0
PASS: R2 positive control: blob landed in the share
PASS: R2 unmounted mountpoint is an empty directory
PASS: R2 create exits nonzero (rc=1)
PASS: R2 create says 'is the share mounted'
FAIL: R2 create derives no root-level path -- mkdir: cannot create directory ‘/ad’: Permission denied mktemp: failed to create file via template ‘/ad/.put.XXXXXX’: No such file or directory Error: artifact_dir_put: mktemp failed in /ad 
PASS: R2 update exits nonzero (rc=1)
PASS: R2 update says 'is the share mounted'
FAIL: R2 update derives no root-level path -- mkdir: cannot create directory ‘/f0’: Permission denied mktemp: failed to create file via template ‘/f0/.put.XXXXXX’: No such file or directory Error: artifact_dir_put: mktemp failed in /f0 
PASS: R2 cold-cache get exits nonzero (rc=1)
PASS: R2 cold-cache get says 'is the share mounted'
PASS: R2 cold-cache get derives no root-level path
PASS: R2 store root was not created
PASS: R2 nothing written into the unmounted mountpoint
PASS: R2 no commit
PASS: R2 no manifest for the refused create
PASS: R2 task file untouched
PASS: R2 existing handle still has 1 version
PASS: R2 attach lock released
RESULT: 24 passed, 15 failed
```

## Reproduction script

Verbatim copy of the file that produced the evidence above (`t1284_item4.sh`).
To rerun it, save this block as `t1284_item4.sh` and use the invocation in its header.

```bash
#!/usr/bin/env bash
# t1284_item4.sh - re-verify t1142 item #4 ("unmount the share and confirm
# operations fail closed with 'is the share mounted?' - nothing is written
# into the empty mountpoint dir") for the dir artifact backend, on a REAL
# mount, without sudo.
#
# Usage (run from anywhere; <tree> is an aitasks checkout or export that has
# .aitask-scripts/):
#   unshare --user --map-root-user --mount --propagation private \
#       bash t1284_item4.sh <tree>
# Pre-fix tree for the negative control (dir.sh as tested by t1142):
#   git archive 9d818998f^ .aitask-scripts | tar -x -C <dir>
#
# The share is a bind mount of a backing dir onto a persistent mountpoint dir:
# a real VFS mount, so after umount the mountpoint is the bare underlying
# directory (the NAS/fstab case). Everything lives in a private mount
# namespace and a mktemp dir; nothing outlives the run.
#   R1 - store root IS the mountpoint      (t1284 clause 2: empty mountpoint)
#   R2 - store root is <mountpoint>/store  (t1142 layout; clause 1: root gone)
# Each check prints PASS:/FAIL:; the last line is the count.
set -uo pipefail

TREE="$(cd "${1:?usage: t1284_item4.sh <tree>}" && pwd)"
ART="$TREE/.aitask-scripts/aitask_artifact.sh"
[[ -x "$ART" ]] || { echo "not a tree: $TREE" >&2; exit 2; }
[[ "$(id -u)" == 0 ]] \
    || { echo "run inside: unshare --user --map-root-user --mount --propagation private" >&2; exit 2; }

PASS=0; FAIL=0
ok()  { PASS=$((PASS + 1)); echo "PASS: $1"; }
bad() { FAIL=$((FAIL + 1)); echo "FAIL: $1${2:+ -- $2}"; }
check() { local d="$1"; shift; if "$@"; then ok "$d"; else bad "$d"; fi; }
has()  { [[ "$2" == *"$1"* ]]; }
# Negative answers must be qualified: an inspection failure (missing or
# unreadable dir, EACCES on a parent) is never "empty" / "absent".
empty_dir() { local out; out="$(find "$1" -mindepth 1 -print -quit)" || return 1; [[ -z "$out" ]]; }
absent() { local out; out="$(LC_ALL=C ls -ld -- "$1" 2>&1)" && return 1; [[ "$out" == *"No such file or directory" ]]; }
# Strip colour codes (a regex, so not expressible as ${var//...}).
# shellcheck disable=SC2001
one_line() { sed 's/\x1b\[[0-9;]*m//g' <<<"$1" | tr '\n' ' ' | cut -c1-240; }

TMP="$(mktemp -d)"
cleanup() {
    mountpoint -q "$TMP/mnt1" && umount "$TMP/mnt1"
    mountpoint -q "$TMP/mnt2" && umount "$TMP/mnt2"
    rm -rf "$TMP"
}
trap cleanup EXIT
export XDG_CACHE_HOME="$TMP/xdg" ATTACH_LOCK_TIMEOUT=2

# Fixture: same shape as tests/test_artifact_share_resolution.sh.
mkdir -p "$TMP/repo/aitasks/metadata" "$TMP/backing1" "$TMP/mnt1" "$TMP/backing2" "$TMP/mnt2"
cd "$TMP/repo" || exit 2
git init -q; git config user.email t@t.t; git config user.name tester
printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask t5 body.\n' > aitasks/t5_demo.md
write_config() {  # write_config <store-path>
    printf 'attachments_gc_grace: 0\nartifacts:\n  default_backend: dir\n  backends:\n    dir:\n      path: %s\n' "$1" \
        > aitasks/metadata/project_config.yaml
}
write_config "$TMP/mnt1"
git add -A; git commit -q -m init
printf '<p>pre</p>\n'   > a.html
printf '<p>v2</p>\n'    > b.html
printf '<p>v3b</p>\n'   > v3b.html
printf '<p>pre2</p>\n'  > c.html
blob_rel() { local h; h="$(sha256sum "$1" | cut -d' ' -f1)"; printf '%s/%s' "${h:0:2}" "${h:2}"; }
nversions() { python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["versions"]))' \
    "artifacts/manifests/${1#art:}.json" 2>/dev/null || echo none; }
commits() { git rev-list --count HEAD; }
no_lock() { absent attachments/.attach.lock; }

# A put that derived its path from an empty root (pre-fix clause 1) shows up as
# mkdir/mktemp errors at /<2hex>. coreutils quotes the path per locale: ASCII
# '/ad' under C, curly ‘/ad’ under UTF-8 - match both.
ROOT_PATH_RE="mktemp|cannot create directory ['‘]/[0-9a-f]{2}['’]"

# refused <label> <expected-msg> <cmd...> -- the op must exit nonzero, name
# the expected cause, and never try to create anything at the filesystem root.
refused() {
    local label="$1" msg="$2" out rc; shift 2
    out="$("$@" 2>&1)"; rc=$?
    if [[ $rc -ne 0 ]]; then ok "$label exits nonzero (rc=$rc)"; else bad "$label exits nonzero" "rc=0: $(one_line "$out")"; fi
    if has "$msg" "$out"; then ok "$label says '$msg'"; else bad "$label says '$msg'" "$(one_line "$out")"; fi
    if [[ "$out" =~ $ROOT_PATH_RE ]]; then
        bad "$label derives no root-level path" "$(one_line "$(grep -E "$ROOT_PATH_RE" <<<"$out")")"
    else ok "$label derives no root-level path"; fi
}

echo "== tree: $TREE"

# ── R1: store root IS the mountpoint ─────────────────────────────────────────
echo "== R1: store root is the mountpoint itself"
MNT="$TMP/mnt1"; BACK="$TMP/backing1"
mount --bind "$BACK" "$MNT"
write_config "$MNT"
"$ART" init-store dir >/dev/null 2>&1 || echo "note: init-store unavailable or failed (expected on the pre-fix tree)"
out="$("$ART" create 5 a.html --kind report --handle art:t5-pre1 --backend dir 2>&1)"; rc=$?
check "R1 positive control: create while mounted exits 0" test "$rc" -eq 0
check "R1 positive control: blob landed in the share" test -f "$BACK/$(blob_rel a.html)"
umount "$MNT"
check "R1 unmounted mountpoint is an empty directory" empty_dir "$MNT"
before="$(commits)"; cp aitasks/t5_demo.md "$TMP/t5.before"
refused "R1 create" "not an initialized artifact store" \
    "$ART" create 5 v3b.html --kind report --handle art:t5-v3b --backend dir
refused "R1 update" "not an initialized artifact store" "$ART" update art:t5-pre1 b.html
rm -rf "$XDG_CACHE_HOME"
refused "R1 cold-cache get" "not an initialized artifact store" "$ART" get art:t5-pre1 --out got1.html
check "R1 nothing written into the unmounted mountpoint" empty_dir "$MNT"
check "R1 no commit" test "$(commits)" = "$before"
check "R1 no manifest for the refused create" absent artifacts/manifests/t5-v3b.json
check "R1 task file untouched" cmp -s aitasks/t5_demo.md "$TMP/t5.before"
check "R1 existing handle still has 1 version" test "$(nversions art:t5-pre1)" = 1
check "R1 attach lock released" no_lock
mount --bind "$BACK" "$MNT"
rm -rf "$XDG_CACHE_HOME"
out="$("$ART" get art:t5-pre1 --out got1.html 2>&1)"; rc=$?
check "R1 after remount: cold-cache get exits 0" test "$rc" -eq 0
check "R1 after remount: bytes match the original" cmp -s got1.html a.html
umount "$MNT"

# ── R2: store root is <mountpoint>/store ─────────────────────────────────────
echo "== R2: store root is a subdirectory of the share"
MNT="$TMP/mnt2"; BACK="$TMP/backing2"
mount --bind "$BACK" "$MNT"
mkdir "$MNT/store"
write_config "$MNT/store"
"$ART" init-store dir >/dev/null 2>&1 || echo "note: init-store unavailable or failed (expected on the pre-fix tree)"
out="$("$ART" create 5 c.html --kind report --handle art:t5-pre2 --backend dir 2>&1)"; rc=$?
check "R2 positive control: create while mounted exits 0" test "$rc" -eq 0
check "R2 positive control: blob landed in the share" test -f "$BACK/store/$(blob_rel c.html)"
umount "$MNT"
check "R2 unmounted mountpoint is an empty directory" empty_dir "$MNT"
before="$(commits)"; cp aitasks/t5_demo.md "$TMP/t5.before"
refused "R2 create" "is the share mounted" \
    "$ART" create 5 v3b.html --kind report --handle art:t5-v3b2 --backend dir
refused "R2 update" "is the share mounted" "$ART" update art:t5-pre2 b.html
rm -rf "$XDG_CACHE_HOME"
refused "R2 cold-cache get" "is the share mounted" "$ART" get art:t5-pre2 --out got2.html
check "R2 store root was not created" absent "$MNT/store"
check "R2 nothing written into the unmounted mountpoint" empty_dir "$MNT"
check "R2 no commit" test "$(commits)" = "$before"
check "R2 no manifest for the refused create" absent artifacts/manifests/t5-v3b2.json
check "R2 task file untouched" cmp -s aitasks/t5_demo.md "$TMP/t5.before"
check "R2 existing handle still has 1 version" test "$(nversions art:t5-pre2)" = 1
check "R2 attach lock released" no_lock

echo "RESULT: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
```

## Post-Review Changes

### Change Request 1 (2026-10-14 00:03)
- **Requested by user:** `empty_dir` discarded `find`'s exit status, so a missing or
  unreadable directory was reported as empty. Inspection failures must be told
  apart from an empty mountpoint.
- **Changes made:**
  - `empty_dir` now requires `find` to succeed.
  - The same fail-open shape was in the `test ! -e` absence checks (manifest
    absent, attach lock released, store root not created): a stat failure such
    as EACCES on a parent read as "absent". They now go through a new `absent`
    helper, which accepts only a genuine ENOENT (`LC_ALL=C ls -ld`, the same
    errno qualification `dir.sh`'s `_artifact_dir_lookup` uses).
  - Probed as a normal user. The old `empty_dir` said "empty" for a missing
    and for a `chmod 000` directory; the new one rejects both. The old
    `! -e` said "absent" for an existing file under an unreadable parent;
    `absent` rejects it. An empty directory and a real ENOENT are still
    accepted.
  - Both trees were re-run with the final script. The results are unchanged:
    39/0 on the current tree, and 24/15 with the same 15 FAILs on the pre-fix
    tree. The evidence and the appendix above were regenerated from that run,
    and the appendix is byte-identical to the file that ran.
- **Files affected:** this plan only (the `## Reproduction script` appendix and the
  `## Reproduction evidence` section). There is still no framework code change.

## Final Implementation Notes
- **Actual work done:** Re-verified t1142 item #4 against the current tree on a
  real mount (a bind mount in an unprivileged user and mount namespace, no
  sudo), with the pre-fix tree (`9d818998f^`) as the negative control.
  - **Current tree:** 39/39 PASS in both layouts. With R1 (store root = the
    mountpoint) and R2 (store root = `<mount>/store`), an unmounted share makes
    `create` / `update` / cold-cache `get` exit 1 with an actionable message.
    Nothing is written into the bare mountpoint, there is no commit and no
    manifest, the task file is untouched, and the lock is released. After
    remount the original reads back byte-identical.
  - **Pre-fix tree:** it FAILs exactly the clause-2 checks (R1: writes into the
    bare mountpoint and commits; after remount the blob is hidden) and the
    clause-1 checks (R2: `mkdir`/`mktemp` at `/<2hex>`).
  - **Pinned tests pass:** `test_artifact_dir_backend.sh` 152/152,
    `test_artifact_share_resolution.sh` 98/98, `test_artifact_cli.sh` 182/182.
  - **No framework code change.** The defects were fixed by t1283 (9d818998f,
    root validated in the op's shell plus the store marker) and t1960
    (86025fc28, held store root). The evidence is in `## Reproduction evidence`
    and the verbatim script in `## Reproduction script`.
- **Deviations from plan:**
  - Explicit `--handle` names, and separate mountpoint/backing pairs for R1 and
    R2, so R2's checks cannot inherit R1 leftovers on the pre-fix tree.
  - An added "attach lock released" check.
  - The clause-1 detector matches both ASCII and curly quotes, and is limited to
    `/<2hex>` paths.
  - Post-review (Change Request 1): qualified `empty_dir` / `absent` helpers.
- **Issues encountered:**
  - Measured on this host: coreutils prints `mkdir: cannot create directory
    ‘/ad’` with UTF-8 curly quotes. The first draft's ASCII-only pattern would
    have missed it, and clause 1 was detected only through the `mktemp` line.
  - A Claude Code safety check refuses `bash -c` probe scripts (and
    `rm -rf "$var"` cleanups), so the helper probe ran from a scratch file that
    removes nothing.
  - `main` advanced to 8718afa08 mid-task. The artifact code paths are
    identical to the plan-time HEAD 6a3a81efc, and the evidence names the tested
    HEAD.
- **Key decisions:**
  - The scenario stays a scratch script preserved verbatim in this plan, not a
    permanent test. §J1/§J2/§J3 of `test_artifact_share_resolution.sh` already
    pin the code path, and to the code an unmounted mountpoint is just an empty
    directory.
  - Mid-operation unmount (EBUSY, `umount -l`) is t1968's, and it is not
    exercised here.
- **Upstream defects identified:** None
