---
Task: t701_whitelist_add_model_refresh_code_models_helpers.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

# Plan for t701: Whitelist add_model / refresh_code_models helpers

## Outcome: No-op archival

After investigation, both halves of t701 are already resolved by previously
landed work or were based on a non-existent script.

## Investigation

### `aitask_add_model.sh` — already whitelisted

`./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_add_model.sh`
returns empty (no `MISSING:` lines). Coverage exists across all 7 touchpoints:

1. `.claude/settings.local.json` — `Bash(./.aitask-scripts/aitask_add_model.sh:*)`
2. `.gemini/policies/aitasks-whitelist.toml` — commandPrefix rule
3. `.codex/rules/default.rules` — prefix_rule allow
4. `seed/claude_settings.local.json` — mirror of #1
5. `seed/geminicli_policies/aitasks-whitelist.toml` — mirror of #2
6. `seed/codex_rules.default.rules` — mirror of #3
7. `seed/opencode_config.seed.json` — bash permission entry

Touchpoints 1, 2, 4, 5, 7 were added in commit `cec464cd` (t802 "add codex
rules allowlist support"), which also introduced the new touchpoints 3 and 6
(`.codex/rules/default.rules` and its seed). t802 thus closed the gap t701
was filed to address.

### `aitask_refresh_code_models.sh` — does not exist

No helper script by this name exists in `.aitask-scripts/`. The
`aitask-refresh-code-models` *skill* (under `.claude/skills/`) is the actual
artifact; it invokes `./.aitask-scripts/aitask_opencode_models.sh` for the
OpenCode discovery path and otherwise uses WebSearch/WebFetch.

`./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist
aitask_opencode_models.sh` returns empty — that helper is also fully
whitelisted across all 7 touchpoints.

The reference in `aiplans/archived/p770_*.md` to `aitask_refresh_code_models.sh`
appears to have been speculative naming; no such script was ever created
(presumably because the refresh workflow lives in the skill prose itself,
not in a single shell entrypoint).

## Changes made

None. No source-tree edits were necessary.

## Final Implementation Notes

- **Actual work done:** Audit-only confirmation. Ran
  `aitask_audit_wrappers.sh audit-helper-whitelist` against both
  `aitask_add_model.sh` and `aitask_opencode_models.sh` (the closest real
  script to the fictional `aitask_refresh_code_models.sh`). Both return zero
  `MISSING:` lines.
- **Deviations from plan:** The original task scope assumed a 0/5 gap for
  both helpers. The gap for `aitask_add_model.sh` was closed by t802. The
  gap for `aitask_refresh_code_models.sh` cannot exist because the script
  does not exist.
- **Issues encountered:** None — investigation was bounded.
- **Key decisions:** With user confirmation, archive as a no-op rather than
  abort. Recording the audit results in this plan so future readers do not
  re-spawn the same task.
- **Upstream defects identified:** None.
