---
Task: t1811_fix_ide_session_override_and_default_session_edges.md
Base branch: main
Output branch: main
---

# t1811 — ide `--session` override, setup probe/writer, YAML-only `default_session` shapes

## Context

t1800 (`d146a440c`) made the five `tmux.default_session` resolvers agree on
blank, null and comment values, and pinned that in
`tests/test_tmux_default_session_resolvers.py`. It deliberately left three
defects out. All three reproduce on HEAD:

| # | Site | Reproduced |
|---|------|------------|
| 1 | `aitask_ide.sh:52` `echo "$SESSION_OVERRIDE"` | `-n`, `-e`, `-E`, `-neE` all print `''`, so `ait ide --session -n` resolves an empty name |
| 2 | `aitask_setup.sh:4140` grep\|sed probe | `# note`, `""`, `null`, `~` all count as "already configured", so the prompt is skipped |
| 3 | `agent_launch_utils.py:747` / `tmux_bootstrap.sh:68` line parsers | flow mapping gives `aitasks` (YAML: `flowsess`); `>-` gives `>-`; `\|` gives `\|`; `yes` gives `yes` (YAML: `True`); `0123` gives `0123` (YAML: `83`) |

**Decisions you made:** (3) the line parsers warn and fall back to `aitasks`,
and the YAML-backed readers stay unchanged. **The one exception is frozen-agent
restore: it refuses instead of falling back.** It runs detached, so the user can
only see it through the saved record. `tmux_bootstrap.sh --create-only` refuses
an unreadable value the same way it already refuses a taken name. Both adjacent
writer bugs in
`_set_tmux_default_session_config` get fixed here: it rewrites
`default_session:` at any indent, and it puts the name into a `sed` replacement
without escaping.

**Review round 1 findings (both confirmed, both addressed below):**
- **Python paths couldn't show the warning.** It's worse than the plan said:
  `tui_switcher._ensure_session_live` reads the bootstrap's stderr only when the
  call fails (`tui_switcher.py:672`). On success, which is the path that creates
  the session, a bash warning would also be dropped.
- **The `#` rule was unspecified.** Measuring it against PyYAML 6.0.3 turned up
  real problems on HEAD, not just gaps in the plan (table in the next section).

**Sizing input:** all 7 registered projects use a plain identifier, so there is
no real incident today. The fix is therefore **one precondition**: the lexical
rule below, which is measured and pinned by the oracle. The warning goes out
through one sentinel and one Python status API, not per-shape special cases.

## The readable-scalar rule (measured against PyYAML 6.0.3)

Measured probe on HEAD. `L` means both line parsers return that value unless a
split is noted. Any YAML error means `load_tmux_defaults` returns `aitasks`.

| value after `default_session:` | YAML | line parsers today | verdict |
|---|---|---|---|
| ` team#1`, ` a#b#c`, ` x#`, ` a##b` | same text | same | readable: `#` not preceded by a space is content |
| ` team#1 # note` | `team#1` | `team#1` | readable: a `#` preceded by a space starts a comment |
| ` team\xa0#1` / ` team#1\xa0` | text kept | **py `team` / `team#1`, bash keeps it** | **twin bug on HEAD**: Python `\s` / `.strip()` treat NBSP as whitespace |
| ` mysess\t# c`, ` mysess\t`, ` my\tsess`, ` \tmysess` | **error** | `mysess` / `my\tsess` | unreadable: a tab outside quotes |
| ` "a\tb"` (literal tab inside quotes) | `a\tb` | same | readable |
| ` "x"#c`, ` "x" #c` | `x` | `x` | readable |
| ` "x" y`, ` "x"\t` | **error** | `x` | unreadable: anything after the closing quote other than spaces and an optional `#…` |
| `mysess` / `"x"` (no space after the colon) | **error** | `mysess` / `x` | unreadable |
| ` a: b` | **error** | `a: b` | unreadable: `: ` inside a plain value |
| ` a:b`, ` a :b`, ` xé`, ` x﻿` | same text | same | readable |
| ` x\x7f`, ` a\x85b`, ` a b` | **error** | text | unreadable: DEL, C1 including NEL, LS/PS |

**The rule.** Both twins implement it byte for byte. The awk runs under
`LC_ALL=C` and matches the UTF-8 byte sequences.

