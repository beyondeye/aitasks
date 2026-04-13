---
date: 2026-04-13
title: "v0.15.1: Scroll back through your agent's output, `ait ide` from a fresh shell just works, TUI switcher, and  now documented"
linkTitle: "v0.15.1"
description: "A quick follow-up to v0.15.0 with one notable feature, a shim fix, and the final piece of the TUI switcher docs."
author: "aitasks team"
---


A quick follow-up to v0.15.0 with one notable feature, a shim fix, and the final piece of the TUI switcher docs.

## Scroll back through your agent's output

The monitor preview has been pretty tight until now — you saw the last few lines and that was it. v0.15.1 gives it real scrollback: mouse-wheel through the last 200 lines, toggle a scrollbar with `b`, or cycle to an XL preset that fills the whole terminal. It still follows the tail automatically, so you only lose the auto-scroll when you actually scroll up to read something.

## `ait ide` from a fresh shell just works

If you ever ran `ait ide` and got a confusing "shim loop" error, that was the global shim leaking its recursion guard into the project-local `ait` it handed off to. That's fixed now. If you installed the shim before this release, re-run `ait setup` once to regenerate it — then it's a one-time thing and you're done.

## TUI switcher, now documented

The `j` TUI switcher shipped a few versions ago but the docs didn't catch up until now. There's a new overview page listing all the TUIs you can jump between, and the board, codebrowser, and settings how-tos each explain how `j` fits into their workflow. The monitor footer also got a small rename — "Jump TUI" is now "TUI switcher", which is what everyone was calling it anyway.

---

---

**Full changelog:** [v0.15.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.15.1)
