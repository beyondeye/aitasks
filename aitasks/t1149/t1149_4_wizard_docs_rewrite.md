---
priority: medium
effort: low
depends: [t1149_2, t1149_3]
issue_type: documentation
status: Ready
labels: [web_site]
gates: [risk_evaluated]
anchor: 1149
created_at: 2026-07-15 18:45
updated_at: 2026-07-20 19:16
---

## Context

Part of t1149 (chatlink config wizard TUI). `website/content/docs/workflows/bug-report-intake.md` documents gateway configuration as manual steps: hand-uncommenting the seeded YAML (config table in "Configure the gateway"), the `mkdir/chmod/printf` token dance ("The bot token" subsection), and `docker build` (appears three times: Prerequisites ~line 51, Walkthrough ~line 195, Troubleshooting ~line 309). With t1149_2 (status panel) and t1149_3 (wizard) landed, the primary configuration path is the TUI.

This child rewrites the "Configure the gateway" + Walkthrough sections around the wizard, keeping the hand-edit path documented as the FALLBACK. Depends on t1149_2 and t1149_3 (documents only what actually shipped).

## Pinned scope boundary (from the approved parent plan, aiplans/p1149_chatlink_config_wizard_tui.md)

Document ONLY current wizard/panel behavior as shipped by t1149_2 + t1149_3. **NO forward references to live Discord validation** — that capability and its doc rows are owned entirely by t1149_5, which updates the same troubleshooting sections when it lands. This prevents the docs implying a validation capability that does not exist yet, and avoids a second rewrite of freshly changed sections.

## Key files to modify

- `website/content/docs/workflows/bug-report-intake.md`:
  - "Configure the gateway": lead with `ait chatlink` -> `w` wizard flow (steps: intake channel -> allowlist -> deny mode / repo name -> ceilings -> token -> final preflight); keep the config-key reference table; move the hand-edit YAML + token shell commands into a clearly-labelled fallback subsection.
  - "Run it": mention the status panel (config checklist visible in the TUI; `r` also refreshes the expensive checks).
  - Walkthrough: replace the hand-edit + token-dance steps with the wizard; keep `docker build` (the wizard does not build the image — the panel only reports whether it exists).
  - Troubleshooting: add/adjust rows for what the panel/wizard now surfaces at config time (e.g. missing image now visible in the panel instead of "session fails right after thread opens" only); keep all existing daemon-refusal rows (unchanged by t1149_1's behavior-preserving contract).
  - Reminder in docs that the wizard writes the config to the working tree and the user commits it with `./ait git` (config is checked-in/shared; token file is per-machine and gitignored).
- Check `aidocs/chat/chatlink_runtime.md` for maintainer-side notes that mention startup-only validation; update if the preflight extraction (t1149_1) changed what it describes.

## Conventions

- `aidocs/framework/documentation_conventions.md`: current-state-only (no version history / "previously you had to..." narration), genericize any passage naming specific coding agents, generic example project names.
- The `intake_channel` metadata note (workspace_id = guild ID, conversation_id = channel ID for Discord) stays — the wizard asks for the same IDs.

## Implementation plan

1. Read the live sections of `bug-report-intake.md` and the shipped wizard/panel behavior (read t1149_2/t1149_3 archived plans + the actual code — document current source, not stale plan).
2. Rewrite the sections listed above; hand-edit path becomes "Manual configuration (fallback)".
3. Verify `hugo build --gc --minify` (in website/) passes.

## Verification

- `cd website && hugo build --gc --minify` succeeds.
- Rendered page: wizard is the primary path; fallback preserved; no mention of live Discord validation; troubleshooting rows consistent with shipped behavior.
- Grep the doc for the old imperative-only framing (`printf '%s' 'YOUR_BOT_TOKEN'` appears only in the fallback subsection).

## Coordination

- **t1189 (chatlink live-check user-facing hints + channel-access docs) has landed
  first** on `website/content/docs/workflows/bug-report-intake.md`: it added (a) a
  server-invite vs. per-channel permission-overwrites paragraph after the invite-URL
  step in Prerequisites, and (b) a troubleshooting row for "the bot lacks access to
  the intake channel". This rewrite MUST carry both forward. t1189 also switched the
  wizard/daemon fix-hint strings to reference this page's public URL
  (`https://www.aitasks.io/docs/workflows/bug-report-intake/`) — keep the page at
  that path.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1157_8** id=2026-09-10T18:36:15Z.9c82ad139677547dd326d189 from=t1157_8 at=2026-09-10T18:36:15Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the overlapping
> | task, not an agent working on it, so it is unverified. Advisory only —
> | tree-relative claims are dated by this note's base SHA; `~` line numbers are
> | approximate. Verify before acting.
> | 
> | 1. The wizard step order changed. As shipped: intake → token → live check →
> |    allowlist → deny/repo → ceilings → summary, seven steps (wizard.py ~1535;
> |    reordered by t1186_3, c10942311).
> | 
> | 2. "No references to live Discord validation" is obsolete. t1149_5 (e76f8d466)
> |    landed first and added a live-validation paragraph (bug-report-intake.md
> |    ~311); its Final Notes (p1149_5 ~410) ask this task to describe seven steps
> |    and fold that paragraph in.
> | 
> | 3. "The user commits the config with ./ait git" is wrong since t1677
> |    (38aaf5dcb): the summary step commits chatlink_config.yaml itself
> |    (wizard.py ~1296-1322); a manual commit is only the fallback when that
> |    fails. The token file stays per-machine and gitignored.
> | 
> | 4. Shipped but absent from your task: resumable drafts with a resume screen
> |    (t1190, 15bdeed47); live Discord allowlist pickers (t1186_4, 976dc4ea2) and
> |    the stale-row flag (be6029f39); per-dimension allow/deny modes inside the
> |    allowlist step (868d01455).
> | 
> | 5. Preserve what's there: the channel-access paragraph and troubleshooting row
> |    (t1189, 92fd88d9f); the auth-mode rows and deny-by-default paragraph
> |    (868d01455). "Run it" (~158-165) still lists only r/q/j — no `w`, no status
> |    panel.
> | 
> | 6. aidocs/chat/chatlink_runtime.md ~113-114 already names preflight and the
> |    wizard (t1186_1); ~28-30 still describe the TUI as a sessions table plus
> |    audit tail only.
> | 
> | 7. OVERLAP: t1157_8 will later rewrite the same sections (Configure the
> |    gateway, The bot token, Walkthrough, Troubleshooting) for multi-workflow
> |    Chatlink, and does not depend on you. Keeping the key table plus a "Manual
> |    configuration (fallback)" structure lets it edit in place.
