---
Task: t1828_reject_illegal_configured_default_session_names.md
Base branch: main
Output branch: main
---

# t1828 — Reject a configured `tmux.default_session` that tmux cannot address

## Context

t1825 (`50b865dda`) added `_tmux_bootstrap_session_name_ok` and wired it into the
two paths where a user **types** a session name: `ait ide --session` (dies) and
`ait setup`'s prompt (warns, falls back to `aitasks`). tmux reads `.` and `:` as
target separators, so a session so named can be created but never addressed.

The **configured** path was left uncovered. With
`tmux:\n  default_session: a.b\n` every one of the four readers accepts it:

| reader | today | after |
|---|---|---|
| `_tmux_bootstrap_default_session_raw` | `a.b`, rc 0 | rc 2 + sentinel |
| `read_default_session_status` | `("a.b", None)` | `("aitasks", "illegal_tmux_name")` |
| `load_tmux_defaults` (board, monitors, agentcrew) | `"a.b"` | `"aitasks"` |
| `spawn_session_detached` | `tmux new-session -s a.b` | refuses / falls back |

So `spawn_session_detached` and `agentcrew_runner` hand tmux a name it cannot
target. **Decided approach: a new `illegal_tmux_name` problem shape**, applied in
both line readers *and* in `load_tmux_defaults` — the last is what stops the
readers from disagreeing, which is the defect's real shape.

### ⚠️ Pull first

`50b865dda` is on `origin/main` but **not** in this checkout — local `main` is
9 behind / 2 ahead. `_tmux_bootstrap_session_name_ok` does not exist on disk yet.
The 2 local commits touch only `tests/test_minimonitor_concern_smoke.py` and
`website/content/docs/tuis/frozenagent/*`, so there is no overlap. Every line
number below is **`origin/main`**. The Remote Drift Check at the checkpoint will
prompt the pull; it must be taken, and **Step 0 below re-verifies the result
before any source is edited**.

## Implementation

### 0. Post-pull re-inspection (blocking — before any edit)

Every helper location, resolver contract and fixture measurement in this plan was
read off `origin/main` while the working tree was 9 behind and 2 ahead. A merge
can move them, and the failure mode is silent: the plan still looks right and the
edited tests still pass. So after the drift check's pull, and **before changing
any source file**, confirm the tree the plan assumes:

1. `git merge-base --is-ancestor 50b865dda HEAD` — t1825's code commit is
   actually present. If not, stop; nothing below applies.
2. `grep -n _tmux_bootstrap_session_name_ok .aitask-scripts/lib/tmux_bootstrap.sh
   .aitask-scripts/aitask_ide.sh .aitask-scripts/aitask_setup.sh` — the predicate
   exists and both t1825 call sites survived the merge.
3. Re-locate the five reader/consumer paths this plan edits, since the line
   numbers cited below are pre-merge: `_tmux_bootstrap_default_session_raw` and
   `spawn_session_detached`'s direct `_scan` call in `tmux_bootstrap.sh`;
   `read_default_session_status`, `DEFAULT_SESSION_PROBLEM_SHAPES` and
   `load_tmux_defaults` in `agent_launch_utils.py`; the notice branch in
   `tui_switcher.py`. Confirm each still has the shape the plan describes —
   in particular that `spawn_session_detached` still reads the scan **directly**,
   which is the whole reason for `_scan_checked`.
4. Re-run the two floor measurements against the merged tree and check them
   against this plan's table (256 newly-illegal corpus values; `cut_comment` 64 →
   42; mutation floors 104 / 43 / 39). A different number means the merge changed
   a fixture and the test edits below must be re-derived, not copied.
5. Only then run the **pre-fix control** (Verification step 8) and start editing.

### 1. `.aitask-scripts/lib/tmux_bootstrap.sh`

Keep the awk scanner's contract ("what YAML reads") intact and add the usability
layer in bash, so `_tmux_bootstrap_session_name_ok` (L393) stays the single bash
definition of the rule. Insert immediately after it:

