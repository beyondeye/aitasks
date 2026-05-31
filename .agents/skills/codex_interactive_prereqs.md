# Codex CLI Interactive Skill Prerequisites

These notes apply to interactive Codex CLI skills that use
`request_user_input` for prompts (task confirmation, plan approval, commit and
merge review).

## Interactive prompts work in default mode

`ait setup` enables the `default_mode_request_user_input` feature in the
generated `.codex/config.toml`, so `request_user_input` is available in
Codex's **default mode** — you do not need to be in plan/Suggest mode for
prompts to surface. In default mode the model is steered to prefer assumptions
and ask only when a decision is unavoidable, so treat the framework's
load-bearing checkpoints (plan approval, commit review, merge approval) as
prompts that must not be skipped.

## Plan-mode launches are handled by the wrapper

You do not need to switch modes yourself. When the planning skills
(`aitask-pick`, `aitask-explore`) are launched through `ait codeagent invoke`
or `ait skillrun`, the wrapper starts Codex in plan mode automatically (it
types `/plan` into the composer) — plan mode reliably surfaces those skills'
commit/merge approval prompts and suits their planning phase. The analysis
skills (`aitask-qa`, `aitask-explain`) are launched directly in default mode.
