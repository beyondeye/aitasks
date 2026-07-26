---
date: 2026-07-26
title: "v0.29.0: Implementation trails, Work reports, and A real setup wizard for chat intake"
linkTitle: "v0.29.0"
description: "v0.29.0 is a big one — two brand-new planning and reporting workflows, a proper setup wizard for chat intake, and Opus 5 / Sonnet 5 wired in as defaults."
author: "aitasks team"
---


v0.29.0 is a big one — two brand-new planning and reporting workflows, a proper setup wizard for chat intake, and Opus 5 / Sonnet 5 wired in as defaults.

## Implementation trails

Big features rarely fit in one task, and figuring out what to do first across a dozen related tasks is a chore you end up redoing every week. `/aitask-trail` does that analysis once and stores the answer: a wave-by-wave implementation plan, backed by evidence from the actual task files, plans, and gate state. It lives as a versioned artifact, so it survives the session — and when the underlying tasks change, the trail tells you it's stale and why. The board picks it up with a new By-Trail view (`z`): waves become columns, each card shows its classification and confidence, and `enter` opens the full narrative.

## Work reports

Someone asks what you shipped this week and you go spelunking through git log. Not anymore. Hit `w` on the board, pick the columns you care about, and `/aitask-work-report` drafts a manager-facing summary: what landed, what's in flight, what's queued. Turn on the projection and it'll estimate a delivery date from your actual recent velocity — with a confidence floor, so it stays quiet when it doesn't have enough data to be honest.

## A real setup wizard for chat intake

Configuring the Discord bug-report intake used to mean hand-editing YAML and guessing at channel IDs. The `ait chatlink` TUI now has a config-check panel showing exactly what's working and what isn't, plus a `w` wizard that walks you through the whole thing. It validates your bot token against Discord live — login, privileged intents, channel visibility, permissions — then fetches your channel members and roles so you pick them from a list instead of pasting snowflake IDs. Get interrupted? It saves a token-free draft and offers to resume.

## Sharper shadow reviews

The shadow companion's implementation review now comes in four tiers — Quick, Basic, Standard, Deep — so you can ask for a hunk-level sanity check or a full adversarial interrogation. Every finding carries a disposition (blocking, follow-up, or informational) and a verdict, and the rules were reworked so a real defect can never be quietly dropped to stay under a cap. If something is omitted, the review has to say so.

## Opus 5 and Sonnet 5

Both are registered for Claude Code. Opus 5 is now the default for the heavy operations — pick, explore, learn, trail, and brainstorm — and Sonnet 5 takes over the lighter ones.

---

---

**Full changelog:** [v0.29.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.29.0)
