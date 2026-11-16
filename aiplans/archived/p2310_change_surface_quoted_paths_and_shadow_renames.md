---
Task: t2310_change_surface_quoted_paths_and_shadow_renames.md
Base branch: main
Output branch: main
---

# t2310 — change surface: raw paths, shared plan-reference matcher; shadow: renames

## Context

t2304 fixed the change surface's rename blind spot with `--no-renames`, but left
three defects in the same family (spawned as an upstream_defect follow-up):

1. `lib/shadow_scope.py:220-235` `dirty_channels()` runs porcelain
   `git diff [--cached] --name-only -z` with rename detection on, so a staged
   rename's OLD path never reaches the shadow's own dirty channels.
2. `aitask_change_surface.sh` reads git output without `-z`, so under the
   default `core.quotePath` a non-ASCII or special path arrives C-quoted
   (`"d\303\251.md"`). That form never equals a plan token or a raw path, so
   such a path is never attributed `TASK`. It also reaches `baseline` →
   `shadow_scope.claim_baseline`, which compares against RAW paths, so the
   shadow loses `baseline_dirty` evidence for those files.
3. The P2 plan-token grammar `[A-Za-z0-9_./-]` (line 249) splits `docs/a|b.md`
   and drops non-ASCII names, so they stay `UNKNOWN`.

User decision (asked during planning): **P2 switches to the shared inverted
search** (`plan_paths.find_references` via `lib/plan_paths_sh.sh`), instead of
widening the local grep class. P2 is only ever used as a membership test over
the DIRTY set (`cmd_list` Pass B), and "which of these git-reported paths does
the plan mention" is exactly the question the inverted search answers. It
already handles `|`, non-ASCII, NFC/NFD and undecodable bytes
(`aidocs/framework/plan_path_reference_extraction_findings.md` §3–§5).

Constraint carried from t2304: no new line prefixes or header values. Consumers
parse `COMMITTED:/TASK:/OTHER:/UNKNOWN:`, `DIRTY_AT_CLAIM:`, `BASELINE:` and
`PLANSCOPE:` as `PREFIX:<path>`.

## Design decisions

- **Paths are raw bytes.** Every git read uses `-z`, and one bash helper,
  `_z_to_lines`, turns the NUL stream into lines. `LC_ALL=C` is exported at the
  top of the script, so `sort -u` and `grep -xF` compare bytes and never collate.
  (Under a UTF-8 locale GNU `sort -u` can fold distinct names, and grep may
  mishandle invalid bytes.)
- **Control-character paths are escaped, not refused or dropped.** The line
  grammar cannot carry a LF. Raw CR is also unsafe: Go's `bufio.ScanLines`, the
  scanner used by the aitasks_go intake, strips a trailing CR, so a raw
  `COMMITTED:src/a.md<CR>` record is read as `src/a.md`. That is a different,
  possibly existing file, and it gets no error (reviewer-reproduced).
  - **Rule:** a path that contains **any control byte (0x01–0x1F or 0x7F)**, or
    that begins with `"`, is printed in git's C-quote form, wrapped in `"…"`:
    - `\` → `\\` and `"` → `\"`;
    - `\a \b \t \n \v \f \r` use their named escapes;
    - every other control byte becomes a 3-digit octal escape `\NNN`.

    That is the subset of git's grammar that both decoders accept: Python
    `codecs.escape_decode` and aitasks_go's `unquote`. Non-ASCII bytes stay
    raw.
  - **Why the leading-`"` case:** quoting it too keeps the encoding injective,
    so every line starting with `"` is an escaped form.
  - **Under `LC_ALL=C`**, the bash helper detects such paths with
    `[[ $p == *[[:cntrl:]]* || $p == \"* ]]` and escapes them byte by byte.
    Only those paths pay the per-byte loop.
  - **Characters that stay raw:** U+2028, U+2029 and `\x85` are not control
    bytes. Only LF-only readers handle them, which is why step 2's
    `_run_lines` fix is still needed.

  The trade-offs:
  - Escaped paths are never plan-scope candidates. They still match a baseline
    exactly (`OTHER` works) and otherwise report `UNKNOWN`, which consumers
    escalate.
  - **Consumer contract (stated in the help text):** a path field that begins
    with `"` is an escaped record.
    - A consumer MUST decode it with git's C-quote grammar **before** any
      filesystem lookup.
    - Its wire spelling names no file. A tracked, clean file can be literally
      named `"a\nb.md"`, so looking up the spelling can hit a real, unrelated
      file. It is never safe to assume that an escaped record is absent from
      the tree.
  - **Current consumers:**
    - aitasks_go's intake (`goengines/internal/testmap/changesurface/changesurface.go`,
      `decodePath` → `unquote`) already decodes any field that starts with `"`.
      It then refuses a decoded LF/CR path as `control-character`, which is
      fail-closed and happens before any lookup.
    - `shadow_scope.claim_baseline` gains the decoder in step 2.
    - The docs_updated gate is read by an agent.
  - Dropping the path instead would under-select silently, which is why the
    escape form is used.
