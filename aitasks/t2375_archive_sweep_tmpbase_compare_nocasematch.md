---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts, shell]
anchor: 2290
followup_kind: upstream_defect
created_at: 2026-11-27 08:09
updated_at: 2026-11-27 08:09
---

## Origin

Spawned from t2362 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/archive_utils.sh:212` (pre-existing): the base comparison in `_ait_archive_cleanup`, `[[ "${TMPDIR:-/tmp}" == "$_AIT_ARCHIVE_TMPBASE" ]]`, folds case when the caller set `shopt -s nocasematch`. An exit-time TMPDIR that differs from the pinned base only by case is then not swept as a second base, so its extractions can leak.

## Diagnostic context

t2362 made the archive sweep's EXIT-trap ownership byte-exact. Review then showed that its first cleanup check, `[[ "$cur" == _ait_archive_cleanup ]]`, honoured a caller's `nocasematch`: a caller's own `_AIT_ARCHIVE_CLEANUP` handler was taken for ours and its extractions leaked. A probe on bash 5.3 shows the scope of the option:
- `[[ == ]]`, `case` and `${x/pat/rep}` fold case under nocasematch;
- `[ = ]`, `${x#pat}`, `${x%pat}` and `${x:i:n}` do not.

t2362 converted every comparison it introduced. This pre-existing path comparison in `_ait_archive_cleanup` is outside that change and was left as is. The archive-name checks at archive_utils.sh lines 68, 77, 86, 100 and 569 (`[[ "$archive" == *.tar.zst ]]`) fold case too, but there that is harmless.

## Suggested fix

Compare with `[ "${TMPDIR:-/tmp}" = "$_AIT_ARCHIVE_TMPBASE" ]`. Add a test: under `shopt -s nocasematch`, set the exit-time TMPDIR to a case-variant of the pinned base, then assert that both bases are swept. A case-insensitive filesystem may make the two paths the same directory; the test must account for that.