```bash
# _tmux_bootstrap_default_session_scan_checked <project_root>
#
# _tmux_bootstrap_default_session_scan with one further rejection on top: a
# readable value tmux cannot address becomes `bad<TAB>illegal_tmux_name`. Kept
# out of the awk so the scanner keeps reporting only what YAML reads; this is
# the usability layer, and both scan consumers share it.
_tmux_bootstrap_default_session_scan_checked() {
    local scan
    scan=$(_tmux_bootstrap_default_session_scan "$1")
    case "$scan" in
        ok$'\t'?*)
            _tmux_bootstrap_session_name_ok "${scan#ok$'\t'}" \
                || scan=$'bad\tillegal_tmux_name'
            ;;
    esac
    printf '%s\n' "$scan"
}
```

Then repoint **both** scan consumers at it — this is the whole point, since
`spawn_session_detached` reads the scan directly and would otherwise keep
creating the session:

- `_tmux_bootstrap_default_session_raw` (L358)
- `spawn_session_detached` (L623)

`_scan_checked` must be defined after `_tmux_bootstrap_session_name_ok`; bash
resolves calls at runtime, but keep them adjacent for readability.

`_tmux_bootstrap_report_unreadable` (L337) needs a third wording arm — neither
existing sentence is true of `a.b`. Add before the file-shape `case`:

```bash
    if [[ "$2" == illegal_tmux_name ]]; then
        printf 'Warning: tmux.default_session in %s is a name tmux cannot address (%s: `.` and `:` are tmux target separators); write a name without them\n' "$1" "$2" >&2
        return 0
    fi
```

Also extend the scan's header contract block (L147-152) and the module contract
header (L45-81) with the new shape and the "readable but unusable" distinction.

### 2. `.aitask-scripts/lib/agent_launch_utils.py`

Add the Python twin of the predicate next to `_normalize_default_session` (L134):

```python
def _tmux_session_name_ok(name: str) -> bool:
    """False when tmux cannot address ``name``.

    tmux reads ``.`` and ``:`` as target separators, so such a session can be
    created but never addressed. Twin of
    ``tmux_bootstrap.sh::_tmux_bootstrap_session_name_ok``.
    """
    return "." not in name and ":" not in name
```

- `DEFAULT_SESSION_PROBLEM_SHAPES` (L735): add `"illegal_tmux_name"`. It is
  **not** a `DEFAULT_SESSION_FILE_SHAPES` member — it is a value shape. Document
  in the tuple's comment that it is the one shape meaning *read faithfully but
  unusable*, so the "cannot be read" framing no longer covers the whole tuple.
- `read_default_session_status` (L900), replacing the final `return` (the
  `non_printable` check above it stays first):

  ```python
      session = _normalize_default_session(value)
      if not _tmux_session_name_ok(session):
          return DEFAULT_TMUX_SESSION, "illegal_tmux_name"
      return session, None
  ```

  Update the docstring: precedence is `encoding` → line shapes →
  `non_printable` → `illegal_tmux_name`, and the last is the only shape where
  YAML read the value correctly.
- `load_tmux_defaults` (L2168) — the divergence this task closes:

  ```python
      session = _normalize_default_session(tmux.get("default_session"))
      defaults["default_session"] = (
          session if _tmux_session_name_ok(session) else DEFAULT_TMUX_SESSION
      )
  ```

  and say so in its docstring.

Do **not** fold the check into `_normalize_default_session`: `read_default_session_status`
must still tell "illegal" apart from "blank" to report a shape.

### 3. `.aitask-scripts/lib/tui_switcher.py` (L697-702)

Add a third wording branch — the only place a shape reaches a user in a TUI:

```python
            if problem == "illegal_tmux_name":
                what = ("tmux.default_session holds `.` or `:`, which tmux reads "
                        "as target separators")
            elif problem in DEFAULT_SESSION_FILE_SHAPES:
```

`agent_restore.py` passes the shape through verbatim — no change needed.

### 4. `seed/project_config.yaml` (L437-439)