- **Baseline file v2.** `capture` writes `version=2` (raw paths). `read_baseline`
  reads a `version=1` file (or one with no version line) and decodes its
  git-C-quoted lines (`"…"`, with `\NNN` octal and the standard escapes).
  Decoding uses `codecs.escape_decode` in the resolved Python, then re-encodes
  through `_z_to_lines`. Without this, a task claimed before the upgrade would
  lose N1 for a non-ASCII path, and a plan-named, pre-claim-dirty path would
  flip from `UNKNOWN` to a false `TASK`. If the decode fails, the script warns
  on stderr and keeps the lines as they are (the pre-fix behaviour).
- **P2 via the bridge, fail-closed.** The candidates are the unescaped dirty
  lines, sent NUL-delimited to `plan_paths_references <plan>`. Only `full` hits
  attribute:
  - `bare` (a single component with no `.`, e.g. `ait` or `Makefile`) is
    dropped, the same narrowing the old `/`-or-extension filter applied.
  - `suffix` is weak, module-relative evidence and is dropped as well.

  When the bridge returns non-zero, the script warns on stderr and sets
  `PLANSCOPE:missing`. That header already means "signal P2 unavailable", so
  no `TASK:` line can appear. No new header value is added.
- **Pass A** uses `git show --no-renames --name-only -z --format= <sha> -- .
  "${EXCLUDES[@]}"`. The pathspec exclusion runs before encoding, so an escaped
  `aitasks/…` path cannot slip past the `^aitasks/` line filter. The existing
  `grep -Ev` stays as a belt.

## Implementation steps

1. **`.aitask-scripts/aitask_change_surface.sh`**
   - Source `lib/python_resolve.sh` and `lib/plan_paths_sh.sh`. Add
     `export LC_ALL=C` after the sources. Call `resolve_python >/dev/null` in the
     parent shell (not inside `$(...)`), so `_AIT_RESOLVED_PYTHON` is cached for
     the bridge and the v1 decode.
   - Add `_z_to_lines` (a `while IFS= read -r -d '' p` loop, escaping as
     specified above).
   - `current_dirty_set`: add `-z` to `git diff --no-renames --name-only HEAD`
     and to `git ls-files --others --exclude-standard`. Pipe both through
     `_z_to_lines`, then `sed 's|^\./||' | grep -v '^$' | sort -u || true`.
   - `cmd_capture`: write `version=2`.
   - `read_baseline`: read `version=`. If it is not `2` and some line starts with
     `"`, run the v1 decode (Python inline, NUL out → `_z_to_lines`). On failure,
     warn and keep the lines.
   - `read_plan_scope`: replace the `grep -oE` tokenizer and the
     `-d`/`-f`/dirty filter loop with the bridge call described above. If the
     plan exists and the dirty set is empty, report `ok` with no paths. Keep the
     "EXACT FILE MATCHES ONLY" and "plan text is data" comments, now stated in
     terms of the inverted search. A directory mention never matches a file
     candidate (`find_references` needs the full candidate bounded by
     delimiters).
   - `cmd_list` Pass A: add `-z` and the pathspec, and pipe through
     `_z_to_lines`.
   - Help text and header comment:
     - Paths are printed raw. A path containing a control byte (LF, CR, TAB,
       …), or beginning with `"`, is printed C-quoted and is never attributed
       `TASK`. **A field that
       begins with `"` must be decoded with git's C-quote grammar before any
       filesystem lookup; its wire spelling names no file.**
     - **Records are terminated by LF alone.** A reader must split on LF only,
       never on a "universal newline" set, because CR, VT and U+2028 are
       legal path bytes.
     - `PLANSCOPE:missing` also covers "the plan could not be scanned".

