---
date: 2026-10-29T12:32:50+02:00
title: "v0.40.1: Test-map runners that clean up after themselves, Code modules for the test map, and No more looping agents under mise"
linkTitle: "v0.40.1"
description: "v0.40.1 gives the test map real runners for your shell scripts, pytest and whole suites, keeps agents launched under mise out of endless loops, and brings lock checks on macOS up to par with Linux."
author: "aitasks team"
---


v0.40.1 gives the test map real runners for your shell scripts, pytest and whole suites, keeps agents launched under mise out of endless loops, and brings lock checks on macOS up to par with Linux.

## Test-map runners that clean up after themselves

`ait testmap` now ships three built-in runners. `bash-file` runs each shell test script as its own unit. `pytest` reports every test case by its exact node id, with xdist supported. `suite` wraps a whole-suite command as one result. On Linux each runner gets its own supervisor, so a test that leaves a daemon behind can't leak it past the run: it's stopped and reaped, and the record says so.

## Code modules for the test map

The test map can now group your files into code modules, inferred from your codemap and Gradle projects. `ait testmap modules --list` shows the table, `--explain <path>` tells you which module owns a file, and `--scan --apply` writes it out. Once you've declared a table, `check` warns you when it drifts out of date or when two modules overlap.

## No more looping agents under mise

If you use mise, a self-referential `mise x` wrapper in `~/.local/bin` could leave an agent launched in tmux looping forever, depending on your shell's PATH order. Now any `~/.local/bin` entry that comes before mise's entries is moved just after them, and nothing else changes, so the pane otherwise gets exactly your PATH.

## Live lock checks on macOS

macOS now records a precise process identity for lock holders, just as Linux does. That means `ait note --with-live`, sync's live-lock pane naming and the lock gate can tell whether a holder is still alive, instead of answering "unknown". Locks taken before the upgrade read as unknown until they're taken again.

## GPT-6.1 Terra and GPT-6 Astra

Codex can now run GPT-6.1 Terra and GPT-6 Astra, and the OpenCode model list was refreshed with ten new models. GPT-5.6 Terra is recorded as superseded by GPT-6.1 Terra.

---

---

**Full changelog:** [v0.40.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.40.1)
