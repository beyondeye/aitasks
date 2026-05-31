---
priority: medium
effort: medium
depends: [862]
issue_type: chore
status: Ready
labels: [codexcli]
created_at: 2026-05-31 10:38
updated_at: 2026-05-31 10:38
---

Follow-up to t862 (Codex caveats docs update).

t861 enabled the `default_mode_request_user_input` feature flag in the
`ait setup`-generated Codex config (`seed/codex_config.seed.toml` →
`.codex/config.toml`), which is meant to make `request_user_input` available
in Codex's **default mode** (not only plan/Suggest mode). t861 deliberately
deferred verifying this end-to-end and left the framework's forced plan-mode
handling in place. t862 updated the website caveats positively but added an
"under review" hedge pending this investigation.

Investigate whether the forced plan-mode handling is still needed:

1. **Smoke test:** Launch Codex (via `ait codeagent invoke` and directly with
   `$aitask-*`) and attempt an interactive `request_user_input` prompt in
   **default mode** (NOT plan mode). Confirm whether prompts actually work with
   `default_mode_request_user_input = true`.
2. **Research:** Check Codex CLI docs and GitHub issues about
   `default_mode_request_user_input` / `request_user_input` availability and
   stability (it is an under-development feature flag, so behavior may change).

If verified that prompts work in default mode, evaluate removing/relaxing the
special handling:
- `.aitask-scripts/aitask_codeagent.sh` and `.aitask-scripts/aitask_skillrun.sh`
  — the `aitask_codex_plan_invoke.py` launch path for `pick`/`explain`/`qa`/`explore`.
- `.aitask-scripts/aitask_codex_plan_invoke.py` — the PTY helper that types
  `/plan <prompt>` to force plan-mode entry.
- `.agents/skills/codex_interactive_prereqs.md` — the "Plan Mode Required / STOP
  if not in plan mode" enforcement embedded in rendered Codex skill bodies.

Consider keeping forced plan mode only for skills that do genuine planning
(`aitask-pick`, `aitask-explore`), where plan mode is desirable for its own
sake, while dropping it for others (`qa`, `explain`).

On the final decision, update `website/content/docs/commands/codeagent.md` and
`website/content/docs/installation/known-issues.md` to remove the "under review"
hedge that t862 added.
