---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [task_attachments]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1065
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-19 07:59
updated_at: 2026-10-19 10:55
completed_at: 2026-10-19 10:55
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

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-19T06:32:53Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-19T07:16:02Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-19T07:55:06Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:5b81116a75461d70

> **✅ gate:risk_evaluated** run=2026-10-19T07:55:06Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2053/risk_evaluated_2026-10-19T07:55:06Z-risk_evaluated-a1.log`