2. **`.aitask-scripts/lib/shadow_scope.py`**
   - `dirty_channels()`: add `--no-renames` to both `diff` sources. Add a
     docstring note pointing at t2304's rationale (the old half must reach the
     review).
   - **Raw baseline handoff (review finding, blocking).**
     - Problem: `_run_lines()` does `_dec(res.stdout).splitlines()`, and
       `str.splitlines` also breaks on CR, VT, FF, `\x1c-\x1e`, `\x85`, U+2028
       and U+2029. All of these are legal in filenames. Once `baseline` emits
       raw paths, a record `DIRTY_AT_CLAIM:docs/a<U+2028>DIRTY_AT_CLAIM:innocent.md`
       parses as two dirty paths, `docs/a` and `innocent.md`. The real path
       loses its `baseline_dirty` evidence, and an unrelated file gains false
       pre-claim evidence. Verified with a probe. Before the fix, git's
       C-quoting hid this.
     - Fix: split on the protocol's literal LF only:
       `_dec(res.stdout).split("\n")`, dropping the final empty element. All
       three callers (`aitask_shadow_context.sh`, `aitask_revert_analyze.sh`,
       `aitask_change_surface.sh`) speak LF-terminated line protocols, so this
       is the correct reading for each of them. Commit subjects and task text
       carrying U+2028 were mis-split there too.
   - **Escaped-form decode** in `claim_baseline()`: a `DIRTY_AT_CLAIM:` value
     that starts and ends with `"` is change_surface's escape form, used for a
     LF or leading-`"` path. Decode it with `codecs.escape_decode` on the
     surrogateescape bytes, then decode back with surrogateescape, so it
     compares equal to the raw path from `dirty_channels()`. If the decode
     fails, the value is kept verbatim. That only loses evidence, it never
     invents any.

3. **Record the consolidation** (the grammar was pinned as deliberately
   different):
   - `tests/test_plan_paths_seam.sh` lines ~74-89: replace the "keeps its own
     broader grammar" guard with three asserts. change_surface sources
     `lib/plan_paths_sh.sh`, calls `plan_paths_references`, and contains no
     `grep -oE` tokenizer and no copy of the extension list.
   - `.aitask-scripts/lib/plan_paths.py` docstring ("NOT THE ONLY EXTRACTOR…"):
     change_surface now consumes the inverted search. The extension grammar's
     consumers are unchanged.
   - `.aitask-scripts/lib/plan_paths_sh.sh` header: "Its only caller" becomes
     the drift check and the change surface.
   - `aidocs/framework/plan_path_reference_extraction_findings.md`: the intro
     paragraph (line ~19) and a new §7 entry, **"Change surface (switched,
     t2310)"**. It covers why the question shape fits, the `full`-only
     narrowing, the fail-closed state, and the measured differential from the
     post-phase below.

