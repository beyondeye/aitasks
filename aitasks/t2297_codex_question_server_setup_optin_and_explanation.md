---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [codex, workflow]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2281
implemented_with: claudecode/opus5_5
created_at: 2026-11-13 14:20
updated_at: 2026-11-16 18:11
---

## Origin

Follow-up to t2281 (Codex workflow questions through the `aitask_questions` MCP server), requested by the user after it was archived.

## Problem

`ait setup` installs the question server as a silent part of the existing "Install Codex CLI skills and config? [Y/n]" prompt:

- Saying yes merges the `[mcp_servers.aitask_questions]` table from `seed/codex_config.seed.toml` into `.codex/config.toml`, and `main()` then runs `setup_questions_deps`, which pip-installs `mcp` (`AIT_PIP_SPECS_QUESTIONS`) into the framework venv whenever `questions_server_registered` is true.
- The only explanation is three `info` lines printed before that prompt in `setup_codex_cli`. There is no separate choice, no flag, and no way to take the Codex skills without the server (or to remove it later) other than editing `.codex/config.toml` by hand.
- What the server changes for the user is not explained at the prompt: forms instead of the built-in prompt, the five-minute timeout and answer-at-the-prompt recovery, and the approval enforcement that only applies to attended Codex sessions with the server registered (gate ledger, reviewed commit, merge, archive guards).

## Goal

Make the question server an explicit, explained choice in `ait setup`.

- Give it its own opt-in, consistent with the existing tiers (`--with-chat`, `--with-dev`, `--with-pypy`): decide between a dedicated Y/n prompt inside Codex setup, a flag, or both, and how the choice is remembered so later plain `ait setup` runs revalidate and repair it (today the registration in `.codex/config.toml` is the marker).
- Explain at the prompt, in a few plain lines, what the server does, what it installs (`mcp` into the venv), that Codex must be restarted, and what happens without it (questions asked in plain text; approval enforcement not active).
- Define the opt-out path: declining leaves no registration and installs nothing; decide whether setup offers to remove an existing registration.
- Non-interactive runs (`--yes`, no terminal) need a defined default.
- Keep `default_mode_request_user_input = true` in the seed (user decision, 2026-11-13).

## Touchpoints

- `.aitask-scripts/aitask_setup.sh`: `setup_codex_cli`, `questions_server_registered`, `setup_questions_deps`, the call in `main()`, usage text.
- `seed/codex_config.seed.toml`.
- `tests/test_setup_questions_server.sh`, `tests/test_setup_agent_config_seeds.sh`.
- Website: `installation/_index.md` ("Optional: Codex CLI support"), `commands/setup-install.md` (Python venv step and tiers), `installation/known-issues.md`.
- `aidocs/codeagents/codex_questions.md`; read `aidocs/framework/aitasks_extension_points.md` before editing the install flow.

## Notes

- Tests must never reach a real `~/.aitask`: `setup_questions_deps` is deliberately called from `main()` and not from `setup_codex_cli`, so driving the Codex setup function directly can never run pip against a real venv. Keep that property.
- The approval enforcement keys on the registration plus `CODEX_THREAD_ID`; an opt-out therefore also switches enforcement off. State that in the explanation rather than hiding it.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-16T16:11:28Z status=pass attempt=1 type=human
