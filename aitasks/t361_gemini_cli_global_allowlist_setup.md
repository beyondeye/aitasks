---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [geminicli]
created_at: 2026-03-10 12:13
updated_at: 2026-03-10 12:13
---

Per-project Gemini CLI policy files (.gemini/policies/*.toml) are not applied by the CLI despite being referenced in settings.json via policyPaths. Global-level policies (~/.gemini/policies/) do work correctly.

The ait setup command should install the aitasks allowlist to the global policy directory (~/.gemini/policies/aitasks-whitelist.toml) as part of Gemini CLI setup, so users do not need to manually copy the file.

Steps:
1. In the Gemini CLI setup section of ait setup (or the install script), copy .gemini/policies/aitasks-whitelist.toml to ~/.gemini/policies/aitasks-whitelist.toml
2. Create ~/.gemini/policies/ directory if it does not exist
3. If a global policy file already exists, merge or warn rather than overwriting
4. Update the Known Issues page to note the fix once implemented

Related: t356 (documented this issue)
