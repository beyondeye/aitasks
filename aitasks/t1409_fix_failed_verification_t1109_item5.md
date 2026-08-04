---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t635_15]
issue_type: bug
status: Implementing
labels: [verification, bug]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/opus5
created_at: 2026-08-04 13:08
updated_at: 2026-08-04 17:26
---

## Failed verification item from t635_15

> **Stale signature re-pends.** Change a **code** file — not anything under

### Source

- **Manual-verification task:** `aitasks/t1109_async_human_gate_live_verify.md` (item #5)
- **Origin feature task:** t635_15
- **Origin archived plan:** `aiplans/archived/p635/p635_15_async_human_gates.md`

### Commits that introduced the failing behavior

- b4df1ea3f feature: Async human gates — ait gate pass + headless hybrid switch (t635_15)

### Files touched by those commits

- .agents/skills/aitask-pickrem-remote-codex-/SKILL.md
- aidocs/gates/aitask-gate-framework.md
- ait
- .aitask-scripts/aitask_gate_pass.sh
- .aitask-scripts/lib/gate_orchestrator.py
- .claude/skills/aitask-gate-template/SKILL.md
- .claude/skills/aitask-pickrem-remote-/SKILL.md
- .claude/skills/aitask-pickrem/SKILL.md.j2
- .claude/skills/task-workflow/gate-recording.md
- .codex/rules/default.rules
- .opencode/skills/aitask-pickrem-remote-/SKILL.md
- seed/claude_settings.local.json
- seed/codex_rules.default.rules
- seed/opencode_config.seed.json
- tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md
- tests/test_gate_cli_wiring.sh
- tests/test_gate_orchestrator.sh
- tests/test_gate_pass.sh

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1109 item #5.

## Diagnosis (from the t1109 live run, 2026-08-04)

**A recorded `pass` freezes the code-binding: a stale witness is never
re-validated, so code changed after sign-off archives unreviewed.**

`aitasks/metadata/gates.yaml:190-201` documents `review_approved` as code-bound:
"a signature against a different code state re-pends". That holds **only while
the gate's ledger status is non-terminal**. Once a `pass` is recorded, the
witness is never read again:

- `gate_orchestrator.py:470` — `run()` short-circuits with "All gates satisfied"
  when `all(_satisfied(state, g) for g in active)`. `_satisfied` reads the
  **ledger status**, never the witness.
- `gate_orchestrator.py:227` (`compute_unlocked`) — likewise skips any gate that
  is already satisfied, so `_handle_human()` (the only caller of
  `_signal_state()`, which does the digest comparison) is unreachable.

Net effect: `_signal_state`'s `stale` branch can only fire before the first
pass, or via the `--gate <name>` force path (`_force_one`, line 516, which
deliberately overrides skip-already-passed).

### Observed (live, task t1408 under a `rendered_gates: [review_approved]` profile)

| step | command | result |
|---|---|---|
| sign against digest `ade0da54f016ff4c` | `ait gate pass 1408 review_approved` | `pass`, ledger note `signed_digest:ade0da54f016ff4c` |
| change a code file → digest becomes `81c0bebb7d96cc4e` | — | witness still stamped `ade0da54f016ff4c` (stamped-but-wrong, not unstamped) |
| **re-run gates** | `ait gates run 1408` | ❌ `All gates satisfied. Task ready for archive` |
| archival guard | `aitask_gate.sh archive-ready 1408` | ❌ `ALL_PASS` |
| force the same gate | `ait gates run 1408 --gate review_approved` | ✅ `pending — stale signature: signed against ade0da54f016ff4c, code now 81c0bebb7d96cc4e — re-sign with 'ait gate pass'` |
| plain re-run, ledger now `pending` | `ait gates run 1408` | ✅ re-pends with the same note; `archive-ready` → `BLOCKED:review_approved` |

So the stale-detection **logic is correct and its note text matches spec** — it
is the dispatch gating that makes it unreachable at the moment it matters.

### Why this is a real hole, not just a test-ordering artifact

The headless lane's documented completion sequence is: stop at pending → human
signs (`ait gate pass`, which records the pass immediately) → **re-run
`/aitask-pickrem <id>` to archive**. Any code change during that resumed run —
e.g. fixing a machine-gate failure surfaced in the same Step 9.5 — moves the
digest, and nothing re-checks it. The task then archives carrying code the
reviewer never approved, which is precisely what the code-binding exists to
prevent.

### Suggested fix direction (not prescriptive)

Re-validate signal-bearing human gates even when ledger-satisfied: before the
`all(_satisfied(...))` short-circuit, for each active human gate with a
`signal_target`, compare the witness digest to the current one and re-pend on
`stale`. Keep the `unstamped` backward-compatibility acceptance
(`gate_orchestrator.py:406-408,419`) untouched. The same re-validation must
reach `aitask_gate.sh archive-ready`, which independently returned `ALL_PASS`
here — fixing only `gates run` would leave the archival guard permissive.

### Regression test

`tests/test_gate_orchestrator.sh` already covers the pre-pass stale case. Add a
case for the post-pass one: sign → mutate the digest → assert `gates run`
re-pends **and** `archive-ready` reports `BLOCKED`. A negative control must show
the assertion failing against today's code (it currently reports `ALL_PASS`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-04T14:26:39Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-04T15:32:26Z status=pass attempt=1 type=human
