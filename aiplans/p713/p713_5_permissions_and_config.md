---
Task: t713_5_permissions_and_config.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_1_*.md, aitasks/t713/t713_2_*.md, aitasks/t713/t713_3_*.md, aitasks/t713/t713_4_*.md, aitasks/t713/t713_6_*.md, aitasks/t713/t713_7_*.md
Archived Sibling Plans: aiplans/archived/p713/p713_*_*.md
Worktree: .
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 15:30
---

## Context

Parent t713 introduces `.aitask-scripts/aitask_syncer.sh` (already on disk; sibling
t713_2 is Done) plus the `tmux.syncer.autostart` config key (already wired into
`aitask_ide.sh:read_syncer_autostart` and
`agent_launch_utils.py:load_tmux_defaults`, both defaulting to `False`).

What is missing is the per-agent permission whitelist coverage and the
seed-level documentation for the new config key. Without these, every code
agent except Codex will prompt the user before invoking `aitask_syncer.sh`,
and fresh installs will have no in-tree documentation explaining the new key.
This child closes those gaps.

The runtime `aitasks/metadata/project_config.yaml` deliberately stays unchanged
because the loaders already default to `false` — adding the key would only
add noise. Verification step 5 (no runtime TUI auto-commit/push of project
config) is verified up-front and just needs to be re-confirmed at
implementation time.

## Verified state of the repo (verify-mode read, 2026-04-30)

- `.aitask-scripts/aitask_syncer.sh` exists.
- None of the 5 whitelist touchpoints reference `aitask_syncer.sh`.
- `aitask_sync.sh` (the existing analog) is the right pattern reference and
  is alphabetically adjacent to the slot where `aitask_syncer.sh` belongs in
  every touchpoint (`sync` < `syncer` < `update`/`zip_old`).
- `seed/project_config.yaml` `tmux:` block has a documented `git_tui:` entry
  and a commented-out `monitor:` example — natural place to insert a
  documented `syncer:` block.
- `aitask_ide.sh` and `agent_launch_utils.py` already default
  `syncer.autostart` to false; runtime project_config.yaml needs no change.
- `settings_app.py` `save_project_settings()` → `save_yaml_config()` writes
  YAML only; no `git commit`/`git push` calls → verification step 5 holds.

## Key Files to Modify (with concrete insertion anchors)

1. **`.claude/settings.local.json`** — runtime Claude whitelist.
   - Insert after line 71 (`"Bash(./.aitask-scripts/aitask_sync.sh:*)",`):
     ```json
     "Bash(./.aitask-scripts/aitask_syncer.sh:*)",
     ```

2. **`.gemini/policies/aitasks-whitelist.toml`** — runtime Gemini whitelist.
   - Insert a new `[[rule]]` block immediately after the existing
     `aitask_sync.sh` rule (ends line 425) and before the `aitask_zip_old.sh`
     rule (starts line 427):
     ```toml
     [[rule]]
     toolName = "run_shell_command"
     commandPrefix = "./.aitask-scripts/aitask_syncer.sh"
     decision = "allow"
     priority = 100
     ```

3. **`seed/claude_settings.local.json`** — seed Claude whitelist.
   - Insert after line 75 (`"Bash(./.aitask-scripts/aitask_sync.sh:*)",`),
     before line 76 (`"Bash(./.aitask-scripts/aitask_update.sh:*)",`):
     ```json
     "Bash(./.aitask-scripts/aitask_syncer.sh:*)",
     ```

4. **`seed/geminicli_policies/aitasks-whitelist.toml`** — seed Gemini whitelist.
   - Insert a new `[[rule]]` block after the existing `aitask_sync.sh` rule
     (ends line 395) and before the `aitask_zip_old.sh` rule (starts line 397):
     ```toml
     [[rule]]
     toolName = "run_shell_command"
     commandPrefix = "./.aitask-scripts/aitask_syncer.sh"
     decision = "allow"
     priority = 100
     ```

5. **`seed/opencode_config.seed.json`** — seed OpenCode whitelist.
   - Insert after line 64 (`"./.aitask-scripts/aitask_sync.sh *": "allow",`),
     before line 65 (`"./.aitask-scripts/aitask_update.sh *": "allow",`):
     ```json
     "./.aitask-scripts/aitask_syncer.sh *": "allow",
     ```

6. **`seed/project_config.yaml`** — document `tmux.syncer.autostart`.
   - Insert a new documentation block under the `tmux:` map, between the
     `git_tui:` block (ends ~line 210) and the commented-out `monitor:`
     example (starts ~line 212). Use the same `# ──...` separator style as
     surrounding blocks. Example body:
     ```yaml
       # ──────────────────────────────────────────────────────────────────
       # syncer.autostart — Auto-launch the syncer TUI as part of `ait ide`.
       #
       # When `true`, `ait ide` opens (or focuses) a singleton `syncer`
       # window inside the project's tmux session — alongside the monitor
       # window that `ait ide` already starts.
       #
       # The syncer TUI tracks remote desync state for the project's
       # tracked refs (`main`, `aitask-data`) and offers pull/push actions.
       # See `ait syncer` to launch it manually at any time.
       #
       # Default: false (omit, leave blank, or set explicitly to false).
       # ──────────────────────────────────────────────────────────────────
       syncer:
         autostart: false
     ```

## Files explicitly NOT to modify