4. **Tests — `tests/test_change_surface.sh`**
   - Add a test hook: `CS="${AIT_TEST_CHANGE_SURFACE:-$PROJECT_DIR/...}"`, so a
     pre-fix copy can be run against the same assertions.
   - Add section **11. RAW PATHS (t2310)**. Pin `core.quotePath=true` through
     `GIT_CONFIG_COUNT` (the same pattern as `RENAMES_ON`). Each case starts
     with a control proving git really C-quotes the path in that fixture
     (`git diff --name-only HEAD` shows `"d\303\251…"`). Cases:
     - 11a. Non-ASCII, plan-named → `TASK:<raw>`. An unnamed non-ASCII path →
       `UNKNOWN:<raw>`. No output line begins with `"`.
     - 11b. `docs/a|b.md`, plan-named in backticks → `TASK:docs/a|b.md`.
     - 11c. An NFD filename on disk, NFC in the plan → `TASK:<NFD original>`.
     - 11d. Pre-claim-dirty non-ASCII path → `DIRTY_AT_CLAIM:<raw>` and
       `OTHER:<raw>`. Plan-named and pre-claim-dirty → `UNKNOWN` (not `TASK`).
     - 11e. A hand-written **v1** baseline with a git-quoted entry decodes to
       the same result as 11d (`OTHER`, and `UNKNOWN` when plan-named). This is
       the transitional false-TASK guard.
     - 11f. A committed non-ASCII path in a `(t<id>)` commit →
       `COMMITTED:<raw>`.
     - 11g. An untracked `a<LF>b.md` → exactly one line `UNKNOWN:"a\nb.md"`.
       There is no `UNKNOWN:a` or `b.md` line, and no `TASK` even when the plan
       names `a` and `b.md`. When captured before the claim → `OTHER:"a\nb.md"`.
     - 11h. **Broken-matcher stub**: `AIT_PLAN_PATHS_DIR=<empty dir>` →
       `PLANSCOPE:missing` and no `TASK:` line. A positive control runs the
       same fixture without the stub and gets `TASK`.
     - 11i. A grammar edge pinned on purpose: plan text `sub/mine.md@v2` no
       longer attributes `sub/mine.md` (findings §3).
     - 11j. Non-LF line breaks stay inside one record.
       - `docs/a<U+2028>DIRTY_AT_CLAIM:innocent.md` (not a control byte) stays
         raw. It yields exactly one `DIRTY_AT_CLAIM:` record, byte-exact.
       - `x<CR>y.md` and `v<VT>w.md` are escaped: `"x\ry.md"` and `"v\vw.md"`.
       - Each path yields exactly one `OTHER:` line in `list`, and there is no
         `DIRTY_AT_CLAIM:innocent.md` record.
     - 11k. **Trailing CR, in the real producer record.**
       - A file `src/a.md<CR>` is committed in a `(t<id>)` commit, beside a
         tracked `src/a.md`, and another file `d.md<CR>` is left untracked.
       - The output contains exactly `COMMITTED:"src/a.md\r"` and
         `UNKNOWN:"d.md\r"`.
       - No output byte is a CR (`LC_ALL=C grep -c $'\r'` = 0), and there is no
         `COMMITTED:src/a.md` line.
       - It is a trailing CR on purpose: an interior CR does not expose the
         truncation.
     - 11l. Escape-form round trip. For each escaped record from 11g, 11j and
       11k, decode the field with `codecs.escape_decode` and compare its bytes
       with the on-disk name (read via `git ls-files -z` / `os.listdir`).
       Decoding one record of each shape is enough, plus a path that starts
       with `"`.
   - Update the file's "Covers" header.

5. **Tests — `tests/test_shadow_scope.sh`**
   - A staged rename with renames pinned on: a control shows that
     `git diff --cached --name-only` hides the old half. The scope output then
     carries a `PART|dirty|staged|…|<old>` line.
   - A pre-claim-dirty non-ASCII file: its PART evidence includes
     `baseline_dirty`. Before the fix it was lost, because `baseline` emitted
     the C-quoted form.
   - **End-to-end splitter regression (the review repro).** Set up the fixture
     like this:
     - Track `innocent.md` and `docs/`.
     - Before the claim, dirty `docs/a<U+2028>DIRTY_AT_CLAIM:innocent.md` (untracked).
     - Run `capture`.
     - After the claim, dirty `innocent.md`.

     The shadow scope output must then show:
     - the U+2028 path's PART carries `baseline_dirty`;
     - `innocent.md`'s PART does **not** carry `baseline_dirty`;
     - no PART line exists for a phantom `docs/a`.

     Add two more checks:
     - A **trailing-CR** variant. Before the claim, `docs/b.md<CR>` is dirty
       and arrives escaped as `"docs/b.md\r"`. `claim_baseline` decodes it, so
       the raw path's PART carries `baseline_dirty`, and a tracked `docs/b.md`
       dirtied after the claim does **not**.
     - A direct unit check that `_run_lines` keeps `\r`, `\v` and U+2028 inside
       a record. Pre-fix control:
     with `splitlines()` restored in a scratch copy of the module, the case
     fails (classified D).

### Post-phase (risk mitigations)

1. [p2_attribution_differential] Measure the P2 switch over the live corpus. In
   the scratchpad, put a copy of the pre-fix script (`git show HEAD:...`) next to
   a `lib` symlink. For every archived plan `aiplans/archived/**/p<id>_*.md`
   whose task has `(t<id>)` commits, take the union of the files those commits
   touched as the candidate "dirty" set. Compute P2 attribution with the old
   grammar (old `read_plan_scope` logic over that candidate list) and with the
   new bridge path. Report counts: same, old-only, new-only. Then classify
   **every** differing path by cause: `@`/`+` continuation, NFC, `|`,
   bare-name, trailing punctuation, or other. Record the table and the script
   verbatim in the plan's Final Implementation Notes and in findings §7.
   - Acceptable: every new-only hit is a real reference, and every old-only
     hit is either an extraction false positive or an explicitly accepted
     narrowing.
   - Otherwise: any unexplained old-only loss of a real reference stops the
     task for a decision before commit.

