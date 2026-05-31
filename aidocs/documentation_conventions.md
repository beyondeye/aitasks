# Documentation Conventions

Conventions for writing aitasks **user-facing** documentation prose (README,
`website/content/docs/`, CLAUDE.md prose, changelog entries for new changes).
Companion to CLAUDE.md's "Documentation Writing" section (current-state-only: no
"previously…", no "this used to be wrong" — version history lives in git / PRs).

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
exceptions — in `aidocs/adding_a_new_codeagent.md` §23b ("Genericization rule").
Follow it there; this entry exists so doc writers who are *not* adding an agent
still reach the rule from a general "how to write docs" entry point.
