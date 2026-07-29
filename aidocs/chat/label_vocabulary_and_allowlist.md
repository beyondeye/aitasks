# Label vocabulary growth and the chatlink allowlist

`aitasks/metadata/labels.txt` plays two roles at once:

1. **Locally**, it is the label *vocabulary* — the suggestion list behind
   `/aitask-pick`'s label filter, the board, and `/aitask-explore`'s label
   confirmation step.
2. **At the chat gateway**, it is a strict *allowlist*: `payload_guard.py`
   rejects any `payload.json` whose `labels` are not a subset of it. That check
   is the trust boundary "a remote submitter may only use labels this repo
   already knows".

This note records why local task creation is allowed to grow that file, and
what keeps the gateway boundary intact while it does.

## Who may write the vocabulary

**Local, attended writers only.** Both write through the shared seam in
`.aitask-scripts/lib/task_utils.sh` (`sanitize_label`, `add_label_to_file`,
`normalize_labels_csv`, `add_labels_csv_to_file`):

- `aitask_create.sh --batch --labels …` registers any new label and commits
  `labels.txt` in the same commit as the task that introduced it.
- `aitask_update.sh --batch --labels / --add-label` does the same, staging
  `labels.txt` only when it actually appended.

**The gateway is not a writer.** A remote payload's labels must byte-match
existing `labels.txt` lines; the guard's subset check is unchanged, and remote
submitters still cannot mint a label. Growth is a local, human-attended act.

## Why the guard's own docstring assumes this

`payload_guard.py` documents its rationale as *"`aitask_create.sh` auto-adds
unknown labels rather than rejecting — so subset enforcement MUST happen
here"*. The guard was designed against a machine-growable vocabulary. Local
auto-add makes that stated assumption true; it does not invert the boundary.

## Why accepted labels stay inert

Every consumer treats a label as data, not as code:

- `aitask_ls.sh` parses via `parse_yaml_list` and string-compares for filtering.
- `aitask_stats_legacy.sh` parses and groups.
- The board reads them as YAML frontmatter.
- The chatlink schema and guard reject control characters and enforce size
  limits before any of this.

No consumer evals, executes, or interpolates a label into an unquoted command
line. And every machine-minted entry is charset-restricted to `[a-z0-9_-]` by
`sanitize_label`, so it cannot escape a YAML scalar, a quoted shell word, or an
`-F` fixed-string match.

## The byte-identity contract

The gateway promises that an accepted payload is created **byte-identical** to
what was submitted. Create-side normalization would rewrite a label only if
`labels.txt` held a non-canonical entry (a hand-edited uppercase or spaced
line). Two things keep that from happening:

- Every entry is a `sanitize_label` fixed point, and the file is `LC_ALL=C`
  sorted and deduplicated. Both properties are pinned against the **live**
  `labels.txt` by `tests/test_label_vocabulary_lib.sh`.
- All writers go through the same seam, which sanitizes before appending.

If you ever hand-edit `labels.txt`, keep entries lowercase `[a-z0-9_-]` and
re-sort with `LC_ALL=C sort -u` — otherwise that test fails and the gateway's
byte-identity promise is no longer guaranteed.

## If a stricter remote policy is ever wanted

Curating a separate chatlink allowlist (or a `# chatlink-allowed` marker
convention inside `labels.txt`) is a **hardening** option, not a fix for a
boundary defect: the membership check, its designed semantics, and label
inertness are all unchanged by local vocabulary growth.

## See also

- `.aitask-scripts/chatlink/payload_guard.py` — the subset check itself
- `.aitask-scripts/lib/task_utils.sh` — the canonical label seam
- `aidocs/chat/chatlink_runtime.md` — gateway runtime and flow
