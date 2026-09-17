---
Task: t1825_reject_illegal_ide_session_names_and_whole_file_yaml_errors.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1825 — Reject illegal `ait ide --session` names; detect whole-file byte-level YAML errors in the default_session line readers

## Context

t1811 (`bc97800ee`) made the two line-oriented `tmux.default_session` readers
(`agent_launch_utils.read_default_session_status` and
`tmux_bootstrap.sh::_tmux_bootstrap_default_session_scan`) read a value only when
PyYAML would read back the same string, and otherwise report a shape. It left two
gaps:

1. `ait ide --session a.b` is passed straight to tmux, which fails there with an
   unhelpful error. `ait setup` already rejects `.` and `:`, because tmux treats
   them as target separators.
2. Whole-file problems are invisible to the line readers. When PyYAML rejects the
   file, `load_tmux_defaults` (board, monitors, agentcrew) returns `aitasks` while
   `ait ide` and registry discovery still return the configured name.

**User decision (scope of gap 2): "Bytes only, document rest".**
- Detect the byte-level problems PyYAML's *Reader* rejects before parsing: invalid
  UTF-8 (bash gains the existing `encoding` shape) and non-printable characters
  anywhere in the file, NUL included (new shape `non_printable`).
- Accept and document the remaining gap: a malformed line under another key. Only
  a full YAML parse can see it.

Measured while planning:
- glibc `iconv -f UTF-8 -t UTF-8` accepts code points above U+10FFFF (`F4 90..`),
  `F5..FF` leads and 5-byte forms, all of which Python's strict decode rejects. So
  `iconv` cannot give parity. The bash side validates UTF-8 with a byte state
  machine inside the existing awk pass, which also avoids a new external tool.
- PyYAML 6.0.3 `Reader.NON_PRINTABLE` is
  `[^\t\n\r -~\x85\xa0-퟿-�\U00010000-\U0010ffff]`.

## Implementation

### 1. `ait ide --session` validation
- `.aitask-scripts/lib/tmux_bootstrap.sh`: add a predicate next to
  `_tmux_bootstrap_session_for`:
  ```bash
  # _tmux_bootstrap_session_name_ok <name>
  # 1 when <name> holds `.` or `:` — tmux reads both as target separators.
  _tmux_bootstrap_session_name_ok() { [[ "$1" != *[.:]* ]]; }
  ```
- `.aitask-scripts/aitask_ide.sh`: in the `--session` case, after the empty check:
  ```bash
  _tmux_bootstrap_session_name_ok "$SESSION_OVERRIDE" \
      || die "Session name contains invalid chars (. or :): $SESSION_OVERRIDE"
  ```
  (`tmux_bootstrap.sh` is already sourced before the parse loop.) Add one line to
  `--help`: "NAME may not contain '.' or ':'."
- `.aitask-scripts/aitask_setup.sh::setup_tmux_default_session`: swap the inline
  `*"."*|*":"*` test for the same predicate through `_setup_tmux_bootstrap_call`.
  This keeps one definition. Its behavior stays warn-and-fall-back.

### 2. Python twin — `.aitask-scripts/lib/agent_launch_utils.py`
- `_YAML_LINE_CONTROL`: add `\x00` to the range (`[\x00-\x08…]`). Rewrite the
  "NUL is not listed" comment: bash now maps NUL to `\001`, which is in its control
  set, so the twins agree.
- Add
  `_YAML_NON_PRINTABLE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f￾￿]")`.
  It is PyYAML's Reader set restricted to what a strict UTF-8 decode can produce:
  surrogates never survive decode, and NEL, BOM, LS and PS are printable. Comment
  it with the verbatim PyYAML pattern.
- `read_default_session_status`: after the line loop, if `problem is None` and
  `_YAML_NON_PRINTABLE.search(text)`, return `(DEFAULT_TMUX_SESSION, "non_printable")`.
  Precedence, stated in the docstring: `encoding` first, because nothing else can
  be read; then the line shapes, unchanged; then `non_printable`. A control
  character on the value line therefore keeps its existing `tab_or_control` shape.
- `DEFAULT_SESSION_PROBLEM_SHAPES`: add `"non_printable"`. Drop the "except
  `encoding`" sentence, since bash now reports it too. Add
  `DEFAULT_SESSION_FILE_SHAPES = ("encoding", "non_printable")` for the notice
  wording below. Document the accepted gap in the docstring: a structurally
  invalid line elsewhere in the file is still not detected, and
  `load_tmux_defaults` falls back while the line readers read the value.

### 3. Bash twin — `_tmux_bootstrap_default_session_scan`
- Pipe: `tr '\r\000' '\n\001'`. NUL becomes a control byte that awk can carry.
- Pass one more env string, `BYTES`, holding bytes `\001`–`\377` built with
  `printf`. In awk `BEGIN`, build `ORD[c] = i` from it, so bytes are compared
  numerically without `\x` escapes or locale classes, in keeping with the existing
  env-byte-string rule.
- New awk function `bytes_check(s)`, run on **every** record before any `next`,
  including blank and comment lines:
  - UTF-8 state machine over ordinals, the RFC 3629 table:
    - `00-7F`
    - `C2-DF` + 1 continuation
    - `E0` + `A0-BF`, `E1-EC|EE-EF` + `80-BF`, `ED` + `80-9F`, each followed by 1
      continuation
    - `F0` + `90-BF`, `F1-F3` + `80-BF`, `F4` + `80-8F`, each followed by 2
      continuations

    A sequence left open at end of record is invalid, because CR and LF are never
    continuation bytes. Sets `enc_bad = 1`.
  - Non-printable, set `np = 1`:
    - single bytes `01-08`, `0B`, `0C`, `0E-1F`, `7F` (CR is already LF; tab is allowed)
    - `C2` followed by `80-84` or `86-9F`
    - `EF BF BE` or `EF BF BF`
