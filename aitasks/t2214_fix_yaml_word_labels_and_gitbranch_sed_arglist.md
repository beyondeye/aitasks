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
created_at: 2026-11-05 12:17
updated_at: 2026-11-05 12:40
---

## Origin

Spawned from t2209 during Step 8b review (commit 9b6cb2761).

## Upstream defect

- `.aitask-scripts/lib/task_utils.sh:2571 — sanitize_label() admits YAML 1.1 words such as on / null / yes / 010, and format_yaml_list() (task_utils.sh:2530) writes them unquoted, so every Python reader (board, task_yaml) reads the label as True / None / 8 instead of the string`
- `.aitask-scripts/lib/artifact_backends/gitbranch.sh:524 — sed invoked with a store-sized argument list fails with "Argument list too long" on large stores; tests/test_artifact_gitbranch_backend.sh fails at HEAD on the "large store migrates" cases`

## Diagnostic context

t2209 made file_references: YAML end to end. Its new path-list writer is
`format_yaml_path_list`, and the plain predicate it uses is `_yaml_path_is_plain`
in lib/task_utils.sh. That writer quotes YAML 1.1 bool/null/number words and
escapes non-printable code points, measured against both PyYAML loaders in
tests/test_file_refs_yaml.sh. `format_yaml_list` was deliberately left unchanged,
because it also writes id / gate lists where integers must stay plain. That leaves
the labels field exposed: a label sanitized to `on`, `null`, `yes` or `010` passes
`[a-z0-9_-]` and is written plain.

The gitbranch failure surfaced in t2209's post-phase sweep. It is identical at HEAD
and on the t2209 tree (`/usr/bin/sed: Argument list too long` at gitbranch.sh line
524) and is unrelated to file_references.

## Suggested fix

- Labels: reject or quote YAML-special words. Either `sanitize_label` refuses them
  (simplest: labels are a controlled vocabulary), or the labels writer quotes them
  via a string-list formatter like `format_yaml_path_list`. Add a PyYAML round-trip
  test.
- gitbranch.sh:524: pass the list through stdin or a file (or xargs) instead of
  argv.
