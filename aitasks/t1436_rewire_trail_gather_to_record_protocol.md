---
priority: medium
effort: low
depends: [1433]
issue_type: refactor
status: Implementing
labels: [python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1433
created_at: 2026-08-05 17:47
updated_at: 2026-08-05 18:27
---

## Context

Deferred half of **t1433**, which extracted the `|`-delimited record protocol
into `.aitask-scripts/lib/record_protocol.py` and rewired two of its three
consumers. `lib/trail_gather.py` was left alone: at implementation time a
concurrent session held **292 lines of uncommitted work** in
`.aitask-scripts/lib/trail_gather.py` (+124) and `tests/test_trail_gather.py`
(+186), so editing either would have swept that in-flight work into t1433's
commit. The split was an explicit user decision, not an oversight.

So the duplication is currently **two copies, not three**: the shared module,
plus `trail_gather.py`'s private block. This task closes it.

## Precondition

`git status --porcelain .aitask-scripts/lib/trail_gather.py tests/test_trail_gather.py`
must be **clean** before starting. If it is not, the other session is still in
flight — stop and wait rather than working around it.

## Work

### 1. Rewire `lib/trail_gather.py`

Delete its private copies — `_RECORD_BREAKING`, `INVALID_ENUM`, `UNKNOWN_ENUM`,
`_has_record_breaking`, `_free_text`, `_enum_field` (they sat at `:160-181`
before the concurrent change; **re-locate by symbol name, not line number**).
Keep the `# --- Delimiter safety ---` header, retargeted to name the shared
module. Keep `_csv_entry` and `_die` in place — `_csv_entry` adds a fourth
reserved character (`,`) only this module needs, and `_die`'s
`trail_gather: ` stderr prefix is deliberately NOT shared (a library path must
not `sys.exit` inside a TUI).

```python
from record_protocol import (  # noqa: E402
    INVALID_ENUM, enum_field, has_record_breaking, sanitize_last_field,
)
```

(`INVALID_ENUM` is needed by `_csv_entry`; `UNKNOWN_ENUM` is not referenced.)

Rename every call site to the shared names: `_has_record_breaking` →
`has_record_breaking`, `_free_text` → `sanitize_last_field`, `_enum_field` →
`enum_field`. Import the shared names directly — **no `import ... as _free_text`
aliases**; that is the convention t1433 followed and the one
`work_report_gather.py`'s own comment argues for.

### 2. `tests/test_trail_gather.py:775`

`trail_gather._free_text` → `trail_gather.sanitize_last_field`. The asserted
value is unchanged: t1433 unified the shared last-field sanitizer on the
CRLF-collapsing policy, which is exactly what `_free_text` already did.

### 3. Add the missing fail-closed characterization

t1433's AC required "the equivalent for `trail_gather`'s protocol output if none
exists" — and none does. **No test anywhere asserts `trail_gather`'s
`EXIT_INFRA` (3) or its `trail_gather: ` stderr prefix** (verified by grep over
`test_trail_gather.py`, `test_trail_skill_contract.sh`, `test_codeagent_trail.sh`).
Mirror `tests/test_work_report_columns_characterization.py`.

Add it as a new section in `tests/test_trail_gather.py` rather than a new file,
so it reuses the existing `SyntheticRepo` fixture. Hoist `run_wrapper` from
`WrapperIntegrationTests` up to `TrailGatherCase`, and add a **sibling** class —
not a subclass (subclassing silently re-runs the base's tests under a second
name; the work-report characterization spells this out at its
`UnorderedPopulatedTests`).

- **Trigger:** overwrite the fixture's `aitasks/metadata/project_config.yaml`
  with a body carrying no `project.name`. That reaches
  `trail_gather.local_project_name` → `_die(..., EXIT_INFRA)` deterministically
  through the real `.sh` entry point.
- **Pin:** `returncode == 3`; stderr starts with `trail_gather: `; stdout carries
  no protocol lines (a fatal path must not emit a partial stream).
- **Negative control** (mirrors
  `test_work_report_columns_characterization.py:180-191`): assert stderr does
  **not** contain `record_protocol:` and is non-empty. Without it the prefix
  assertion passes vacuously if the shared module ever takes over the message —
  precisely the regression this rewiring could introduce.
- **Positive control:** the same fixture with a valid `project.name` exits 0.

## Verification

```bash
~/.aitask/venv/bin/python -m pytest tests/test_trail_gather.py tests/test_record_protocol.py -q
bash tests/test_no_lib_to_tui_import.sh 2>&1 | tail -3
bash tests/run_all_python_tests.sh          # read ONLY the last line
```

Prove the new guard discriminates before committing: change `trail_gather._die`'s
prefix to `record_protocol: ` and confirm the negative control fails with a
**named** test id, then restore (undo the edit; do not `git checkout`). Purge
`__pycache__` first so a stale `.pyc` cannot decide the result.

## Done when

`grep -c '_free_text\|_enum_field\|_has_record_breaking\|_RECORD_BREAKING' .aitask-scripts/lib/trail_gather.py`
returns 0, and a repo-wide scan for inline `replace("\r"` under
`.aitask-scripts/**.py` returns only `lib/record_protocol.py`.