## Verification

- `bash tests/test_change_surface.sh`, `bash tests/test_shadow_scope.sh` and
  `bash tests/test_plan_paths_seam.sh` all PASS.
- Pre-fix control. Run `tests/test_change_surface.sh` with
  `AIT_TEST_CHANGE_SURFACE=<scratch copy of HEAD's script with a lib symlink>`
  and classify each new section-11 assertion: D (detects the defect, fails
  pre-fix), C (control), S (safety/negative that already passes), or P (pinned
  edge). Do the same for the shadow rename case: run it with `--no-renames`
  temporarily absent, using a scratch copy of the module path, never by
  editing the tree back. Record the table in Final Implementation Notes.
- `shellcheck .aitask-scripts/aitask_change_surface.sh`.
- Regression: `bash tests/test_remote_drift_check*.sh` (the bridge it shares)
  and the python suite subset touching plan_paths/shadow_scope
  (`bash tests/run_all_python_tests.sh` with `set -o pipefail`; read the last
  line).
- Consumer interpretation, verification only, nothing written into
  aitasks_go:
  - Copy aitasks_go's `changesurface.go` into a scratch Go module (as the
    reviewer did) and feed it the real producer output from fixtures 11g, 11j
    and 11k.
  - Expected: the escaped CR, LF and VT records give `control-character`
    errors. The U+2028 record parses to its exact path. No record is
    truncated, so no `src/a.md` appears.
  - Record the output in Final Implementation Notes.
- Real-tree smoke: `./.aitask-scripts/aitask_change_surface.sh list 2310` in
  this checkout. Its own files come out `TASK`, and no line begins with `"`.

## Risk

### Code-health risk: medium
- P2 grammar swap changes TASK attribution for every `list` consumer (docs_updated gate, future testmap intake): `@`/`+` continuations, NFC folding and `full`-vs-old-filter edges classify differently than before · severity: medium · → mitigation: inline post-phase p2_attribution_differential
- New Python dependency on a previously bash-only `list`/`baseline` path; a broken interpreter must degrade to PLANSCOPE:missing, not to TASK · severity: low · → mitigation: covered in-plan by test 11h (broken-matcher stub + positive control)
- `export LC_ALL=C` script-wide alters sort/grep semantics for all paths, incl. sourced task_utils helpers · severity: low · → mitigation: none beyond the full existing suite (sections 1–10) passing unchanged

- Raw paths reach every line-protocol reader of change_surface output; a reader that splits on more than LF (Python `splitlines`) mis-parses records and can invent evidence · severity: medium · → mitigation: shadow `_run_lines` LF-only split + end-to-end U+2028/CR regression (step 2, step 5); the only Python reader of the output today is `shadow_scope.claim_baseline` (consumer grep: pick_own writes, docs_updated gate is agent-read, the testmap intake is not built yet)

### Goal-achievement risk: low
- The escaped form for LF / leading-`"` paths is a quoted path value a consumer could mistake for a filename (wire-spelling collision with a tracked file literally named `"a\nb.md"`) · severity: low · → mitigation: decode-before-lookup contract in the help text; the aitasks_go intake already decodes then refuses control chars; regression carried to the selector repo (Step 8b follow-up below)

### Planned mitigations
- timing: post-phase | name: p2_attribution_differential | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: P2 grammar swap changes TASK attribution | desc: replay archived plans × own-commit files through old vs new P2, classify every differing path by cause, stop on unexplained real-reference loss

## Follow-up carried to the selector (Step 8b, no selector code in t2310)

Create one task in **aitasks_go** (`ait create --batch --project aitasks_go`,
`issue_type: test`, `followup_kind: upstream_defect`, effort low, anchored
under its M4 parent t61). It covers `goengines/internal/testmap/changesurface/`:

