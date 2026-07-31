---
date: 2026-07-31
title: "v0.30.0: The shadow companion,  in the full monitor, Manage every linked repo from the syncer, and Triage that keeps up with you"
linkTitle: "v0.30.0"
description: "v0.30.0 brings the shadow companion to the full monitor, turns the syncer into a real cross-repo control panel, and adds a pile of triage shortcuts you'll wonder how you lived without."
author: "aitasks team"
---


v0.30.0 brings the shadow companion to the full monitor, turns the syncer into a real cross-repo control panel, and adds a pile of triage shortcuts you'll wonder how you lived without.

## The shadow companion, in the full monitor

Everything the minimonitor could do with a shadow agent, the full monitor can now do too — and then some. Your shadow sits in its own column right beside the agent it's watching, with a live preview you can type into. When it raises concerns, you get a badge on the agent's card and a toast the moment they appear; hit `c` to page through them. Spawning is `e` / `E`, same as before, with a guard so you can't accidentally end up with two shadows on one agent.

## Manage every linked repo from the syncer

The syncer grew two new tabs. **Versions** shows you which framework version each of your linked repos is running and upgrades them in place — including a clean handoff when it's upgrading the repo the syncer itself is running from. **Settings** shows how any configuration value resolves across all your repos side by side, and a four-step wizard pushes one setting out to the others. Secrets get masked, writes are atomic, and a type conflict gets reported instead of quietly overwriting what was there.

## Triage that keeps up with you

Agents that have actually finished now show a COMPLETED badge instead of blending in with the merely idle ones — with their own counter and auto-switch filter. Press `space` on any agent to mark it as prioritized, and that mark follows it across every repo you're working in. Press `p` to launch a task by typing its number, and you'll get a heads-up if its dependencies aren't met yet. In the minimonitor, `I` pulls up task info for the agent you're currently following, no matter where your focus is.

## Gates that repair themselves

If your project's gate registry has drifted from the framework's — missing fields, gates that never got a verifier — `ait gates sync-registry` reconciles it for you. It fills in what's missing, reports what genuinely conflicts instead of guessing, and leaves your comments byte-for-byte intact. Nothing is committed on your behalf. And if you pick up a task whose active gate has no verifier configured, you now find out at pick time rather than at the end.

## Know what you forgot to document

The new `/aitask-docs-gap` skill looks at everything that landed since your last release, works out which changes should have shown up in the docs and didn't, and files a single documentation task covering the gaps. This release's own documentation pass came from it.

---

---

**Full changelog:** [v0.30.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.30.0)
