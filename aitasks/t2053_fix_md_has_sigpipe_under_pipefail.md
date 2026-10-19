---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
followup_kind: upstream_defect
created_at: 2026-10-19 07:59
updated_at: 2026-10-19 07:59
---

## Origin

Spawned from t1231_1 during Step 8b review.

## Upstream defect

- `tests/test_no_unscoped_task_commit.sh:672` — `md_has` pipes the whole markdown list into `grep -qxF` under `set -o pipefail`. grep exits on the first match, the `printf` writer gets SIGPIPE, and the pipeline returns 141. So "markdown: the canonical teaching skill is in scope" (and intermittently "the root instruction doc is in scope", i.e. CLAUDE.md) fails although the file IS enumerated.

## Diagnostic context

While running the regression suites for t1231_1 (none of which touch markdown or this test), `test_no_unscoped_task_commit.sh` failed on those scope assertions. The files are tracked and in `md_in_scope`. Reproduction:

```bash
bash -c 'set -o pipefail; mapfile -t A < <(git ls-files -- "*.md" "*.j2")
  printf "%s\n" "${A[@]}" | grep -qxF ".claude/skills/ait-git/SKILL.md"; echo "rc=$?"'
# rc=141   (without pipefail: rc=0)
```

The failure is load/timing dependent: it passed on one re-run, then failed three times in a row. It is not caused by t1231_1's changes.

## Suggested fix

Make `md_has` immune to early reader exit, e.g. loop over the array in bash
(`local f; for f in ...; do [[ "$f" == "$1" ]] && return 0; done; return 1`) or
use `grep -xF` without `-q` with output to `/dev/null` (grep then reads all input).
Audit the file for other `| grep -q` pipelines under pipefail.
