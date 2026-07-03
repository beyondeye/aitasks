---
date: 2026-07-03
title: "v0.27.0: Attach files to your tasks, Quality gates that actually run, and Teach it a new skill"
linkTitle: "v0.27.0"
description: "v0.27.0 is a big one — task attachments, a real quality-gate framework, and a way to teach the tool new skills all landed in the same release."
author: "aitasks team"
---


v0.27.0 is a big one — task attachments, a real quality-gate framework, and a way to teach the tool new skills all landed in the same release.

## Attach files to your tasks

You can now attach files to any task with the new `ait attach` command. Attachments are stored content-addressed and reference-counted, so the same file shared across tasks is only stored once, and blobs are garbage-collected when nothing points at them anymore — including the tricky cases where you archive or fold a task.

## Quality gates that actually run

Tasks can now declare gates — build, test, lint, risk-evaluation, and even a docs-update gate — that run automatically before a task is allowed to complete. Human approval gates (review, merge) can be signed off out-of-band with `ait gate pass`, and those signatures are bound to the exact code state, so an approval can't be quietly reused against different changes.

## Teach it a new skill

The new `/aitask-learn-skill` command turns almost anything into a reusable skill: point it at a local file, a URL, a repo path, or even a live terminal pane, and it generates a complete skill for you. The shadow companion ties in too — it can now diagnose a followed agent's errors on request and spawn a learner to capture what it's doing.

## A snappier monitor

The monitor got a round of performance work: gate summaries are cached by file modification time instead of being re-read every tick, focus switching does far less redundant rendering, and synchronous tmux calls were pulled out of the refresh path so the UI stays responsive.

---

---

**Full changelog:** [v0.27.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.27.0)
