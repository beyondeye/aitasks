---
priority: medium
effort: medium
depends: [1981_2, 1981_4]
issue_type: manual_verification
status: Ready
labels: [task_relations, task-workflow, skills]
anchor: 1981
followup_kind: risk_mitigation
created_at: 2026-11-08 15:26
updated_at: 2026-11-08 15:26
---

## Origin

Risk-mitigation ("after") follow-up for t1981_5, created at Step 8d after implementation landed.

## Risk addressed

unlanded t1981_4/t1981_2 dependencies leave the complete-path flow fixture-only

- **Dependencies that have not landed.** t1981_4 provides `relations_expected_plan` and t1981_2 provides the static fallback. Until both land, an enabled Step 8e always reads `unverifiable(no_expected_identity)` and the fallback is "unavailable", so the complete-path push flow is exercised only by fixtures, not end to end in a real session · severity: medium · → mitigation: relations_consumption_live_verification

## Goal

Once t1981_4 (triggers: the Step 7 `stamp` call that sets `relations_expected_plan`) and t1981_2 (the candidate generator with `--fallback-push`) have landed, verify t1981_5's consumer flow end to end in a real session, in a scratch project with relations analysis **enabled** (`ait relations enable`), not only through the fixtures in `tests/test_relations_consume.py`.

Checklist:
- Pick-time check (task-workflow Step 3 Check 8): a Ready task with stored relations shows `SUMMARY:` verbatim, at most 8 items with direction, freshness and (for landed tasks) confirmation and the archived plan path; `related_work` reaches planning.
- Step 8 re-check: a relation published after the pick shows as `late`; one whose source already sent a note is marked "covered by note <id>".
- Step 8e complete path: after a real plan approval (stamp written by t1981_4's Step 7), `analysis-state --expect-plan <relations_expected_plan>` reads `complete`; `notify-candidates` produces a PUSH row for an in-flight target that still cites a basis the diff touched; the multi-select offer appears; a selected row is sent through `/aitask-note` using `NOTE_TARGET:` and recorded with `notify-outcome ... --outcome sent --note-id <id>`.
- Step 8e incomplete paths: "Run analysis now and wait" (including the cap's second confirmation and `--over-cap`), "Static discovery fallback" with real `UNCONFIRMED:` rows from t1981_2, and "Proceed with what exists"; none is ever worded "no affected targets".
- `/aitask-note` with no target lists the sender's open related tasks first, then falls back to Related Task Discovery.
- `ait relations ledgers --export` shows the `pull` and `notify` rows written by the above.
