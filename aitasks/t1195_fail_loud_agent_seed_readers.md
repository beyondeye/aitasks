---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [codexcli, codeagent]
gates: [risk_evaluated]
anchor: 1171
created_at: 2026-07-20 23:15
updated_at: 2026-07-20 23:15
---

## Origin

Risk-mitigation ("after") follow-up for t1185, created at Step 8d after
implementation landed.

## Risk addressed

- addresses: code-health — silent no-op defect class
- `The reader sites left unchanged by this task still skip silently when a seed is absent, which is what let this bug pass setup undetected in the first place. · severity: low`

## Goal

t1185 fixed the *supply* side (seeds now get populated into
`aitasks/metadata/` on every `ait setup`) but deliberately left the *reader*
side unchanged. Four readers in `.aitask-scripts/aitask_setup.sh` still treat a
missing seed as a silent no-op:

- `:2067` — `codex_config.seed.toml` (`setup_codex_cli`)
- `:2081` — `codex_rules.default.rules` (`setup_codex_cli`)
- `:2218` — `opencode_config.seed.json` (`setup_opencode`)
- `:1807` — `claude_settings.seed.json`

(Line numbers are pre-t1185; re-locate them in the current source rather than
trusting these offsets — t1185 inserted ~59 lines earlier in the file.)

Each is wrapped in `if [[ -f "$seed" ]]` with no `else`. When the file is
absent, setup completes and reports success while silently skipping the merge.
That is precisely how t1180's failure went undetected: `ait setup` said it
succeeded, but `.codex/config.toml` never gained
`default_mode_request_user_input = true`.

Convert these silent skips into visible warnings so the next occurrence of this
defect class self-reports. Follow the existing wording precedent in the same
file — `ensure_project_config_defaults()` (`:1568`) and
`ensure_chatlink_config()` (`:1619`) both warn with "X is missing from
aitasks/metadata/ and no seed template is available." plus a remediation hint
pointing at `ait setup` (note the CLAUDE.md verb rule: "populate-missing" →
`ait setup`, not `ait upgrade`).

Keep the behavior non-fatal — warn and continue, do not abort setup. A missing
optional agent seed should not take down an otherwise good install.

## Verification

- With the seed absent, setup emits a warning naming the missing file and still
  exits 0.
- With the seed present, no warning is emitted (assert the negative — a warning
  that always fires is noise, not a signal).
- Existing suites still pass: `tests/test_setup_agent_config_seeds.sh`,
  `tests/test_agent_instructions.sh`, `tests/test_opencode_setup.sh`.
