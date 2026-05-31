---
Task: t846_documentation_for_manual_verification_auto_mode.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Plan: Document autonomous manual-verification on the docs site (t846)

## Terminology (per user feedback)

User-facing docs must **avoid the term "auto-execution."** Use **"autonomous"**
and frame the feature plainly: a manual-verification checklist is meant to be
worked through by a *human*, but it can instead be run **fully or partially by
an AI agent** — the agent handles the mechanically-checkable items and leaves
the genuinely human ones (visual rendering, UX judgement) for the interactive
loop. Literal identifiers stay verbatim where they are code/config tokens (the
`auto` verb, the `autonomous` / `autonomous_with_plan` profile values, the
`…_manual_verification_auto.md` plan filename, the plan's `## Execution Log`
heading) — the rule governs prose and section headings, not identifiers.

## Context

t843 added an optional **autonomous-verification mode** to the Manual
Verification Procedure: an up-front Step 1.5 offer to have an AI agent run the
whole checklist (two strategies — *autonomous* and *autonomous_with_plan*), a
per-item `auto` verb inside the interactive loop, persistence of the run to
`aiplans/p<id>_manual_verification_auto.md`, and a new profile knob. t851
(brainstorm) renamed the knob and t859 (now merged) applied that rename across
all source files. The runtime behaviour is fully documented in the skill
closure (`.claude/skills/task-workflow/manual-verification.md` Step 1.5,
`auto-verification.md`, `profiles.md`), and the Settings TUI
(`lib/profile_editor.py`) already exposes `manual_verification_mode`. **The
website docs have no coverage of any of this.** This task closes that gap.

All three deps are merged/archived (t843, t851, t859); the source tree uses the
**new** names exclusively (`grep` confirms zero `manual_verification_auto_mode`
left). This task uses the **new** names everywhere:
- key: `manual_verification_mode`
- values: `ask | manual | autonomous | autonomous_with_plan`

Canonical schema row (source of truth, `profiles.md` line 40) to mirror:

> `manual_verification_mode` | string | no | `"ask"` (default — prompt fires with
> autonomous / autonomous_with_plan / skip), `"manual"` (skip prompt; straight to
> interactive), `"autonomous"` (skip prompt; run autonomous),
> `"autonomous_with_plan"` (skip prompt; design + approve + execute). Controls only
> the up-front prompt — the per-item `auto` verb in the interactive loop is always
> available regardless.

Per CLAUDE.md "Documentation Writing": current-state only, no "previously"
phrasing. Filename keeps the old key per the task note (`/aitask-update` does
not rename files).

## Files to modify

### 1. `website/content/docs/workflows/manual-verification.md` — the main pass

**1a. Forward cross-link in the "Running a Manual-Verification Task" intro**
(after the "Steps 4 … still run first" sentence, ~line 76): add one sentence
noting an AI agent can run the checklist before the interactive loop, linking
to the new section: `see [Autonomous verification](#autonomous-verification)`.

**1b. Refresh the verb lists to include `auto`** (t843 added the verb; the page
predates it and is now stale):
- The in-render tip example (~line 88-89): change the example to
  `"3 pass, 4 fail, 5 skip not applicable, 6 auto"` and the verb list to
  `(verbs: pass / fail / skip / defer / auto)`, matching the runtime tip in the
  procedure (`manual-verification.md` lines 147-151).
- The "Other (free text)" table row (~line 100): mention the `auto` verb in the
  batch-update description (has the AI agent verify that item autonomously;
  always autonomous, links to the new section).

**1c. Add a new `## Autonomous verification` H2** (slug
`#autonomous-verification`) inserted after the "Running a Manual-Verification
Task" section and before "## Fail → Follow-up Bug Task". Lead paragraph states
the framing: the checklist is meant for a human, but an AI agent can run it
**fully or partially** — it attempts each mechanically-checkable item (CLI
calls, file inspection, tmux-driven TUIs), marks pass/fail/defer, and leaves
the human-only checks for the interactive loop. Subsections (content drawn from
`auto-verification.md` + `manual-verification.md` Step 1.5):
- **The up-front offer (Step 1.5)** — the 3 options: *Yes, autonomous*
  (recommended), *Yes, design plan first and approve*, *No, go straight to
  interactive*; what each does; both "Yes" branches fall through to the
  interactive loop for items still pending/defer; Fail still spawns the
  follow-up bug task; undecidable items left `defer` with a reason.
- **Per-item autonomy** — the `auto` verb in the Other field (`3 auto` / bare
  `auto`) has the agent verify a single item on demand, available regardless of
  the profile setting. (This is the "partially" path — let the agent take the
  mechanical items one at a time while you drive the rest.)
- **The run record (plan file)** — persisted to
  `aiplans/p<id>_manual_verification_auto.md`
  (`aiplans/p<parent>/p<id>_…` for children); the autonomous strategy writes
  the log retroactively, autonomous_with_plan writes the plan up front + appends
  an execution log; committed as `ait: Add manual-verification auto-execution
  plan for t<id>` (commit subject is a fixed code string, kept verbatim).