The `default_session` comment documents the YAML-form rule; add the name rule.
**Do not promise a warning** — that would be false for most consumers: only
`ait ide`, `ait setup`, the detached bootstrap and the TUI switcher's
create-session notice report a shape. `load_tmux_defaults` returns a bare dict,
so the board, both monitors, agentcrew, `agent_command_screen` and even the
switcher's own session fallback (`tui_switcher.py:1498`) substitute `aitasks`
**silently**. State the fallback, and scope the notice honestly:

> The name may not contain `.` or `:` — tmux reads both as target separators, so
> such a session can be created but never addressed. A value holding either is
> ignored and `aitasks` is used instead. `ait ide`, `ait setup` and the TUI
> switcher say so; the other TUIs fall back without a message.

(The `surface_illegal_name_in_yaml_readers` mitigation is what would let that
last sentence be dropped later; until it lands, the comment must not claim it.)

## Tests

### `tests/test_tmux_default_session_resolvers.py`

**Two existing `PARITY_ROWS` rows must move** — measured, not guessed:
`'colon without a following space'` (`a:b`) and `'space before a colon'`
(`a :b`). They currently assert all five resolvers return the value; after the
change all five return `aitasks`. Leaving them fails `ResolverParityTests` **and**
`ReadableRowsReportNoProblemTests`.

New table beside `UNREADABLE_ROWS`, seeded with those two:

```python
# (name, bytes, the value YAML reads — which every reader now refuses)
ILLEGAL_NAME_ROWS = [
    ("colon without a following space", _row(" a:b"), "a:b"),
    ("space before a colon", _row(" a :b"), "a :b"),
    ("dotted", _row(" a.b"), "a.b"),
    ("leading dot", _row(" .lead"), ".lead"),
    ("quoted dotted", _row(" 'x.y'"), "x.y"),
    ("trailing colon", _row(" 'trail:'"), "trail:"),
]
```

`a.b` cannot go in `UNREADABLE_ROWS`: `test_every_row_is_a_real_divergence`
asserts YAML disagrees with the naive reading, and here YAML agrees. Hence a
separate class, `IllegalTmuxNameTests`:

- `test_every_resolver_falls_back_to_the_default` — all five `RESOLVERS`, the
  YAML-backed ones included. This is the assertion that fails today.
- `test_both_line_readers_announce_the_shape` — `read_default_session_status`
  returns `(D, "illegal_tmux_name")` and `_sentinel_shape(_bash_raw(root).stderr)`
  matches, with rc 2.
- `test_rows_are_read_faithfully_by_yaml` — the **oracle control** the house
  style requires: `_yaml_value(data)` equals the third column, proving each row
  is a *usability* refusal, not a readability one.
- `test_an_unreadable_shape_wins` — precedence: a block scalar carrying a dotted
  name reports `block_scalar`, and `# \x7f` beside a dotted value reports
  `non_printable`, not `illegal_tmux_name`.
- `test_legal_punctuation_is_unaffected` — control over `my_proj-2`, `-n`,
  `a b`, `team#1`: still read, still no shape.

**`GeneratedCorpusInvariantTests` will fail as written** — measured against the
seeded corpus (2000 values, seed 1811): 256 values become `illegal_tmux_name`,
and the floors move

| counter | before | after | floor 50 |
|---|---|---|---|
| kept_hash | 108 | 80 | ok |
| cut_comment | 64 | **42** | **fails** |
| fell_back | 990 | 1246 | ok |
| agreed | 937 | 681 | ok |

Fix by computing `kept_hash` / `cut_comment` from the **PyYAML oracle**
(`_yaml_value(_row(value))`) instead of from the post-refusal session. Those two
floors exist to prove the *generator* still emits hash-bearing and
comment-cutting values; sourcing them from the oracle states exactly that and is
immune to any future fallback rule. They then hold at 108 / 64. Add a fifth
counter `illegal` with the same floor of 50 (measured 256). In the
`p_shape is not None` branch, when the shape is `illegal_tmux_name`, also assert
`_yaml_backed(root) == D` — the divergence closed.

