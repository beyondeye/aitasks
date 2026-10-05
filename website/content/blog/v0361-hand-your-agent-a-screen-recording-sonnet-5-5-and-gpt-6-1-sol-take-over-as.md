---
date: 2026-10-05
title: "v0.36.1: Hand your agent a screen recording, and Sonnet 5.5 and GPT-6.1 Sol take over as defaults"
linkTitle: "v0.36.1"
description: "v0.36.1 is a small release with two additions: your agent can now watch a screen recording, and newer models are the defaults."
author: "aitasks team"
---


v0.36.1 is a small release with two additions: your agent can now watch a screen recording, and newer models are the defaults.

## Hand your agent a screen recording

Coding agents can read images but not video, so a bug-report clip or a motion mockup used to be a dead end. The new `/aitask-screen-recording` skill turns a recording into contact sheets, key frames and a timeline that the agent can read. For animations, it also measures duration and easing, so "match this transition" gets real numbers instead of a guess. You need ffmpeg installed, and nothing is uploaded or written into your repo.

## Sonnet 5.5 and GPT-6.1 Sol take over as defaults

Claude Sonnet 5.5 is registered, along with a 1M-context variant. It is now the default wherever Sonnet 5 was, including explain, QA, batch review, work reports and the brainstorm operations. On the Codex side, GPT-6.1 Sol replaces GPT-6 Sol for shadow and discuss agents. The older models remain registered if you want to pin them.

---

---

**Full changelog:** [v0.36.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.36.1)
