---
Task: t1967_fix_artifact_sha256_newline_filename.md
Base branch: main
Output branch: main
---

# t1967 — `artifact_sha256` dies on file names containing a newline

## Context

`artifact_sha256` (`.aitask-scripts/lib/artifact_utils.sh:28-49`) passes the
file name to the hashing tool as an argument. Every tool echoes that name back:

- `openssl dgst -sha256 <f>` → `SHA2-256(<f>)= <hex>` — a newline in `<f>`
  splits the line, so `awk '{print $NF}'` prints a non-hash field per line;
- `sha256sum <f>` / `shasum -a 256 <f>` escape such names as `\<hex>  <f-escaped>`,
  so `$1` carries a leading `\`.

The helper fails closed (`die "unexpected hash output"`), so nothing is
mis-hashed, but `ait artifact create` / `ait attach` of such a file dies. A name
beginning with `-` is a second instance of the same class: as a bare relative
argument it is parsed as an option by every tool.

Found by t1960 (dir artifact backend, `tests/test_artifact_dir_backend.sh`
section G), which had to compare bytes with `cmp` instead of hashing.

## Fix — hash from stdin so no tool ever sees the name

Measured on this host (all three print just the hex plus a stdin marker, which
the existing awk parses already handle):

```
openssl dgst -sha256 < f   → SHA2-256(stdin)= e3b0…b855     ($NF = hex)
sha256sum < f              → e3b0…b855  -                   ($1  = hex)
shasum -a 256 < f          → e3b0…b855  -                   ($1  = hex)
```

### 1. `.aitask-scripts/lib/artifact_utils.sh` — `artifact_sha256`

- Change the three invocations to read from stdin:
  - `hex="$(openssl dgst -sha256 < "$file" | awk '{print $NF}')"`
  - `hex="$(sha256sum < "$file" | awk '{print $1}')"`
  - `hex="$(shasum -a 256 < "$file" | awk '{print $1}')"`
- Update the comment: openssl prints `<ALGO>(stdin)= <hex>`; the file is fed on
  stdin so no tool sees (or echoes, or option-parses) its name — names with a
  newline, a leading `-`, or other bytes the tools would escape all hash the
  same.
- Unreadable file: the redirect fails, the hex is empty, and the existing
  `die "…unexpected hash output…"` fires — still fail-closed, same as today
  (`openssl` erroring on an unreadable file also reached that die). No change to
  the `[[ -f ]]` guard, normalization, validation or output format.
- Precedent for the stdin form already in-repo: `aitask_gate.sh:762-767` hashes
  via `printf … | openssl dgst -sha256 | awk '{print $NF}'`.

### 2. Regression test — `tests/test_attach_scaffold.sh` (new "Test 1b", after Test 1)

This file already owns the `artifact_sha256` unit tests (known vector, shape).

- Fixtures in `$TMP`, all with content `hello\n` and expected hash the known
  vector `sha256:5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03`
  (confirm with `sha256sum < file` while implementing):
  - a name with an embedded newline: `"$TMP/nl"$'\n'"name.bin"`
  - a name ending in a newline: `"$TMP/trail.bin"$'\n'`
  - a name with spaces: `"$TMP/sp ace name.bin"`
  - a name starting with `-`, hashed as a bare relative arg: `( cd "$TMP" && artifact_sha256 -dash.bin )`
- **Per-backend coverage**: the helper picks the first available tool, so on a
  normal host only openssl is exercised. For each of `openssl`, `sha256sum`,
  `shasum` that exists on the host, build `$TMP/bin_<tool>/` with symlinks to
  that tool plus `awk` and `tr` only, and run each fixture as
  `PATH="$TMP/bin_<tool>" artifact_sha256 <file>` (inside `$( )`). Assert the
  known vector for every fixture × backend. A tool absent on the host is
  skipped with an `echo "SKIP: …"` line (not counted as pass).
  Also assert, per backend, the plain `$TMP/hello` file still hashes to the
  vector (positive control that the restricted PATH actually works, so a
  newline-name failure cannot be blamed on the PATH sandbox).
- **Red proof**: run the new test against the unfixed helper first — the
  newline and `-dash` cases must FAIL on every backend before step 1 lands.

### 3. `tests/test_artifact_dir_backend.sh` section G (small follow-through)

Add one assertion next to the existing `cmp` check (line ~443):
`assert_eq "G: the newline-named destination hashes to the blob" "$HF" "$(artifact_sha256 "nl.dst$NL")"`.
Keep the `cmp` check (it is independent byte evidence).

## Out of scope (note only)

`.aitask-scripts/lib/engine_install.sh:79-90` `engine_sha256` has the same
argument-passing shape (`sha256sum "$1"`, `${out%% *}`), also fail-closed. Its
inputs are framework-managed engine-slot paths; list it under "Upstream defects
identified" in the final notes so Step 8b can offer a follow-up rather than
widening this task.

## Verification

```bash
bash tests/test_attach_scaffold.sh
bash tests/test_artifact_dir_backend.sh
bash tests/test_attach_local_backend.sh
bash tests/test_artifact_share_resolution.sh
shellcheck .aitask-scripts/lib/artifact_utils.sh
```

All must print a zero-failure summary and exit 0.

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no merge; run the gate orchestrator /
build verification, then archive via `aitask_archive.sh 1967`.

## Risk

### Code-health risk: low
- None identified. One function, three invocations; output parsing and the
  fail-closed validation are unchanged, and the stdin output formats were
  measured for all three tools on this host.

### Goal-achievement risk: low
- None identified. The fix removes the name from every tool's argv and output,
  covering newline, leading-dash and escaped-character names; the per-backend
  test proves it for each fallback, not just the first-available tool.

## Final Implementation Notes
- **Actual work done:** `artifact_sha256` (`.aitask-scripts/lib/artifact_utils.sh`) now feeds the file to `openssl dgst -sha256` / `sha256sum` / `shasum -a 256` on stdin, so no tool sees, echoes or option-parses the name; the existing `$NF` / `$1` awk parses handle the `(stdin)=` / `  -` output unchanged. New Test 1b in `tests/test_attach_scaffold.sh` hashes a name with an embedded newline, a name ending in a newline and a name with spaces through EACH backend (a restricted PATH holding one tool + awk + tr), with a plain-name positive control per backend. `tests/test_artifact_dir_backend.sh` section G now also asserts the newline-named destination hashes to the blob.
- **Deviations from plan:** Dropped the leading-`-` relative-name fixture: exercising a bare relative argument needs a `cd`, and the cd-guard lint (`tests/test_cd_guard_lint.sh`) then requires `enter_scratch_cwd` for the whole file — not worth it for a bonus case the stdin form covers by construction.
- **Issues encountered:** Red proof confirmed before the fix: 6 failures in test_attach_scaffold (both newline cases × openssl/sha256sum/shasum) and 1 in test_artifact_dir_backend section G; spaces and positive controls passed. After the fix all pass, plus test_attach_local_backend, test_artifact_share_resolution, test_attach_fold_rebind, test_attach_archive_gc, test_attach_gc_manifest_blocking, test_artifact_fold_transfer, test_attach_task_delete_decref. `test_cd_guard_lint.sh` has one failure in another session's untracked `tests/test_install_upgrade_dirty_baseline.sh:52` — unrelated to this change.
- **Key decisions:** Kept the `[[ -f ]]` guard and the fail-closed `die` unchanged; an unreadable file now fails at the redirect and still reaches that die.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/engine_install.sh:79-90 — engine_sha256 passes the path as an argument to sha256sum/shasum and takes ${out%% *}; a name with a newline or backslash makes the tool escape it with a leading '\', so the hash fails validation (fail-closed). Same fix: hash from stdin.`
