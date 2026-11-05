---
Task: t2209_fix_file_references_comma_split_and_unquoted_writer.md
Base branch: main
Output branch: main
---

# t2209 — `file_references:` reader comma-split + unquoted writer

## Context

`file_references:` is a YAML flow list, but the shell side treats it as CSV end to end:

- **Reader** `get_file_references()` (`.aitask-scripts/lib/task_utils.sh:3381`) strips the
  brackets and splits on `,`, so the valid `["a,b.py"]` is read as `a` + `b.py`.
  `aitask_verification_stale.sh` reads its scope this way and can report a false
  `DECISION:FRESH` (reproduced in t1663_1). The same reader feeds `aitask_find_by_file.sh`,
  `aitask_create.sh` auto-merge and `union_file_references()` (fold).
- **Writer** `format_yaml_list()` (`task_utils.sh:2530`) writes entries unquoted. So
  `docs/a[bc].md` comes out as invalid YAML, and `on` / `null` / `010` become non-strings
  for every Python reader.
- **Carrier.** The defect is wider than the task text. `aitask_update.sh` re-reads the
  field with `parse_yaml_list` (`:618`), which strips *all* quotes and spaces, and then
  re-serializes it on **every** update (`:1241`, `:2276`). So a plain `--status`
  change today turns `["a,b.py"]` into `[a, b.py]` and `my file.py` into `myfile.py`.
  `aitask_create.sh` (`dedup_file_refs`), `union_file_references()` and
  `aitask_fold_mark.sh` also carry the list as CSV. A quoting writer on its own would be
  undone by the next update.
- **Joiner** (found in plan review, reproduced). `join_yaml_flow_lists` counts brackets
  inside quoted scalars. So a valid `["a[.py"]` swallows the following frontmatter
  fields for `aitask_update.sh`, `read_yaml_field` and `read_yaml_list` (§2b).
- **Code points** (found in plan review, measured). PyYAML folds a literal U+0085 inside
  `"…"` to a space and rejects literal C1/DEL/U+FFFE/U+FFFF, and `[[:cntrl:]]` is
  locale-dependent. So quoting must escape byte-exactly, and validation must be
  locale-independent (§3).

t1663_1 already fixed its own reader (`aitask_premise_stale.sh`, via `task_yaml.parse_frontmatter`
+ `task_premise.task_fields`). That fix set the rule this plan follows: **read the field
with the real YAML reader, and only a string entry is a path** — never comma-split, never
`str()`-coerce a non-string, never drop one.

Outcome: every shell consumer reads the field as YAML and fails closed on an unreadable
field. Every shell writer emits YAML that round-trips each entry as the identical string.
An update that does not touch file refs leaves the field byte-identical.

## Approach

### Pre-phase (risk mitigations)

1. [update_passthrough_characterization] Before editing `aitask_update.sh`, add a test
   block to `tests/test_file_references.sh`. A task created with `--file-ref a.py
   --file-ref b.py:10-20` gets, in turn, `--status Implementing`, `--priority high` and
   `--add-label x` (batch). After each, assert that the `file_references:` line is
   byte-identical to `file_references: [a.py, b.py:10-20]`. Also cover a task whose only
   refs are then removed with `--remove-file-ref` (×2): assert the field line is absent.
   Run it on the unmodified tree and confirm it is green **before** any update change, so
   it is a real characterization, not a red test. It must stay green afterwards.

### 1. Shared classifier — `.aitask-scripts/lib/task_yaml.py`

Add `file_reference_entries(metadata) -> list[tuple[bool, object]]`. It is the single
"which entries are paths" rule, lifted verbatim from `task_premise.task_fields`:
- `None` / `""` / missing → `[]`
- a bare scalar → a one-entry list
- an entry is ok iff `isinstance(item, str) and item and "\0" not in item`

`task_premise.task_fields` switches to calling it, with no output change; this is
pinned by the existing `tests/test_task_premise.py`. `task_yaml` is the base layer and
already a dependency of `task_premise`, so the import direction stays legal.

### 2. Reader — `task_utils.sh`

New `read_file_references_batch <file>...`. It makes **one** Python call (interpreter via
`resolve_python`, already sourced by `task_utils.sh:19`) with a single-quoted `-c` glue,
using the same sys.path discipline as `_FIELDS_GLUE` in `aitask_premise_stale.sh`: drop
`""`/`"."`, then append the lib dir (resolved from `${BASH_SOURCE[0]}`, not the caller's
`SCRIPT_DIR`). Per file it parses with `task_yaml.parse_frontmatter`, then emits a
count-attested block:

