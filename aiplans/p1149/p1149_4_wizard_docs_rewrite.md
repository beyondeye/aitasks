---
Task: t1149_4_wizard_docs_rewrite.md
Parent Task: aitasks/t1149_chatlink_config_wizard_tui.md
Sibling Tasks: aitasks/t1149/t1149_1_preflight_module.md, aitasks/t1149/t1149_2_config_status_panel.md, aitasks/t1149/t1149_3_config_wizard_flow.md, aitasks/t1149/t1149_5_live_discord_validation.md
Archived Sibling Plans: aiplans/archived/p1149/p1149_*_*.md
Worktree: (per picking profile)
Branch: (per picking profile)
Base branch: main
---

# p1149_4 — Docs rewrite around the wizard

Rewrite the "Configure the gateway" + Walkthrough sections of
`website/content/docs/workflows/bug-report-intake.md` around the shipped
wizard (t1149_3) + status panel (t1149_2), keeping the hand-edit YAML /
token-shell / `docker build` path as a clearly-labelled **fallback**.
Depends on t1149_2 + t1149_3.

## Pinned scope boundary (parent plan)

Document ONLY behavior actually shipped by t1149_2 + t1149_3. **NO forward
references to live Discord validation** — t1149_5 owns that capability and
its doc rows entirely, updating these same sections when it lands.

## Implementation steps

1. Read the SHIPPED code + archived sibling plans
   (`aiplans/archived/p1149/p1149_2_*.md`, `p1149_3_*.md`) — document current
   source, not the plan (plans drift).
2. "Configure the gateway": lead with `ait chatlink` → `w` (step list:
   intake channel → allowlist → deny mode / repo name → ceilings → token →
   final preflight). Keep the config-key reference table. Move the hand-edit
   YAML + `mkdir/chmod/printf` token commands into "Manual configuration
   (fallback)".
3. "Run it": mention the status panel checklist; `r` refreshes the expensive
   checks too.
4. Walkthrough: replace hand-edit + token-dance steps with the wizard; KEEP
   `docker build` (the wizard reports the image, it does not build it).
5. Troubleshooting: add/adjust rows for what the panel/wizard surface at
   config time (e.g. missing image visible in the panel); keep all existing
   daemon-refusal rows (unchanged by t1149_1's behavior-preserving
   contract). Note the wizard writes to the working tree and the user
   commits with `./ait git` (config shared; token per-machine, gitignored).
6. Check `aidocs/chat/chatlink_runtime.md` for startup-only-validation
   phrasing invalidated by the preflight extraction; update if needed.
7. Conventions: `aidocs/framework/documentation_conventions.md` —
   current-state-only, genericized agent names, generic example project
   names.

## Verification

- `cd website && hugo build --gc --minify` succeeds.
- Rendered page: wizard primary, fallback preserved, zero mention of live Discord validation, troubleshooting rows consistent with shipped behavior.
- `printf '%s' 'YOUR_BOT_TOKEN'` appears only inside the fallback subsection.

Refer to Step 9 (Post-Implementation) of the task workflow for merge/archival.
