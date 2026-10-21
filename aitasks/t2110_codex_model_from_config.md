---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [codex, frozen, session_persistence]
gates: [risk_evaluated]
anchor: 2040
followup_kind: risk_mitigation
created_at: 2026-10-21 15:32
updated_at: 2026-10-21 15:32
---

## Origin

Risk-mitigation ("after") follow-up for t2077, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — hand-started codex with no -m is cleared to re-pick, not resumable

- A hand-started codex whose argv names no model (the usual way to type it) is cleared to re-pick, not made resumable. The `claude --resume <codex-uuid>` hazard is gone, but resumability for that case needs the model from codex's own config · severity: medium · → mitigation: codex_model_from_config

## Goal

When a live codex's argv names no model, resolve it from codex's own config ($CODEX_HOME/config.toml model, -c model= / --profile in argv) so the freeze can record codex/<model> and a hand-started codex resumes instead of re-picking.

Context from t2077:
- `agent_sessions.codex_observe_pid` returns `cli_id` from the SAME process it
  read the session from (the pane process, or the shell's single foreground
  codex child). Today `cli_id` is the `-m` / `--model` / `--model=` value only.
- `agent_freeze._observe_codex_session` maps `cli_id` via
  `_codex_agent_string`; an empty `cli_id` falls back to a codex label already
  on the record (`_with_remembered_label`), else the observation is
  "unnameable" and `_capture_codex_session` clears a blank-kind record's id.
- Live measurement (t2077): a hand-typed `codex -c tui.alternate_screen=never`
  carries no `-m`; the TUI status line showed the config's model
  ("GPT-6-Astra high").
- Resolution must stay evidence-based: read the model the PROCESS would use
  (its `CODEX_HOME` from `/proc/<pid>/environ`, `-c model=…`, `--profile`
  selecting a `[profiles.<name>] model`), and only accept an exact
  `AGENT_STRING:` match from `aitask_resolve_detected_agent.sh`. A `/model`
  switch inside the TUI is not visible this way — document that limitation,
  or find positive evidence (e.g. the rollout's turn context) before trusting
  config over runtime.
