---
Task: t777_4_aitask_skill_verify_and_precommit.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_4 — `ait skill verify` + tests + pre-commit hook

## Scope

Verifier that re-renders every `.j2` against `default.yaml` for each of the 4 agents and asserts no error + non-empty output. Also asserts every stub SKILL.md follows the canonical pattern. Pre-commit hook adopts the verifier.

## Step Order

1. **Write `aitask_skill_verify.sh`** — walks every `.j2`, renders for each agent, accumulates failures; greps stubs for canonical bash commands.
2. **Add `verify` subcommand** under the `skill)` case in `./ait` (the case was added in t777_2).
3. **Install pre-commit hook** — find existing project hook or create `.git/hooks/pre-commit`; trigger `ait skill verify` when any `.j2` or stub `SKILL.md` is staged.
4. **Extend `tests/test_skill_template.sh`** — assert `ait skill verify` passes on clean checkout; plant deliberately broken `.j2` in scratch tree and assert non-zero exit.
5. **5-touchpoint whitelist** for `aitask_skill_verify.sh`.

## Critical Files

- `.aitask-scripts/aitask_skill_verify.sh` (new)
- `./ait` (modify — extend `skill)` case)
- Pre-commit hook file (new or extended)
- `tests/test_skill_template.sh` (extend)
- 5 whitelist files

## Pitfalls

- **No committed renders to diff against** — the verifier only smoke-checks renderer success + non-empty output, plus structural checks on stubs. Diff-against-committed (the original Plan agent design) does not apply.

## Verification

See task description. Pre-commit hook should fire when a stub or `.j2` is staged.
