---
Task: t871_manual_verification_investigate_codex_forced_plan_mode_follo.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t871 — Auto-Verification Execution Record (autonomous)

Manual-verification follow-up to t866 (relax Codex forced plan mode for the
analysis skills `qa`/`explain`, keep it for the planning skills
`pick`/`explore`). This file is a retroactive record of the autonomous
auto-verification pass run before the interactive loop.

The structural behavior (which launch path each skill takes) is fully
determined by command construction, so it was verified with `--dry-run` on the
real `aitask_codeagent.sh` / `aitask_skillrun.sh` (side-effect-free). The
live behavioral half of items 1–2 (whether a `request_user_input` prompt
actually surfaces during a real Codex flow) cannot be automated — it needs a
real `codex` binary, a real model, and human observation of the TUI — so those
two items were deferred to the interactive smoke test.

## Execution Log

### Item 1
- Item text: Launch `ait codeagent invoke qa <archived-task-id>` with a `codex/*` agent string — confirm Codex starts in DEFAULT mode (composer does NOT show /plan) and that a request_user_input prompt actually surfaces during the qa flow.
- Approach: CLI invocation — `--dry-run` command-construction check (default-mode half); live half is not automatable.
- Action run: `./.aitask-scripts/aitask_codeagent.sh --agent-string codex/gpt5_4 --dry-run invoke qa 866`
- Output (trimmed): `DRY_RUN: codex -m gpt-5.4 $aitask-qa 866`
- Verdict: defer — default-mode half **confirmed** (direct `codex` launch, no `aitask_codex_plan_invoke` → composer will NOT show `/plan`). The "request_user_input prompt actually surfaces during the qa flow" half requires an interactive Codex session with human observation; deferred to the interactive loop.

### Item 2
- Item text: Launch `ait codeagent invoke explain <source-file>` with a `codex/*` agent string — confirm DEFAULT mode and that any request_user_input prompt surfaces (not silently skipped).
- Approach: CLI invocation — `--dry-run` command-construction check (default-mode half); live half is not automatable.
- Action run: `./.aitask-scripts/aitask_codeagent.sh --agent-string codex/gpt5_4 --dry-run invoke explain .aitask-scripts/aitask_codeagent.sh`
- Output (trimmed): `DRY_RUN: codex -m gpt-5.4 $aitask-explain .aitask-scripts/aitask_codeagent.sh`
- Verdict: defer — default-mode half **confirmed** (direct `codex` launch, no plan helper). Live `request_user_input` surfacing requires an interactive Codex session; deferred to the interactive loop.

### Item 3
- Item text: Launch `ait codeagent invoke pick <task-id>` with a `codex/*` agent string — confirm the composer DOES show /plan (plan mode still forced for the planning skill).
- Approach: CLI invocation — `--dry-run` command-construction check (fully determined by launch path).
- Action run: `./.aitask-scripts/aitask_codeagent.sh --agent-string codex/gpt5_4 --dry-run invoke pick 866`
- Output (trimmed): `DRY_RUN: python3 .../aitask_codex_plan_invoke.py --prompt $aitask-pick 866 -- codex -m gpt-5.4`
- Verdict: pass — `pick` routes through `aitask_codex_plan_invoke.py`, whose job is to type `/plan` into the PTY, so the composer shows `/plan`. Plan mode still forced for the planning skill.

### Item 4
- Item text: Launch `ait codeagent invoke explore` with a `codex/*` agent string — confirm the composer DOES show /plan (plan mode still forced).
- Approach: CLI invocation — `--dry-run` command-construction check (fully determined by launch path).
- Action run: `./.aitask-scripts/aitask_codeagent.sh --agent-string codex/gpt5_4 --dry-run invoke explore`
- Output (trimmed): `DRY_RUN: python3 .../aitask_codex_plan_invoke.py --prompt $aitask-explore -- codex -m gpt-5.4`
- Verdict: pass — `explore` routes through `aitask_codex_plan_invoke.py` (`/plan` typed → composer shows `/plan`). Plan mode still forced.

### Item 5
- Item text: Run `ait skillrun qa <id> --agent-string codex/<model>` then `ait skillrun pick <id> --agent-string codex/<model>` — confirm qa launches directly (no aitask_codex_plan_invoke) and pick uses the plan helper (parity with `ait codeagent`).
- Approach: CLI invocation — `--dry-run` command-construction check (this item is itself a structural parity check).
- Action run: `./.aitask-scripts/aitask_skillrun.sh qa 866 --agent-string codex/gpt5_4 --dry-run` then `... pick 866 ...`
- Output (trimmed):
  - qa → `DRY_RUN: codex -m gpt-5.4 $aitask-qa --profile default 866`
  - pick → `DRY_RUN: .../venv/bin/python .../aitask_codex_plan_invoke.py --prompt $aitask-pick --profile fast 866 -- codex -m gpt-5.4`
- Verdict: pass — `skillrun qa` launches `codex` directly (no `aitask_codex_plan_invoke`); `skillrun pick` uses the plan helper. Parity with `ait codeagent` confirmed.

## Cleanup

None — all verification was side-effect-free (`--dry-run` only). No scratch
files or tmux sessions were created.