```
FILE:<path>
REF:<entry>          one per ok entry
BAD:<repr>           a non-string / empty / NUL entry, AND any entry holding LF or CR
                     (it cannot be framed as one bash line)
INVALID:frontmatter  instead of REF/BAD when the frontmatter does not parse
END:<n REF+BAD lines>
```

followed by a final `DONE:<n files>`. Entries carry no encoding, because LF/CR/NUL are
already classified as BAD. A file path holding a newline is refused before the call.

The bash side validates the framing: exactly one block per requested file, in order, with
the END count matching and DONE matching. Any deviation, a non-zero Python exit, or
no interpreter fails the **whole** call, and **nothing** is printed (all-or-nothing, no
partial list). Exit codes: `0` ok, `2` framing/parse failure, `3` python unavailable.

`get_file_references <file>` is rewritten on top of it, keeping the same stdout contract
(one entry per line). New exit contract:
- `0` — the field is absent/empty or every entry is a string
- `2` — unparseable frontmatter, any `BAD:` entry, or a framing failure; prints nothing
- `3` — no Python

Its header comment documents this contract and the string-only rule.

`union_file_references` uses one batch call and emits **newline-separated** output
instead of CSV. It returns non-zero if any source is unreadable or has a BAD entry,
because silently dropping a folded child's scope would lose data.

The glue opens the file `encoding="utf-8"` (strict) and maps `UnicodeDecodeError`, like any
parse exception, to `INVALID:frontmatter`.

### 2b. Quote-aware flow-list joining — `.aitask-scripts/lib/yaml_utils.sh`

**Verified defect (review finding).** `_join_yaml_flow_lists_impl` counts every `[` and `]`
in the accumulated buffer, including those inside quoted scalars. Reproduced: the valid
`file_references: ["a[.py"]` swallows the following `verification_baseline:` and `labels:`
lines into one record. The same joiner feeds `read_yaml_field` and `aitask_update.sh`'s
frontmatter parse. So once the new writer can legitimately emit `"a[.py"`, an unrelated
status update would rewrite the following fields as junk, and `read_yaml_field
verification_baseline` would read nothing. `read_yaml_list`'s own capture loop
(`yaml_utils.sh:~293`) uses the same naive count.

Fix: one shared, pure-bash flow scanner (bash 3.2 compatible), used by **both** the joiner
and the `read_yaml_list` capture loop, so the two cannot disagree (the t1609 one-definition
pattern).

- **`_yaml_flow_begin <line>`** — decides whether a logical record is a flow sequence. The
  line's value (after leading spaces, any `- ` block-sequence indicators and an optional
  `<key>:` plus spaces) must begin with `[`.
  - A record that does **not** begin a flow sequence is never joined. Its brackets are
    literal scalar text, so `title: a [b` no longer swallows the next line.
- **`_yaml_flow_scan <physical line>`** — advances carried state (`_yfs_depth`, `_yfs_q`
  ∈ none / dq / sq, `_yfs_prev` = previous significant char) over one physical line:
  - **normal state:**
    - `[` / `{` → depth +1; `]` / `}` → depth −1.
    - `"` / `'` opens a quoted scalar only at a scalar start, i.e. when `_yfs_prev` ∈
      `[ { ,`, or after `:` + whitespace. So the apostrophe in `[it's, x]` stays literal.
    - `#` at line start or after whitespace → rest of the physical line is a comment.
  - **dq:** `\` skips the next char; `"` closes.
  - **sq:** `''` is an escaped quote; a lone `'` closes.
  - Quote state carries across physical lines; comment state does not.
  - **Fast path:** a buffer with no `"`, `'` or `#` uses the existing count, which gives
    the identical result, so the common case adds no per-char loop.
- **New `yaml_field_block <field>`** (stdin = frontmatter text) prints the field's
  **original physical lines verbatim**: from `^<field>:` through the end of its logical
  record, with the same scanner deciding the extent. This is what `aitask_update.sh` passes
  through. It is never the space-joined value: joining a quoted scalar that spans lines
  with `" "` would change its folded content.

### 3. Writer — `task_utils.sh`

