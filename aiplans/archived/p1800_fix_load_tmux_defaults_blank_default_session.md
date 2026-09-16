---
Task: t1800_fix_load_tmux_defaults_blank_default_session.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1800 — Make every tmux session-name resolver agree on blank, null and commented `default_session`

## Context

`seed/project_config.yaml:441` ships `default_session:` with no value. Four code
paths **resolve a project's tmux session name** from that key, and they disagree
whenever the value is blank, null, whitespace-only or commented. The unquoted
blank rows were measured against fixtures; the rest come from reading the code:

| config value | YAML | `load_tmux_defaults` | `_read_default_session` | monitor / minimonitor `main()` | bash `_tmux_bootstrap_resolve_session` |
|---|---|---|---|---|---|
| blank (seed shape) | `None` | `'None'` | `aitasks` | `None` | `aitasks` |
| `# note` / `null` / `~` | `None` | `'None'` | `# note` / `null` / `~` | `None` | `# note` / `null` / `~` |
| `""` / `''` | `''` | `''` | `aitasks` | `''` | `aitasks` |
| `"   "` / `'   '` | `'   '` | `'   '` | `'   '` | `'   '` | `aitasks` |
| `mysess  # team` | `mysess` | `mysess` | `mysess  # team` | `mysess` | `mysess  # team` |
| `-n` / `-e` | `-n` | `-n` | `-n` | `-n` | **empty** (bash `echo` eats it) |

Consequences today: `ait ide` attaches to `aitasks`, while
`agentcrew_runner.py:436` creates a tmux session literally named `None`, the
board (`aitask_board.py:12210, 12388`) looks in session `None` outside tmux,
`agent_command_screen.py:580` pre-fills `None`, and the monitors
(`monitor_app.py:3894`, `minimonitor_app.py:5302`) start on `None` or `''`.
That answers the task's open question: **the monitors share the defect**.
Separately, bash's builtin `echo` treats option-like names as flags, so a
configured `default_session: -n` makes `_tmux_bootstrap_resolve_session`
(`tmux_bootstrap.sh:67`) print nothing, and `ait ide` gets an empty session name.

There are two reader families, each with its own defect:
1. **YAML-backed readers** (`load_tmux_defaults`; the monitors via the raw
   `tmux:` dict) stringify or pass through null and never treat blank as
   absent.
2. **Line parsers** (`_read_default_session`; the bash awk) don't understand
   YAML scalars. They miss inline comments, YAML-1.1 null spellings and
   quoted-scalar delimiters, and have no indentation rule. The bash output also
   goes through `echo`.

## Design

**Keep the two families; fix each; make them agree where both can read.**
- **YAML-backed readers keep YAML parsing.** `load_tmux_defaults`, and the
  monitors (routed through it), gain only the blank rule: null, empty or
  whitespace-only resolves to `DEFAULT_TMUX_SESSION`. Every other value stays
  `str(yaml_value)` exactly as today.
  - That preserves every non-blank configuration the board, agent-command
    dialog, agentcrew and monitors accept: flow mappings, block scalars and
    typed scalars.
  - The task is about blank values, so it removes no configuration form.
- **Line parsers get YAML-scalar extraction** (option A, chosen by the user):
  `_read_default_session` and its bash twin share one rule. `ait ide` stays
  Python-free. Bash output goes through `printf '%s\n'`.

**Contract** — pinned by the test (step 7):
- **Parity (all five resolver paths equal).** This covers every blank or null
  form and every single-line plain or quoted string scalar that is a direct
  child of a column-0 `tmux:` block. It includes option-like names (`-n`,
  `-neE`), `#` inside values, quoted content kept verbatim, 4-space blocks,
  nested-only keys, comment banners, blank and whitespace-only lines, and LF,
  CRLF and CR-only line endings in any combination with those. On these rows
  every path also equals YAML's reading (the YAML oracle).
