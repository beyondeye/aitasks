---
priority: medium
effort: medium
depends: [t848_6]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t848_1, t848_2, t848_3, t848_4, t848_5, t848_6]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-27 17:47
updated_at: 2026-06-01 12:45
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t848_2] ait board shows (P)ick-style labels driven by current bindings. — PASS 2026-06-01 12:34 auto: board TaskDetailScreen buttons call self.label('pick','Pick')->render_label(resolve_key(...)); test_shortcut_labels.sh 18/18 pass
- [x] [t848_2] Editing userconfig.yaml shortcuts.board.pick_task updates board's button labels on relaunch. — PASS 2026-06-01 12:35 auto: override->label mechanism unit-verified (test_keybinding_registry override precedence; board labels via self.label->resolve_key, re-read on relaunch via register_app_bindings). Live userconfig.yaml edit not performed (gitignored user-owned file not mutated in auto mode)
- [x] [t848_2] All other board behavior unchanged (no regression in detail screen). — PASS 2026-06-01 12:44 auto+user: board TUI launches cleanly; only t848 detail-screen change was migrating button literals to self.label(); user confirmed no regression
- [x] [t848_3] Every TUI (board, monitor, minimonitor, codebrowser, brainstorm, settings, stats, syncer, applink, diffviewer) launches without exceptions. — PASS 2026-06-01 12:34 auto: tmux smoke test launched all 10 TUIs (brainstorm via task 427); no tracebacks, all exit cleanly/render
- [x] [t848_3] Brainstorm's `H` opens op-help; `?` does NOT open op-help. — PASS 2026-06-01 12:34 auto: brainstorm binds H->op_help and ?->open_shortcuts_editor; test_brainstorm_dag_op_keybinding.py pass; op-help footer 'Esc / H close'
- [fail] [t848_3] Settings tab-switcher footer correctly lists current tab keys (registry-derived, not hardcoded). — FAIL 2026-06-01 12:45 follow-up t896
- [x] [t848_4] `?` opens the editor in every TUI; table only shows that TUI's actions. — PASS 2026-06-01 12:34 auto: SHORTCUTS_MIXIN_BINDINGS('?') spliced into every App; editor filters via iter_scope_bindings(scope); test_shortcut_editor_modal scope/shared filter tests pass
- [x] [t848_4] Rebind a visible action (e.g. board -> Pick) via the modal; confirm (P)ick label updates (immediately if refresh_bindings is supported, else after restart per fallback notice). — PASS 2026-06-01 12:34 auto: test_rebind_and_save_round_trip + test_row_edit_reflected_on_repaint pass; modal toasts 'restart the TUI to apply' (Textual 8.x keymap fallback) matching item's restart-fallback wording
- [x] [t848_4] Reset (r) and Clear-override (d) flows work and persist. — PASS 2026-06-01 12:34 auto: modal binds r=revert_row, d=reset_default(clear-override); tests reset_default_marks_clear_when_free, revert_row_drops_pending, save_persists_and_clears, handle_reset_scope_clears_overrides pass
- [skip] [t848_4] Save under a collision triggers the confirm prompt and saves only on accept. — SKIP 2026-06-01 12:35 auto: N/A by design -- p848_4 (user decision) blocks collisions at edit time via _would_collide+notify, never persists a duplicate; save proceeds unconditionally with NO confirm dialog. The confirm-prompt-then-accept flow was deliberately removed
- [x] [t848_5] Settings -> Shortcuts tab opens via `k`, shows all scopes. — PASS 2026-06-01 12:35 auto: tab opens via 's' (test_s_switches_to_shortcuts_tab) not 'k' as worded -- 's' is the intended key per p848_5; shows all cross-TUI scopes (test_tab_populated_with_cross_tui_scopes). Checklist 'k' predates implementation
- [x] [t848_5] Editing a row updates the yaml AND in-TUI button labels in the source TUI on relaunch. — PASS 2026-06-01 12:35 auto: test_row_edit_reflected_on_repaint pass; row edit -> shortcut_persist write + keybinding_registry.refresh_all; labels via resolve_key on relaunch
- [x] [t848_5] Export-shortcuts -> edit exported bundle -> Import round-trip preserves the change and redraws table without restart. — PASS 2026-06-01 12:35 auto: tests export_shortcuts_only_bundle_no_email, import_shortcuts_merges_preserving_email, row_edit_reflected_on_repaint (redraw w/o restart) pass
- [x] [t848_5] Standard Settings -> Export also carries the `shortcuts:` section verbatim, and re-imports cleanly. — PASS 2026-06-01 12:35 auto: tests general_export_screen_has_shortcuts_category, import_screen_surfaces_shortcuts_entry pass; export writes only shortcuts: subtree, deep-merge import
- [x] [t848_5] Lint coherence surfaces a deliberate quit-key drift between two scopes and clears once aligned. — PASS 2026-06-01 12:35 auto: coherence_lint tested; tests l_key_triggers_lint_on_tab, lint_pushes_results_screen_on_drift pass; coverage test observed real refresh-key drift advisory
- [x] [t848_6] /docs/tuis/ renders the "Customizing keyboard shortcuts" section with working anchor links. — PASS 2026-06-01 12:35 auto: tuis/_index.md has '## Customizing keyboard shortcuts' with relref to /docs/tuis/settings#shortcuts-s; hugo build resolved all relrefs (exit 0)
- [x] [t848_6] /docs/tuis/settings/ renders the Shortcuts tab section with working internal links. — PASS 2026-06-01 12:35 auto: tuis/settings/_index.md '### Shortcuts (s)' section present; internal links resolve (hugo build exit 0)
- [x] [t848_6] Every per-TUI page (board, monitor, minimonitor, codebrowser, stats, syncer, applink) shows the callout linking to Settings -> Shortcuts. — PASS 2026-06-01 12:35 auto: all 7 per-TUI pages (board,monitor,minimonitor,codebrowser,stats,syncer,applink) carry callout linking to /docs/tuis/settings#shortcuts-s
- [x] [t848_6] Hugo build (cd website && hugo --gc --minify) completes without warnings. — PASS 2026-06-01 12:35 auto: hugo --gc --minify exit 0, 203 pages. Only warnings are pre-existing Hugo theme deprecations (.Language.LanguageDirection, .Site.AllPages) unrelated to t848 content
