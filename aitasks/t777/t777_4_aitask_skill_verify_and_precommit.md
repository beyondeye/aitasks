---
priority: high
effort: low
depends: [t777_3]
issue_type: feature
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 11:58
updated_at: 2026-05-17 11:58
---

## Context

Depends on t777_2 and t777_3. Adds `ait skill verify` — re-renders every `.j2` for every agent against `default.yaml` and asserts the renderer raises no errors and produces non-empty output. Also extends the test suite and installs a pre-commit hook.

Since per-profile renders are gitignored (under the `*-/` trailing-hyphen convention), the verifier does NOT diff against a committed render. It is purely a "templates render cleanly for default profile across all 4 agents" smoke check, plus a structural check that every per-agent stub follows the canonical pattern documented in `.claude/skills/task-workflow/stub-skill-pattern.md` (from t777_3).

**Per-agent stub surfaces (per t777_3 design):** the verifier MUST scan all four surfaces, not just `<agent>/skills/<skill>/SKILL.md`:
- Claude stub: `.claude/skills/<skill>/SKILL.md`
- Codex stub: `.agents/skills/<skill>/SKILL.md`
- Gemini stub: `.gemini/commands/<skill>.toml` `prompt` field
- OpenCode stub: `.opencode/commands/<skill>.md` body

## Key Files to Modify

- `.aitask-scripts/aitask_skill_verify.sh` (new) — the verifier
- `./ait` (modify) — add `verify` subcommand under existing `skill)` case from t777_2
- Pre-commit hook (either new in `.git/hooks/pre-commit` or extension of existing `.aitask-scripts/pre-commit` if present) — invoke `ait skill verify` when any `.j2` or stub `SKILL.md` is staged
- `tests/test_skill_template.sh` (extend) — assertion that `ait skill verify` passes
- 5-touchpoint whitelist for `aitask_skill_verify.sh`

## Reference Files for Patterns

- `tests/test_*.sh` — bash test pattern with `assert_*` helpers
- `.aitask-scripts/aitask_audit_wrappers.sh` — pattern for a script that walks a directory tree and runs checks
- Existing pre-commit infra if any (search `find . -name "pre-commit*" -not -path "./node_modules/*"`)

## Implementation Plan

### 1. aitask_skill_verify.sh
- Source `lib/python_resolve.sh`, `lib/agent_skills_paths.sh`.
- Find every `.j2` under `.claude/skills/<skill>/` (Claude authoring path).
- For each `.j2`:
  - For each agent in (claude, codex, gemini, opencode):
    - Render against `aitasks/metadata/profiles/default.yaml` to /dev/null
    - On error: print "VERIFY_FAIL: <template> agent=<agent>: <error>" and accumulate failures
- For each per-agent stub surface (per `stub-skill-pattern.md` §3g table):
  - Claude: `.claude/skills/<skill>/SKILL.md`
  - Codex: `.agents/skills/<skill>/SKILL.md`
  - Gemini: `.gemini/commands/<skill>.toml` (read the `prompt` field)
  - OpenCode: `.opencode/commands/<skill>.md` (read the body)
  - grep for the canonical bash commands (`aitask_skill_resolve_profile.sh`, `ait skill render`)
  - grep for the Read-and-follow dispatch instruction (path includes trailing hyphen: `<skill>-<profile>-/SKILL.md`)
  - On failure: print "STUB_FAIL: <path>: missing <expected>"
- Non-zero exit if any failures.

### 2. ait dispatcher
Extend the `skill)` case (added in t777_2) with `verify`:
```bash
verify) exec "$SCRIPTS_DIR/aitask_skill_verify.sh" "$@" ;;
```

### 3. Pre-commit hook
Find or create the project pre-commit hook. Add:
```bash
# If any .j2 OR any stub surface (Claude/Codex SKILL.md, Gemini command TOML,
# OpenCode command MD) is staged, run ait skill verify
if git diff --cached --name-only | grep -qE '(\.j2$|skills/[^/]+/SKILL\.md$|\.gemini/commands/[^/]+\.toml$|\.opencode/commands/[^/]+\.md$)'; then
    ./ait skill verify || exit 1
fi
```

### 4. Tests
Extend `tests/test_skill_template.sh`:
- `assert ./ait skill verify` exits 0 on the current checkout
- Plant a deliberately broken `.j2` in a temp tree, point the verifier at it, assert it exits non-zero

### 5. 5-touchpoint whitelist
Same five files as t777_2 — entries for `aitask_skill_verify.sh`.

## Verification Steps

1. `ait skill verify` exits 0 after t777_6+ have produced .j2 files.
2. `bash tests/test_skill_template.sh` PASS.
3. Pre-commit hook fires when a stub is modified and blocks the commit if verify fails.
4. `shellcheck .aitask-scripts/aitask_skill_verify.sh` clean.
5. The 5 whitelist files contain the new entries.