- **Legacy YAML-only forms: preserved, not unified.** Flow mappings
  (`tmux: {default_session: x}`), block scalars (`>-`, `|`) and typed scalars
  (`yes` → `True`, `0123` → `83`) keep exactly today's `load_tmux_defaults`
  value, and now reach the monitors through it too. The line parsers could
  never read these forms and still can't: they give `aitasks`, `>-`, `|` or the
  source text, as today.
  - That divergence predates this task and is not about blank values. It is
    recorded under Final Implementation Notes → Upstream defects for Step 8b,
    and deliberately **not** pinned from the line-parser side (pinning a known
    defect would make its later fix look like a regression).
- **Invalid YAML** (e.g. tab indentation): YAML-backed readers fall back to the
  default on a parse error, as today. The two line parsers are pinned to agree
  with each other.

A pre-plan simulation of exactly the algorithms below gave **0 mismatches**:
- 42 parity rows, including the verbatim seed file and the seed converted to
  CRLF;
- 1 twin-only row;
- 5 legacy rows, whose YAML-backed values equal today's. These ran in the
  previous simulation run; the YAML-backed logic is unchanged since.

The Python side was driven through `io.TextIOWrapper`, which handles newlines
the same way as the real `open()`.

**Explicitly outside the contract:**
- **`aitask_setup.sh:4140`**: `setup_tmux_default_session`'s "already
  configured?" probe. It is not a resolver; it never produces a session name,
  only decides whether to offer an optional prompt that defaults to `aitasks`.
  For `# note`, `""` or `null` it wrongly reports "already configured" and skips
  the prompt. The key stays blank, which every resolver now reads as `aitasks`,
  the same value the prompt would write. The misleading message is recorded as
  an upstream defect.
- **`applink/server.py`** keeps its own `DEFAULT_SESSION` and never reads the
  config (t1583 owns that question).
- **`ait ide --session <name>`** (`aitask_ide.sh:16` accepts the value, `:52`
  prints it with `echo "$SESSION_OVERRIDE"`). It has the same `echo` hazard
  (`--session -n` yields an empty session), but the explicit override never
  reads `tmux.default_session`, so it is independent of this blank-config
  defect. It also has no test seam: the script runs the IDE at top level. It is
  **not changed here**. It is listed under Final Implementation Notes → Upstream
  defects, and Step 8b creates a focused follow-up task for the fix and a
  committed test.

## Implementation

### 1. `.aitask-scripts/lib/agent_launch_utils.py` — shared blank rule

Directly after `DEFAULT_TMUX_SESSION = "aitasks"` (line 130) and its comment
block:

```python
def _normalize_default_session(value: object) -> str:
    """Map a ``tmux.default_session`` value to the session name it selects.

    ``None`` (YAML null — blank, ``~``, ``null``, comment-only), ``""`` and
    whitespace-only mean "not configured" → :data:`DEFAULT_TMUX_SESSION`.
    Anything else is ``str(value)`` unchanged, so every non-blank form the
    YAML-backed readers accepted before keeps resolving the same way. Shared by
    :func:`load_tmux_defaults` and :func:`_read_default_session`.
    """
    if value is None:
        return DEFAULT_TMUX_SESSION
    text = str(value)
    return text if text.strip() else DEFAULT_TMUX_SESSION
```

### 2. Same file — line-scalar helper

Place this just above `_read_default_session` (line 709). `re` is already
imported at line 17.

```python
_YAML_NULLS = ("", "~", "null", "Null", "NULL")


def _yaml_line_scalar(raw: str) -> str | None:
    """Read the scalar in the text after ``key:`` on one YAML line.

    Quoted: the content between the opening quote and the next matching quote,
    verbatim (anything after the closing quote, e.g. a comment, is dropped).
    Plain: cut at the first ``#`` that begins the text or follows whitespace —
    YAML's inline-comment rule, so ``my#sess`` survives — then trim; YAML-1.1
    null spellings (and empty) return ``None``. Flow mappings, block and typed
    scalars are not interpreted. The bash twin is the awk in
    ``tmux_bootstrap.sh::_tmux_bootstrap_resolve_session``;
    ``tests/test_tmux_default_session_resolvers.py`` pins them together.
    """
    s = raw.strip()
    if s[:1] in ('"', "'"):
        end = s.find(s[0], 1)
        return s[1:end] if end != -1 else s[1:]
    value = re.split(r"(?:^|\s)#", s, maxsplit=1)[0].rstrip()
    return None if value in _YAML_NULLS else value
```

