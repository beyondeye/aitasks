---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Done
labels: [backend]
created_at: 2026-07-25 23:29
updated_at: 2026-07-25 23:30
completed_at: 2026-07-25 23:30
---

Follow-up to t1241. Promote `claudecode/sonnet5` (registered in t1241) to the
operational default for every op currently defaulting to `sonnet4_6`, in BOTH
live (`aitasks/metadata/codeagent_config.json`) and seed
(`seed/codeagent_config.json`).

Ops (live): explain, work-report, batch-review, qa, raw, brainstorm-comparator,
brainstorm-initializer. Seed has the first five (brainstorm-* absent → helper
skips them). Use `aitask_add_model.sh promote-config --name sonnet5`.

Also sync the manual-review surface: website defaults table + qa-default prose
(`codeagent.md`, `codebrowser/how-to.md`), and default-sensitive tests
(`test_codeagent.sh` Test 28 resolve-explain, `test_brainstorm_crew.py`
comparator/initializer fixtures + assertion). Leave `sonnet4_6` registered
(still a valid model) and leave incidental example args (crew.md) untouched.