- `.codex/config.toml` and `seed/codex_config.seed.toml` — Codex uses a
  prompt/forbidden-only permission model (CLAUDE.md "Adding a New Helper
  Script" → Codex exception). No allowlist entry is added.
- `aitasks/metadata/project_config.yaml` — runtime project config; loader
  defaults handle the missing key (`aitask_ide.sh:read_syncer_autostart`
  returns `0`, `load_tmux_defaults` returns `False`). Adding it would create
  noise without changing behavior.

## Reference patterns

- `aitask_sync.sh` entries in each of the 5 touchpoints — copy the exact
  shape, just swap `sync` → `syncer`. Specifically:
  - `.claude/settings.local.json:71`
  - `.gemini/policies/aitasks-whitelist.toml:421-425`
  - `seed/claude_settings.local.json:75`
  - `seed/geminicli_policies/aitasks-whitelist.toml:391-395`
  - `seed/opencode_config.seed.json:64`
- `seed/project_config.yaml` `git_tui:` documentation block (lines ~192-210):
  style reference for the new `syncer:` block — `# ──...` ruler, prose
  description, default value statement, terminating ruler.

## Implementation Steps

1. Edit each of the 5 whitelist files using the anchors above. Maintain
   alphabetical ordering (every existing list keeps `aitask_sync` immediately
   before `aitask_syncer` and `aitask_syncer` before the next entry).
2. Edit `seed/project_config.yaml` to insert the documented `syncer:` block
   under `tmux:` between `git_tui:` and the commented `monitor:` example.
3. Re-confirm verification step 5 by re-reading
   `.aitask-scripts/settings/settings_app.py:save_project_settings` and
   `.aitask-scripts/lib/config_utils.py:save_yaml_config` — both must remain
   pure YAML/JSON writers with no `subprocess.run(["git", ...])` or
   `./ait git` invocations.

## Verification

Quick checks (run from repo root):

```bash
# Touchpoint coverage — must print 5 hits, one per file:
grep -l "aitask_syncer.sh" \
  .claude/settings.local.json \
  .gemini/policies/aitasks-whitelist.toml \
  seed/claude_settings.local.json \
  seed/geminicli_policies/aitasks-whitelist.toml \
  seed/opencode_config.seed.json

# JSON syntax (Claude + OpenCode files):
python3 -m json.tool .claude/settings.local.json > /dev/null
python3 -m json.tool seed/claude_settings.local.json > /dev/null
python3 -m json.tool seed/opencode_config.seed.json > /dev/null

# TOML syntax (Gemini files):
python3 -c 'import tomllib,sys; tomllib.load(open(".gemini/policies/aitasks-whitelist.toml","rb"))'
python3 -c 'import tomllib,sys; tomllib.load(open("seed/geminicli_policies/aitasks-whitelist.toml","rb"))'

# YAML syntax (seed project config):
python3 -c 'import yaml; yaml.safe_load(open("seed/project_config.yaml"))'

# Confirm syncer.autostart documented in seed:
grep -n "syncer.autostart\|^  syncer:" seed/project_config.yaml
```

Manual confirmation:

- Re-read `aitask_ide.sh:read_syncer_autostart` and confirm a
  `tmux.syncer.autostart`-less `aitasks/metadata/project_config.yaml` still
  yields `0`/false (it does — `awk` returns no output → `[[ -z "$out" ]]
  && out="0"`).
- Re-read `agent_launch_utils.py:load_tmux_defaults` and confirm the
  `defaults["syncer_autostart"]` initial value is `False` (it is, line 702).

Step 9 (Post-Implementation): standard archival flow.

## Final Implementation Notes

- **Actual work done:** Implemented the plan exactly as written. Six files
  modified: 5 whitelist touchpoints gained one `aitask_syncer.sh` entry each
  (alphabetical position between `aitask_sync` and the next entry), and
  `seed/project_config.yaml` gained a documented `tmux.syncer:` block (with
  prose explanation of `autostart`, an example showing `true`, and the
  default-false stance) inserted between `git_tui:` and the
  commented-out `monitor:` example. Total: +36 lines, -0 lines.
- **Deviations from plan:** None. The plan's anchors (line numbers + before/
  after entries) matched the runtime files exactly.
- **Issues encountered:** None.
- **Key decisions:**
  - Followed CLAUDE.md "Adding a New Helper Script" 5-touchpoint rule
    verbatim — no Codex allowlist entry (Codex prompt/forbidden model).
  - Kept the documented `syncer:` block commented-out in `seed/project_config.yaml`
    so it is purely documentation in fresh installs (matches the pattern
    used by the adjacent `monitor:` example block); loader defaults handle
    the absent key as `false`.
  - Did not modify runtime `aitasks/metadata/project_config.yaml` — both
    `aitask_ide.sh:read_syncer_autostart` and
    `agent_launch_utils.py:load_tmux_defaults` already default to false.
  - Verification step 5 confirmed by re-reading
    `.aitask-scripts/settings/settings_app.py:save_project_settings` →
    `.aitask-scripts/lib/config_utils.py:save_yaml_config`: pure YAML write,
    no `git`/`./ait git` calls anywhere in the save path.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - `t713_6_website_syncer_docs.md` (next sibling): the user-facing docs for
    `tmux.syncer.autostart` should mirror the seed comment block prose —
    auto-launch via `ait ide`, default false, manual launch via `ait syncer`.
    Reference the seed block as the canonical wording so the website and
    seed stay in sync.
  - `t713_7_manual_verification_syncer_tui.md` (later sibling): the Codex
    exception means Codex users will be prompted on first `aitask_syncer.sh`
    invocation; this is by design and not a verification failure.
- **Verification results (2026-04-30):**
  - `grep -l aitask_syncer.sh` across 5 touchpoints → all 5 hit.
  - JSON/TOML/YAML syntax checks all green.
  - `seed/project_config.yaml`: `# autostart: true` (line 228) and
    `#   autostart: false` (line 231) both visible.