### 3. Same file — rewrite `_read_default_session()` (lines 709-749)

- The nested `_unquote` goes away.
- **Direct-child rule:** the first non-comment, space-indented content line of
  the `tmux:` block fixes the child indent. Only a `default_session:` at that
  exact indent counts.
- Whitespace-only and tab-indented lines are skipped, mirroring the awk twin.

```python
    in_tmux_block = False
    child_indent: int | None = None
    try:
        with open(cfg, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.rstrip("\n")
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if line[:1] not in (" ", "\t"):
                    in_tmux_block = line.startswith("tmux:")
                    child_indent = None
                    continue
                if not in_tmux_block or line[:1] == "\t":
                    continue
                stripped = line.lstrip(" ")
                indent = len(line) - len(stripped)
                if child_indent is None:
                    child_indent = indent
                if indent == child_indent and stripped.startswith("default_session:"):
                    return _normalize_default_session(
                        _yaml_line_scalar(stripped[len("default_session:"):])
                    )
    except OSError:
        pass
    return DEFAULT_TMUX_SESSION
```

Docstring: state the contract (direct child, single-line scalar, null/blank →
default) and name the awk twin.

### 4. Same file — `load_tmux_defaults()` keeps YAML (lines 1890-1928)

- The `defaults` literal uses `DEFAULT_TMUX_SESSION` instead of `"aitasks"`.
- Replace lines 1913-1914 with
  `defaults["default_session"] = _normalize_default_session(tmux.get("default_session"))`.
  YAML parsing, the `isinstance(tmux, dict)` guard and the `except Exception`
  fallback are untouched.
- Docstring: a blank, null or comment-only `default_session` falls back to the
  default like an absent one; any other value is `str()` of what YAML read.

### 5. Monitors — `monitor_app.py:3894`, `minimonitor_app.py:5302`

