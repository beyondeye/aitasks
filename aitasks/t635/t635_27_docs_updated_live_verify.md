---
priority: medium
effort: low
depends: [t635_19]
issue_type: manual_verification
status: Implementing
labels: [gates]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
assigned_to: dario-e@beyond-eye.com
anchor: 635
created_at: 2026-07-01 10:45
updated_at: 2026-07-27 08:15
---

## Context

Live end-to-end verification of the `docs_updated` procedure-backed gate shipped
in t635_19. The gate's value rests on the agent skill's inference + user
confirmation, which unit tests cannot exercise. This autonomous
manual-verification drives the whole flow against a real task.

## Verification checklist

- [x] Declare `gates: [docs_updated]` on a scratch/real task and confirm `ait gates run <id>` reports it **needs agent** (deferred, no shell exec, exit 0). — PASS 2026-07-26 17:07 auto: ait gates run 1252 (real task, gates:[docs_updated]) => 'docs_updated: needs agent (procedure-backed gate)', rc=0, zero ledger appends, no .aitask-gates/1252 log dir; procedure-gates lists it, archive-ready BLOCKED:docs_updated
- [x] Run task-workflow Step 8: `procedure-gates` lists it; `begin-procedure` opens a running block + prints RUN_ID/ATTEMPT; the `aitask-gate-docs-updated` skill fires, inspects the change, infers the right doc page (e.g. a TUI/skill change → the matching `website/content/docs/...` page), **confirms with the user**, applies, and appends `pass` via `append --only-if-running`. — PASS 2026-07-26 17:23 auto: full Step 8 dispatch on t1252. procedure-gates listed docs_updated; begin-procedure printed RUN_ID:2026-07-26T14:08:53Z ATTEMPT:1 and opened the running block; skill read the configured guide, gathered the change surface (aitask_lock.sh new --count subcommand), applied the map rule 'ait subcommand -> commands/' to infer website/content/docs/commands/lock.md, confirmed via AskUserQuestion (Apply), applied the table row, appended pass via append --only-if-running. Derived status=pass, archive-ready ALL_PASS, procedure-gates now empty. Negative control: repeat --only-if-running append with same run-id no-opped (rc=0, no second block)
- [x] The `_index.md` manual-list rule: a NEW `workflows/*.md` page without its `_index.md` bullet is flagged. — PASS 2026-07-26 17:35 auto: t1253 run 2026-07-26T14:24:10Z. Created NEW website/content/docs/workflows/scratch-gate-probe.md with no _index.md bullet. The configured guide (aitasks/metadata/doc_update_guide.md) carries BOTH the map row (line 34) and the 'Known footgun' section (line 36); following the skill the missing bullet was flagged, surfaced in the user confirmation, and fixed. archive-ready ALL_PASS
- [x] No-docs-needed change → skill records **`skip`** (not pass); `archive-ready` still `ALL_PASS`. — PASS 2026-07-26 17:44 auto: t1254 test-only change (tests/test_scratch_gate_probe.sh). Skill recorded skip via append --only-if-running; ledger marker is the distinct skip glyph, derived status='skip' NOT pass, grep status=pass returns 0. archive-ready=ALL_PASS and procedure-gates empty => skip is terminal-satisfied and unblocks archival while staying distinct from pass
- [x] User-rejected doc work → `fail`; archival BLOCKED until resolved. — PASS 2026-07-27 08:15 auto: t1255. Doc-warranted change (ait lock --count example); user chose Reject at the confirmation => skill recorded fail. archive-ready=BLOCKED:docs_updated and aitask_archive.sh 1255 exited 2 (GATE_PENDING/GATE_BLOCKED), task not archived. 'Until resolved' half also verified: gate stayed listed in procedure-gates after fail, re-dispatch applied the doc fix and recorded pass, after which status=pass, archive-ready=ALL_PASS and procedure-gates empty. NOTE: begin-procedure reported ATTEMPT 1->3->5 (see plan Upstream defects)
- [x] Archive fail-safe: a declared-but-unrun `docs_updated` blocks archival. — PASS 2026-07-26 17:23 auto: t1253 declared gates:[docs_updated] with an EMPTY ledger (0 gate markers, never run). archive-ready=BLOCKED:docs_updated; aitask_archive.sh 1253 exited 2 printing GATE_PENDING:docs_updated + GATE_BLOCKED; task file stayed in aitasks/ and was NOT moved to aitasks/archived/. Override escape hatch --ignore-gates documented in the refusal message

## Notes
Coordinate: runs after t635_19 landed the gate. The **docs_updated_activation**
follow-up (**t635_28**) depends on THIS task passing.
