---
Task: t802_add_codex_rules_allowlist_support.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Updated aitasks to treat current Codex CLI `.rules` files as a first-class helper allowlist mechanism. The prior framework assumption was that Codex could only prompt or forbid commands, but current Codex supports `prefix_rule(... decision = "allow")`, so trusted aitasks helper scripts can be allowlisted like the existing Claude, Gemini, and OpenCode touchpoints.

## Files Modified

- `.aitask-scripts/aitask_audit_wrappers.sh`: expanded helper whitelist auditing from five to seven touchpoints, adding runtime and seed Codex rules files. Added Codex rule presence checks and insertion support.
- `.aitask-scripts/aitask_setup.sh`: added merge support for `.codex/rules/default.rules`, preserving user-authored rules while appending missing aitasks helper rules from the seed.
- `install.sh`: stores the Codex rules seed under `aitasks/metadata/` during framework install.
- `.codex/rules/default.rules` and `seed/codex_rules.default.rules`: added allow rules for trusted `.aitask-scripts/aitask_*.sh` helpers.
- `.codex/config.toml` and `seed/codex_config.seed.toml`: replaced stale comments that said Codex could not pre-approve commands with pointers to the `.rules` file.
- Claude, Gemini, and OpenCode permission files: added the missing `aitask_add_model.sh` helper discovered by the expanded audit.
- Tests: updated Codex setup coverage, helper whitelist assertions, and the stale verifier baseline expectation.
- Documentation: updated extension-point guidance, audit-wrapper docs, install docs, and release copy to describe seven helper permission touchpoints and Codex `.rules` allowlists.

## Probable User Intent

The goal was to remove repeated Codex approval prompts for trusted aitasks skill bootstrap helpers, especially `aitask_skill_resolve_profile.sh` and `aitask_skill_render.sh`, after confirming that recent Codex CLI versions support allow rules. The implementation aligns the framework with current OpenAI Codex behavior while preserving existing user rules and maintaining parity across supported code agents.

## Final Implementation Notes

- **Actual work done:** Added Codex runtime and seed rules files, integrated them into setup/install/audit flows, updated docs and tests, and filled the newly exposed `aitask_add_model.sh` helper allowlist gap across all audited touchpoints.
- **Deviations from plan:** N/A (retroactive wrap - no prior plan existed).
- **Issues encountered:** `tests/test_skill_verify.sh` had a stale baseline that expected no `.j2` templates in the repository; it was updated to assert the current healthy verifier output.
- **Key decisions:** Kept Codex allow rules in `.rules` files rather than `.codex/config.toml`, matching current Codex documentation. Merge behavior appends missing aitasks rules and preserves existing user-authored rules.
- **Verification:** Ran `bash tests/test_agent_instructions.sh`, `bash tests/test_skill_render.sh`, `bash tests/test_skill_verify.sh`, `bash -n` on the updated shell scripts, helper whitelist audit, and `codex execpolicy check` against runtime and seed rules.