In both `main()`s, replace
`configured_session = tmux_config.get("default_session", "aitasks")` with
`configured_session = load_tmux_defaults(project_root)["default_session"]`.
Both monitors were YAML-backed before and stay YAML-backed, so every legacy form
still reaches them. The only changes are the blank rule and `str()` on a typed
value, which used to flow through as a raw `bool`/`int`. The precedence logic
after it (CLI > detected > configured, and the monitor's mismatch check) is
unchanged.

Imports: add `load_tmux_defaults` to the one-line
`from agent_launch_utils import …` at `monitor_app.py:79`, and to the
parenthesized block at `minimonitor_app.py:90`. `tmux_config` stays for the other
keys.

### 6. Bash — `.aitask-scripts/lib/tmux_bootstrap.sh:44-67`

Replace `_tmux_bootstrap_resolve_session`'s awk with the twin. It uses POSIX
features only: 2-arg `match` + `RLENGTH`, `substr`, `index`, `sub`
(`aidocs/framework/sed_macos_issues.md`). The single quote comes in via
`-v SQ="'"`. The block ends at a non-space, non-tab, non-`#` column-0 line, so
tab-indented lines are ignored exactly as in Python.

**Line endings.** Python's text-mode `open()` applies universal newlines: CRLF
and CR-only files arrive as LF lines. Without the same treatment the awk sees a
blank CRLF line as a lone `\r` record, which matches the block terminator and
ends the `tmux:` block. It sees a whitespace-plus-`\r` line as indented content
that can fix the wrong child indent, and a CR-only file as a single record.
- So the file is fed through `tr '\r' '\n'` (POSIX `tr` escapes, BSD-safe).
  CRLF becomes an extra blank line and CR becomes LF.
- An explicit `/^[ \t]*$/ { next }` rule runs **before** the block-boundary
  checks, so blank and whitespace-only records never start, end or indent a
  block.
- Failure behaviour is unchanged: an unreadable file still fails the command
  substitution exactly as the direct `awk … "$cfg"` did.

The resolver prints with `printf`:

```bash
name=$(tr '\r' '\n' < "$cfg" | awk -v SQ="'" '
    /^[ \t]*$/ { next }
    /^tmux:/ { intmux=1; ci=0; next }
    /^[^ \t#]/ { intmux=0; next }
    intmux && /^ +[^ #]/ {
        match($0, /^ +/); ind = RLENGTH
        if (ci == 0) ci = ind
        if (ind != ci) next
        v = substr($0, ind + 1)
        if (substr(v, 1, 16) != "default_session:") next
        v = substr(v, 17)
        sub(/^[ \t]+/, "", v)
        q = substr(v, 1, 1)
        if (q == "\"" || q == SQ) {
            v = substr(v, 2); i = index(v, q)
            if (i > 0) v = substr(v, 1, i - 1)
        } else {
            sub(/^#.*/, "", v); sub(/[ \t]#.*/, "", v); sub(/[[:space:]]+$/, "", v)
            if (v == "~" || v == "null" || v == "Null" || v == "NULL") v = ""
        }
        print v; exit
    }
')
if [[ -n "${name//[[:space:]]/}" ]]; then
    printf '%s\n' "$name"
    return
fi
```

- The whitespace-aware blank test is bash-3.2-safe; it's needed because quoted
  content is now verbatim.
- The fallback `echo "aitasks"` becomes `printf '%s\n' aitasks` for
  consistency (a literal, so it's safe either way).
- Update the header comment to state the rule, name the Python twin
  (`_yaml_line_scalar` / `_read_default_session`), and say why output uses
  `printf`.

### 7. New test — `tests/test_tmux_default_session_resolvers.py`

This is a unittest module. The `sys.path` setup and the `main()`-driving harness
follow `tests/test_minimonitor_session_bar_config.py` and
`tests/test_monitor_pane_marker_wiring.py`. Each fixture is written as bytes
(so the CRLF and CR-only rows survive) under a `tempfile.TemporaryDirectory` at
`<root>/aitasks/metadata/project_config.yaml`.

**Five resolver paths** (the `resolve(path, root)` helpers):
1. `load_tmux_defaults(root)["default_session"]`
2. `_read_default_session(root)`
3. the bash resolver: `subprocess.run(["bash", "-c", 'source "$1"; _tmux_bootstrap_resolve_session "$2"', "_", <repo>/.aitask-scripts/lib/tmux_bootstrap.sh, str(root)], capture_output=True, text=True, check=True)`, with only the final newline removed (so `  x  ` and `-n` are compared exactly)
4. `minimonitor_app.main()` — the `session` kwarg it hands the App
5. `monitor_app.main()` — the same

Paths 4-5 run the real `main()` with only its module-level seams patched:
- `load_tmux_defaults` → `lambda _root: agent_launch_utils.load_tmux_defaults(fixture_root)`, so the real reader parses the fixture (`main()` derives `project_root` from `__file__`, so the path is redirected, not the parsing);
- `load_project_tmux_config` → the real loader on `fixture_root`;
- `load_monitor_config` → `lambda _root: {}`;
- `_detect_tmux_session` → `lambda: None`;
- `sys.argv` → `["app.py"]`;
- the App class → a recorder with a no-op `run()`.

**`ResolverParityTests`**: 42 rows, including the verbatim seed file and its CRLF conversion; all five paths
must equal the expected value (`subTest(fixture=…, resolver=…)`).
- **Blank / null → default:** `` (seed shape), ` # note`, ` ""`, ` ''`,
  ` "   "`, ` '   '`, `   `, ` null`, ` Null`, ` NULL`, ` ~`, ` null # c`.
- **Strings, verbatim:**
  - ` nULL` → `nULL`, ` "null"` → `null`, ` '~'` → `~`;
  - ` mysess` → `mysess`, ` mysess  # team` → `mysess`;
  - ` my#sess` → `my#sess`, ` "my#sess"` → `my#sess`;
  - ` "x" # c` → `x`, ` "  x  "` → `  x  `.
- **Option-like:** ` -n` → `-n`, ` "-n"` → `-n`, ` -e` → `-e`,
  ` -neE` → `-neE`.
- **Structure:**
  - 4-space block → `four`;
  - nested-only `syncer: default_session:` → default;
  - nested + direct → `direct`;
  - comment banner first → `bannered`;
  - whitespace-only line first → `wsline`;
  - blank line first → `blankline`.
- **Line endings** (fixtures written as bytes):
  - CRLF file → `crlf`;
  - CRLF with a blank line between `tmux:` and the key → `crlfblank` (the
    combined case: a lone-`\r` record must not end the block);
  - CRLF with a whitespace-only line first → `crlfws`;
  - CRLF with a comment banner then a blank line → `crlfmix`;
  - CR-only file → `cronly`;
  - CR-only with a blank line first → `crblank`;
  - CRLF with a blank value → default;
  - **the shipped seed converted to CRLF** → default.
- **More structure:**
  - key absent → default;
  - `default_session` under a later top-level key → default;
  - no config file → default.
- **The shipped seed, copied verbatim** from `seed/project_config.yaml` →
  default. If someone gives the seed a value, this fails loudly instead of the
  pin going quietly stale.

**YAML oracle** (`test_parity_rows_match_yaml`): for every parity row with a
file, `yaml.safe_load` must give `None` or a `str`, and
`_normalize_default_session` of it must equal the expected value. That proves
the parity rows encode YAML's reading rather than whatever the parsers were
tuned to.

**`LegacyYamlFormsPreservedTests`** (compatibility): for each legacy row, paths
1, 4 and 5 must equal the value pre-fix `load_tmux_defaults` returned, pinned as
literals:
- `tmux: {default_session: flowsess}` → `flowsess`;
- `>-` block → `blocksess`;
- `|` block → `blocksess\n`;
- ` yes` → `True`;
- ` 0123` → `83`.

Line-parser paths are deliberately not asserted here (see the Contract). A
companion assertion requires each legacy row to be a shape the line parsers
cannot read: YAML yields a non-`str` value, or the key is not on a
`default_session:` line with a single-line value. So a row can't be moved here
to hide a parity failure.

**`LineParserTwinTests`**: on the tab-indented block (invalid YAML), paths 2 and
3 must agree (`tabbed`).

**`MonitorMismatchCheckTests`** (`monitor_app.main()`): on the blank-seed and
` # note` rows, with `_detect_tmux_session` returning:
- `"other"` → `expected_session == DEFAULT_TMUX_SESSION`;
- `DEFAULT_TMUX_SESSION` → `expected_session is None`.

**Negative control** (`test_harness_feeds_the_fixture_to_main`): the ` mysess`
row reaches each App as `mysess`. Otherwise a harness ignoring the fixture would
pass every blank row vacuously, because the default is also the answer.

### 8. Red proof, then fix

Write the test file **first** and run it against unchanged code. Expected
failures:
- every disagreeing cell in the Context table, including the bash `-n` / `-e`
  rows (empty output);
- the 4-space, nested and whitespace-line rows;
- the CRLF-with-blank-line, CRLF-comment-then-blank and CR-only rows, on the
  bash path only. A pre-plan check of today's awk gave empty output (so the
  `aitasks` fallback) for CRLF + blank line and for CR-only: it ends the block on
  a lone `\r` record, or reads a CR-only file as one record. Python's `open()`
  already handles both. The CRLF + whitespace-line row **passes today**, because
  the current awk hard-codes a two-space indent and has no child-indent rule to
  mislead. It is a regression guard for the new rule, not a red row;
- both `main()`s on every blank row;
- the mismatch cases.

The legacy rows should **pass** before the fix as well as after. That is the
compatibility proof. Then apply steps 1-6 and re-run green. No stash and no
restore.

## Verification

```bash
python3 tests/test_tmux_default_session_resolvers.py          # red before steps 1-6 (legacy rows green throughout), green after
python3 -m unittest tests.test_git_tui_config tests.test_minimonitor_own_header_session \
    tests.test_session_key_collision tests.test_minimonitor_session_bar_config \
    tests.test_monitor_pane_marker_wiring tests.test_agent_command_dialog_default_session \
    tests.test_project_groups
shellcheck .aitask-scripts/lib/tmux_bootstrap.sh
set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -n 5   # read the last-line verdict
```

## Step 9 reference

Current-branch mode (profile `fast`): no branch or worktree to merge. After
review and commit, Step 9 runs build verification and archival
(`./.aitask-scripts/aitask_archive.sh 1800`), then `./ait git push`.

## Risk

### Code-health risk: low
- The bash resolver runs on every `ait ide` launch. An awk mistake would misname the session for every user, including those with an ordinary configured value. The rewrite is POSIX-only, was simulated with 0 mismatches, is exercised through the real `bash -c 'source …'` path on every parity row, and `shellcheck` runs · severity: low · → mitigation: none (covered by the parity matrix)
- The monitor's mismatch banner can now appear on a blank-configured project run inside a tmux session not named `aitasks`. Before, `configured_session` was `None`, so no mismatch was ever computed. This is intended (it matches an absent key) and pinned by `MonitorMismatchCheckTests` · severity: low · → mitigation: none (intended behavior)

### Goal-achievement risk: low
- The two line parsers are separate implementations and could drift on a shape the matrix does not cover. The contract is stated as a subset, the parity matrix pins them against each other and against YAML, and legacy YAML-only forms are pinned from the YAML-backed side so compatibility cannot silently break · severity: low · → mitigation: none (scope stated; oracle + legacy tests)

## Implementation Progress (2026-09-14)

- [x] Steps 1-6 applied; step 7 test written first; step 8 red → green.
  - Red: `tests/test_tmux_default_session_resolvers.py` exited 1 on unchanged
    code (the predicted `'None'`/`None`, `# note`/`null`/`~`, bash `-n` → `''`,
    mismatch and tab-twin failures).
  - Green after the fix: 9 tests OK.
  - The related modules (136 tests) pass, and `shellcheck` is clean.
- **Deviation (step 6) — awk reads to EOF behind a `done` flag instead of
  `print v; exit`.** The plan's `tr … | awk` pipe made the early `exit` a SIGPIPE
  source. Measured with extracted functions on a 3.3 MB config:
  - the `exit` mutant makes `tr` exit 141 on 5/5 runs, while the fix gives `tr=0`;
  - a **direct** call under `set -euo pipefail` aborts (rc=141) on the mutant
    and survives on the fix;
  - today's callers (`$(…)` in `aitask_ide.sh` and `tmux_bootstrap.sh`) survive
    both, because errexit is not inherited into command substitution.

  So this is defence for direct callers, not a fix for a live abort, and the
  code comment says exactly that. (An earlier control that seemed to prove
  a live abort was invalid: it sourced a copied file whose relative
  `tmux_exec.sh` source did not exist.)
- **Deviation (step 7) — the YAML oracle uses a test-local blank rule**
  (`_session_from_yaml`), not `_normalize_default_session`. That keeps the ground
  truth independent of the code under test, and the red run collectable.
- **Deviation (step 7)** — 43 parity rows: the 42 simulated plus "no config
  file". The monitor harness patches `load_tmux_defaults` with `create=True`, so
  the red run could drive the pre-fix `main()`.
- **Observation (red proof)** — the monitors' typed legacy rows (`yes`,
  `0123`) failed pre-fix: `True != 'True'`, `83 != '83'`. The monitors passed
  the raw `bool`/`int` through. The "legacy rows pass before and after"
  compatibility proof therefore holds for `load_tmux_defaults` and the
  monitors' flow/block rows, not the monitors' typed rows. That is the latent
  defect step 5 names.