New `format_yaml_path_list` (stdin or `$1`: **newline-separated** entries → `[a, "b,c"]`;
empty → `[]`). `format_yaml_list` is **left unchanged**, so its id / label / gate callers
see no behaviour change. Per entry:
- **plain** iff it matches `^[A-Za-z_/][A-Za-z0-9_./^:-]*$` or `^\.[A-Za-z_][A-Za-z0-9_./^:-]*$`,
  AND it does not end in `:`, AND it is not (case-insensitively) one of
  `y n yes no true false on off null` plus the `.inf` / `.nan` forms.
  - Rationale: every YAML 1.1 implicit non-string (int, float, sexagesimal, timestamp)
    starts with a digit, `+`, `-` or `.digit`; bool/null are the listed words; and the
    charset excludes every flow indicator (`,[]{}?#` and space). Over-quoting is harmless;
    under-quoting is what the differential test below rules out.
- **otherwise** double-quoted, with escaping done **byte-exactly**: the body runs in a
  subshell with `LC_ALL=C` exported, so the output is identical under every locale.
  - Order: `\` → `\\` first, then `"` → `\"`, then code points PyYAML cannot carry
    literally.
  - **Measured on PyYAML (both `SafeLoader` and `task_yaml._TaskSafeLoader`):**
    - a literal U+0085 inside `"…"` is folded to a space;
    - literal C1 controls, DEL and U+FFFE/U+FFFF raise `ReaderError`, making the whole
      file unreadable;
    - LS, PS, BOM and TAB load intact;
    - the escapes `\x85`, `\L`, `\x90`, `\uFEFF`, `\x7F`, `\t` all round-trip.
  - Escape set, matched as UTF-8 byte sequences:
    - C0 `0x01–0x1F` → `\xNN`
    - DEL → `\x7F`
    - C1 U+0080–U+009F (`C2 80`–`C2 9F`, NEL included) → `\xNN`
    - U+2028 → `\L`, U+2029 → `\P`
    - U+FEFF → `\uFEFF`, U+FFFE → `\uFFFE`, U+FFFF → `\uFFFF`
  - LS, PS and BOM are escaped although they measured intact: YAML 1.1 defines LS/PS as
    line breaks, and escaping is harmless.
  - Plain entries are ASCII-only by the predicate, so they can never hold one of these.
- LF / CR still make the function `die`. They cannot arrive (`validate_file_ref` rejects
  them and the reader classifies them as BAD), and an escaped `\n` would be written as an
  entry the reader then refuses.

Existing outputs such as `[foo.py, bar.py:10-20]` and `[foo.py:10-20^30-40]` are
unchanged, so the current `tests/test_file_references.sh` literal assertions keep holding.

`validate_file_ref` becomes **locale-independent**:
- **C0 + DEL rejected** — test `[[ -n "$(printf '%s' "$ref" | LC_ALL=C tr -dc '\001-\037\177')" ]]`
  instead of the locale-sensitive `[[:cntrl:]]`. A newline would otherwise split an entry
  on the new newline carrier; today it already passes the `[^:]+` regex.
- **Invalid UTF-8 rejected** — if the ref holds any byte ≥ 0x80 (`LC_ALL=C tr -d
  '\000-\177'` leaves output), pipe its bytes to `resolve_python` running
  `sys.stdin.buffer.read().decode("utf-8")` (strict). This is the real decoder, not a
  hand-written UTF-8 table.
  - Non-zero exit → `die "Invalid file reference: not valid UTF-8"`.
  - No interpreter → `die` with that reason (fail closed).
  - Pure-ASCII refs never touch Python, so `create` keeps no Python dependency for the
    common case.
- U+0085 and the other escaped code points stay **accepted**: they are valid UTF-8, and
  the formatter round-trips them.

### 4. Carriers → newline-separated, field read as YAML

- **`aitask_update.sh`**
  - Drop the `parse_yaml_list` for this field at `:618`. Capture
    `CURRENT_FILE_REFERENCES_BLOCK=$(printf '%s\n' "$yaml_content" | yaml_field_block
    file_references)` from the **unjoined** frontmatter text: the complete original
    physical lines, never the joined `$value`.
  - **No `--file-ref` / `--remove-file-ref` ops:** emit that block verbatim, so the field
    stays byte-identical, including a multi-line or commented form. Because the joiner is
    now quote-aware (§2b), the fields that follow are parsed as their own records. A block
    whose value is empty or `[ ]` is still omitted, preserving today's "empty list is
    dropped" rule that `aidocs/framework/manual_verification_staleness.md` documents.
  - **With ops:** read the current list with `get_file_references "$file"`, branching
    explicitly on its status. Non-zero → `die "file_references: in <file> cannot be read as
    a list of path strings (<reason>); edit it by hand before --file-ref/--remove-file-ref"`.
    Then `process_file_references_operations` works on newline-separated input (`mapfile`
    instead of `IFS=','`), and the result goes through `format_yaml_path_list`.
  - The write function's param 21 (`:698`) becomes the **complete field text to emit**:
    either the verbatim block, or `file_references: <format_yaml_path_list output>`. Empty
    means omit. `:840` prints it with `printf '%s\n'` instead of calling
    `format_yaml_list`. This covers the batch (`:2276`) and interactive (`:1241`,
    `:1778`) call sites.
