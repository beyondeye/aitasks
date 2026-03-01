---
Task: t195_python_codebrowser.md
Branch: main
Base branch: main
---

# Plan: t195 — Python Code Browser TUI

This is the parent plan. See child plans in `aiplans/p195/` for individual task plans.

## Architecture

See `/home/ddt/.claude/plans/zazzy-percolating-lobster.md` for the full architecture document.

## Child Tasks (11 total)

### Core Features (Phase 1-3)
1. **t195_1** — Core scaffold + launcher (no deps)
2. **t195_2** — File tree browser widget (deps: t195_1)
3. **t195_3** — Code viewer with syntax highlighting (deps: t195_1, t195_2)
4. **t195_4** — Explain data auto-generation (deps: t195_1)

### Integration (Phase 4-6)
5. **t195_5** — Task annotation overlay (deps: t195_3, t195_4)
6. **t195_6** — Cursor navigation + range selection (deps: t195_3, t195_5)
7. **t195_7** — Claude Code explain integration (deps: t195_4, t195_6)

### Risk Mitigation Follow-ups (Phase 4-7)
8. **t195_8** — Rendering hardening (deps: t195_5)
9. **t195_9** — Viewport windowing for large files (deps: t195_6)
10. **t195_10** — Explain generation optimization + UX (deps: t195_4, t195_5)
11. **t195_11** — `--no-recurse` flag for extract script (deps: t195_4)

## Recommended Order
Phase 1: t195_1 → Phase 2: t195_2 + t195_4 (parallel) → Phase 3: t195_3 → Phase 4: t195_5 + t195_11 → Phase 5: t195_6 + t195_10 → Phase 6: t195_7 + t195_8 → Phase 7: t195_9

## Step 9 Reference
After all children complete: archive parent task per shared workflow.
