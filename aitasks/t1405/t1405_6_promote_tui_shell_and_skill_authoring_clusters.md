---
priority: high
effort: high
depends: [t1405_5]
issue_type: documentation
status: Ready
labels: [documentation, docs, tui]
gates: [risk_evaluated]
anchor: 1405
created_at: 2026-08-04 13:47
updated_at: 2026-08-04 13:47
---

## Context

Sixth child of t1405. Promotes three clusters (~27 memories) into three existing
docs: TUI, shell/security, and skill authoring.

Read first:
1. `aiplans/p1405_triage_agent_memory_store_into_aidocs.md` — the parent plan,
   which owns the per-memory decision gate, the store-concurrency rules, and the
   journal schema. Binding here; do not re-derive.
2. `aiplans/archived/p1405/p1405_1_*.md` — the frozen manifest and the triage
   table naming exactly which memories this child owns.

The store is outside the repo, so its deletions and `MEMORY.md` edits appear in
no git diff — say so in the Final Implementation Notes.

## Scope

### -> `aidocs/framework/tui_conventions.md` (~12; already 30 KB / 24 sections)

Test Textual markup/display bugs at render level (`widget.render().plain`;
prefer `markup=False` over escaping); any "the user sees X" claim needs a real
terminal (tmux pane capture) — `run_test` geometry can report a widget as
displayed that is never drawn; visible is not readable (verify at ordinary
terminal widths; shed context before signal when truncating); checkbox glyphs
(checked/unchecked, always shown) for mark state, marked = bold yellow;
focused+hovered rows show a shade of the focus accent, never the neutral gray
hover; prefer context-scoped bare single keys (gated via `check_action`) over
modifier chords; a keybinding gate is not the action's guard — re-check inside
`action_*`; a build-time frozen predicate strands stale UI state, and direct-call
tests cannot prove the repaint is wired into the production tick; per-view footer
labels need duplicate-key bindings (`check_action` alone never relabels the
rendered footer); `Pilot.pause()` always sleeps >=20 ms so it must never appear
inside a timed region.

Two of these are **MERGE**, not new sections:
- the tmux OSC-52 visible-pane-only fact folds into the existing
  `## Clipboard copies route through lib/tui_clipboard.copy_to_system_clipboard`
  section;
- the one-TUI-per-window / `j`-opens-the-switcher terminology folds into the
  existing tmux-layout material (check `tui_conventions.md` and
  `tmux_gateway.md` and pick the one that already owns it).

### -> `aidocs/framework/shell_conventions.md` (3)

Quoting cannot secure substitution — validate at the write site and pass a bound
variable or a path, never the literal; line-oriented tools (sed/grep/read) are
blind to embedded newlines, so fold control characters before any line-oriented
stage and never use grep to detect the newline it is meant to catch; when
free-form text flows into a delimiter-encoded field the boundary is undecidable
on read, so neutralize the delimiter at the write site.

**This file has no `##` sections at all** — it is a flat bullet list under the H1
with a bolded lead clause per bullet. Match that style; do not introduce headings.

### -> `aidocs/framework/skill_authoring_conventions.md` (~12; already 34 KB / 18 sections)

A contract stated only in prose is not enforced — agents follow the command
block, so put the contract there and guard the rendered command shape; make
branch decisions engine-owned via a machine-checkable sentinel + exit code
rather than agent-side re-derivation; multi-command workflow bash belongs in a
whitelisted `aitask_*.sh` helper with a unit test, not inlined in skill markdown;
enforce a skill's contractual behaviour in the skill source, not in a
behaviour-memory; skill UX — no I/O before the first prompt, auto-detect from
free text instead of always prompting, thread runtime context variables; make the
composition/precedence rule explicit when new steering combines with prior
instructions; prefer an explicit mode selector over a magic-value trigger; offer
a newly-unlocked action immediately in-session rather than making re-entry the
only trigger; do not accept an in-repo rationale for keeping a skill static —
re-derive it; skill-closure changes auto-render to all agents, so cross-agent
port follow-ups are no-ops unless the change touches agent-specific surfaces;
`aitask_skill_rerender.sh` takes a profile argument (one call per profile).

One **MERGE**: the Fable-5 invisible-narration fact (assistant prose in the same
turn as a tool call may not render; put decision content in the AskUserQuestion
payload) folds into that doc's **existing** `## AskUserQuestion visibility rule`
section — do not add a parallel one.

## Key files

- `aidocs/framework/tui_conventions.md`, `shell_conventions.md`,
  `skill_authoring_conventions.md` — the three promotion targets.
- `.aitask-memtriage/t1405_6.tsv` — the rulings journal (git-ignored).

## House style (non-negotiable)

`tui_conventions.md` and `skill_authoring_conventions.md`: one `##` per rule,
the heading being **the rule stated as a full sentence**, then rule paragraph +
rationale paragraph. `shell_conventions.md`: flat bullets, bolded lead clause,
no headings. Drop the "surfaced in tNNN" narrative in all three.

Record the source -> merged `doc#heading` mapping for every MERGE; t1405_7 needs
it to rewrite `[[wikilinks]]`.

## Verification

- Every claim re-verified against current source before promotion; UNVERIFIABLE
  items are structurally ineligible for promotion and are listed as dropped.
- Every cited source path still exists, for each of the three docs:

```bash
for d in tui_conventions shell_conventions skill_authoring_conventions; do
  missing=$(grep -o '`[^`]*\.\(sh\|py\|md\|json\|yaml\)`' "aidocs/framework/$d.md" |
            tr -d '`' | sort -u | while read -r f; do [ -e "$f" ] || echo "$f"; done)
  [ -z "$missing" ] || { printf 'DEAD REFS in %s:\n%s\n' "$d" "$missing" >&2; exit 1; }
done
```

- `bash tests/test_aidocs_pointer_parity.sh` passes.
- Every ruling journalled `state=done`, each PROMOTE/MERGE row carrying a
  verbatim >=40-char excerpt of the text actually written.
- Promoted memory files deleted and their `MEMORY.md` lines removed by matching
  the link target after re-reading the file — never by wholesale regeneration.
