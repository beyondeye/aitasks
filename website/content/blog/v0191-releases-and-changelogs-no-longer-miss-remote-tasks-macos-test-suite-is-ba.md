---
date: 2026-04-28
title: "v0.19.1: Releases and changelogs no longer miss remote tasks, and macOS test suite is back at parity with Linux"
linkTitle: "v0.19.1"
description: "v0.19.1 is a quick follow-up to v0.19.0 with two reliability fixes you'll appreciate if you contribute to aitasks itself or develop on macOS."
author: "aitasks team"
---


v0.19.1 is a quick follow-up to v0.19.0 with two reliability fixes you'll appreciate if you contribute to aitasks itself or develop on macOS.

## Releases and changelogs no longer miss remote tasks

If you cut a release while local `main` was a few commits behind `origin/main`, the changelog could silently skip those tasks and the release tag could land on stale code. The release script and the `/aitask-changelog` skill now fetch and offer to pull before doing anything destructive, so you can run them confidently from any clone.

## macOS test suite is back at parity with Linux

Two long-standing portability bugs in the bash test suite have been fixed — one around BSD `sed -i` in archive-overbreadth tests, and one where macOS' tmpdir resolution made a multi-session test compare paths that should have matched. If you develop aitasks on macOS, the portability-related failures are gone.

---

---

**Full changelog:** [v0.19.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.19.1)
