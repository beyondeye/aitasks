---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Folded
labels: [claudeskills]
folded_into: 691
created_at: 2026-04-28 00:08
updated_at: 2026-04-28 08:35
boardidx: 40
---

Spawned from t679 during planning. Two skills added to `.claude/skills/` (the source of truth) were never propagated to the other agent trees, per the CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" rule that says cross-agent ports should be tracked as separate tasks.

## Cross-agent skill gap

| Skill | `.claude/skills` | `.opencode/skills` | `.agents/skills` (codex) | `.opencode/commands` | `.gemini/commands` | gemini policy `activate_skill` |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `aitask-add-model` | YES | — | — | — | — | — |
| `aitask-qa` | YES | YES | YES | — | YES | — |
| (other 20 `aitask-*`) | YES | YES | YES | YES | YES | YES |

Note: `.gemini/skills/` is intentionally empty (consolidated into `.agents/skills/` per `tests/test_gemini_setup.sh:41`).

## Touchpoints to add

### `aitask-add-model` (missing from every non-claude tree)

- `.opencode/skills/aitask-add-model/SKILL.md` — adapt from `.claude/skills/aitask-add-model/SKILL.md`.
- `.opencode/commands/aitask-add-model.md` — mirror existing wrappers (e.g. `.opencode/commands/aitask-create.md`).
- `.agents/skills/aitask-add-model/SKILL.md` — adapt from `.claude/skills/aitask-add-model/SKILL.md`.
- `.gemini/commands/aitask-add-model.toml` — mirror existing toml wrappers.
- `seed/geminicli_policies/aitasks-whitelist.toml` — add a `[[rule]]` block:
  ```toml
  [[rule]]
  toolName = "activate_skill"
  argsPattern = "aitask-add-model"
  decision = "allow"
  priority = 100
  ```
  Insert at the alphabetical position between `argsPattern = "aitask-changelog"` and `argsPattern = "aitask-contribute"`.

### `aitask-qa` (missing from opencode commands and gemini policy)

- `.opencode/commands/aitask-qa.md` — mirror existing wrappers.
- `seed/geminicli_policies/aitasks-whitelist.toml` — add a `[[rule]]` block for `argsPattern = "aitask-qa"` between `aitask-pr-import` and `aitask-refresh-code-models` (or wherever alphabetical).

The opencode skill, codex skill, and gemini command for `aitask-qa` already exist.

## Whitelisting touchpoints

Verify any helper-script paths inside the new SKILL.md files are already whitelisted across all five touchpoints listed in CLAUDE.md "Adding a New Helper Script". For these two skills, no new helper scripts should be needed — just wrappers around existing helpers.

## Verification

After the wrappers are added:

```bash
bash tests/test_opencode_setup.sh   # expect counts to grow by 2 (skill + command)
bash tests/test_gemini_setup.sh     # expect activate_skill count to grow by 2
```

Both tests now use dynamic counts (committed in t679), so the assertions self-adjust — no test edits needed.

Spot-check the new entries are present:

```bash
ls -d .opencode/skills/aitask-add-model .agents/skills/aitask-add-model
ls .opencode/commands/aitask-add-model.md .opencode/commands/aitask-qa.md
ls .gemini/commands/aitask-add-model.toml
grep -c '^toolName = "activate_skill"$' seed/geminicli_policies/aitasks-whitelist.toml   # was 20, expect 22
```
