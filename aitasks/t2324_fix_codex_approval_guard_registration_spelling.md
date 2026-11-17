---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codex, workflow]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2281
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-17 09:56
updated_at: 2026-11-17 17:21
---

## Origin

Spawned from t2297 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_gate.sh:242 — codex_attended_approvals recognizes only the literal [mcp_servers.aitask_questions] header, so a quoted or dotted-key registration that Codex does start leaves the approval guard off`
- `tests/test_note_with_live_composition.sh:582 — "task-workflow (default|fast) offers /aitask-note exactly once" fails at HEAD: the rendered task-workflow mentions /aitask-note twice since e5f34774a (t1912_3)`
- `tests/test_install_engine_binary.sh — S2/E4 fail at HEAD: goengines/build.sh copies goengines/ci/preflight.sh, which the goengines export (6405506d1) does not ship`

The three defects are unrelated. The first one names this task. The other two were found in the same test sweep and are recorded here so they are not lost; split them out or send them to their owners (t1912 for the /aitask-note double offer, the goengines export for the missing preflight.sh) as you see fit.

## Diagnostic context

- **Approval guard.** t2297 made `ait setup`'s `questions_server_registered` (`.aitask-scripts/aitask_setup.sh`) parse `.codex/config.toml` whenever its literal-header grep misses. The reason is that Codex starts the `aitask_questions` server for every valid TOML spelling: `[mcp_servers."aitask_questions"]`, and a dotted `mcp_servers.aitask_questions.command = "…"` at top level. `aitask_gate.sh`'s `codex_attended_approvals` still does `grep -q '^\[mcp_servers\.aitask_questions\]'`, so for those spellings the server runs and the questions are asked through it, but the approval/receipt guard (gate ledger, reviewed commit, merge, archive) is not active. That is the case `aidocs/codeagents/codex_questions.md` "Gate enforcement → Scope" describes as "registers `[mcp_servers.aitask_questions]`". `ait setup` itself only ever writes the literal spelling, so this matters only for hand-written registrations.
- **/aitask-note double offer.** `tests/test_note_with_live_composition.sh` test 7 renders `.claude/skills/task-workflow/SKILL.md` (claude, profiles default/fast) and expects exactly one `/aitask-note` offer; it counts 2. The source has been clean at HEAD since e5f34774a (t1912_3), so the failure is not caused by t2297. Verified on 2026-11-17 with `skill_template.py .claude/skills/task-workflow/SKILL.md aitasks/metadata/profiles/fast.yaml claude | grep -c /aitask-note` = 2.
- **Engine build test.** `tests/test_install_engine_binary.sh` S2 and E4 build the engine from source; `goengines/build.sh` fails with `cp: cannot stat '…/goengines/ci/preflight.sh'`, and `goengines/ci/` does not exist in the checkout.

## Suggested fix

- Guard: share one parsed registration check between `aitask_setup.sh` and `aitask_gate.sh`, for example a small `lib/` helper with the grep fast path plus the tomllib fallback, and add quoted and dotted-key cases to `tests/test_gate_codex_approvals.sh`.
- The other two: decide whether the second `/aitask-note` mention is intended (then fix the test) or a duplicate (then fix the procedure), and either ship `goengines/ci/preflight.sh` or drop the copy from `build.sh`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-17T15:21:33Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-17T16:39:29Z status=pass attempt=1 type=human
