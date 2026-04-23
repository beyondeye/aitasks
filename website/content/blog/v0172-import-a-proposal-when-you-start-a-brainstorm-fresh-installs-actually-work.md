---
date: 2026-04-23
title: "v0.17.2: Import a proposal when you start a brainstorm, and Fresh installs actually work now"
linkTitle: "v0.17.2"
description: "v0.17.2 is mostly a stabilization release — a new way to kick off a brainstorm session, plus a handful of install and test-scaffolding fixes that have been biting people trying out the framework for the first time."
author: "aitasks team"
---


v0.17.2 is mostly a stabilization release — a new way to kick off a brainstorm session, plus a handful of install and test-scaffolding fixes that have been biting people trying out the framework for the first time.

## Import a proposal when you start a brainstorm

When you run `ait brainstorm <N>` on a fresh task, the init modal now gives you three choices: Blank, Import Proposal…, or Cancel. Picking Import opens a markdown file picker (filtered to `.md` / `.markdown`), runs an initializer agent over the file you chose, and applies its output to seed the first brainstorm node — so you can bring an existing design doc or proposal straight into the tree instead of starting from scratch.

## Fresh installs actually work now

`install.sh` was shipping without `project_config.yaml` from the seed files, so the very first `ait` run on a new project could trip over missing config. That's fixed. Framework-update commits also no longer get truncated at the 20th file, which is what a lot of people were hitting after `ait update` against bigger trees.

---

---

**Full changelog:** [v0.17.2 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.17.2)
