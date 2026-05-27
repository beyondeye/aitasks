---
date: 2026-05-27
title: "v0.21.1: Choose-sibling picker in monitor, Brainstorm retry-apply actually retries, and Release-post YAML hardening"
linkTitle: "v0.21.1"
description: "v0.21.1 is a small patch — a couple of brainstorm/monitor papercuts and a fix for the v0.21.0 release-post pipeline so the next blog post doesn't break."
author: "aitasks team"
---


v0.21.1 is a small patch — a couple of brainstorm/monitor papercuts and a fix for the v0.21.0 release-post pipeline so the next blog post doesn't break.

## Choose-sibling picker in monitor

The monitor TUI's next-task dialog now lets you pick any ready sibling of the current task from a list, with blocked-by-sibling annotations on each row. Mid-family pivots no longer require backing out to the board.

## Brainstorm retry-apply actually retries

The `ctrl+shift+x/y/d` retry-apply bindings in brainstorm were silently doing nothing once their internal tracking set drained — typically right after the original apply ran. They now rescan the worktree for completed agents on every invocation, and surface a clear notify when there's nothing to retry.

## Release-post YAML hardening

`website/new_release_post.sh` now escapes title and description fields before writing the blog frontmatter and runs a Python YAML smoke check after generation, so a release post with inner quotes can't ship a broken page anymore (and the v0.21.0 post is now repaired).

---

---

**Full changelog:** [v0.21.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.21.1)
