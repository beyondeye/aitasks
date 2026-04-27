---
Task: t674_whitelist_bare_ait_crew_form.md
Base branch: main
plan_verified: []
---

# Plan: Whitelist bare `ait crew` form for code agents (t674)

## Context

Task t650_1 (2026-04-26) added `./ait crew` whitelists across Claude / Gemini / OpenCode configs to stop crew agents from prompting on every status update. But `aitask_crew_addwork.sh:211-230` writes per-agent instructions that tell crew agents to invoke the **bare** form:

```bash
ait crew status --crew <id> --agent <name> heartbeat
ait crew command list --crew <id> --agent <name>
```

(no `./` prefix — correct, since the crew worktree is a narrow checkout that does not contain `ait`, and `ait` is installed to `~/.local/bin/`.)

Whitelist patterns require `./ait crew` exactly, so the bare form does not match. Result: every heartbeat / status / command-list call from a crew agent prompts the user, defeating the t650_1 fix in practice.

Fix: add a sibling whitelist entry for the bare `ait crew` form alongside each existing `./ait crew` entry. Keep the `./ait crew` entries — they're still used by humans / skills running from project root.

Codex is exempt per CLAUDE.md "Codex exception" (prompt-by-default model — no allow rules).

## Touchpoints

Five files, mirroring the t650_1 commit pattern:

1. **`.claude/settings.local.json`** — line 123 currently `"Bash(./ait crew:*)"`. Add `"Bash(ait crew:*)"` (with the appropriate trailing comma adjustment).
2. **`seed/claude_settings.local.json`** — line 28 currently `"Bash(./ait crew:*)",`. Add `"Bash(ait crew:*)",` immediately after.
3. **`.gemini/policies/aitasks-whitelist.toml`** — lines 499-503 currently a `[[rule]]` block with `commandPrefix = "./ait crew"`. Add a sibling `[[rule]]` block with `commandPrefix = "ait crew"`, `decision = "allow"`, `priority = 100`.
4. **`seed/geminicli_policies/aitasks-whitelist.toml`** — lines 529-533, same shape as #3.
5. **`seed/opencode_config.seed.json`** — line 17 currently `"./ait crew *": "allow",`. Add `"ait crew *": "allow",` immediately after.

No Codex change.

## Concrete edits

### 1. `.claude/settings.local.json:123`

Current:
```json
      "Bash(./ait crew:*)"
    ]
```

New:
```json
      "Bash(./ait crew:*)",
      "Bash(ait crew:*)"
    ]
```

### 2. `seed/claude_settings.local.json:28`

Current:
```json
      "Bash(./ait crew:*)",
```

New:
```json
      "Bash(./ait crew:*)",
      "Bash(ait crew:*)",
```

### 3. `.gemini/policies/aitasks-whitelist.toml` (after line 503)

Insert immediately after the existing `./ait crew` block:
```toml
[[rule]]
toolName = "run_shell_command"
commandPrefix = "ait crew"
decision = "allow"
priority = 100
```

### 4. `seed/geminicli_policies/aitasks-whitelist.toml` (after line 533)

Same insertion as #3.

### 5. `seed/opencode_config.seed.json:17`

Current:
```json
      "./ait crew *": "allow",
```

New:
```json
      "./ait crew *": "allow",
      "ait crew *": "allow",
```

## Verification

1. **Pattern sanity check** — `grep -n "ait crew" .claude/settings.local.json seed/claude_settings.local.json .gemini/policies/aitasks-whitelist.toml seed/geminicli_policies/aitasks-whitelist.toml seed/opencode_config.seed.json` should show **2** entries per file (one `./ait crew`, one bare `ait crew`).
2. **JSON / TOML validity** — `python3 -c "import json; json.load(open('.claude/settings.local.json'))"`, same for `seed/claude_settings.local.json` and `seed/opencode_config.seed.json`. For TOML: `python3 -c "import tomllib; tomllib.load(open('.gemini/policies/aitasks-whitelist.toml','rb'))"` (and seed equivalent).
3. **Manual verification (deferred — sibling task candidate per Step 8c):**
   - Inside a crew worktree (`.aitask-crews/crew-<id>/`), launch a Claude Code agent and have it run `ait crew status --crew <id> --agent <name> heartbeat`. It must execute without a permission prompt.
   - Repeat for Gemini CLI and OpenCode if available.

## Out of scope

- t669 (Postponed, identical symptom) — leave untouched per user direction during exploration.
- t456 (broader per-agent permission framework) — orthogonal.
- Other `ait <subcommand>` forms (`ait git`, `ait codeagent`, etc.) — only `ait crew` is invoked from inside crew worktrees per `aitask_crew_addwork.sh:211-230`. If other prompts surface in the wild, file a follow-up task.
- Updating `aitask_crew_addwork.sh:211-230` to emit `./ait crew …` — would not work in crew worktrees (no `ait` script checked out) and would break parity with `ait` being PATH-resolved.

## Reference: t650_1 commit (precedent)

Commit `1e438ca2`, `bug: Whitelist ./ait crew for all code agents (t650_1)`, 2026-04-26 — added the `./ait crew` entries this plan complements. Same 5 touchpoints; this is the bare-form sibling pass.

## Step 9 reference

Per task-workflow Step 9, after user approval and commit, run `./ait git push` and let `aitask_archive.sh 674` handle status/lock/commit. No worktree to clean up (working on current branch).

## Final Implementation Notes

- **Actual work done:** Five sibling whitelist entries added, exactly as planned — bare `ait crew` (no `./` prefix) added alongside each existing `./ait crew` entry across `.claude/settings.local.json`, `seed/claude_settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/geminicli_policies/aitasks-whitelist.toml`, and `seed/opencode_config.seed.json`. No changes to `aitask_crew_addwork.sh` or any runtime helper.
- **Deviations from plan:** None.
- **Issues encountered:** None for the implementation itself. Plan externalization initially returned `MULTIPLE_CANDIDATES` because an unrelated `quizzical-rolling-eagle.md` was also recent; resolved by passing `--internal /home/ddt/.claude/plans/twinkling-sniffing-cherny.md` explicitly.
- **Key decisions:**
  - Kept the `./ait crew` entries (humans / project-root skills still use them); added bare entries as siblings rather than replacements.
  - Codex skipped per CLAUDE.md "Codex exception" — its prompt-by-default model has no `allow` decision to grant.
- **Upstream defects identified:** None. The fix is exactly the gap left by t650_1 (bare-form call site overlooked when `./ait crew` was whitelisted), not an upstream defect in another script.
- **Verification performed:**
  - `grep -n "ait crew"` across all 5 files — confirmed 2 entries per file (one `./ait crew`, one bare `ait crew`), 10 entries total.
  - `python3 -c "import json; json.load(...)"` for the 3 JSON files — all OK.
  - `python3 -c "import tomllib; tomllib.load(...)"` for the 2 TOML files — all OK.
- **Follow-up considerations:** Real-world manual verification (launch a crew agent, observe no prompts on heartbeat/status calls) is deferred to a Step 8c manual_verification sibling if the user wants one. The mechanical whitelist match is verified statically by the grep/parse checks above.

