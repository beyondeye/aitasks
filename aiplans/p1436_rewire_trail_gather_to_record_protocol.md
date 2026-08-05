---
Task: t1436_rewire_trail_gather_to_record_protocol.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1436 — Rewire `trail_gather` onto `lib/record_protocol.py`

## Context

**t1433** extracted the `|`-delimited record-protocol safety policy into
`.aitask-scripts/lib/record_protocol.py` and rewired two of its three consumers
(`lib/work_report_gather.py`, `lib/board_columns.py`). `lib/trail_gather.py` was
left alone by an explicit user decision: a concurrent session held ~292 lines of
uncommitted work in that file and its test, so editing either would have swept
in-flight work into t1433's commit.

The duplication is therefore **two copies, not three** today: the shared module
plus `trail_gather.py`'s private six-symbol block at `:166-187`. This task
closes it, and adds the fail-closed characterization t1433's AC asked for and
that does not exist anywhere yet.

**Precondition — verified clean.**
`git status --porcelain .aitask-scripts/lib/trail_gather.py tests/test_trail_gather.py`
returned empty, so the concurrent session has landed.

## Findings from exploration

- The private block sits at `trail_gather.py:166-187` (constants `_RECORD_BREAKING`,
  `INVALID_ENUM`, `UNKNOWN_ENUM`; functions `_has_record_breaking`, `_free_text`,
  `_enum_field`). The task file's `:160-181` estimate is stale — relocated by symbol.
- `_free_text` is byte-identical to `record_protocol.sanitize_last_field`
  (same three replacements, same order — t1433 unified on the CRLF-collapsing
  policy that `_free_text` already had). `_has_record_breaking` / `_enum_field`
  are likewise semantically identical to their shared counterparts.
- `UNKNOWN_ENUM` has no reference outside the deleted `_enum_field`.
  `INVALID_ENUM` is still needed — by `_csv_entry`, which stays local.