`GeneratedWholeFileMutationTests` needs **no change**: measured floors after the
change are `encoding` 104, `non_printable` 43, `readable` 39, all ≥ 30.

Update the module docstring's contract list.

### `tests/test_ide_session_override.sh`

New section after 2b (`make_project`/`isolated` already exist):
`default_session: a.b` → `_tmux_bootstrap_resolve_session` prints `aitasks`,
stderr carries `DEFAULT_SESSION_UNREADABLE:illegal_tmux_name:` and the "cannot
address" wording; driven through `ait ide`, the nesting refusal names `aitasks`.
Plus a `--create-only` row: exit 44, `BOOTSTRAP_FAILED:default_session_unreadable:illegal_tmux_name`,
and an **empty stub log** proving no tmux call.

### `tests/test_setup_tmux_default_session.sh`

One row in the unreadable-probe loop (the `label|body|shape` spec):
`'dotted configured name (t1828)|tmux:\n  default_session: a.b\n|illegal_tmux_name'`.
The existing "configured value is left alone" probes (`mysess`, `team#1`) are
unaffected — verified.

### `tests/test_tui_switcher_default_session_notify.py`

`test_an_illegal_name_is_worded_as_a_tmux_target_problem` — asserts the new
sentence and `assertNotIn("single-line", …)` / `assertNotIn("not valid YAML", …)`.
`test_a_line_shape_keeps_the_value_wording` (`block_scalar`) must still pass.

### Post-phase (risk mitigations)

1. `[remeasure_corpus_floors]` With the source change and the test edits in
   place, re-run the floor measurement against the **real** code — not the
   projection in this plan — for all five `GeneratedCorpusInvariantTests`
   counters (`kept_hash`, `cut_comment`, `fell_back`, `agreed`, `illegal`) and
   the three `GeneratedWholeFileMutationTests` counters (`encoding`,
   `non_printable`, `readable`). Record each observed number in a short comment
   beside its `assertGreaterEqual` floor, so a later failure is legible as a
   degenerate generator rather than a moved baseline. If any measured value
   disagrees with this plan's table, treat the plan as wrong and reconcile
   before continuing.

## Verification

1. `bash tests/test_ide_session_override.sh`
2. `bash tests/test_setup_tmux_default_session.sh`
3. `python3 tests/test_tmux_default_session_resolvers.py`
4. `python3 tests/test_tui_switcher_default_session_notify.py`
5. `bash tests/run_all_python_tests.sh` — **read only the last line**; use
   `set -o pipefail` if piping.
6. `shellcheck .aitask-scripts/lib/tmux_bootstrap.sh .aitask-scripts/aitask_setup.sh .aitask-scripts/aitask_ide.sh`
7. Live repo, no false positive — this repo's `tmux:` block has no
   `default_session` key, so both twins must still answer `aitasks` with no shape:
   `bash -c 'source .aitask-scripts/lib/tmux_bootstrap.sh; _tmux_bootstrap_default_session_raw .'`
8. **Pre-fix control** — before touching the source, add `ILLEGAL_NAME_ROWS` +
   `IllegalTmuxNameTests` and watch `test_every_resolver_falls_back_to_the_default`
   fail on all five resolvers. A test that never failed is not evidence.
9. **Negative control** — with the fix in, temporarily drop the `spawn_session_detached`
   call-site change and confirm the `--create-only` row in
   `test_ide_session_override.sh` goes red. This is the call site a `_raw`-only
   fix would silently miss.

## Risk

### Code-health risk: medium
- `load_tmux_defaults` now refuses a name it has always returned, and it feeds
  actual session **creation** (`agentcrew_runner.py:437`) plus window targeting in
  the board and both monitors. A project deliberately running a dotted session
  moves to `aitasks`, which is explicitly *not* unique across repos. · severity: medium (residual — the fallback stays silent for these consumers until `surface_illegal_name_in_yaml_readers` lands) · → mitigation: t1835
