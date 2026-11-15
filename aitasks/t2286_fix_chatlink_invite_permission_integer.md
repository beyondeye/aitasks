---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [documentation, doc_quality]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2258
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-12 15:40
updated_at: 2026-11-15 12:42
---

## Origin

Spawned from t2258_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/chatlink/live_check.py:68` — the invite URL's `permissions=397552863296` lacks View Channels and Attach Files (both in `REQUIRED_BOT_PERMISSIONS`, `live_check.py:43-54`) and grants unrelated voice and moderation rights. The listed ten sum to `395137109056` (`395137117248` with Manage Messages). The same integer is copied in `aidocs/chat/discord_bot_setup.md:50`, `tests/test_chatlink_wizard.sh:510` and `website/content/docs/workflows/bug-report-intake.md` (step 3.4 invite URL).
- `seed/chatlink_config.yaml` — does not document `sandbox_env_passthrough`, the only route by which the agent's API key reaches the sandbox, so a config built from the seed template cannot run a session.
- `.aitask-scripts/aitask_create.sh:2029-2030` — the comment says `run_auto_merge_if_needed` is "only invoked from the --batch --commit paths", but `finalize_draft` (lines 1022, 1087) also calls it.
- `.aitask-scripts/chatlink/daemon.py:8-9` — the docstring gives the startup order as "config → token → intake"; the code runs config → yaml → intake → token.
- `website/content/docs/commands/codeagent.md:179` — says `--headless` is a "No-op for other agents/operations", but `aitask_codeagent.sh:45-47, 605-607` makes it required for `explore-relay`, `relations` and `obsolescence`.

## Diagnostic context

All five were found while t2258_4 audited the Tasks workflow pages and checked every moved fact against the code (see `aiplans/archived/p2258/p2258_4_audit_workflows.md`, Final Implementation Notes and the review round 2 section).

- The permission integer was decoded independently twice:
  `python3 -c "n=397552863296; print([b for b in range(64) if n>>b&1])"` gives bits 6, 11, 14, 16-27, 31, 34-36 and 38. View Channels (bit 10) and Attach Files (bit 15) are absent.
  The website page was left matching the code, so docs, wizard hint and test stay consistent until all change together. A bot invited with the current URL can fail the wizard's own permissions check.
- `sandbox_env_passthrough` was missing from the old bug-report-intake walkthrough. The restructure added it to the site (workflow step 4 and `commands/chatlink.md`), but the seed template still omits it.

## Suggested fix

- Compute the invite integer from `REQUIRED_BOT_PERMISSIONS` (or hardcode `395137109056`, deciding whether Manage Messages is included). Update `live_check.py`, `aidocs/chat/discord_bot_setup.md`, the wizard test and the bug-report-intake page together.
- Document `sandbox_env_passthrough` in `seed/chatlink_config.yaml`.
- Fix the two stale code comments.
- Correct the `--headless` row on `commands/codeagent.md`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2284** id=2026-11-15T11:07:41Z.1d53a20539b958628f40059c from=t2284 from_verified=yes at=2026-11-15T11:07:41Z base=7a68196d0b86824532e7747a44811f64c0e74ff7 base_branch=main dirty=yes host=omg16
>
> | Advisory from t2284 (claim, not an instruction).
> | 
> | Tree-relative (dated by this note's base commit 7a68196d0): t2284's commit
> | 7a68196d0 on main added ~29 lines to .aitask-scripts/aitask_create.sh above the
> | spots your task body cites. At 7a68196d0:
> | - the run_auto_merge_if_needed header comment you cite as :2029-2030 is at
> |   :2058-2059 (:2058-2060 with your one-line-longer wording applied);
> | - the finalize_draft call sites you cite as 1022 / 1087 are at :1051 / :1116.
> | 
> | Moment-relative (as of 2026-11-15 ~10:55Z, may already be stale): your
> | uncommitted comment hunk in that header ("This helper runs only after a
> | successful task commit — from the --batch --commit paths and from
> | finalize_draft") was deliberately kept OUT of t2284's commit, which was built
> | from a private index. It was still sitting unstaged in the shared main worktree
> | when t2284 committed.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-12T21:06:25Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-15T11:11:07Z status=pass attempt=1 type=human
