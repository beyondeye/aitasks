# Documentation Conventions

Conventions for writing aitasks **user-facing** documentation prose (README,
`website/content/docs/`, CLAUDE.md prose, changelog entries for new changes).

## Current-state-only: no version history in doc bodies

User-facing docs (website, README-level content) describe the **current state
only**.

- No "earlier versions of this page said…", "previously we recommended…",
  "this used to be wrong", "this corrects an earlier mistake".
- State correct behavior positively. Version history belongs in git and PR
  descriptions, not in doc bodies.
- Internal plan files (`aiplans/`) may still record deviations from earlier
  plans — the rule applies to user-facing content.
- **"Delete X, eventually integrate into Y" means redirect cross-refs now,
  defer content migration.** Read Y first. If Y already covers the essential
  content, "integrate" collapses to updating cross-references from X to Y —
  do not wholesale-migrate X's prose into Y in the same task. Defer the
  richer integration as a follow-up task and surface cross-reference
  redirects explicitly in Post-Review Changes (they break silently if
  missed).

## "Autonomous", not "auto-execution", for manual-verification prose

In user-facing prose for the manual-verification auto mode (the
`manual_verification_mode` profile knob, the Step 1.5 whole-checklist offer, the
per-item `auto` verb), avoid the terms "auto-execution" / "auto-execute". Use
**"autonomous"** and frame it plainly: a manual-verification checklist is meant
to be worked through by a *human*, but it can instead be run **fully or partially
by an AI agent** — the agent handles the mechanically-checkable items (CLI calls,
file inspection, tmux-driven TUIs) and leaves human-only checks (visual
rendering, UX judgement) for the interactive loop.

The rule governs **prose and section headings only**; the internal procedure
files still name it the "Auto-Verification Procedure". Keep literal identifiers
verbatim where they are code/config tokens: the `auto` verb, the `autonomous` /
`autonomous_with_plan` profile values, the `…_manual_verification_auto.md` plan
filename, the plan's `## Execution Log` heading, and fixed commit subjects. The
canonical section heading for this content is `## Autonomous verification`. The
rule applies to the sibling Codex / OpenCode skill-port docs too.

## Genericize the supported-agent set in blurb prose

In marketing / introductory / blurb prose, do not enumerate the full
supported-agent set — prefer agent-set-agnostic phrasing ("Claude Code and all
other supported coding agents"). Keep literal enumerations only where the list
*is* the documentation (CLI mapping tables, per-agent install / known-issue
sections, model-self-detection lists, touchpoint tables).

This rule is documented in full — preferred phrasings, the acceptable
one-or-two-anchor variant, and the complete list of literal-enumeration
exceptions — in `aidocs/framework/adding_a_new_codeagent.md` §23b ("Genericization rule").
Follow it there; this entry exists so doc writers who are *not* adding an agent
still reach the rule from a general "how to write docs" entry point.
