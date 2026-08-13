---
priority: medium
effort: medium
depends: [1515]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1515]
assigned_to: dario-e@beyond-eye.com
anchor: 1210
followup_kind: manual_verification
created_at: 2026-08-13 23:57
updated_at: 2026-08-14 00:02
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1515

## Verification Checklist

- [ ] Live branch-mode artifact round trip: on this repo (aitasks/ symlinked to .aitask-data/), pick a scratch task, run `ait artifact create <task> <file> --kind report --handle art:tmp-check` then `ait artifact rm <task> art:tmp-check`; confirm the task frontmatter has NO `artifacts:` key afterwards and matches its pre-create state modulo updated_at. The e2e test (tests/test_artifact_cli.sh F11) runs in a legacy-mode fixture repo, so task_git routing to the data branch is not covered by automation.
- [ ] Live attachment round trip: same check via `ait attach add <task> <file>` then `ait attach rm <task> <name>`; confirm no bare `attachments:` key is left behind. The shared helper lib/frontmatter_patch.py changed for attachments too, and no CLI-level attach test asserts the key disappears.
- [ ] Board sanity: open `ait board` on a task whose last artifact was just removed and confirm the trail / artifact surfaces render normally now that the key is absent rather than parsing as None.