1. **Changed-LF-file regression.** Feed the intake the real script's record for
   an untracked `a<LF>b.md`, which is `UNKNOWN:"a\nb.md"`. Prove that the
   record is decoded (not taken as a literal name) and then refused as
   `control-character` before any filesystem lookup.
2. **Tracked-clean wire-spelling regression.** In a fixture holding a tracked,
   clean file literally named `"a\nb.md"`, the same record must never resolve
   to that file. Also feed the escape of the literal file,
   `"\"a\\nb.md\""`, and check that it round-trips to the literal name.
3. **Trailing-CR reader regression.** Check what the intake does with a raw
   `COMMITTED:src/a.md<CR><LF>` record. Today `bufio.ScanLines` turns it into
   `src/a.md` with no error. Two fixes are possible:
   - harden the reader to LF-only splitting, so a raw CR reaches
     `validatePath` and is refused;
   - or keep `ScanLines` and assert that the producer never emits a raw CR.

   The t2310 producer escapes it as `"src/a.md\r"`, which the intake refuses
   as `control-character`. Pin both the escaped record and the raw one.
4. **Doc comment refresh.** The package comment currently says "git C-quoted
   when it carries bytes git quotes". Since t2310 the producer emits raw UTF-8
   and quotes only paths that contain a control byte or begin with `"`. Its rename sentence ("until then a
   rename's old path is absent") is also stale since t2304.

Before creating the task, check aitasks_go's open tasks for an existing owner
(`ait projects exec aitasks_go -- ./ait ls -v 99`, plus the t61 children). If
one owns the intake, send it a `./ait note --project aitasks_go` instead.

## Step 9

Post-implementation: commit code (`bug: … (t2310)`) and the plan separately via
`./ait git`, then archive per task-workflow Step 9 (current-branch mode, no
merge).

## Final Implementation Notes

- **Actual work done:** Implemented as planned:
  - `aitask_change_surface.sh`:
    - `-z` reads plus `_z_to_lines` (raw paths, git C-quote escape for any
      control byte or a leading `"`);
    - `export LC_ALL=C`;
    - baseline `version=2`, with v1 decode via `codecs.escape_decode`;
    - P2 through `plan_paths_references` (only `full` attributes; fail-closed
      → `PLANSCOPE:missing`);
    - Pass A with `-z` plus pathspec excludes;
    - help text gains the PATH ENCODING contract (LF-only records,
      decode-before-lookup).
  - `shadow_scope.py`:
    - `--no-renames` on both `dirty_channels` diffs;
    - `_run_lines` splits on LF only;
    - `_surface_path` decodes escaped `DIRTY_AT_CLAIM:` values.
  - The consolidation is recorded in `test_plan_paths_seam.sh`, the
    `plan_paths.py` docstring, the `plan_paths_sh.sh` header, and the findings
    doc intro and §7 ("Change surface (switched, t2310)", with the differential
    script verbatim).
- **Deviations from plan:**
  - `lib/plan_paths_sh.sh` is sourced **lazily** inside `read_plan_scope`,
    not at startup. A `source` that fails also fails closed to
    `PLANSCOPE:missing`. Reason: the first run of section 9 failed. That
    section scaffolds a fake repo (`setup_fake_aitask_repo`) with no
    plan-paths module, and `aitask_pick_own.sh` runs `capture` there, so an
    eager `source` killed the capture. `capture` must not gain a dependency it
    never uses.
  - Test 11l: the round trip is checked against the fixture names, plus an
    on-disk existence check per name, rather than `git ls-files -z`.
- **Issues encountered:**
  - Two review rounds during planning, both folded into the plan before
    approval: (1) `str.splitlines` splitting raw records, and (2) the trailing
    CR dropped by Go's `bufio.ScanLines`, which led to escaping every control
    byte, not only LF.
  - The local `go` 1.27.4 toolchain fails with a GOEXPERIMENT `nodwarf5`
    mismatch. The scratch Go harness was built with the installed 1.27.3
    instead.
- **Key decisions:**
  - P2 moves to the shared inverted search (user choice).
  - The differential found 5 old-only real references, all prefix forms
    (`/path`, `@path`, `\.path`, `<tree>/path`). The user accepted them as a
    recorded narrowing, since UNKNOWN is the recoverable direction.
- **Upstream defects identified:**
  - `aitasks_go:goengines/internal/testmap/changesurface/changesurface.go:101`
    — `bufio.NewScanner` with the default `ScanLines` drops a trailing CR, so
    a raw `COMMITTED:src/a.md<CR>` record parses as committed `src/a.md` with
    no error. The package comment ("git C-quoted when it carries bytes git
    quotes"; "until then a rename's old path is absent") is also stale. This
    is carried to aitasks_go as the planned selector follow-up.
  - `tests/test_metadata_writer_inventory.py:346` — the
    `NewWriterTripwire` test fails on main. It names
    `.aitask-scripts/lib/sitrep_crash.py` (from t2299_2) as a writer under
    `aitasks/metadata` that is unclassified (not in WIRED, KNOWN_UNCOMMITTED
    or PINNED_FILES).
- **Differential (post-phase p2_attribution_differential), 2026-11-16:** 2159
  archived plans (loose plus the `_b*` bundles) with `(t<id>)` commits.
  Results: same 9549, new-only 0, old-only 5:
  - t361 and t793: repo-rooted `/`;
  - t812_2: `@`-mention;
  - t1449: markdown `\.`;
  - t2246: `<tree>/`.

  The script is reproduced verbatim in findings §7.
- **Pre-fix control (`AIT_TEST_CHANGE_SURFACE=<HEAD copy + lib symlink>`):**
  136 assertions, 18 fail pre-fix.
  - **D** (detects the defect):
    - 11a: TASK raw, UNKNOWN raw, no escaped non-ASCII record;
    - 11b: `|`;
    - 11c: NFD;
    - 11d: DIRTY_AT_CLAIM raw, OTHER, UNKNOWN on conflict;
    - 11e: v1 decode, three assertions;
    - 11f: COMMITTED raw;
    - 11h: missing, no TASK, UNKNOWN (the pre-fix script had no matcher to
      break);
    - 11i: `@v2`;
    - 11j: the U+2028 baseline record, and OTHER for it.
  - **C** (controls): every `control:` line, plus the 11h positive controls.
  - **S** (already passing pre-fix, because git's own quoting coincided):
    every LF, CR, VT, trailing-CR and leading-quote record, and the NEG lines.
    These are **not** vacuous. A mutant of the new script with escaping
    disabled (`if false; then` in `_z_to_lines`) fails 13 of them:
    - the LF record, its single-record count, its first-half NEG, its
      never-TASK NEG, and its pre-claim OTHER;
    - the CR and VT baseline records, and OTHER for each;
    - both trailing-CR records, the no-raw-CR check, and the leading-quote
      escape.
- **Shadow pre-fix controls (scratch mirror):**
  - (a) Everything at HEAD: 5 fail, namely the U+2028, trailing-CR and
    non-ASCII `baseline_dirty` cases, the `_run_lines` unit check, and the
    staged-rename old half.
  - (b) The new change_surface with HEAD's shadow_scope: 5 fail. This one
    includes `NEG: innocent.md gets no invented baseline evidence`, which is
    the reviewer's repro reproduced end to end.
- **Consumer interpretation (scratch harness around aitasks_go's real
  `changesurface.go`):**
  - The producer's `UNKNOWN:"a\nb.md"`, `UNKNOWN:"x\ry.md"`,
    `UNKNOWN:"v\vw.md"` and `COMMITTED:"src/a.md\r"` are each refused as
    `control-character`.
  - The U+2028 record parses as one UNKNOWN path, untruncated.
  - A hand-made raw `COMMITTED:src/a.md<CR>` parses as committed `src/a.md`
    with no error. That is the hazard the escape removes, and it is carried to
    the aitasks_go follow-up.
- **Verification:**
  - Passing: `test_change_surface.sh` 136/136, `test_shadow_scope.sh` 60/60,
    `test_plan_paths_seam.sh` 22/22, `test_remote_drift_check.sh` 70/70, all
    `test_shadow_*.sh` and both `test_pick_own_*.sh`, and
    `shellcheck -S warning` clean.
  - Python suite: `PYTHON SUITE: FAILED (runner=pytest, exit=1)`, with 12379
    passed and 1 failed. The one failure is
    `test_metadata_writer_inventory.py::test_no_unclassified_file_writes_metadata`,
    which names `.aitask-scripts/lib/sitrep_crash.py`. That file was added by
    t2299_2 and t2307, which are already on main, and t2310 does not touch it,
    so the failure is pre-existing and unrelated.
