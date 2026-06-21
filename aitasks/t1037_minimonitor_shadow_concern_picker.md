---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitask_monitormini, shadow, claudeskills, clipboard, tui]
children_to_implement: [t1037_3, t1037_4, t1037_5, t1037_6]
created_at: 2026-06-21 11:19
updated_at: 2026-06-21 14:38
boardidx: 50
---

## Goal

Add a UX flow in the **minimonitor TUI** that lets the user pick which of the
shadow agent's concerns to forward to the followed code-agent, without
manually re-typing or copy-pasting the full list.

End-to-end target flow:

1. The shadow agent (via `aitask-shadow` skill, esp. `plan-challenge.md`)
   produces a structured concerns list on a plan it just reviewed.
2. Minimonitor auto-detects the structured block in the shadow pane's
   captured terminal output.
3. The user opens a "select concerns" modal (hotkey or proactive offer),
   sees each concern with its priority + plan-region tags as a check-list,
   and ticks the ones they want addressed.
4. On confirm, minimonitor builds a clipboard payload:
   - Preamble: `"I have some concerns: please verify them and if valid please address in the plan"`
   - Followed by the selected concern blocks (verbatim, in order).
5. The payload is copied to the system clipboard.
6. The user pastes into the code-agent pane.
7. Toast: `"Concerns copied to clipboard."`

## Why this matters

Without this, the user has to manually copy individual concern lines from the
shadow pane and stitch them into a new prompt for the code-agent — high
friction, lossy, and discourages selective steering. With it, the user can
quickly retain control over which concerns actually enter the plan instead of
silently delegating all concerns to the shadow agent. Closely related (but NOT
folded) brainstorm: t1017 (shadow steerability) — that task may want a broader
answer; this task delivers one concrete piece of it.

## Origin

Scoped via `/aitask-explore` in the `aitasks_mobile` repo on 2026-06-21 and
moved here on the same day — the implementation surface is entirely in this
framework repo (minimonitor, aitask-shadow skill, Textual clipboard), so the
task belongs alongside the code it changes.

## Constraints / design points (from scoping)

- **Concern format must be both human-readable and machine-parseable.** Each
  concern carries at least: priority (e.g. high/medium/low), plan-region
  label (which section of the plan it targets), and body text. Format should
  let the user copy-paste manually if they want, AND let the parser extract
  items reliably. Exact spelling of the format (numbered markdown vs. fenced
  sentinel vs. YAML-in-fence) is a planning decision — must round-trip
  through tmux/terminal without escape-sequence damage and must fit the
  patterns shadow already uses (see `plan-challenge.md`).
- **Components to change:**
  - `.claude/skills/aitask-shadow/plan-challenge.md` and any peer
    sub-procedure that emits concern-like lists — instruct the agent to
    emit the agreed structured block.
  - Optional: aidocs spec for the format so the parser and the prompt stay
    in sync.
  - A new parser in `.aitask-scripts/monitor/` (sibling to the existing
    `prompt_patterns.py`, `monitor_shared.py`) that extracts items from a
    capture buffer.
  - A new Textual modal in `.aitask-scripts/monitor/minimonitor_app.py`
    patterned on existing modals (`KillConfirmDialog`, `NextSiblingDialog`,
    `ChooseSiblingModal`, `TaskDetailDialog`) — checkbox list +
    confirm/cancel.
  - Hotkey + trigger logic: at minimum a manual hotkey; nice-to-have an
    auto-offer when a fresh concerns block is detected on the shadow pane.
- **Clipboard portability:** use Textual's built-in `app.copy_to_clipboard()`
  which already wraps OSC 52 and works on Linux (wl-copy/xclip when
  available, OSC 52 otherwise), macOS (pbcopy / OSC 52), Windows (clip.exe
  / OSC 52), AND across SSH/tmux — covers the "all aitasks platforms +
  OSC 52 fallback" requirement with zero new dependencies. Prior art:
  `.aitask-scripts/codebrowser/codebrowser_app.py:147,153` and
  `.aitask-scripts/lib/agent_command_screen.py:666–672`.
- **Source of capture:** reuse `.aitask-scripts/aitask_shadow_capture.sh
  <pane_id>` for the cleaned terminal snapshot — same path the shadow skill
  itself uses; no new pane-reading machinery needed.
- **No code-agent output changes:** the parser/UX only attaches to the
  shadow agent's output, not the code-agent's.

## Decomposition suggestion (planning to finalize)

Likely children (planning task will finalize order and dependencies):

1. **Concern-block format spec** — pin the format (priority + plan-region
   + body, wrapper sentinel), document in aidocs.
2. **Shadow skill prompt update** — `plan-challenge.md` (+ peers if
   applicable) instructs the agent to always emit the format on concern
   lists; verify with a sample run.
3. **Parser module** in `.aitask-scripts/monitor/` — pure-function extract
   from capture text → list of `Concern(priority, region, body)`. Unit
   tested.
4. **Minimonitor concern-picker modal** — Textual modal with checkbox list,
   priority/region badges, select-all/none, confirm builds clipboard
   payload (preamble + selected items) and calls
   `app.copy_to_clipboard()` + `notify(...)`.
5. **Trigger wiring** — hotkey binding in `minimonitor_app.py` (and
   optional proactive auto-offer when a fresh concerns block appears on
   the shadow pane).

## Open questions for planning

- Should the parser run on every refresh tick (continuous) or only on
  user-triggered hotkey (lazy)? Latter is simpler; former enables
  auto-offer.
- If the agreed format wraps concerns in a sentinel fence, what is the
  fence string? (Must not collide with markdown code fences common in
  agent output.)
- Should multi-block (shadow re-issues concerns after fresh review)
  replace or accumulate?
- Should the modal also expose a "copy ALL" shortcut for the user who
  wants the manual-paste fast path with the preamble already attached?

## Non-goals

- No keystroke injection into the code-agent pane (shadow is advisory-only
  by guardrail — preserve that).
- No clipboard helper script reinvention — use Textual's `copy_to_clipboard`.
- No changes to how the code-agent itself formats its output.


NOTE: the feature we are implementing here has some similarity to https://code.claude.com/docs/en/ultraplan
perhaps review the current implementation plan for this feature in light of the design of ultraplan??