1. **Only a space (0x20) separates tokens.** NBSP and other Unicode spaces are
   content. Trimming removes spaces only.
2. **Separator:** a non-empty value must start with a space. Otherwise it's
   unreadable.
3. **Forbidden characters** anywhere outside a quoted body make the value
   unreadable: tab, C0 controls, DEL, C1 (`\xC2\x80`–`\xC2\x9F`) and U+2028/2029.
   Inside a quoted body, a tab is allowed; other controls still make it
   unreadable.
4. **Plain comment:** a `#` starts a comment only when it's the first
   non-space character of the value, or when it immediately follows a space.
   Everything from there on is dropped. `team#1` keeps its hash.
5. **Quoted:** the closing quote must be on the same line. `"…"` must contain no
   `\`. `'…'` must contain no `''`. After the closing quote only `[ ]*` may
   follow, optionally followed by `#…`. Anything else makes it unreadable.
6. **Plain structure:**
   - It must not start with any of `[ { | > & * ! % @` or a backtick. That
     covers flow collections, block scalars, anchors, aliases and tags.
   - It must not contain `: `.
   - It must not match a PyYAML 6.0.3 implicit resolver: bool, int, float,
     timestamp, `<<` or `=`.
   - Two exceptions still round-trip and stay readable: canonical decimal ints
     (`^(0|-?[1-9][0-9]*)$`) and `True` / `False`.
   - Null spellings and an empty value still mean "not configured", as today.
7. **Block structure:**
   - If the `tmux:` line continues with `{`, it's a flow mapping, and any
     `default_session:` inside that block is unreadable.
   - If the next non-blank line is indented deeper than the child indent, the
     plain value continues on that line and is unreadable. Comment-line behavior
     gets settled against the oracle while implementing, and those rows are
     pinned.

**Out of scope for the rule:** errors elsewhere in the file (a bad byte on
another line). YAML falls back to the default there too, but that is a whole-file
validity question that the line-oriented design can't answer. It's recorded
under Deferred.

## The warning contract: one sentinel, one status API, every consumer

A resolver never prints *only* free text. The unreadable state is carried as
structured data, and each consumer either shows it or is explicitly documented
as structured-only.

**Producers**
- **Bash:** `_tmux_bootstrap_default_session_raw <root>` exits `2` and writes
  two lines to stderr: `DEFAULT_SESSION_UNREADABLE:<shape>:<cfg path>`, then a
  human-readable line. That's the same sentinel-then-detail shape as
  `BOOTSTRAP_FAILED:`. Possible `<shape>` values: `flow_mapping`,
  `block_scalar`, `typed_scalar`, `node_property`, `quoted_escape`,
  `trailing_content`, `tab_or_control`, `missing_separator`,
  `mapping_indicator`, `continuation`.
- **Python:** `read_default_session_status(root) -> tuple[str, str | None]`
  returns `(session, shape_or_None)` and never prints.
  - `_read_default_session` becomes a thin wrapper around it, so its
    signature and callers don't change.
  - New shared helper `parse_default_session_unreadable(stderr) -> str | None`,
    the one parser for the sentinel.
- **`AitasksSession`:** new optional field
  `default_session_problem: str | None = None`. Registry synthesis
  (`agent_launch_utils.py:903`) fills it. It's additive, not part of `key`, and
  `dataclasses.replace` preserves it.

**Consumers.** I grepped every caller of the two parsers and of
`discover_aitasks_sessions(include_registered=True)`:

| Consumer | Creates a session? | Route |
|---|---|---|
| `ait ide` (`aitask_ide.sh`) | yes | stderr to the terminal (shown) |
| `tmux_bootstrap.sh` run standalone from a shell | yes | stderr (shown) |
| `ait setup` probe | no, it writes config | warns and leaves the file untouched (shown) |
| `tui_switcher._ensure_session_live` | **yes** | **after a successful bootstrap, if `entry.default_session_problem` is set or `parse_default_session_unreadable(result.stderr)` matches, `self.app.notify(…, severity="warning")` naming the project, the shape and the session it fell back to. Textual-safe, and the same method already uses `notify`.** |
| `agent_restore._bootstrap_project_session` (`--create-only`) | yes, but runs detached through `run-shell -b` | **Refuses and does not fall back.** `--create-only` exits **44** and prints `BOOTSTRAP_FAILED:default_session_unreadable:<shape>` (after the `DEFAULT_SESSION_UNREADABLE:` sentinel), **before any tmux call, so nothing is created**. `_bootstrap_project_session` maps that to `why="default_session_unreadable:<shape>"`. `_launch_into_new_window` returns `no_session_for_root:…\|bootstrap:default_session_unreadable:<shape>`. `_rollback` saves it as `last_error`. `restore_verdict` turns it into `restore failed: … — capture kept` (`warn=True`), and `monitor_shared` shows it with `notify(severity="warning")`. The record stays `frozen` and can be restored once the config is fixed. All of this uses existing code paths (the saved record is the only channel a user sees, per `_rollback`'s docstring), with no record-schema change. |
| `stats_app.discover_stats_sessions` | no, label only | structured-only: the field is available, and a label has no side effect |
| `discover_aitasks_sessions()` without the flag (`agent_freeze`, `agent_restore`, monitor) | — | not affected: no synthesis, and the monitors read through `load_tmux_defaults` |

The documentation states this contract: **every path that creates a session
shows the problem.** Interactive paths warn and fall back. The detached restore
path refuses and reports through its saved record. Only the stats label, which
creates no session, keeps the problem as data without showing it.

## Implementation

### Pre-phase (risk mitigations)
1. [pin_real_config_sessions] **Before editing any file**, write a test-free
   Python snippet to the scratchpad. It iterates over the paths in
   `~/.config/aitasks/projects.yaml` plus this repo and records, per project:
   - `load_tmux_defaults`, `_read_default_session` and bash
     `_tmux_bootstrap_resolve_session` (the monitors read through
     `load_tmux_defaults`, so this covers all five resolvers);
   - bash's stderr.

   Write sorted `path|resolver|session|stderr` rows to
   `<scratchpad>/t1811_sessions_before.txt`. Expected: 7 projects × 3 readers,
   all readers agreeing, stderr empty. After implementation, rerun the snippet
   into `…_after.txt`, which must be identical. For `_after`, also record
   `read_default_session_status(...)[1]` and require it to be `None` for all 7
   projects. Any difference is a regression: stop.

### 1. `lib/tmux_bootstrap.sh`: one reader, three entry points
- **`_tmux_bootstrap_default_session_raw <root>`:**
  - The awk runs under `LC_ALL=C` and implements rules 1–7. It reads to EOF, as
    today, which the continuation check needs.
  - It passes `ok<TAB>value` or `bad<TAB>shape` to bash.
  - On `ok`, bash prints the value (empty means not configured) and exits `0`.
  - On `bad`, bash writes the sentinel and the human line to stderr and exits
    `2`.
  - The PyYAML regexes live in one commented block, with the version they were
    copied from.
- **`_tmux_bootstrap_resolve_session <root>`:** `name=$(raw) || name=""`,
  falling back to `aitasks`. Output uses `printf`. Stderr passes through
  untouched, so the sentinel reaches every caller.
- **`spawn_session_detached <root> [--create-only]`:**
  - Resolve through the raw reader and keep its rc.
  - If rc is 2 in `--create-only` mode: after the sentinel, write
    `BOOTSTRAP_FAILED:default_session_unreadable:<shape>` and the human line to
    stderr, then `return 44`. This happens **before** `ait_tmux_session_target`
    and any `has-session` or `new-session` call.
  - In the default ensure mode: warn and fall back to `aitasks`, as before.
  - Update the exit-code list in the docblock
    (`44 unreadable default_session (--create-only only)`) and the header
    comment for the create-only form.
- **New `_tmux_bootstrap_session_for <root> [override]`:** prints a non-empty
  override with `printf '%s\n'`, otherwise the resolved session.
- Update the header comment: the rule, the rc-2 contract and the sentinel.

### 2. `aitask_ide.sh`: defect 1
- Replace `resolve_session()` and its `echo` with
  `SESSION=$(_tmux_bootstrap_session_for "$(pwd)" "$SESSION_OVERRIDE")`.

### 3. `lib/agent_launch_utils.py`: the Python twin and the status API
- **`_yaml_line_scalar`:**
  - Replace `re.split(r"(?:^|\s)#")`, `.strip()` and `.rstrip()` with logic that
    uses spaces only. This fixes the NBSP twin bug.
  - Return a small result that is either `value | None` or unreadable with a
    `shape`, using the same checks and regexes as the awk, compiled once.
- **`read_default_session_status(root)`:**
  - Detects a flow-mapping `tmux:` line.
  - Keeps scanning after a match, for the continuation check.
  - Returns `(DEFAULT_TMUX_SESSION, shape)` for unreadable values.
- **`_read_default_session(root)`** now returns
  `read_default_session_status(root)[0]`.
- Add **`parse_default_session_unreadable(stderr)`**.
- Add the **`AitasksSession.default_session_problem`** field, filled in the
  registry synthesis branch.
- Update the docstrings to state the rule and the contract.

### 4. `lib/tui_switcher.py`: notification route
- In `_ensure_session_live`, after the `returncode == 0` branch and before the
  `is_live` flip:
  ```python
  problem = entry.default_session_problem or parse_default_session_unreadable(result.stderr or "")
  if problem:
      self.app.notify(f"{entry.project_name}: tmux.default_session is not a plain single-line value ({problem}); using session '{DEFAULT_TMUX_SESSION}'", severity="warning")
  ```

### 4b. `lib/agent_restore.py`: map the refusal
- `_bootstrap_project_session`: in the stderr loop, next to the
  `session_exists` and `stale_path` branches, add:
  `if line.startswith("BOOTSTRAP_FAILED:default_session_unreadable:"): return "", "default_session_unreadable:" + line.split(":", 2)[2].strip()`.
  It has to be an explicit branch. The fallback "last stderr line" would
  otherwise pick the human-readable line.
- Update the docstring to list the new outcome. The rest of the path already
  works: `_launch_into_new_window` → `_rollback` → `last_error` → verdict →
  notify.

### 5. `aitask_setup.sh`: probe (defect 2) and writer (the adjacent bugs)
- **Probe:** call the raw reader in an isolated subshell. Sourcing
  `tmux_bootstrap.sh` directly would load `terminal_compat.sh`, which redefines
  setup's `[ait]`-prefixed `info`/`warn`/`success`/`die`:
  ```bash
  rc=0
  current=$(bash -c 'source "$1"; _tmux_bootstrap_default_session_raw "$2"' _ \
            "$SCRIPT_DIR/lib/tmux_bootstrap.sh" "$project_dir") || rc=$?
  ```
  - `rc=2`: the sentinel has already reached the terminal. Also `warn` that
    setup is leaving the value untouched, and return. Rewriting it could, for
    example, duplicate the `tmux:` block after a flow mapping.
  - Any other non-zero rc: treat the value as not configured and prompt. That's
    the fail-safe direction and is idempotent.
  - rc 0 with output: already configured.
- **Writer `_set_tmux_default_session_config`:** replace grep, sed and append
  with one awk pass:
  - The value comes in through `ENVIRON`, not `-v`, which processes escapes.
  - Replace only the direct child at the child indent inside the column-0
    `tmux:` block. A nested `syncer: default_session:` is left alone.
  - If the block has no key, insert it at the child indent (2 if there are no
    children). If there's no block, append one.
  - Write the value single-quoted (with `'` doubled) unless it's a plain
    identifier `^[A-Za-z_][A-Za-z0-9_-]*$` that isn't a bool or null spelling.
- **Verify read-back:** use the same raw reader. The write only counts if rc is
  0 and the value equals the name.

### 6. Docs (current state only)
- `seed/project_config.yaml`: in the `default_session` comment, say to use a
  single-line plain or quoted name, and that anything else falls back to
  `aitasks` with a warning.
- `website/content/docs/tuis/monitor/reference.md`: in the
  `tmux.default_session` row, say "single-line string (plain or quoted)" and
  that other YAML forms fall back to `aitasks` with a warning in `ait ide` and
  the TUI switcher. Run `python3 check_links.py --build` afterwards.

### Post-phase (risk mitigations)
1. [twin_regex_generated_corpus] Add `GeneratedCorpusInvariantTests` to
   `tests/test_tmux_default_session_resolvers.py`:
   - `random.Random(1811)` builds about 2,000 raw values, each written verbatim
     after `default_session:` into its own config.
   - **Alphabet:** `0-9 _ . : - + x b o e E #`, a space, a tab, NBSP, DEL, `é`,
     quotes, letters. Bool, null, `inf`/`nan` spellings and date fragments are
     spliced in, and a leading space is chosen randomly. **No character class is
     filtered out.** Hashes and spaces are included on purpose, and the oracle
     decides.
   - **Speed:** a single `bash` process loops over all the configs and prints
     `rc<TAB>value<TAB>sentinel_shape` per config. Python reads them all
     in-process.
   - **Per value:**
     - **Invariant:** `yaml_backed == line`, or (`line == D` and bash rc 2 and
       the sentinel is present and
       `read_default_session_status(...)[1] == sentinel shape`).
     - **Twin:** Python and bash agree on the value and on readable versus
       unreadable.
   - **Floors (each ≥ 50):**
     - tokens containing a `#` that stays in the result;
     - tokens where a space-preceded `#` really gets cut;
     - tokens that fall back;
     - tokens YAML reads the same.

     If any floor fails, the generator is broken, not the code.
   - **Runtime:** ≤ ~10 s on this box. Otherwise shrink N and keep the floors.

## Tests

### `tests/test_tmux_default_session_resolvers.py` (keeps its oracle discipline)
- **`PARITY_ROWS`, readable positive controls** (all five resolvers return the
  text; the existing `test_parity_rows_match_yaml` oracle proves each one;
  bash prints no sentinel):
  - Hash cases: `team#1`, `a#b#c`, `x#`, `a##b`, `team#1 # note` → `team#1`.
  - Colon and Unicode: `a:b`, `a :b`, `xé`, `team\xa0#1`, `team#1\xa0`.
  - Quoted with a comment: `"x"#c` → `x`, `"x" #c` → `x`; quoted with a literal
    tab: `"a<TAB>b"`.
  - Canonical ints and bools: `5`, `0`, `-7`, `True`, `False`; lookalikes
    `yes_proj`, `2024proj`, `x-y`.
  - **The NBSP rows are red on HEAD.** They are the proof of the Python twin
    fix.
- **`LegacyYamlFormsPreservedTests.test_line_parsers_fall_back_on_yaml_only_shapes`:**
  for each `LEGACY_ROW`, both line parsers return `D`, bash exits rc 2 with the
  sentinel shape (`flow_mapping`, `block_scalar`, `typed_scalar`), and the
  Python status gives the same shape. The existing YAML-backed pins are
  unchanged.
- **New `UnreadableScalarTests` (`UNREADABLE_ROWS`):**
  - Rows:
    - tab cases: `mysess<TAB># c`, `mysess<TAB>`, `my<TAB>sess`,
      `<TAB>mysess`, `"x"<TAB>`;
    - quoted endings and escapes: `"x" y`, `"a\tb"` with a backslash escape,
      `'it''s'`, an unclosed quote;
    - structure: missing separator `mysess`, `a: b`, `&a x`, `*a`,
      `!!str 0123`, `[a]`, `{a: b}`, `>2-`, continuation;
    - typed scalars: `0x1F`, `1_000`, `+5`, `-0`, `1.50`, `.inf`,
      `2024-01-01`, `1:30`, `<<`, `=`, `on`, `OFF`;
    - control characters: DEL, NEL, U+2028.
  - For each row, both twins return `D` with the **expected shape**, and bash
    exits rc 2 with the sentinel.
  - **Oracle control:** `load_tmux_defaults(root) != the raw text`, or YAML
    raises. Every row is proven to be a real divergence.
- **Python status and sentinel parser:**
  - `parse_default_session_unreadable` round-trips a real bash stderr.
  - It returns `None` on stderr that carries only `BOOTSTRAP_FAILED:` or is
    empty.

### `tests/test_discover_include_registered.py` (extend its registry fixture)
- A registered, non-live repo with `default_session: >-` gives a synthesized
  entry with `session == "aitasks"` and `default_session_problem ==
  "block_scalar"`.
- **Control:** a plain repo gives `default_session_problem is None`.
- `dataclasses.replace(entry, is_live=True)` keeps the field.

### New switcher notification test (in the existing switcher test module if one covers `_ensure_session_live`, otherwise `tests/test_tui_switcher_default_session_notify.py`)
- Drive the real `_ensure_session_live`, with `subprocess.run` patched to return
  rc 0 and stderr carrying the sentinel, and `app.notify` recorded.
  - Assert one `severity="warning"` notification naming the project, the shape
    and `aitasks`.
  - Assert the entry is flipped live.
- A second route through the entry field alone (stderr empty,
  `default_session_problem` set) also notifies.
- **Negative controls, which must clear:**
  - rc 0 with no sentinel and no field: **no** notification.
  - rc 1 with `BOOTSTRAP_FAILED:stale_path`: the existing modal path, with no
    warning notification.

### Restore refusal (the whole visible chain)
- **Bash, in `tests/test_ide_session_override.sh`:**
  - `bash tmux_bootstrap.sh --create-only <root>` on a `>-` config, with a stub
    `tmux` on `PATH` that logs every call. Expect exit 44, stderr containing
    both `DEFAULT_SESSION_UNREADABLE:block_scalar:` and
    `BOOTSTRAP_FAILED:default_session_unreadable:block_scalar`, stdout without
    `BOOTSTRAP_CREATED:`, and **an empty stub call log**, so nothing was
    created.
  - **Controls:** the same config **without** `--create-only` exits 0, warns
    and calls `new-session -s aitasks`. A plain config with `--create-only`
    creates the session normally.
- **`tests/test_agent_restore.py`:**
  - `_bootstrap_project_session` with `subprocess.run` patched to exit 44 with
    the real two-line stderr returns `("", "default_session_unreadable:block_scalar")`.
    **Control:** the existing `session_exists` and `stale_path` mappings still
    hold.
  - Drive `_launch_into_new_window` with `_session_for_root` returning `None` and
    the refused bootstrap. The returned error contains
    `bootstrap:default_session_unreadable:block_scalar`.
- **`tests/test_frozen_restore_verdict.py`:** add a row. A `frozen` record whose
  `restore_attempts` rose and whose `last_error` is
  `<nonce>:respawn:no_session_for_root:/p|bootstrap:default_session_unreadable:block_scalar`
  gives `done=True`, `warn=True`, and a message containing
  `default_session_unreadable:block_scalar` and `capture kept`.

### New `tests/test_ide_session_override.sh`
- **Library:** `_tmux_bootstrap_session_for "$root" <v>` returns exactly `-n`,
  `-e`, `-E`, `-neE` and `a b`. An empty override falls back to the config.
- **Real entry point, with no production seam:** run `aitask_ide.sh --session -n`
  with `TMUX=<tmp>/ait,1,0` and a stub `tmux` first on `PATH` that answers
  `display-message` with `other`. Assert stderr contains
  `configured session is '-n'` and the exit code is 1.
- **Red proof:** run it against a scratch copy of the pre-fix script. Output is
  `''`. No stash.
- **Sentinel through the entry point:** a config with `>-` and no `--session`.
  Stderr contains `DEFAULT_SESSION_UNREADABLE:block_scalar:` and
  `configured session is 'aitasks'`.
- Uses `tests/lib/asserts.sh`. Subshell bodies also call `assert_counters_init`
  and `assert_counters_load`.

### New `tests/test_setup_tmux_default_session.sh` (`--source-only`)
The scaffold holds `tmux_bootstrap.sh`, `tmux_exec.sh` and `terminal_compat.sh`
in a temp `.aitask-scripts/lib/`, with `SCRIPT_DIR` pointed at it and a non-tty
stdin.
- **Probe:**
  - `# note`, `""`, `null`, `~` prompt, and the file ends with
    `default_session: aitasks`.
  - `mysess` and `team#1` stay untouched with "already configured".
  - Flow-mapping, block-scalar and `mysess<TAB># c` configs: the sentinel and
    the warning are printed, and the **file is byte-identical** afterwards.
- **Writer:**
  - A nested-only `syncer: default_session: keep` is left alone, and the direct
    key is inserted.
  - Names `my/sess`, `a&b`, `yes`, `null` and `team#1` read back exactly through
    the raw reader.
  - With no block, one is appended.
  - A 4-space block gets the key inserted at 4 spaces.
- **Negative control:** an inlined copy of the pre-fix grep|sed writer is shown
  to corrupt the file or read back wrong for each writer case, which proves the
  fixtures discriminate.

## Verification
```bash
python3 tests/test_tmux_default_session_resolvers.py
python3 tests/test_discover_include_registered.py
python3 tests/<switcher notify test>
python3 tests/test_agent_restore.py
python3 tests/test_frozen_restore_verdict.py
bash tests/test_restore_session_bootstrap_live.sh     # existing create-only live contract still holds
bash tests/test_ide_session_override.sh
bash tests/test_setup_tmux_default_session.sh
python3 tests/test_minimonitor_own_header_session.py
python3 tests/test_session_key_collision.py
bash tests/test_no_raw_tmux.sh
shellcheck .aitask-scripts/aitask_ide.sh .aitask-scripts/aitask_setup.sh .aitask-scripts/lib/tmux_bootstrap.sh
(cd website && python3 check_links.py --build)
set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -3   # last line is the verdict
```
The pre-phase diff (`t1811_sessions_before.txt` against `_after.txt`) must be
empty.

## Deferred, with owners
- **Whole-file YAML validity:** a malformed line elsewhere in
  `project_config.yaml` makes the YAML readers fall back to `aitasks` while the
  line parsers still read `default_session`. The line-oriented design can't see
  this. Same route.
- **`ait ide --session` doesn't reject tmux-illegal names (`.`, `:`),** which
  setup does. A pre-existing gap. Same route.

## Step 9
Post-implementation follows task-workflow Step 9. The work is on the current
branch, so there is no merge. After that come the gates (`risk_evaluated`), then
archival.

## Risk

### Code-health risk: medium
- The readable-scalar rule could flag a value that YAML reads back as the same
  string. The session would then become `aitasks` (the stats label shows only
  the data), or frozen-agent restore would refuse a config that is actually
  fine. This touches the shared resolver behind `ait ide`,
  `spawn_session_detached`, restore and registry discovery.
  · severity: medium (residual: low. Every registered real config is pinned
  unchanged with no sentinel, and the measured lexical table is pinned by
  oracle rows) · → mitigation: inline pre-phase pin_real_config_sessions
- The PyYAML implicit-resolver regexes and the byte-class rules get copied twice,
  into awk ERE under `LC_ALL=C` and into Python. The two copies could drift
  apart in a way a hand-picked corpus misses. · severity: medium (residual:
  low. A seeded, unfiltered generated corpus checks the twins against PyYAML,
  with floors on both sides of every split) · → mitigation: inline post-phase
  twin_regex_generated_corpus
- A new field on the frozen `AitasksSession` changes dataclass equality. The
  field defaults to `None`, is not part of `key`, and is preserved by
  `dataclasses.replace`. Covered by the discovery test. · severity: low
  · → mitigation: none
- Rewriting `_set_tmux_default_session_config` could corrupt an existing config
  during `ait setup`. Covered by the byte-identical, round-trip and nested-key
  writer tests. · severity: low · → mitigation: none

### Goal-achievement risk: low
- Warning visibility is a defined contract, and every session-creating path
  shows the problem. Interactive paths warn and fall back. The detached restore
  path refuses through its saved `last_error`, which you chose. A refused
  restore needs the config fixed before it can be retried, but that is visible
  and recoverable (the record stays `frozen`, the capture is kept).
  · severity: low · → mitigation: none
- New exit code 44 on `tmux_bootstrap.sh --create-only`. Its only caller is
  `agent_restore`, which maps it explicitly, and an unknown code would still
  fail closed through the "last stderr line" fallback. · severity: low
  · → mitigation: none
- The comment-line case of the continuation rule gets settled against the oracle
  while implementing, and its rows are pinned. · severity: low
  · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: pin_real_config_sessions | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: readable-scalar rule over-flags a real value | desc: snapshot every registered project's resolved session across all readers before/after; diff must be empty with no sentinel and no status problem
- timing: post-phase | name: twin_regex_generated_corpus | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: awk/Python PyYAML-regex and byte-class transcription drift | desc: seeded ~2000-value unfiltered corpus asserting yaml==line or (default+rc2+sentinel+matching shape), bash==python, with >=50 floors on kept-hash, cut-comment, fallback and agreement