- **`aitask_create.sh`**
  - `dedup_file_refs` prints newline-separated.
  - The three writer functions (`:587`, `:724`, `:2117`) call `format_yaml_path_list`.
  - Every consumer of `deduped_file_refs` (`:2352`, `:2392`, `:2426`, `:2680`) is
    re-checked so none still splits on `,`.
  - `run_auto_merge_if_needed` (`:1933`) reads via `get_file_references` with an explicit
    status check. On failure it warns and skips auto-merge; it is best-effort, never a
    verdict.
- **`aitask_fold_mark.sh` (`:241`)**
  - `if ! union=$(union_file_references …); then die …; fi`, then read the lines into
    `file_ref_args`.
  - This runs in Step 3, **before** the first mutation (the update at `:523`), so a refusal
    leaves nothing half-done. That ordering gets re-verified during implementation.
- **`aitask_find_by_file.sh`**
  - Status-filter in bash as now, then pre-select the files that carry a `^file_references:`
    line (exactly the set the old reader could match), then make **one**
    `read_file_references_batch` call and match path-only portions per block.
  - A failed call → error to stderr, exit non-zero. `create` already treats that as "no
    matches".
  - A per-file `INVALID` / `BAD` block → that file is skipped with a stderr warning.
    Matching is best-effort, never a verdict.
- **`aitask_verification_stale.sh` (`:217`)**
  - Capture `get_file_references` with an explicit status branch, never `|| out=""`.
  - Status 2 → `_emit_skip BASELINE:NONE 0 "file_references: could not be read as a list of
    path strings"`.
  - Status 3 → `_emit_skip … "python unavailable"`.
  - Never FRESH.

### 5. Test scaffold

