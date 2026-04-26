---
priority: medium
effort: medium
depends: [t653_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [653_1, 653_2, 653_3]
created_at: 2026-04-26 14:38
updated_at: 2026-04-26 14:38
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t653_1] Build a synthetic session at .aitask-crews/crew-brainstorm-9999/ that mirrors session 635 (placeholder n000_init + valid initializer_bootstrap_output.md + status: Completed). Run `ait brainstorm 9999`. Confirm: dashboard auto-applies on load, n000_init shows real description, banner stays hidden. Clean up: rm -rf .aitask-crews/crew-brainstorm-9999/.
- [ ] [t653_1] Same fixture but with status: Error and NO _output.md. Open `ait brainstorm 9999`. Confirm: banner shows with retry-CLI hint. While TUI stays open, copy a valid _output.md into the session dir. Within 30 s confirm the slow watcher applies the output, banner clears, dashboard refreshes.
- [ ] [t653_1] Same fixture but write a malformed _output.md (e.g., bracket left unclosed in NODE_YAML). Open the TUI. Confirm: banner appears with the YAML error and stays visible through arrow-key navigation, scrolling, and detail-modal open/close. Press Ctrl+R to manually retry; banner re-renders the same error. Replace the malformed file with a good one and Ctrl+R again — apply succeeds, banner clears.
- [ ] [t653_1] Happy-path regression: run `ait brainstorm` on a fresh small clean proposal (no em-dashes) end-to-end. Confirm: agent completes, dashboard auto-updates within ~2 s of agent's Completed write, banner never appears.
- [ ] [t653_2] After this child lands, run `ait brainstorm apply-initializer 635` on the user's actual stuck session 635. Confirm: prints APPLIED:n000_init. Then open `ait brainstorm 635` and confirm n000_init shows the real description and the imported proposal markdown.
- [ ] [t653_2] Confirm the new ./.aitask-scripts/aitask_brainstorm_apply_initializer.sh runs in this session WITHOUT a permission prompt — invoke it once with a nonexistent session ID and verify no prompt is shown.
- [ ] [t653_3] Contrive a brainstorm crew where an agent ends up in Error (set heartbeat_timeout_minutes: 0 in _crew_meta.yaml and wait one runner iteration). Run `ait crew status set --crew <id> --agent <name> --status Completed`. Confirm: command succeeds (no validator rejection), local _status.yaml flips, a new git commit appears in the worktree, and `git log origin/<branch>..HEAD` is empty (i.e., the commit was pushed).
- [ ] [t653_3] Confirm no regression in runner push cadence: tail a runner log during a small live brainstorm crew and verify exactly one "runner: iteration N" push per iteration — neither doubled nor missing.
- [ ] [t653 parent] Final integration check: with t650 + all three t653 children landed, run a fresh `ait brainstorm` import on a proposal whose initializer agent will produce em-dashes in NODE_YAML (e.g., the gates-framework proposal). Confirm end-to-end: agent runs > 6 min without false-Error, _output.md is auto-applied (tolerant load), dashboard shows real proposal, remote reflects final Completed status.