- **Profile control: `manual_verification_mode`** — a 4-row value table
  (`ask`/`manual`/`autonomous`/`autonomous_with_plan`) mirroring the canonical
  row; note it controls only the up-front offer (the per-item `auto` verb is
  always available); link to
  `[Execution Profiles](../../skills/aitask-pick/execution-profiles/)`.

### 2. `website/content/docs/skills/aitask-pick/execution-profiles.md` — profile schema

Add a `manual_verification_mode` row to the "Standard Profile Fields" table,
directly after the existing `manual_verification_followup_mode` row (~line 39).
Description gives the four values and notes the per-item `auto` verb is always
available; cross-link to the workflow page's new section
(`../../workflows/manual-verification/#autonomous-verification`).

### 3. `website/content/docs/tuis/settings/reference.md` — settings profile schema

Add a `manual_verification_mode` row to the existing "### Manual Verification"
section, after the `manual_verification_followup_mode` row (~line 136). Format
matches the section's `Key | Type | Options | Description` table (enum;
`ask`, `manual`, `autonomous`, `autonomous_with_plan`). Accurate because
`lib/profile_editor.py` already registers the key with exactly these enum values.

### 4. `website/content/docs/concepts/execution-profiles.md` — discoverability

Add `manual_verification_mode` to the illustrative "for example …" key list in
the "What it is" paragraph (~line 11), alongside the existing
`manual_verification_followup_mode`. Small, but it surfaces the key on the
concept page so readers of one MV feature discover the other.

## Out of scope / deliberately NOT edited

- **Blog posts** `blog/v0181-…` and `blog/v0170-…` mention `manual_verification`
  / Pass/Fail/Skip/Defer, but they are **dated release announcements**. Editing
  them to add current-state cross-links would be anachronistic and violates the
  spirit of the docs rule. Left untouched (surfaced here per the cross-ref
  redirect convention).
- `commands/task-management.md:62` and `development/task-format.md:51` mention
  only the `--verifies` flag / `verifies` field, not the verification loop or
  auto-mode — no cross-link warranted.
- No source/skill/procedure files change (this is a docs-only task; the runtime
  closure is already correct post-t859).

## Verification

```bash
cd website && hugo build --gc --minify   # must succeed, no broken-ref errors
```
- Confirm `hugo` emits no `REF_NOT_FOUND` / broken-link warnings for the new
  relative links.
- Spot-check anchors: the new `## Autonomous verification` H2 yields the slug
  `#autonomous-verification` (Hugo auto-slug) — verify the same-page link in (1a)
  and the cross-page link in (2) match it.
- `grep -rn "manual_verification_mode" website/content/` shows the key on all
  four edited pages with consistent value set.
- Optional visual pass (`cd website && ./serve.sh`): new H2 renders on the
  workflow page; both schema tables show the new key; cross-links land.

## Post-Implementation (Step 9)

Docs-only change on `main` (no worktree). After review/commit: standard
archival via `./.aitask-scripts/aitask_archive.sh 846`, then `./ait git push`.
Per CLAUDE.md, the Claude Code skill is source of truth — but here only website
docs change, so no sibling skill-port tasks for other agents are needed.

## Final Implementation Notes

- **Actual work done:** Edited all 4 planned website pages.
  - `workflows/manual-verification.md`: added the `## Autonomous verification`
    H2 (lead framing + 4 subsections: up-front offer / per-item autonomy / run
    record / `manual_verification_mode` value table), a forward cross-link in
    the "Running" intro, refreshed the in-render tip example and the "Other
    (free text)" table row to include the `auto` verb.
  - `skills/aitask-pick/execution-profiles.md`: added the
    `manual_verification_mode` row to the Standard Profile Fields table,
    cross-linked to the new workflow section.
  - `tuis/settings/reference.md`: added the `manual_verification_mode` row to
    the "Manual Verification" section (enum values match `profile_editor.py`).
  - `concepts/execution-profiles.md`: added the key to the illustrative key
    list.
- **Deviations from plan:** None. User feedback during planning steered the
  terminology away from "auto-execution" toward "autonomous" / "AI agent runs
  a human checklist fully or partially" — incorporated into the plan before
  approval and reflected throughout.
- **Issues encountered:** Initial HTML-anchor verification grep used quoted
  attribute matching (`id="…"`), which missed Hugo's minified output (unquoted
  attributes). Re-ran unquoted and confirmed `<h2 id=autonomous-verification>`,
  the same-page links, and the cross-page link
  (`../../workflows/manual-verification/#autonomous-verification`) all resolve.
- **Key decisions:** Refreshed the stale verb lists to include `auto` (a t843
  addition the page predated) so the docs match the runtime tip. Left the two
  dated blog posts (`v0181`, `v0170`) untouched — they are release
  announcements, not current-state docs. Kept literal tokens (`auto`,
  `autonomous` / `autonomous_with_plan`, `…_manual_verification_auto.md`,
  `## Execution Log`) verbatim; the "autonomous, not auto-execution" rule
  governs prose/headings only.
- **Verification:** `hugo --source website build --gc --minify` succeeds (only
  pre-existing theme deprecation WARNs, no broken-ref errors); `grep` confirms
  `manual_verification_mode` rendered on all four pages with a consistent value
  set; new H2 anchor and all cross-links resolve in the generated HTML.
- **Upstream defects identified:** None.
