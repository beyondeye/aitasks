---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [aitask-create, bash_scripts, framework]
gates: [risk_evaluated]
anchor: 1312
created_at: 2026-07-29 18:39
updated_at: 2026-07-29 18:39
boardidx: 92160
---

## Origin

Risk-mitigation ("after") follow-up for t1312, created at Step 8d after
implementation landed. Independently re-raised during t1312's Step 8 review,
which confirmed the race by reading the implementation.

## Risk addressed

addresses: code-health — whole-file `sort -u` rewrite on the data branch

Verbatim from t1312's plan `## Risk` → Code-health risk:

> - Whole-file `sort -u` rewrite on the data branch = merge-conflict surface,
>   and concurrent writers can last-writer-wins a label away (atomic `mv` fixes
>   torn reads, not lost updates; a registry lock would drop labels instead —
>   worse) · severity: medium · → mitigation: `labels_txt_concurrent_append`

## The race, concretely

`add_label_to_file` in `.aitask-scripts/lib/task_utils.sh` does:

```bash
tmp="${file}.tmp.$$"
{ cat "$file"; echo "$label"; } | LC_ALL=C sort -u > "$tmp" && mv "$tmp" "$file"
```

The temp-file + `mv` makes the write **atomic for readers** — nobody ever sees a
half-written vocabulary. It does **not** make it atomic for writers. Two
concurrent `aitask_create.sh --batch --commit` runs each `cat` their own
snapshot, each append their own label, and each `mv` the result: the second `mv`
wins and the first writer's brand-new label is gone from the file — while its
task frontmatter still references it. That breaks the invariant t1312
established (frontmatter ⊆ vocabulary) exactly in the parallel-agent case this
repo runs routinely.

The `$$`-suffixed temp name prevents two writers from clobbering each other's
*temp* file, so the failure is a silent lost update, never a corrupt file.

Secondary cost: rewriting the whole file on every new label maximises the
merge-conflict surface on the `aitask-data` branch, where several checkouts
push independently.

## Goal

Make `labels.txt` appends conflict-tolerant and lost-update-free. Two candidate
directions (evaluate both; they are not exclusive):

1. **Append-only write, dedupe at read time.** `add_label_to_file` appends a
   single line with `>>` (atomic for a short line on a local filesystem) and
   never rewrites; `get_existing_labels` already sorts and dedupes on read, so
   readers are unaffected. This removes both the lost update and most of the
   merge-conflict surface, at the cost of the file no longer being canonically
   sorted on disk.
   **Blocker to resolve first:** t1312 pins the live file as `LC_ALL=C sort -u`
   canonical in `tests/test_label_vocabulary_lib.sh`, and the chatlink
   byte-identity contract (`aidocs/chat/label_vocabulary_and_allowlist.md`)
   leans on entries being sanitize_label fixed points. Decide whether
   canonicalisation moves to a periodic/`ait` maintenance step, and update that
   test and doc in the same change.

2. **A git merge driver for `labels.txt`** (union merge) so concurrent branches
   combine rather than conflict. Complements (1) rather than replacing it — it
   addresses the cross-checkout half of the problem, not the same-checkout
   race.

Explicitly rejected in t1312's planning: a registry lock around the read-modify
-write. Under contention it would make writers *drop* labels rather than
serialise them — strictly worse than the current behaviour.

## Verification

- A test that runs N concurrent `add_label_to_file` calls with distinct labels
  and asserts all N survive in the vocabulary. Prove it fails against today's
  implementation first (negative control) — a concurrency test that passes
  before the fix is testing nothing.
- `tests/test_label_vocabulary_lib.sh` still passes, or its collation and
  fixed-point pins are deliberately updated in the same commit with the
  rationale recorded.
- `bash tests/test_label_autoadd.sh` and `bash tests/test_update_label_staging.sh`
  still pass — both assert on exact commit contents and worktree cleanliness.