- `spawn_session_detached --create-only` gains a new exit-44 refusal on the
  frozen-agent restore path (`agent_restore.py`), for configs that restored
  before. · severity: medium (residual — pinned by a stub-tmux test row this task adds; live confirmation deferred to the mitigation) · → mitigation: t1836
- The `GeneratedCorpusInvariantTests` floor rework re-sources two counters from
  the PyYAML oracle. Those floors exist to catch generator degeneration; a
  careless edit (e.g. just lowering 50) would quietly weaken the suite. · severity: low (residual — addressed by inline post-phase remeasure_corpus_floors) · → mitigation: inline post-phase remeasure_corpus_floors
- A third spelling of the `.`/`:` rule (bash predicate + Python predicate) — twin
  drift risk. · severity: low · → mitigation: none (the resolvers test pins bash↔Python parity over the 2000-value corpus, and `ILLEGAL_NAME_ROWS` asserts both twins per row)

### Goal-achievement risk: low
- The whole plan is written against `origin/main` while the tree is 9 behind / 2
  ahead; the pull is mandatory, and a merge could move the helper locations and
  fixture measurements the plan depends on without any test going red. · severity: low (residual — Step 0 re-verifies the merged tree, including re-measuring the floors, before any source edit) · → mitigation: none (covered in-plan by Implementation Step 0, blocking)
- The settings-TUI write path stays unvalidated by user decision: an illegal name
  can still be *written*, only neutralized on read. · severity: low · → mitigation: none (accepted by user decision; follow-up filed at Step 8d)

### Planned mitigations
- timing: post-phase | name: remeasure_corpus_floors | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the corpus-floor rework could weaken a generator-degeneration guard | desc: re-measure all eight generated-test floors against the real code and record the observed numbers beside each assertion
- timing: after | name: surface_illegal_name_in_yaml_readers | type: enhancement | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: load_tmux_defaults falls back silently for board / monitors / agentcrew | desc: give load_tmux_defaults a status channel so its consumers can notify on a default_session fallback the way the TUI switcher already does | created: t1835
- timing: after | name: verify_dotted_session_refusal_live | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: the new exit-44 refusal on the frozen-agent restore path | desc: with a real tmux, confirm ait ide, a switcher bootstrap and a frozen-agent restore all warn and use aitasks for a dotted config, that no a.b session is created, and that --create-only exits 44 | created: t1836

## Step 9 (Post-Implementation)

Follow task-workflow Step 9 for cleanup, archival and merge. Work is on the
current branch (`fast` profile), output branch `main`.

**Follow-up to file at Step 8d:** `ait settings` exposes `tmux.default_session`
as an unvalidated free-text field (`settings/settings_app.py:277`,
`TMUX_CONFIG_SCHEMA`, `type: string`) — a third way to write a name tmux cannot
address. Reader-side fallback neutralizes it, but the TUI should refuse it at the
point of entry, as `ait setup` and `ait ide` already do. `upstream_defect`.

## Final Implementation Notes

- **Actual work done:** as planned. `illegal_tmux_name` is now a problem shape
  reported by both line readers and honoured by `load_tmux_defaults`, so all five
  resolvers refuse a configured name holding `.` or `:` and fall back to
  `aitasks`.
  - bash: `_tmux_bootstrap_default_session_scan_checked` wraps the awk scanner
    and reuses `_tmux_bootstrap_session_name_ok`, keeping one definition of the
    rule. **Both** scan consumers route through it — `_tmux_bootstrap_default_session_raw`
    and `spawn_session_detached`, which reads the scan directly.
  - `_tmux_bootstrap_report_unreadable` and `tui_switcher.py` each gained a third
    wording arm; neither existing sentence is true of `a.b`.
  - Python: `_tmux_session_name_ok` twin, applied in `read_default_session_status`
    (last in precedence) and in `load_tmux_defaults` (the divergence closed).
  - `seed/project_config.yaml` documents the rule and names only the surfaces
    that actually report it.

