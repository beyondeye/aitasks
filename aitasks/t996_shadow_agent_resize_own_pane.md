---
priority: medium
effort: low
depends: []
issue_type: feature
status: Ready
labels: [claudeskills, tmux]
created_at: 2026-06-15 12:13
updated_at: 2026-06-15 12:13
boardidx: 300
---

## Goal

Add a new **shadow-agent capability**: on user request, resize the shadow's
**own** tmux pane to a user-specified number of columns. The capability must be
defined in a **separate markdown procedure file** under the shadow skill and
**referenced as one of the shadow agent's capabilities from the main
`SKILL.md`** (matching the existing `plan-explain.md` / `plan-challenge.md` /
`plan-socratic.md` / `plan-assumptions.md` pattern).

## Context

- Identified as a future enhancement during t994 (minimonitor shadow-pane
  placement/width). The shadow pane currently spawns at a fixed initial width
  (`shadow_pane_width`, default 60) via tmux `-l`; tmux has **no persistent
  per-pane minimum**, so after a window resize the shadow can end up too narrow
  or too wide. Letting the shadow resize itself on demand covers that gap.
- The shadow agent skill lives at `.claude/skills/aitask-shadow/` (plain skill,
  NOT a profile-aware stub skill). `SKILL.md` Step 3 ("Serve the request — one
  flow, routed by the user's ask") routes structured asks to sub-procedure
  files via "read and follow `<file>.md`".
- **Advisory-only guardrail (load-bearing) is preserved:** the shadow is
  read-only *with respect to the followed agent*. Resizing the shadow's **own**
  pane does NOT violate this — it sends no keystrokes/input to the followed
  agent. The new capability MUST target only the shadow's own pane
  (`$TMUX_PANE`); it must NOT resize (or otherwise drive) the followed agent's
  pane. State this explicitly in the procedure so the contract stays clear.
- An agent can resize its own pane at runtime with `tmux resize-pane -t
  "$TMUX_PANE" -x <cols>`. The framework already does this for the minimonitor's
  self-pinning (`TmuxMonitor.resize_pane` in `_maybe_pin_width`,
  `.aitask-scripts/monitor/minimonitor_app.py`).

## Key files

- **New helper:** `.aitask-scripts/aitask_shadow_resize.sh` — encapsulates the
  resize. Per the "encapsulate workflow bash in a helper script" convention,
  the tmux call goes in a whitelisted `aitask_*.sh` helper with a unit test, not
  inlined in skill markdown.
- **New procedure:** `.claude/skills/aitask-shadow/resize-pane.md`.
- **Edit:** `.claude/skills/aitask-shadow/SKILL.md` — add the capability
  reference in Step 3.
- **New test:** `tests/test_shadow_resize.sh` (mirror
  `tests/test_shadow_capture.sh` / `test_shadow_context.sh`).

## Implementation plan

1. **Helper `aitask_shadow_resize.sh`:**
   - Follow `.aitask-scripts/aitask_shadow_capture.sh` for structure (shebang,
     `set -euo pipefail`, `SCRIPT_DIR`, sourcing).
   - **Route the tmux call through the gateway** `lib/tmux_exec.sh` (call
     `ait_tmux resize-pane -t "<pane>" -x "<cols>"`). Do NOT call `tmux`
     directly — `tests/test_no_raw_tmux.sh` scans `.aitask-scripts/` and would
     fail on a raw call (same rule the capture/context helpers obey).
   - Args: `<cols>` (required, the target column count) and an optional
     `<pane_id>` defaulting to `$TMUX_PANE` (explicit arg keeps it unit-testable
     without a live pane).
   - **Validate** `<cols>` is a positive integer; reject non-numeric / <=0 with a
     clear error and non-zero exit. Optionally clamp to a sane lower bound
     (e.g. 20) so the user can't collapse the pane to nothing; document the
     bound. tmux clamps an over-large value to the available width on its own.
   - Emit a structured success line (e.g. `RESIZED:<pane>:<cols>`) for the
     procedure/test to parse.

2. **Procedure `resize-pane.md`:**
   - Describe the capability: when the user asks the shadow to resize its pane
     to N columns (e.g. "make yourself 100 wide", "shrink to 50 cols"), parse N
     and run `./.aitask-scripts/aitask_shadow_resize.sh <N>` (defaulting the
     pane to `$TMUX_PANE`).
   - Re-state the advisory-only constraint: own pane only; never resize/drive the
     followed agent's pane.
   - Keep it short and methodology-focused, like the other `plan-*.md` files.

3. **Reference from `SKILL.md` Step 3:** add a bullet for the resize capability.
   It is an **action** capability rather than a plan analysis — group it
   appropriately (e.g. a short "Pane control" item, or extend the structured
   list) with the "read and follow `resize-pane.md`" pointer. Keep wording
   consistent with the existing entries.

4. **Test `tests/test_shadow_resize.sh`:** assert valid input resizes (mock the
   gateway / assert the constructed `resize-pane` argv as the capture/context
   tests do), and that invalid input (non-numeric, <=0) is rejected with a
   non-zero exit. Run with `bash tests/test_shadow_resize.sh`.

5. **Skill verify:** run `./.aitask-scripts/aitask_skill_verify.sh` after editing
   the skill so the new referenced procedure file is picked up.

## Cross-agent coordination

Source of truth is the Claude Code shadow skill. The shadow skill is ported
separately to Codex CLI (**aitasks#988**, in progress) and OpenCode
(**aitasks#989**). This new capability (procedure file + SKILL.md reference;
the `aitask_shadow_resize.sh` helper is shared/agent-agnostic) must also land in
those ports — coordinate with t988/t989 (add a reverse pointer in each) or spin a
small follow-up once they merge.

## Verification

- `bash tests/test_shadow_resize.sh` passes.
- `bash tests/test_no_raw_tmux.sh` still passes (helper uses the gateway).
- `./.aitask-scripts/aitask_skill_verify.sh` passes with the new procedure file.
- Manual: launch a shadow via minimonitor `e`, ask it "resize yourself to 100
  columns" → its own pane widens to ~100; ask "shrink to 40" → narrows; confirm
  the followed agent's pane is never resized.
