---
date: 2026-06-04
title: "v0.23.1: Installs that just re-run cleanly, and Less untracked clutter from generated skills"
linkTitle: "v0.23.1"
description: "v0.23.1 is a small housekeeping release that smooths out installs and setup."
author: "aitasks team"
---


v0.23.1 is a small housekeeping release that smooths out installs and setup.

## Installs that just re-run cleanly

Running the installer again won't trip over itself anymore. If the global `ait` shim is already in place, setup quietly moves on instead of bailing out — and any stray `packaging/` directory the installer used to leave behind now gets cleaned up on its own.

## Less untracked clutter from generated skills

`ait setup` now lays down the right gitignore rules so the skill variants your tools render locally stay out of your way, while the committed headless prerenders are still tracked. Your `git status` stays clean.

---

---

**Full changelog:** [v0.23.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.23.1)
