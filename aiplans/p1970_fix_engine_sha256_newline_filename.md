---
Task: t1970_fix_engine_sha256_newline_filename.md
Base branch: main
Output branch: main
---

# t1970 — engine_sha256: hash from stdin

## Context

`engine_sha256` (`.aitask-scripts/lib/engine_install.sh:78-91`) passes the path
as an argument to `sha256sum` / `shasum -a 256` and keeps `${out%% *}`. Both
tools escape a name containing a newline or backslash by prefixing the line
with `\` (`\<hex>  <escaped-name>`), so the digest fails the
`^[0-9a-f]{64}$` check and the function returns 1 — fail-closed, which blocks
engine verification (`engine_file_matches`, line ~104). A name beginning with
`-` would also be option-parsed. t1967 fixed the identical shape in
`artifact_sha256` (`lib/artifact_utils.sh`) by feeding the file on stdin; apply
the same fix here. Working on the current branch (profile `fast`).

## Steps

1. **`.aitask-scripts/lib/engine_install.sh` — `engine_sha256`.** Feed the file
   on stdin so the name reaches neither argv nor output:
   ```bash
   # engine_sha256 <file> — print the file's sha256 hex digest.
   # The file is fed on stdin so the tool never sees its name: sha256sum/shasum
   # escape a name holding a newline or backslash with a leading '\' (which the
   # hex check below would reject) and option-parse a leading '-'. stderr is
   # redirected first so a missing/unreadable file's redirect error stays quiet.
   engine_sha256() {
       local out
       if command -v sha256sum >/dev/null 2>&1; then
           out="$(sha256sum 2>/dev/null < "$1")" || return 1
       elif command -v shasum >/dev/null 2>&1; then
           out="$(shasum -a 256 2>/dev/null < "$1")" || return 1
       ...
   ```
   Output becomes `<hex>  -`, so `${out%% *}` and the regex check are unchanged.
   `2>/dev/null` stays *before* `<` so the shell's own "No such file" redirect
   error is silenced too (the old argv form silenced the tool's equivalent).

2. **`tests/test_install_engine_binary.sh` — new section `H` (after `R`).**
   Mirror t1967's per-backend pattern (`tests/test_attach_scaffold.sh` Test 1b):
   for each of `sha256sum`, `shasum` that is installed (else `SKIP:` line), build
   `$WORK/hbin_<tool>/` holding only a symlink to that tool, source
   `engine_install.sh` from `$PROJECT_DIR` in a `bash -c` (with `warn(){ :; }`,
   as R0 does), and call `PATH="$bin" engine_sha256 <file>`. Known vector:
   `printf 'hello\n'` → `5891b5b5…6be03`. Cases:
   - H1 positive control: plain name hashes to the vector;
   - H2 name with an embedded newline; H3 name ending in a newline;
   - H4 name with a backslash; H5 relative name starting with `-` (run with
     `cd` into the fixture dir);
   - H6 missing file: rc 1, empty stdout, empty stderr.
   Also `engine_file_matches` on the newline name against the vector → rc 0
   (the actual consumer).

## Verification

- `bash tests/test_install_engine_binary.sh` — all pass (S2/E4 may SKIP without Go).
- Pre-fix control: temporarily confirm H2–H5 fail against the old argv form
  (checked by running the new section's logic against `git show HEAD:` copy of
  the lib in a scratch dir — never by restoring the working tree).
- `shellcheck .aitask-scripts/lib/engine_install.sh`.

Then Step 9 (Post-Implementation): review, commit, archive.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
