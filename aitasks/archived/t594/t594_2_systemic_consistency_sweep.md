---
priority: high
effort: low
depends: []
issue_type: documentation
status: Done
labels: []
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-19 17:10
updated_at: 2026-04-19 19:48
completed_at: 2026-04-19 19:48
---

Cross-cutting child of t594. Align wording and resolve contradictions for 5 repeated concepts across the website, plus fix two narrative contradictions — all without removing repeated content (conservative dedup per user).

## Context

Parent plan: `aiplans/p594_website_documentation_coherence.md`. This child finalizes canonical wording for repeated concepts so siblings t594_4/5/6 don't re-fix the same lines. Runs independently of t594_1/3.

## Key Files to Modify

**TUI switcher `j` key (4+ pages):**
- `website/content/docs/getting-started.md:41`
- `website/content/docs/tuis/_index.md:27`
- `website/content/docs/installation/terminal-setup.md:38`
- `website/content/docs/workflows/tmux-ide.md:33`
- Plus any other hits from `grep -rn "TUI switcher" website/content`.

**Install curl command (3 pages):**
- `website/content/docs/installation/_index.md:8-26`
- `website/content/docs/getting-started.md:10-26`
- `website/content/docs/installation/windows-wsl.md:40-52`

**"Run from project root" warning (3+ pages):**
- `website/content/docs/installation/_index.md:12`
- `website/content/docs/getting-started.md:20`
- `website/content/docs/skills/_index.md:14`

**Task file format (2 pages):**
- `website/content/docs/concepts/tasks.md:8-10`
- `website/content/docs/development/task-format.md:7-10`

**Pick variants (3 pages):**
- `website/content/docs/skills/aitask-pick/_index.md`
- `website/content/docs/skills/aitask-pickrem.md`
- `website/content/docs/skills/aitask-pickweb.md`

## Reference Files for Patterns (Authoritative Sources)

- `install.sh` at repo root — canonical curl command and `ait setup` invocation.
- `aitasks/metadata/profiles/fast.yaml:10` — `post_plan_action: ask` is the ground truth for the fast profile contradiction.
- `.claude/skills/aitask-pickrem/SKILL.md` — profile is required for pickrem.

## Implementation Plan

1. **TUI switcher `j`:** pick one canonical sentence (e.g., "Press `j` inside any main TUI to open the TUI switcher dialog and jump to another TUI.") and replace all 4+ instances with the same sentence shape — keep in all pages.
2. **Install curl command:** verify against `install.sh`; ensure all 3 pages show the exact same command, same flags, same follow-up `ait setup` step.
3. **Project-root warning:** unify to one sentence shape across the 3 pages.
4. **Task file format:** align sentences in `concepts/tasks.md` and `development/task-format.md`; add an explicit line in `concepts/tasks.md` saying `development/task-format.md` is the full-schema authority.
5. **Pick variants:** unify step names across pick/pickrem/pickweb. Remove the duplicate comparison table inside `aitask-pickweb.md` (identical tables at lines 26-48 and 38-46).
6. **Contradiction fix 1:** align the `aitask-pickrem.md` prose with the comparison table's "Required, auto-selected" phrasing.
7. **Contradiction fix 2 (fast profile):** update `skills/aitask-pick/_index.md:24` and `execution-profiles.md:14` to describe the shipped `fast` profile as "pauses for confirmation after plan approval" (matches `fast.yaml: post_plan_action: ask`). Do NOT change the YAML.

## Verification Steps

- `grep -rn "TUI switcher" website/content/docs/` — all hits share the same canonical sentence.
- `diff <(grep -A2 "curl" website/content/docs/installation/_index.md) <(grep -A2 "curl" website/content/docs/getting-started.md)` — curl commands match verbatim.
- `/aitask-pick --profile fast` — the doc's description of the fast profile matches observed behavior (a prompt appears after plan approval).
- `cd website && hugo build --gc --minify` succeeds.
