---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [git, robustness, test]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-08-25 12:51
updated_at: 2026-08-25 12:51
---

## Context

Spawned "after" risk mitigation for **t1599** (scope task-data commits to their
own paths), confirmed during t1599's planning.

t1599's headline verification — "new claim commits show a 0% foreign-path
rate" — is a **lagging indicator**. It only becomes meaningful once enough new
claim commits have accumulated on the `aitask-data` branch *after* the fix
ships. None of t1599's four children can assert it at merge time; their tests
run against synthetic fixtures, which proves the mechanism but not the
production outcome.

This task closes that gap: an independent ground-truth check against real
history, rather than a second artifact of the same code.

## Precondition

Do not run this until **t1599_1** (`aitask_pick_own.sh` scoping) has been merged
to `main` and roughly **50 new claim commits** have landed on `aitask-data`.
Check with:

```bash
git -C .aitask-data log --oneline --grep='^ait: Start work on t' \
  <t1599_1-merge-sha>..aitask-data | wc -l
```

If fewer than ~50, **Defer** — do not Pass or Fail on a thin sample.

## Verification checklist

- [ ] Identify the merge commit that landed t1599_1 and record its SHA.
- [ ] Confirm ≥50 claim commits exist after it (command above). If not, Defer.
- [ ] Run the foreign-path scan over **only** the post-fix window and confirm the
      rate is **0%**:

```bash
tot=0; bad=0
while IFS=$'\t' read -r sha subj; do
  id=$(printf '%s' "$subj" | sed -n 's/^ait: Start work on t\([0-9_]*\):.*/\1/p')
  [ -n "$id" ] || continue
  tot=$((tot+1))
  n=$(git -C .aitask-data show --name-only --format='' "$sha" | grep -v '^$' \
      | grep -v '^aitasks/metadata/emails.txt$' \
      | grep -vcE "(^|/)t${id}(_|\.md$)" || true)
  if [ "$n" -gt 0 ]; then bad=$((bad+1)); echo "  FOREIGN: $sha t$id ($n paths)"; fi
done < <(git -C .aitask-data log --format='%H%x09%s' \
           --grep='^ait: Start work on t' <t1599_1-merge-sha>..aitask-data)
echo "$bad/$tot post-fix claim commits carry a foreign path"
```

- [ ] Baseline for comparison: **106/400 (26.5%)** measured pre-fix over
      Jul 1 – Aug 25 2026. Record the new numerator/denominator in the task.
- [ ] If t1599_3 also shipped, spot-check sync auto-commits in the same window
      (pre-fix baseline: **18/66** carried >2 task/plan files) and confirm each
      commit now names a single task.
- [ ] If t1599_2 shipped, check any `ait: Fold tasks into t…` commits in the
      window (pre-fix: **5/11** swallowed).
- [ ] For **any** non-zero result, capture the offending SHAs and open a bug
      against the owning child rather than editing here.

## Notes

- The scan MUST run against `.aitask-data`, not `main`. `main` still carries 81
  pre-migration claim commits from Feb 2026 that are not current behaviour and
  will skew the result.
- `aitasks/metadata/emails.txt` is excluded as legitimate shared churn. If the
  scan is widened, re-check that exclusion list — do not silently broaden it to
  hide a real swallow.
- A **Pass** here is what upgrades t1599's verification from "fixtures pass" to
  "the defect is gone in production".