- **Deviations from plan:**
  - **The plan's oracle-floor numbers were wrong.** It claimed `kept_hash` /
    `cut_comment` would "hold at 108 / 64" once sourced from PyYAML. Measured:
    **113 / 75**. The oracle population is the YAML-*parseable* rows, which is
    strictly larger than the reader-*readable* rows (a block scalar parses for
    YAML but is announced by the line reader). Both are far above the floor of
    50, so the fix stood; only the recorded numbers changed.
  - The plan's `_yaml_value(_row(value))` needed a `yaml.YAMLError` guard — the
    corpus is deliberately unfiltered, so many rows are not valid YAML and
    `_yaml_value` raises on them. Those rows are announced by both readers and
    were never in that population.
  - Added `LEGAL_NAME_ROWS` and `test_legal_punctuation_is_unaffected` beyond the
    plan, to pin the refusal as narrow (`my_proj-2`, `-n`, `a b`, `team#1`,
    `team/one` all still read).
  - `GeneratedWholeFileMutationTests` needed no logic change, as planned; only a
    measured-numbers comment was added.

- **Issues encountered:**
  - **A pre-existing t1825 defect blocked verification and was fixed in its own
    commit** (`c4292217b`, user-approved scope decision):
    `_tmux_bootstrap_default_session_scan` set `LC_ALL=C` on the awk stage but
    left the `tr` feeding it in the caller's locale. BSD `tr` (macOS) reads its
    input as characters and aborts with "Illegal byte sequence" on invalid UTF-8,
    truncating the stream — so the bytes the `ENC_BAD` state machine exists to
    find never reached awk and `encoding` was silently never reported. 12 tests
    were red on macOS before any t1828 change; all 12 pass with the locale set.
    GNU `tr` is byte-oriented, which is why t1825 shipped green on Linux.
  - Two `PARITY_ROWS` rows (`a:b`, `a :b`) had to move to `ILLEGAL_NAME_ROWS`;
    leaving them failed `ResolverParityTests` and `ReadableRowsReportNoProblemTests`.

- **Key decisions:**
  - The usability check lives in bash, **not** in the awk. The scanner's contract
    is "what YAML reads", and `a.b` is read correctly — it is unusable, not
    unreadable. Keeping awk pure also avoided a fourth spelling of the rule.
  - `illegal_tmux_name` is **not** a `DEFAULT_SESSION_FILE_SHAPES` member: it is a
    value shape, and it is last in precedence because a value must be readable
    before it can be judged unusable.
  - `kept_hash` / `cut_comment` are now counted from PyYAML rather than from the
    reader's answer. Those floors are about the *generator*; tying them to what
    the reader returns is what broke `cut_comment` (64 → 42) without the
    generator changing at all.

- **Verification:**
  - Pre-fix control: `IllegalTmuxNameTests` failed 44 times across all five
    resolvers, while both of its controls passed — so the fixtures were sound and
    the test was not vacuous.
  - Negative control: reverting only the `spawn_session_detached` call site
    produced `BOOTSTRAP_CREATED:a.b` and `tmux has-session -t =a.b` — exactly the
    bug. This is the call site a `_raw`-only fix would have missed.
  - Post-fix: resolvers 31/31, ide 55/55, setup 55/55, switcher notify 7/7.
  - **Full Python suite: PASSED (runner=unittest, exit=0)** — 7882 tests, 7
    skipped. No pytest/xdist tier on this box, so the serial lane ran (~1118s).
  - `shellcheck` clean on `tmux_bootstrap.sh`.
  - No false positive: the live repo (`default_session: aitasks`) and the seed
    (blank) both still read with no shape.
  - Post-phase mitigation `remeasure_corpus_floors` done: measured live at
    113 / 75 / 1246 / 681 / 256 and 104 / 43 / 39, recorded beside each floor.

- **Upstream defects identified:**
  - `.aitask-scripts/settings/settings_app.py:277` — `TMUX_CONFIG_SCHEMA["default_session"]`
    is an unvalidated free-text string field, so `ait settings` is a third way to
    write a name tmux cannot address. Reader-side fallback neutralizes it, but the
    TUI should refuse it at the point of entry as `ait setup` and `ait ide` do.
