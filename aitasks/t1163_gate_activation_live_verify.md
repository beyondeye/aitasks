---
priority: medium
effort: medium
depends: []
issue_type: manual_verification
status: Implementing
labels: [gates, task_workflow, execution_profiles]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
assigned_to: dario-e@beyond-eye.com
anchor: 635
created_at: 2026-07-19 22:28
updated_at: 2026-07-20 10:04
---

## Origin

Risk-mitigation ("after") follow-up for t635_33, created at Step 8d after implementation landed.

## Risk addressed

Code-health: "Wide blast radius across load-bearing enforcement" and "Subtle mis-enforcement failure modes — a single missed read-site silently reintroduces t1147 (wrongful block) or under-enforces (skips a real gate)". Goal-achievement: "Correctness invariant spans many sites + the render layer — 'a filtered gate is invisible everywhere' is only true if every enforcer + the render omission + the materialize safety-valve all agree; partly encoded in markdown/Jinja".

## Goal

Live cross-profile verification of the t635_33 active-gates model through the REAL pick→archive flow (not unit fixtures): a task declaring a profile-filtered gate archives cleanly under a lean profile with no manual gate append, the same declaration is enforced under `fast`, and the board/monitor show the correct active set.

## Checklist

- [x] Pick a fresh throwaway task under the `fast` profile via `/aitask-pick`: Step 4 prints `MATERIALIZED:risk_evaluated` (or NOOP on re-pick) and the task file carries the four `active_gates*` fields with `active_gates_profile: fast` — PASS 2026-07-20 10:03 auto: t1172 fast pick materialized active_gates risk_evaluated with profile fast tuple
- [x] During planning under `fast`, the risk producer runs (a `## Risk` section is authored); `ait gates run` at Step 9 records exactly ONE `risk_evaluated` entry (no double-record with the Step-7 self-record) — PASS 2026-07-20 10:03 auto: t1172 plan included Risk section, should-self-record exited 1, ait gates run recorded one terminal risk_evaluated pass
- [x] Set a throwaway task's frontmatter to `gates: [risk_evaluated]`, pick it under the `default` profile: Step 4 prints `MATERIALIZED:(empty)`, the rendered workflow shows NO risk-producer steps, `aitask_gate.sh archive-ready <id>` prints `NO_GATES`, and the task archives with no manual gate append — PASS 2026-07-20 10:03 auto: t1173 default materialized empty active set, default rendered workflow had no risk producer, archive-ready NO_GATES, archived without gate append
- [x] The same declared task re-picked under `fast` is enforced: `archive-ready` prints `BLOCKED:risk_evaluated` until the gate passes — PASS 2026-07-20 10:03 auto: equivalent t1174 declaration under fast materialized risk_evaluated and archive-ready blocked until ait gates run passed
- [x] An explicit `gates: []` opt-out task picked under `fast` keeps its `gates: []` key after materialization, stays `FRESH`, and never resurrects `risk_evaluated` from the profile defaults — PASS 2026-07-20 10:03 auto: t1175 explicit gates empty list persisted, active-gates-status FRESH with empty active set, archive-ready NO_GATES
- [x] `ait board`: a task with a failed historical run of a profile-filtered gate is NOT classified "failed gate" in the In-Flight view; `ait monitor`'s gate column count excludes the filtered gate — PASS 2026-07-20 10:03 auto: t1176 board manager classified filtered failed gate as agent/resume, not failed gate; monitor GateSummaryCache returned empty summary
- [x] Dependency check: a task whose declared gate was profile-filtered (with `also_blocks_dependents: [risk_evaluated]`) releases its dependents in `ait ls` after archival — PASS 2026-07-20 10:04 auto: t1177 default filtered risk_evaluated also_blocks_dependents; after archival, aitask_ls showed dependent t1178 Ready
