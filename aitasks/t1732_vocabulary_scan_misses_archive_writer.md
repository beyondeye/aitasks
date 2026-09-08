---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [test, task_metadata, documentation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-07 18:39
updated_at: 2026-09-08 12:28
---

## Defect

`tests/test_docs_vocabulary_coverage.sh` fails on the live repo:

```
FAIL E/corpus: task files carry frontmatter keys no known writer emits:
      ['archived_reason'] (hand-edited, or a retired field)
```

`archived_reason` is a real, legitimately-written field, not a hand edit. It is
emitted by `.aitask-scripts/aitask_archive.sh` (the `--superseded` flow, added by
t400):

```bash
awk '/^status:/{print; print "archived_reason: superseded"; next}1' "$file_path" ...
```

The scanner's writer set is derived from `ECHO_WRITERS` in
`tests/lib/docs_vocabulary_scan.py`, which lists only:

```python
ECHO_WRITERS = [
    ".aitask-scripts/aitask_update.sh",
    ".aitask-scripts/aitask_create.sh",
]
```

`aitask_archive.sh` is not in it, and its write is an `awk` insertion rather than
the `echo "<field>: ..."` shape the extractor looks for — so the field can never
be discovered and every task file carrying it is reported as an unknown key.

## Why it only just started failing

The gap has been latent since t400. The `E/corpus` check compares the **live**
`aitasks/` corpus against the derived writer set, so it stayed green while no
task file carried the field. The first one appeared on 2026-09-07 18:20
(`aitasks/archived/t1730_*.md`, archived with `--superseded`), and the suite has
failed since. Confirmed by a natural experiment: the same suite passed a full run
earlier the same afternoon and failed the next run, with no scanner or writer
change in between.

Discovered while implementing t1599_4, which owns `aitask_archive.sh` but only
for commit path-scoping — the writer-coverage gap is a separate concern and was
deliberately not fixed there.

## Suggested fix

Decide which of these is right, and say why in the code:

1. Add `.aitask-scripts/aitask_archive.sh` to `ECHO_WRITERS` **and** teach the
   extractor the `awk '... print "<field>: ..."'` insertion shape — otherwise
   adding the file changes nothing, because the regex will not match.
2. Or register `archived_reason` explicitly, the way `DRAFT_ONLY_KEYS` carves out
   keys that are deliberately not table fields — with a comment naming its writer.

Then check whether `archived_reason` needs a row in the website Frontmatter
field table: if it becomes a discovered writer field, `D/field-coverage` will
demand one.

## Verification

- `bash tests/test_docs_vocabulary_coverage.sh` passes on the live repo.
- A negative control: the check must still fail for a genuinely unknown key
  (seed a task file with a made-up field and confirm `E/corpus` fires), so the
  fix does not silence the diagnostic wholesale.
- Sweep for other fields written outside the two `ECHO_WRITERS` scripts — the
  same blind spot may hide more than one field.