- The BOM strip on record 1 stays as it is. U+FEFF is printable anyway.
- `END`: `if (enc_bad) bad encoding; else if (problem != "") bad problem; else if (np) bad non_printable; else ok`.
  This matches the Python precedence.
- Update the header comment block: the new rule bullet and the accepted
  structural gap.

### 4. Notice wording for file-level shapes (every consumer)
- `tmux_bootstrap.sh::_tmux_bootstrap_report_unreadable`: the sentinel line is
  unchanged. The human line branches on the shape: `encoding`/`non_printable` →
  `Warning: <cfg> is not valid YAML (<shape>: invalid UTF-8 or a non-printable character); tmux.default_session cannot be trusted`.
  All other shapes keep today's text.
- `.aitask-scripts/lib/tui_switcher.py` (~l.695): same branch using
  `DEFAULT_SESSION_FILE_SHAPES`, giving
  `"{project}: project_config.yaml is not valid YAML ({problem}); using session 'aitasks'"`.
- `agent_restore.py` passes `default_session_unreadable:<shape>` through
  unchanged. No change is needed; the new shape flows through it.

### 5. Tests
- `tests/test_ide_session_override.sh`: new section. `ait ide --session a.b` and
  `--session a:b` each exit 1 with "invalid chars", and the stub tmux log stays
  empty, so the refusal happens before tmux. Library rows for the predicate:
  `a.b`, `a:b` → 1; `-n`, `a b`, `ok` → 0.
- `tests/test_tmux_default_session_resolvers.py`:
  - `FileLevelByteTests` — a UTF-8 matrix. Each case is embedded on a **comment
    line elsewhere** in a file whose `default_session: ok`:
    - valid: ascii, 2/3/4-byte max `F4 8F BF BF`, BOM, NEL, LS
    - invalid: overlong `C0 80`, `E0 80 80`, surrogate `ED A0 80`, `F4 90 80 80`,
      `F5`, `FF`, 5-byte, truncated 2/3, lone continuation, truncated at EOF

    Oracle: `data.decode("utf-8")` decides valid or invalid; the code under test
    does not. Assert that bash shape == Python shape == `encoding` exactly when the
    oracle says invalid, else `None`/`rc 0`.
  - A non-printable matrix on another line: NUL, `\x01`, `\x0b`, `\x1f`, DEL, U+0080,
    U+009F, U+FFFE, U+FFFF → `non_printable`. Tab, CR, NEL (`\x85`), NBSP, U+FFFD → readable.
    Oracle: `yaml.safe_load` raises `ReaderError` exactly for the first group. Also
    assert `_yaml_backed(root) == D` for every announced row, which is the
    divergence this closes.
  - Precedence rows: an invalid UTF-8 byte plus a block-scalar value → `encoding`.
    DEL on the value line → `tab_or_control`. NUL on the value line →
    `tab_or_control` in both twins.
  - Corpus: add `"\x00"` and `"\x85"` to `_CORPUS_CHARS`, so NUL is no longer
    excluded from the twin invariant. Add a whole-file mutation pass: for each of
    ~200 seeded corpus values, append a comment line holding one random byte from a
    pool of the invalid and non-printable bytes above. Assert that the twins agree
    and that the shape is set whenever `yaml.safe_load` fails with a
    `ReaderError`. Keep the oracle discipline.
  - Update the module docstring's contract list.
- `tests/test_tui_switcher_default_session_notify.py`: add one case for a
  `non_printable` problem asserting the file-level wording. Keep the existing case
  on the old wording.
- `tests/test_setup_tmux_default_session.sh`: add a probe spec
  `'NUL elsewhere|…|non_printable'`, if `printf '%b'` there can emit `\0`.
  Otherwise use a DEL comment line.

## Verification
- `bash tests/test_ide_session_override.sh`
- `bash tests/test_setup_tmux_default_session.sh`
- `python3 tests/test_tmux_default_session_resolvers.py`
- `bash tests/run_all_python_tests.sh --test-dir tests` (full suite; read the last line)
- `shellcheck .aitask-scripts/aitask_ide.sh .aitask-scripts/lib/tmux_bootstrap.sh .aitask-scripts/aitask_setup.sh`
- Real repo: `bash -c 'source .aitask-scripts/lib/tmux_bootstrap.sh; _tmux_bootstrap_default_session_raw .'`
  still prints the configured name with rc 0, and so does the Python status (no
  false positive on the live config).
- Negative control: temporarily flip the `F4` upper bound to `BF` in awk, in a
  scratch copy, and confirm the matrix test fails.

## Step 9 (Post-Implementation)
Follow the task-workflow Step 9 cleanup, archival and merge. The work is on the
current branch under the `fast` profile.

## Risk

### Code-health risk: medium
- A new awk UTF-8/non-printable byte scan now runs on every line of the reader
  behind `ait ide`, bootstrap and setup. A false positive would silently move a
  valid project onto session `aitasks`. · severity: medium · → mitigation: none (covered in-plan: oracle-driven valid/invalid matrix, live-config check, negative control)
- awk portability of a 255-byte env string and `ORD[]` lookup under `LC_ALL=C`
  (mawk, BSD awk), and `tr '\000'` on BSD. · severity: low · → mitigation: none (same env-byte-string technique the reader already relies on; not testable on macOS here, stated in the commit)

### Goal-achievement risk: low
- A structurally malformed line elsewhere in the file remains undetected. This was
  accepted by the user's scope decision and is documented in both twins.
  · severity: low · → mitigation: none (accepted by user decision)
