---
Task: t778_minimize_claude_p_usage_for_billing.md
Worktree: (none — working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Minimize `claude -p` / `--print` headless usage (t778)

## Context

Claude Code bills `claude -p` / `claude --print` (headless/print mode) at a
higher per-token rate than interactive invocations. The goal is to eliminate
the framework's remaining runtime/dev headless invocations and add a guard
convention so new ones don't creep in.

The task (written 2026-05-17) named two call sites by line number; the tree
has since shifted. Re-verified current state:

1. **`.aitask-scripts/aitask_codeagent.sh:427`** — the `batch-review` op for
   `claudecode` appends `--print`. No automated runtime caller exists (only
   `ait codeagent invoke batch-review` + tests); the Codex branch already runs
   batch-review interactively. **No test asserts the `--print` behavior**, so
   gating it is safe.
2. **`aidocs/codeagents/extract_claudecode_tools.sh:23`** — manual one-shot dev
   script using `claude -p` with a static heredoc prompt. Not in any hot path.
3. Guard convention missing from `CLAUDE.md` Shell Conventions.

**Stale-acceptance note:** The task's acceptance grep
(`grep 'claude -p\|claude --print'`) can no longer return *zero* matches, and
shouldn't. Two legitimate references were added since the task was filed and
must remain — they *document the prohibition*, they aren't invocations:
- `aidocs/framework/skill_authoring_conventions.md:477-489` — the "Do not route
  skill invocation through `claude -p`" section.
- `.aitask-scripts/aitask_skillrun.sh:21` — a comment stating it does *not* use
  `claude -p`.
The reinterpreted acceptance is: **no actual `claude -p`/`claude --print`
invocations remain, and `batch-review` no longer emits `--print` by default.**

## Decisions (confirmed with user)

- Call site #1: **Add an opt-in `--headless` flag** (default interactive; CI can
  still get a non-interactive run). Matches the task's stated preference and
  keeps `batch-review` distinct from `raw`.
- Call site #2: **Drop `-p`, keep the script interactive** (paste-and-go).

## Changes

### 1. `.aitask-scripts/aitask_codeagent.sh` — gate `--print` behind `--headless`

- Add a global option default near the other `OPT_*` vars (line ~33):
  ```bash
  OPT_HEADLESS=false
  ```
- Parse `--headless` in `main()`'s global-flag `while` loop, mirroring
  `--dry-run` (line ~571):
  ```bash
  --headless)
      OPT_HEADLESS=true
      shift
      ;;
  ```
- In `build_invoke_command()`, change the `claudecode` → `batch-review` case
  (line 426-428) to append `--print` only when headless:
  ```bash
  batch-review)
      if [[ "$OPT_HEADLESS" == true ]]; then
          CMD+=("--print" "${args[@]}")
      else
          CMD+=("${args[@]}")
      fi
      ;;
  ```
- Update `show_help()`: add `--headless` to the Options block, noting it only
  affects `claudecode batch-review` (no-op elsewhere), and add an example
  (`ait codeagent --headless invoke batch-review <args>`).

`--headless` is a no-op for other agents/operations (none consume `--print`);
documented as such rather than erroring, to keep the change minimal.

### 2. `aidocs/codeagents/extract_claudecode_tools.sh` — drop `-p`

Change the invocation (lines 23-25) from `claude -p \` to `claude \`, leaving
`--dangerously-skip-permissions` and `"${PROMPT}"` intact. It becomes an
interactive paste-and-go session; the post-run `OUTPUT_FILE` existence check
still works after the session exits. No other lines change.

### 3. `CLAUDE.md` — add guard convention under Shell Conventions

Append one bullet after the "System libs added to `./ait`…" bullet (after
line 120), before the macOS-portability blockquote:

> - **Avoid `claude -p` / `claude --print` (headless print mode) in scripts and
>   skills.** Claude Code bills headless print mode at a higher per-token rate
>   than interactive invocations against an existing session. Default to
>   interactive mode; gate any genuinely non-interactive need (e.g. CI) behind
>   an explicit opt-in flag. This applies to skill `.md` files too. See
>   `aidocs/framework/skill_authoring_conventions.md` ("Do not route skill
>   invocation through `claude -p`") for the skill-rendering rationale.

### 4. `tests/test_codeagent.sh` — regression guard for the gating

Add two `--dry-run` assertions alongside the existing codex batch-review block
(line ~253):
- `claudecode batch-review` **without** `--headless` does **not** contain
  `--print`.
- `claudecode --headless invoke batch-review` **does** contain `--print`.

### 5. `website/content/docs/commands/codeagent.md` — document the flag

The Options list / passthrough description (around line 155) mentions
batch-review passthrough; add a one-line note that `--headless` opts a
`claudecode batch-review` run into non-interactive `--print` mode (default is
interactive). Current-state prose only, per doc conventions.

## Out of scope (per task)

- Skill `.md` files (no agent is instructed to call `claude -p`).
- Cost optimization of *interactive* claude calls.
- The two legitimate prohibition references (kept intentionally).

## Verification

1. Lint: `shellcheck .aitask-scripts/aitask_codeagent.sh aidocs/codeagents/extract_claudecode_tools.sh`
2. Behavior (dry-run, no live agent launched):
   ```bash
   ./.aitask-scripts/aitask_codeagent.sh --agent-string claudecode/opus4_8 --dry-run invoke batch-review foo   # NO --print
   ./.aitask-scripts/aitask_codeagent.sh --agent-string claudecode/opus4_8 --headless --dry-run invoke batch-review foo   # HAS --print
   ```
3. Tests: `bash tests/test_codeagent.sh` (expect PASS).
4. Acceptance grep (reinterpreted) — only the two documented references remain,
   no invocations:
   ```bash
   grep -rn 'claude -p\|claude --print' . --include='*.sh' --include='*.py' --include='*.md' | grep -v '/archived/' | grep -v '.aitask-crews/'
   # expect: only skill_authoring_conventions.md (prohibition doc) + aitask_skillrun.sh:21 (comment)
   ```
5. Step 9: merge to current branch (working on current branch — no worktree),
   then archive via `./.aitask-scripts/aitask_archive.sh 778`.

## Follow-ups to suggest (other agents)

Per CLAUDE.md, the `aitask_codeagent.sh` `--headless` flag is a Claude-tree-
agnostic shell script (not a skill surface), so no Codex/OpenCode skill port is
needed. The CLAUDE.md guard is repo-internal. No cross-agent port tasks
required.

## Risk

### Code-health risk: low
- Small, localized changes: one new global flag mirroring the existing
  `--dry-run` pattern, one dev-script one-liner, one doc bullet, one test pair.
  No load-bearing runtime path touched. `--headless` is a benign no-op for
  non-applicable agent/op combos. · severity: low · → mitigation: none

### Goal-achievement risk: low
- Requirements verified against the live tree (line numbers re-located, test
  coverage confirmed absent). The only nuance — the literal acceptance grep
  cannot reach zero — is handled by explicit reinterpretation documented above.
  · severity: low · → mitigation: none

None of the identified risks warrant before/after mitigation tasks.
