---
Task: t1169_rename_shadow_review_tiers_drop_codex_chooser.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Post-t1158 follow-up in three parts: (1) renamed the shadow
implementation-review effort tiers quick/basic/standard/deep →
quick/default/advanced/deep across the Claude-tree shadow skill files, keeping
the old names as free-text aliases; (2) removed the deterministic two-stage
tier chooser for 3-option-capped agents after empirically verifying, in a live
tmux-driven Codex session (v0.144.6), that `request_user_input` accepts 4
options per question — and corrected the stale 3-option-cap claim in the Codex
tool-mapping doc; (3) documented the tiered implementation review modes on the
website shadow-agent page.

## Files Modified

- `.claude/skills/aitask-shadow/impl-challenge.md` — tier names renamed
  throughout (intro, tier-selection keyword table, AskUserQuestion options,
  angle-activation table columns, tier section headers `Tier: Default (=
  Legacy)` / `Tier: Advanced`, scoping guard rails, findings-presentation and
  concern-body verdict references). The two-stage 3-option-capped chooser
  paragraph replaced by a note that the single 4-option question works on
  every supported agent, citing the live Codex verification. Free-text
  detection now maps "default"/"basic"/"legacy"/unqualified "adversarial
  review" → Default and "advanced"/"standard"/"normal" → Advanced.
- `.claude/skills/aitask-shadow/impl-review-angles.md` — shadow/legacy-axes
  intro renamed (Default tier's attack surface; S0 is Default-only,
  superseded by A–E in Advanced/Deep).
- `.claude/skills/aitask-shadow/SKILL.md` — Step 3 routing bullet renamed
  (tier list, "adversarial review" with no qualifier → default; recommends
  advanced).
- `.agents/skills/codex_tool_mapping.md` — `request_user_input` options limit
  corrected: 4 options per question verified working on Codex v0.144.6
  (2026-07-20); the combine/split/drop adaptation guidance replaced with
  "present 4-option questions as-is"; the 3-questions-per-call cap retained
  (untested).
- `website/content/docs/workflows/shadow-agent.md` — "Review the
  implementation" section documents the four tiers (Quick / Default /
  Advanced / Deep) with pass structure, findings caps, disposition tags,
  blocking-first ordering, verdicts, cap-overflow disclosure, tier request
  phrases, and free-text angle scoping; the concern-forwarding section notes
  disposition/verdict text in concern bodies. Hugo production build verified.

## Probable User Intent

The original t1158 tier names ("basic"/"standard") did not communicate their
roles: "Default" makes explicit that the legacy-compatible tier is what an
unqualified ask gets, and "Advanced" better signals the systematic
angle-based upgrade. The two-stage Codex chooser was designed against a
documented 3-option cap; the user questioned that limit's validity and its UX
cost, and a live driven Codex session disproved the cap — so the workaround
and the stale documentation were both removed. The website update makes the
new review modes discoverable to end users.

## Verification

- Live Codex test: spawned `codex` in a tmux window, prompted a
  `request_user_input` call with 4 options; all four rendered and were
  selectable (plus Codex's own "None of the above" row).
- `python3 -m unittest tests.test_concern_parser` — OK.
- `./.aitask-scripts/aitask_skill_verify.sh` — OK (no golden/stub impact).
- `grep` sweep: no stray old tier names outside the intentional free-text
  aliases.
- `hugo build --gc --minify` — clean production build.

## Final Implementation Notes

- **Actual work done:** Tier renames across the three Claude-tree shadow
  skill files, two-stage chooser removal, Codex tool-mapping correction, and
  the website shadow-agent tier documentation (see Files Modified).
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed for
  this follow-up; the archived p1158 plan documents the original tier design
  under the old names).
- **Issues encountered:** N/A (changes were already made and verified before
  wrapping).
- **Key decisions:** Old tier names kept as permanent free-text aliases so
  existing user habits keep routing correctly; the Codex mapping doc records
  the verified version/date for the lifted options cap while retaining the
  untested questions-per-call cap; internal Codex-adaptation details were
  deliberately kept out of the website page (current-state-only, user-level
  prose). The t1168 live-check checklist was updated to the new tier names in
  a separate data-branch commit.
- **Upstream defects identified:** None (the concern-parser split-marker
  fragility surfaced during this work was already spawned as t1167 from
  t1158's Step 8b).
