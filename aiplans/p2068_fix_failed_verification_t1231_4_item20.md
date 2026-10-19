---
Task: t2068_fix_failed_verification_t1231_4_item20.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: add the missing Profiles / Shortcuts keys to the settings reference (t2068)

## Context

Manual verification t1231_4 item #20 failed: `website/content/docs/tuis/settings/reference.md`
matches the live `ait settings` TUI on its **Tabs** and **Global** tables, but the
**Within Tabs** table omits tab-scoped keys the TUI binds and shows on screen:

- **Profiles tab** — `w` / `v` / `x` (Save / Revert / Delete profile) and `Tab` (switch pane).
- **Shortcuts tab** — `d` (Reset scope) and `l` (Lint coherence); described only in `_index.md`.

Source of truth (verified):

- `.aitask-scripts/settings/settings_app.py:2082-2089` — `Binding("d", "sc_reset")`,
  `Binding("l", "sc_lint")`, `Binding("w", "profile_save")`, `Binding("v", "profile_revert")`,
  `Binding("x", "profile_delete")`, all tab-gated in `check_action` (`:2128`).
- `:4612-4645` — `action_profile_save` (no-op + "No changes to save" toast when clean, else
  confirm dialog), `action_profile_revert` (no-op when clean), `action_profile_delete`
  (confirm dialog).
- `:2386-2394` — `on_key`: `Tab` / `Shift+Tab` on the Profiles tab call
  `_cycle_profile_pane` (`:4548`), which moves focus between the profile selector, search
  box, fields and buttons.
- `:4467-4470` — Profiles hint line `Tab: switch pane | … | w/v/x: save/revert/delete`.
- `:4951-4953` — Shortcuts buttons `Reset scope` (d) / `Lint coherence` (l);
  `:4985-5000` — `Enter` on a Shortcuts row opens `ShortcutEditorModal` for that row's scope
  (also absent from the reference table; documented in `_index.md:142`, so it is added too —
  same tab, same "every key" criterion).

## Change (single file)

`website/content/docs/tuis/settings/reference.md`, **Within Tabs** table — insert these rows,
keeping the table's existing grouping by tab (Profiles rows next to the existing Profiles `?`
row; Shortcuts rows after them, before the `Escape` / Modals row):

| Key | Action | Context |
|-----|--------|---------|
| **Tab** / **Shift+Tab** | Move focus between the profile selector, search box, fields and buttons | Profiles |
| **w** | Save the selected profile (after a confirmation; only when it has unsaved changes) | Profiles |
| **v** | Revert the selected profile's unsaved changes | Profiles |
| **x** | Delete the selected profile (after a confirmation) | Profiles |
| **Enter** | Open the shortcut editor for the selected row's scope | Shortcuts |
| **d** | Reset scope — clear every override for the selected row's scope (after a confirmation) | Shortcuts |
| **l** | Lint coherence — report actions that should share a key across TUIs but have drifted apart | Shortcuts |

Wording mirrors `_index.md:142-147` for the Shortcuts rows. No other page changes
(`_index.md` already describes the Shortcuts buttons; current-state prose only, per
`aidocs/framework/documentation_conventions.md`).

## Verification

- `cd website && python3 check_links.py --build` — must pass (CLAUDE.md rule for any
  `website/content/` edit).
- Re-read the edited table against the `BINDINGS` list / hint lines above: every
  `profile_*` and `sc_*` binding plus the Profiles `Tab` and Shortcuts `Enter` handling now has
  a row.
- `cd website && hugo build --gc --minify` renders the table (sanity: no markdown breakage).

## Step 9

Post-implementation: commit (`documentation: … (t2068)`), archive via the standard Step 9 flow.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
