---
priority: medium
effort: medium
depends: [t2211_5]
issue_type: documentation
status: Ready
labels: [sitrep, documentation]
gates: [risk_evaluated]
anchor: 2175
created_at: 2026-11-05 15:37
updated_at: 2026-11-05 15:37
---

## Context

Child 6 of t2211: the docs for the three-pane sitrep window, the new sitrep TUI, the guarded
request delivery, the slimmed skill and `ait board --focus`. Docs are a first-class
deliverable (`aidocs/framework/planning_conventions.md`, "User-facing features"). Parent
plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`. Read the archived plans of
t2211_1..5 (`aiplans/archived/p2211/`) for what actually landed, and document the landed
behaviour, not this description.

## First step

Re-read the landed docs (t2175_6 edited `aidocs/framework/sitrep.md`, the website workflow
page and the skill page) and confirm they are clean against HEAD.

## Files

- `aidocs/framework/sitrep.md`:
  - "The sitrep window" (~L46): the roles (agent, TUI, minimonitor), the layout, the
    `@aitask_sitrep_tui_root` stamp, the two-predicate table (not an agent for listing / a
    real occupant for retention), the four-way spawn and its statuses, the new wire lines
    `SITREP_ADDED_TUI:` / `SITREP_RESPAWNED_AGENT:`, agent-exit behaviour, races;
  - a new section "The sitrep TUI": views, pointers, actions, reload, the request-delivery
    phases with their refusals / results and the `@aitask_dispatch_ack` ack;
  - "The skill" (~L267): the slim menu and TUI requests;
  - "Tests" (~L322): the new test files.
- `aidocs/framework/tmux_gateway.md`: confirm `@aitask_sitrep_tui_root` and
  `@aitask_dispatch_ack` are in the option inventory (added by t2211_2 / t2211_4).
- `website/content/docs/workflows/sitrep.md`: opening (three panes), what happens at start
  (the TUI harvests + refreshes), the list (in the TUI), triage / asking via TUI keys, the
  shortcodes table (slim), dismissing / restoring (TUI), closing a finished agent.
- `website/content/docs/skills/aitask-sitrep.md`: the capabilities table (slim). "What it
  never does" keeps "type into another agent's pane" and adds that the sitrep TUI types into
  the sitrep agent only at the user's request, refusing when the agent is at a dialog, holds
  a draft, is working or is in copy-mode.
- NEW `website/content/docs/tuis/sitrep/` (`_index.md`, `how-to.md`, `reference.md`),
  modelled on `website/content/docs/tuis/trails/` (front matter: title, linkTitle, weight,
  description, maturity, depth). The reference covers keys (default bindings + the shortcut
  scope `sitrep_tui`), groups, pointer kinds, actions, request keys with their refusals and
  results in user terms.
- `website/content/docs/tuis/_index.md`: add a bullet to "Available TUIs".
- The board reference page: `ait board --focus <id>`.
- Follow `aidocs/framework/documentation_conventions.md`:
  - current state only, no version history;
  - say "autonomous" if auto modes are mentioned;
  - genericize agent names where the passage names the supported coding agents.
- Prefer `{{< relref "/docs/..." >}}` for internal links.

## Verification

- `cd website && hugo build --gc --minify && python3 check_links.py --build` (mandatory).
- Offer `python3 check_link_relevance.py` for the new and retargeted links.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2211_8** id=2026-11-08T08:40:10Z.55f2b54f82b3c8d362ad1494 from=t2211_8 at=2026-11-08T08:40:10Z base=97af1d19ae282df63a283693757f25a30b657244 base_branch=main dirty=yes host=omg16
>
> | Advisory: t2211_8 (before t2211_3) adds a fixed list header, an action-oriented 'What to do' column replacing the internal kind/state, a 'how' line in details, plain-language source labels (KEY receipts hidden), Markdown for task/plan sources, and click-selects/Enter-opens. Document these on the TUI page.