- Nothing outside the module touches the private names. A repo-wide grep for
  `trail_gather._*` / `from trail_gather import` hits exactly one line:
  `tests/test_trail_gather.py:955` (`_free_text`; the task file's `:775` is stale).
- **No test anywhere pins `trail_gather`'s `EXIT_INFRA` (3) or its
  `trail_gather: ` stderr prefix** — confirmed against `test_trail_gather.py`,
  `test_trail_skill_contract.sh`, `test_codeagent_trail.sh`.
- `trail_gather.py` already inserts `lib/` into `sys.path` at `:128-131`, so a
  bare `from record_protocol import …` resolves however the module is invoked.
  `record_protocol` imports nothing, so this adds no startup cost anywhere.

## Work

### Pre-phase (risk mitigations)

- **`probe_wrapper_stderr`** — before writing any stderr assertion, build the
  fatal fixture by hand and run `aitask_trail_gather.sh snapshot --scope task 100`
  in it with a `project.name`-less `project_config.yaml`. **Record the observed
  raw stderr verbatim in a comment on the new test class** — that comment is the
  documented boundary behavior. Then pick the assertion from this table; do not
  leave the shape open:

  - **Case A — stderr is exactly the one `_die` line** (expected). Pin the
    **whole stream**: `proc.stderr.splitlines()` has length 1, and that line both
    `.startswith("trail_gather: ")` and `.endswith(": missing project.name")`.
    Whole-stream means no other module may contribute output at all.
  - **Case B — the wrapper emits a preamble** (e.g. `require_ait_python`
    diagnostics). Pin a **specified line**: exactly one stderr line ends with
    `": missing project.name"`, and *that* line starts with `trail_gather: `.
    Quote the observed preamble in the comment so a future change to it is a
    visible diff rather than a silent widening.

  Either way the assertion names which line carries the message, so a later
  wrapper preamble can never make the ownership contract ambiguous, and the
  `record_protocol:` negative control below is unaffected.

### 1. `.aitask-scripts/lib/trail_gather.py` — rewire

**Import** (insert into the existing sorted `lib/` block at `:135-140`, between
`gate_ledger` and `task_yaml`). Import the shared names **directly** — no
`import … as _free_text` aliases; that is the convention t1433 followed and the
one `work_report_gather.py`'s own comment argues for:

```python
from record_protocol import (  # noqa: E402
    INVALID_ENUM, enum_field, has_record_breaking, sanitize_last_field,
)
```

**Delete** `_RECORD_BREAKING`, `INVALID_ENUM`, `UNKNOWN_ENUM` (`:166-168`) and
`_has_record_breaking`, `_free_text`, `_enum_field` (`:173-187`).

**Keep** the `# --- Delimiter safety ---` header, retargeted to name the shared
module — mirroring `work_report_gather.py:89-101`. Also keep, in place:

- `_csv_entry` — it adds a fourth reserved character (`,`) only this module needs;
- `_die` — its `trail_gather: ` stderr prefix is deliberately **not** shared
  (a library path must not `sys.exit` inside a TUI).

**Rename every call site** to the shared names:

| old | new | sites |
|---|---|---|
| `_has_record_breaking` | `has_record_breaking` | `_csv_entry`, `:480` |
| `_free_text` | `sanitize_last_field` | `emit_errors` (`:206`), `:510`, `:926` |
| `_enum_field` | `enum_field` | `:492`, `:495`, `:505-508` |

### 2. `tests/test_trail_gather.py:955` — follow the rename

`trail_gather._free_text("a\r\nb\nc")` → `trail_gather.sanitize_last_field(...)`.
The asserted value `"a b c"` is unchanged.

### 3. `tests/test_trail_gather.py` — add the missing fail-closed characterization

Added as a **new section in this file** (not a new file) so it reuses the
existing `SyntheticRepo` / `TrailGatherCase` fixture.

- **Hoist** `run_wrapper` out of `WrapperIntegrationTests` (`:1056-1060`) up into
  `TrailGatherCase`'s helpers block, right after `run_cli` (`:143-147`).
  `WrapperIntegrationTests` then inherits it unchanged.
- **New sibling class** `InfraExitCharacterizationTests(TrailGatherCase)` placed
  after `WrapperIntegrationTests` under a `# --- J2. Fail-closed infra path`
  header — a **sibling, not a subclass**: subclassing silently re-runs the base's
  tests under a second name (the point
  `test_work_report_columns_characterization.py` spells out at
  `UnorderedPopulatedTests:136-142`). Update the module docstring's section list.
- Declare `EXIT_INFRA = 3` as an **independent literal** in the test module with
  a comment, rather than importing `trail_gather.EXIT_INFRA` — the same
  independent-ground-truth convention the work-report characterization uses at
  its `:48-55`.

Tests, mirroring `test_work_report_columns_characterization.py`:

- **Trigger** — overwrite the fixture's `aitasks/metadata/project_config.yaml`
  with a body carrying no `project.name`. `cmd_snapshot` calls
  `local_project_name()` as its **first** statement (`:534`), which reaches
  `_die(f"{config_path}: missing project.name", EXIT_INFRA)` deterministically
  through the real `.sh` entry point — the only boundary where the exit status
  and stderr prefix are observable.
- `test_missing_project_name_exits_infra` — `returncode == 3`.
- `test_fatal_path_emits_no_protocol_lines` — stdout is empty (a fatal path must
  not emit a partial stream). Nothing is printed before the `_die`, so the exact
  pin is `assertEqual(proc.stdout, "")`.
- `test_message_carries_the_trail_gather_prefix` — the prefix pin, in the exact
  shape the pre-phase probe selected (Case A or Case B). It asserts the
  **message body** (`": missing project.name"`) as well as the prefix, so the
  test names *this* `_die` call site rather than accepting any `EXIT_INFRA` —
  `cmd_drift` has a second `_die` at `:843` (version lock) that would otherwise
  satisfy a prefix-only assertion.
- `test_prefix_assertion_discriminates` — **negative control**, mirroring
  `test_work_report_columns_characterization.py:180-191`: stderr does **not**
  contain `record_protocol:`, and is non-empty. Without it the prefix assertion
  passes vacuously if the shared module ever takes over the message — precisely
  the regression this rewiring could introduce.
- `test_a_valid_config_is_not_rejected` — **positive control**: the same fixture
  with its pristine valid `project.name` exits 0, proving the fatal path is
  reached by the bad config only.

### Post-phase (risk mitigations)

- **`characterize_drift_infra_exit`** — `cmd_drift` reaches
  `local_project_name()` too, so the `EXIT_INFRA` + `trail_gather: ` contract has
  **two** entry paths while step 3 pins only `snapshot`. Add a `drift` case to
  `InfraExitCharacterizationTests` asserting the same pins: `returncode == 3`,
  empty stdout, and the message assertion in the shape the pre-phase selected.

  **The fixture ordering is load-bearing, not incidental.** `cmd_drift` calls
  `local_project_name()` at `:820` — **before** the `--trail` existence check at
  `:824` and before `trail_schema.load_trail()` at `:828`. So a missing,
  unreadable, or schema-invalid trail exits 3 with the *identical* message, and a
  carelessly-built test would pass while proving nothing about the valid-trail
  path. Therefore, in this order:

  1. With `project_config.yaml` **still valid**, build a real snapshot and a
     schema-valid trail on disk (`self.snapshot("--scope", "task", "100")` +
     `self.make_trail(snap)` — the existing in-process helpers, which themselves
     require a valid config).
  2. **Positive control, before any mutation:** run
     `run_wrapper("drift", "--trail", str(trail))` and assert `returncode == 0`
     with `CURRENT` on stdout. This is what proves the trail is schema-valid and
     the path is live — without it the exit-3 below is unattributable.
  3. Remove `project.name` from the config. That is the **single** mutation
     between the two runs.
  4. Re-run the wrapper on **the same trail path** and assert the three fatal
     pins.

  Because only the config changed between steps 2 and 4, the exit-3 result is
  attributable to the config alone and cannot be an `invalid_trail` /
  `trail_unreadable` artifact. Confirm empirically that the drift path really is
  fatal-before-output rather than assuming parity with `snapshot`.

## Verification

```bash
find . -name __pycache__ -prune -exec rm -rf {} +      # no stale .pyc decides this
~/.aitask/venv/bin/python -m pytest tests/test_trail_gather.py \
    tests/test_record_protocol.py -q
bash tests/test_no_lib_to_tui_import.sh 2>&1 | tail -3
bash tests/run_all_python_tests.sh                     # read ONLY the last line
```

**Prove the new guard discriminates** before committing: change
`trail_gather._die`'s prefix to `record_protocol: `, re-run, and confirm the
negative control fails with a **named** test id
(`InfraExitCharacterizationTests.test_prefix_assertion_discriminates`). Then
restore by **undoing the edit** — do not `git checkout` (other files are dirty
in this worktree).

**Done when** (task's own acceptance):

```bash
grep -c '_free_text\|_enum_field\|_has_record_breaking\|_RECORD_BREAKING' \
    .aitask-scripts/lib/trail_gather.py                     # -> 0
grep -rn 'replace("\r"' --include=*.py .aitask-scripts/     # -> only lib/record_protocol.py
```

Step 9 (Post-Implementation) then runs the merge / archival flow as usual.

## Risk

### Code-health risk: low

- The shared symbols are semantically identical to the deleted private ones
  (`sanitize_last_field` is byte-identical to `_free_text`), so the rewire is a
  rename plus an import; blast radius is one `lib/` module and its test, with no
  external consumer of the private names (verified by repo-wide grep)
  · severity: low · → mitigation: inline post-phase characterize_drift_infra_exit
- Deleting the constants could orphan a reference — `INVALID_ENUM` is still used
  by the retained `_csv_entry` and is therefore re-imported, while `UNKNOWN_ENUM`
  is genuinely unreferenced · severity: low · → mitigation: inline post-phase
  characterize_drift_infra_exit

### Goal-achievement risk: low

- The new characterization's `stderr.startswith("trail_gather: ")` pin assumes
  the trail wrapper emits nothing on stderr before Python runs. The analogous
  work-report characterization passes under that assumption, but
  `aitask_trail_gather.sh` is a different script · severity: low
  · → mitigation: inline pre-phase probe_wrapper_stderr

### Planned mitigations
- timing: pre-phase | name: probe_wrapper_stderr | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — unverified stderr-prefix assumption | desc: probe the real wrapper's stderr on the fatal path before pinning the assertion shape
- timing: post-phase | name: characterize_drift_infra_exit | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — only one of two EXIT_INFRA entry paths pinned | desc: extend the characterization to the drift verb so both fatal entry paths are covered

**Reassessment after inlining:** both phases are additive, independently
verifiable test work on the same two files the plan already touches. Neither
changes the rewire itself, so the two levels stand at **low / low**.
