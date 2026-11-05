---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [task-workflow, verification]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1538
followup_kind: upstream_defect
created_at: 2026-11-05 08:21
updated_at: 2026-11-05 08:33
---

## Origin

Spawned from t1663_1 during Step 8b review (commit 306241f3d).

## Upstream defect

- `.aitask-scripts/lib/task_utils.sh:3381 — get_file_references() splits the flow list on commas, ignoring YAML quoting, so the valid entry "a,b.py" becomes the two paths "a" and "b.py"; aitask_verification_stale.sh (t1555) still reads its scope this way.`
- `.aitask-scripts/lib/task_utils.sh:2530 — format_yaml_list() writes file_references: (and other lists) as an unquoted flow list, so an entry containing ",", "[", "]" or a leading ":" is written as invalid or differently-parsed YAML.`

## Diagnostic context

t1663_1 built `aitask_premise_stale.sh`, which first read Tier-A scope through `get_file_references()` (the same reader `aitask_verification_stale.sh` uses). A review reproduced the defect. In a repo holding `a,b.py`, `a` and `b.py`, the valid field `file_references: ["a,b.py"]` was read as the two other files. After a change to `a,b.py` only, the helper reported `FILES:2` / `DECISION:FRESH`, a false all-clear.

t1663_1 fixed its own reader. It now reads the field through `task_yaml.parse_frontmatter` (`lib/task_premise.py::task_fields`), where only string entries are paths. YAML 1.1 turns unquoted `null` / `on` / `010` into `None` / `True` / `8`, so non-strings are counted invalid references. t1663_1 did NOT touch `get_file_references()` or `format_yaml_list()`, which are shared helpers with other consumers.

Other things worth knowing:
- `format_yaml_list` is the writer side of the same field. Because it writes unquoted, an entry such as `docs/a[bc].md` or `:12` is invalid YAML. `python3 -c 'import yaml; yaml.safe_load("[docs/a[bc].md]")'` raises `ParserError`, so every Python reader (board, `task_yaml`, the premise helper, which reads it as `SKIP`/`invalid_frontmatter`) sees a broken file.
- The same unquoted writer turns `on`, `null` or `010` entries into non-strings for those readers.

## Suggested fix

- Reader: make `get_file_references()` parse the field as YAML (e.g. shell out to `task_yaml`, as `aitask_premise_stale.sh`'s `_FIELDS_GLUE` does), or retire it in favour of a shared reader. Then re-run `tests/test_verification_stale.sh` with a quoted-comma fixture.
- Writer: quote list entries that YAML would mis-read in `format_yaml_list()` (or emit via a YAML serializer), with round-trip tests for `,` `[` `]` `:` `#` `on` `null` `010` and leading/trailing spaces.
- Check the other `format_yaml_list` callers (labels, depends, verifies, …) for behaviour changes.
