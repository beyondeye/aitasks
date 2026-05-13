---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [website, documentation, modelvrapper]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-13 10:25
updated_at: 2026-05-13 10:31
---

Surface the existing model-refresh workflow in the website docs under an Installation subpage. Today the relevant skill pages exist (`website/content/docs/skills/aitask-refresh-code-models.md` and `aitask-add-model.md`) but they are not discoverable from the Installation section, which is where a new user looking for "how do I refresh the supported-models list?" lands first.

## Context

- Source-of-truth model lists live in `aitasks/metadata/models_<agent>.json` (claudecode, geminicli, codex, opencode) and their `seed/` counterparts.
- The skill `aitask-refresh-code-models` (`.claude/skills/aitask-refresh-code-models/SKILL.md`) handles refreshing all four agents. OpenCode is special-cased to use CLI discovery via `bash .aitask-scripts/aitask_opencode_models.sh` (see SKILL.md lines 46-51); the other three use Claude's `WebSearch`/`WebFetch`.
- `aitask-add-model` registers a single known model and optionally promotes it to default.
- This follow-up was requested by the user during Step 8 review of t770 (refreshing the opencode list); see `aiplans/archived/p770_refresh_opencode_models_and_sync_seed.md` "Final Implementation Notes".

## Existing website assets to reuse

- `website/content/docs/skills/aitask-refresh-code-models.md` — full skill reference
- `website/content/docs/skills/aitask-add-model.md` — single-model registration reference
- `website/content/docs/skills/verified-scores.md` — related context on the `verified` scores preserved by the refresh
- `website/content/docs/installation/_index.md` — landing for the new subpage

## Proposed scope

Add `website/content/docs/installation/updating-model-lists.md` (Hugo/Docsy markdown). Recommended outline:

1. **Why refresh** — vendors release new coding-capable models periodically; the local `aitasks/metadata/models_<agent>.json` files drive the Settings TUI, agent attribution, and stats verified-scores.
2. **One-shot refresh of all agents** — `/aitask-refresh-code-models` walks through claude/codex/gemini (web research) and opencode (CLI discovery). Cross-link the [skill reference](../skills/aitask-refresh-code-models/).
3. **OpenCode-specific quick path** — `bash .aitask-scripts/aitask_opencode_models.sh [--dry-run|--sync-seed]` for users who only need the opencode list. Mention preservation of `verified` scores and the `unavailable` status marker.
4. **Adding a single known model** — cross-link `/aitask-add-model` for users who already know the cli_id and just want to register it.
5. **Where the files live** — `aitasks/metadata/models_<agent>.json` (runtime, on the task-data branch) and `seed/models_<agent>.json` (template for new projects bootstrapped via `ait setup`; only present in the source repo).
6. **Commit conventions** — metadata via `./ait git`, seed via plain `git`, per CLAUDE.md "Git Operations on Task/Plan Files".

Then update `website/content/docs/installation/_index.md` so the new page is discoverable (Hugo/Docsy auto-lists child pages by `weight`; assign a sensible weight to slot it after the platform guides).

## Plan considerations

- Verify the page renders correctly under `cd website && ./serve.sh`.
- Per CLAUDE.md "Documentation Writing": describe the current state only, no version history in doc prose.
- Per CLAUDE.md "ait setup vs ait upgrade": use the verb that matches semantics. Refreshing model lists is neither — say "refresh" or "update". Reserve `ait setup` only if pointing at install/repair flows.
- Cross-link to the existing skill pages rather than duplicating their content. The new page is a navigational/orientation page, not a re-write.

## Out of scope

- Modifying the skill SKILL.md files themselves.
- Changing the model JSON schema or the merge logic in `aitask_opencode_models.sh`.
- Adding CLI-based discovery for the other agents (tracked in t408).