- **Environment** — `main` advanced mid-session (t1784 `68158b17f` touched
  `tmux_bootstrap.sh`). The file's diff was verified to contain only this task's
  hunks. `tests/test_session_hook_install.sh` is modified by a concurrent session
  and is excluded from this task's commit.

## Final Implementation Notes
- **Actual work done:** Implemented as planned (code commit `d146a440c`).
  - `_normalize_default_session` holds the one blank rule.
  - `_yaml_line_scalar` implements YAML-1.1 nulls, inline comments and quoted
    scalars.
  - `_read_default_session` was rewritten with the direct-child indent rule and
    skips whitespace-only and tab-indented lines.
  - `load_tmux_defaults` keeps YAML and gains only the blank rule. Both
    monitors' `main()` now read through `load_tmux_defaults`.
  - The bash `_tmux_bootstrap_resolve_session` twin uses `tr '\r' '\n'`
    universal newlines, POSIX awk and `printf` output.
  - The new `tests/test_tmux_default_session_resolvers.py` has 9 tests: 43
    parity rows across 5 resolver paths, a YAML oracle, 5 legacy YAML-only
    rows, a tab-indent twin row, the monitor mismatch check and a harness
    negative control.
  - Verification: the new test went red (rc=1) on unchanged code and green
    after the fix. The related modules pass (136 tests), `shellcheck` is
    clean, and `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
- **Deviations from plan:** See "Implementation Progress" above.
  - The awk reads to EOF behind a `done` flag instead of `print v; exit`. It
    guards direct callers against a measured SIGPIPE abort (rc=141); the
    current `$(…)` callers survive either way.
  - The YAML oracle uses a test-local blank rule.
  - There are 43 parity rows, not 42 (adds "no config file").
  - The monitor harness patches with `create=True`, so the red run could drive
    the pre-fix `main()`.
- **Issues encountered:**
  - The plan went through six review rounds, each closing one YAML/shell
    corner of the parity claim: quoted whitespace, inline comments, null
    spellings, `echo -n`, a compatibility break (routing YAML readers through
    the line parser), and CRLF blank lines.
  - The first SIGPIPE mutant control was invalid: a copied file's relative
    `tmux_exec.sh` source was missing. It was redone with extracted functions,
    and the resulting finding corrected an over-strong claim in the code
    comment.
  - `main` advanced mid-session: t1784 `68158b17f` touched
    `tmux_bootstrap.sh`. The diff was verified to contain only this task's
    hunks before the path-scoped commit.
  - A concurrent session's dirty and untracked files (board trail view, docs,
    `tests/test_session_hook_install.sh`) were excluded.
  - The monitors' typed legacy rows failed pre-fix, because a raw
    `bool`/`int` was passed as the session.
- **Key decisions:**
  - Twin line parsers, not a single YAML authority bridged into bash (user's
    choice, option A). `ait ide` stays Python-free.
  - The YAML-backed readers keep YAML, so no configuration form that existing
    callers accept is removed.
  - The `ait ide --session` override is kept out of scope (it never reads
    `tmux.default_session`).
  - Legacy YAML-only rows are pinned from the YAML-backed side only. Pinning
    the line parsers' known divergence would make its fix look like a
    regression.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_ide.sh:52 — echo "$SESSION_OVERRIDE" swallows an option-like --session value (e.g. --session -n), so ait ide resolves an empty session name; needs printf plus a test seam (the script runs the IDE at top level)`
  - `.aitask-scripts/aitask_setup.sh:4140 — setup_tmux_default_session's "already configured?" probe (grep | sed) treats a null, comment-only or quoted-empty default_session (# note, "", null, ~) as configured, prints e.g. "already configured: # note" and skips the prompt`
  - `.aitask-scripts/lib/agent_launch_utils.py:747 / .aitask-scripts/lib/tmux_bootstrap.sh:68 — the line parsers cannot read YAML-only default_session shapes that load_tmux_defaults accepts: a flow mapping resolves to aitasks, a block scalar (>- or |) to its literal indicator (ait ide would name its session '>-'), a typed scalar (yes, 0123) to its source text instead of True/83`