Add `task_yaml.py` to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()`. Per the
shell_conventions bridge rule, `task_utils.sh` now has a runtime Python sibling. Any
scaffold-parity test is updated with it. Tests whose fake repos copy `task_utils.sh`
manually are checked as well: grep `--file-ref|file_references|aitask_fold_mark|aitask_find_by_file`
across `tests/*.sh`.

### 6. Docs (current-state only)

- `aidocs/framework/manual_verification_staleness.md` — reader-row text: the reader now
  parses YAML, follows the string-only rule and the exit contract.
- `website/content/docs/development/task-format.md` — `file_references` row: entries
  YAML-quoted when needed, so commas and brackets are allowed.
- Stale comments in `aitask_premise_stale.sh:85,209` that say `get_file_references()`
  "turns `a,b.py` into `a` + `b.py`" get reworded so they no longer describe current
  behaviour falsely.
- Grep `website/content` / `aidocs` for any other claim of comma-splitting, and run
  `python3 check_links.py --build` if a website page changes.

### 7. Other `format_yaml_list` callers (task's last bullet)

They are unchanged by construction. Finding to report at review: `sanitize_label` admits
`on` / `null` / `yes` / `010`, which `format_yaml_list` writes plain and Python reads as
`True` / `None` / `8`. That is a separate latent defect in the labels field. It will be
offered as an upstream-defect follow-up at Step 8b, not fixed here.

### Post-phase (risk mitigations)

1. [scaffold_consumer_sweep] List every `tests/*.sh` matching
   `aitask_create.sh|aitask_update.sh|aitask_fold_mark.sh|aitask_find_by_file.sh|task_utils.sh`.
   - **Baseline:** run them against a HEAD checkout in a separate scratch `git worktree add`
     (never a stash, never touching the shared dirty tree). Record pass/fail per file.
   - **Comparison:** run the same list on the implemented tree.
   - Every file that fails now but passed at baseline is fixed in this task (typically a
     fake repo missing `task_yaml.py`, or a literal CSV expectation). Pre-existing failures
     are listed in Final Implementation Notes as pre-existing, with their baseline output.
   - Remove the scratch worktree afterwards (`git worktree remove`).

## Verification

1. **New `tests/test_file_refs_yaml.sh`** — skips cleanly when no Python with PyYAML is
   present, since it is about the parser. For this file only, `assert_counters_init` /
   `assert_counters_load` apply if subshells are used.
   - **Formatter differential.** Corpus: `, [ ] { } : # ? & * ! | > % @` and a backtick,
     each as the leading char, inside and trailing; `on On null Null ~ y n yes 010 0x1f
     1.5 .inf .nan .gitignore 1:30 2026-01-01 85_2`; leading/trailing spaces; `"` `\` `'`;
     non-ASCII; `a,b.py`; `docs/a[bc].md`; `:12`; `foo:`.
   - For every corpus entry (and the corpus as one list): `format_yaml_path_list` output
     loaded by **both** `yaml.safe_load` and `task_yaml._TaskSafeLoader` yields the
     identical list of identical `str`s.
   - **Reader** round-trip: a task file written with that line, read back through
     `get_file_references`, returns the same entries byte-for-byte.
   - **Reader fail-closed cases**: unquoted `[on, 010]` → exit 2, no output;
     `[docs/a[bc].md]` → exit 2; unparseable frontmatter → exit 2; no Python
     (`AIT_PYTHON` pointing at a failing stub, with `_AIT_RESOLVED_PYTHON` unset) → exit 3.
   - **Batch framing**: a stub interpreter that drops one REF line / one END / DONE → the
     whole call fails and prints nothing. This is a mutant per guard.
   - **Code-point escaping (review finding 2).** Corpus entries `a<X>b.py` for every C0
     `0x01–0x1F` except LF/CR, DEL, every C1 `U+0080–U+009F` (U+0085 named explicitly),
     U+2028, U+2029, U+FEFF, U+FFFE, U+FFFF, plus `é`, U+FDD0 and an astral emoji.
     - Run `format_yaml_path_list` under **`LC_ALL=C`** and under a UTF-8 locale (whichever
       of `C.UTF-8` / `en_US.UTF-8` `locale -a` lists; that half is skipped with a printed
       reason if none). Assert byte-identical output across the two.
     - Assert both loaders read back the identical `str`, and `get_file_references`
       returns the identical bytes.
     - Negative control: a hand-written literal `"a<U+0085>b.py"` line is read as
       `a b.py`. This proves the probe sees the folding the escape exists to prevent.
   - **Joiner / scanner differential (review finding 1).** Frontmatter corpora, each
     followed by `verification_baseline: abc @ 2026-01-01 10:00` and `labels: [x]`:
     - `file_references: ["a[.py"]`, `['it''s [']`, `["a\"[", b]`, `[it's, x]`
     - `[a] # [x`, a list wrapped over two lines with a `#` comment and a quoted `]`
     - a dq scalar spanning two lines, `title: a [b`, `  - name: x [y`
     - the existing wrapped-plain-list case

     For each corpus:
     - the top-level keys seen in `join_yaml_flow_lists` output (`^[A-Za-z0-9_]+:`) equal
       PyYAML's top-level keys;
     - `read_yaml_field … verification_baseline` returns the value;
     - `read_yaml_list … labels` returns `x`;
     - `yaml_field_block file_references` returns exactly the original physical lines.
     - A mutant that disables quote tracking (via an env seam only the test sets, or a
       sourced override of `_yaml_flow_scan`) must fail the `"a[.py"` case. This proves
       the scanner is what the case exercises.
   - **Input validation under `LC_ALL=C`** (finding 2): `validate_file_ref` accepts
     `a<U+0085>b.py`, `é.py` and `a,b.py`. It rejects `$'a\nb'`, `$'a\tb'`, `$'a\x7fb'` and
     `$'a\xffb'` (invalid UTF-8) identically under `LC_ALL=C` and the UTF-8 locale.
2. **`tests/test_verification_stale.sh`** gets a quoted-comma fixture: files `a,b.py`, `a`,
   `b.py` exist, `file_references: ["a,b.py"]`, only `a,b.py` changes → not FRESH, and
   `FILES:1`. Plus an unreadable field → SKIP.
3. **`tests/test_file_references.sh`**
   - `--file-ref "a,b.py"` creates `["a,b.py"]`.
   - `ait update --status …` on a task with `["a,b.py", "my file.py"]` leaves the line
     byte-identical. This is red before the fix.
   - `--file-ref x.py` on it appends while preserving both entries.
   - Malformed field + `--file-ref` → dies, file untouched.
   - `--file-ref $'a\nb'` → rejected.
   - **End-to-end (review finding 1).** A task whose frontmatter holds
     `file_references: ["a[.py"]` followed by `verification_baseline: <sha> @ <ts>` and
     `labels: [ui]` gets `ait update --batch <id> --status Implementing`. Assert:
     - the `file_references:` line is byte-identical;
     - `verification_baseline:` and `labels:` are each still their own line with the same
       value;
     - PyYAML parses the result with every key except `status` / `updated_at` equal to
       before.
     - Repeat with `--file-ref b.py` (the ops path): `["a[.py", b.py]`, following fields
       intact.
     - Red before the fix.
   - **End-to-end (finding 2).** Under `LC_ALL=C`, `--file-ref $'a\xc2\x85b.py'` writes
     `["a\x85b.py"]`, and `get_file_references` returns the original bytes.
4. **`tests/test_fold_file_refs_union.sh`** — a folded child with `["a,b.py"]` unions as one
   entry. A folded child with an unreadable field → fold refuses, primary untouched.
5. **find_by_file** — `aitask_find_by_file.sh a,b.py` matches the quoted task.
6. Run the touched and related suites individually:
   - `test_format_yaml_list.sh`, `test_file_references.sh`, `test_fold_file_refs_union.sh`,
     `test_verification_stale.sh`, `test_premise_stale.sh`, `test_draft_finalize.sh`,
     `test_archive_verification_gate.sh`, plus the new test.
   - Every existing `yaml_utils` test, found by grepping
     `tests/*.sh` for `join_yaml_flow_lists|read_yaml_list|read_yaml_field`. The
     scanner change applies to every frontmatter read, so these tests pin the
     wrapped-list (t1444/t1609) behaviour.
   - `bash tests/run_all_python_tests.sh --test-dir …` covering `test_task_premise.py` /
     `test_board_detail_screen.py`, with the exit status checked, not piped.
   - `shellcheck` on every edited script.
7. Then Step 9 (Post-Implementation): review, commit, archival.

## Risk

### Code-health risk: medium
- `aitask_update.sh` now passes `file_references:` through verbatim (original physical
  lines via `yaml_field_block`, never the joined value) on every update without file-ref
  ops (load-bearing path: claims, status changes). A slip in the pass-through or the
  empty-list rule changes every update · severity: low (residual — addressed by inline
  pre-phase update_passthrough_characterization) · → mitigation: inline pre-phase update_passthrough_characterization
- A new Python dependency for the reader (`find_by_file`, `verification_stale`, fold, update
  file-ref ops). Fake-repo tests or minimal environments without `task_yaml.py` / PyYAML now
  fail where they used to pass. The failures are loud (exit 3 / die), but they could break
  unrelated test files that scaffold their own lib dir · severity: medium (residual: the
  test side is addressed by inline post-phase scaffold_consumer_sweep; the minimal-environment
  side remains, bounded to file-ref operations) · → mitigation: inline post-phase scaffold_consumer_sweep
- The formatter's plain-scalar predicate is a hand-written lexical rule. It is mitigated
  in-plan by the PyYAML differential corpus (both loaders) · severity: low · → mitigation: none
- The quote-aware flow scanner (§2b) changes the shared joiner behind `read_yaml_field` /
  `read_yaml_list` / `aitask_update.sh`, i.e. every frontmatter read. A scanner slip
  mis-joins records repo-wide. Bounded by:
  - the fast path, which is byte-identical behaviour for buffers without quotes or `#`;
  - the PyYAML key-set differential plus the disable-scanner mutant;
  - the existing `yaml_utils` tests in the sweep.

  Added by the review round, after mitigation selection · severity: medium · → mitigation: none
- Code-point escaping and the UTF-8 check are byte-level rules. They are pinned by the
  two-locale corpus and the U+0085 negative control. The UTF-8 check runs the real decoder
  rather than a table · severity: low · → mitigation: none

### Goal-achievement risk: low
- None identified. Both suggested fixes (YAML reader, quoting writer) plus the carrier
  defect that would undo them are covered. Other `format_yaml_list` callers were checked
  and left unchanged, and the labels finding is routed to a follow-up.

### Planned mitigations
- timing: pre-phase | name: update_passthrough_characterization | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: aitask_update.sh verbatim pass-through on every update | desc: pin byte-identical file_references across unrelated batch updates, green before the change
- timing: post-phase | name: scaffold_consumer_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: new python dependency breaking scaffolded tests | desc: run every create/update/fold/find_by_file/task_utils test vs a HEAD worktree baseline and fix new failures
