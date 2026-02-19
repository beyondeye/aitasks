---
title: "Overview"
linkTitle: "Overview"
weight: 5
description: "The challenge aitasks addresses, its core philosophy, and key features."
---

## The Challenge

AI coding agents have reached a proficiency level where, given correct specs and intent, they are almost always capable of handling a code-development task. The challenge is the transfer of intent from developer/designer to the AI agent. The challenge is two-fold:

1. Transfer intent in a structured way that optimizes context building for the AI agent
2. Maximize speed so that the human in the loop does not become the bottleneck for development speed

## Core Philosophy

**"Light Spec" engine:** Unlike rigid Spec-Driven Development (e.g., Speckit), tasks here are living documents:

- **Raw Intent:** A task starts as a simple Markdown file capturing the goal.
- **Iterative Refinement:** An included AI workflow refines task files in stages — expanding context, adding technical details, and verifying requirements — before code is written.

## Key Features & Architecture

- **Repository-Centric** (Inspired by [Conductor](https://github.com/gemini-cli-extensions/conductor))
  - **Tasks as Files:** Every task is a Markdown file stored within the code repository.
  - **Self-Contained Metadata:** Task metadata (status, priority, assignee) is stored directly in the file's YAML frontmatter.

- **Daemon-less & Stateless** (The [Beads](https://github.com/steveyegge/beads) Evolution)
  - No SQL backend, no background daemons. Just files and scripts.

- **Remote-Ready:** Because the state is entirely in the file system, it works seamlessly in remote AI-agent sessions.

- **Dual-Mode CLI** tools optimized for two distinct users:
  - **Interactive Mode (For Humans):** Optimized for "Flow." Rapidly create, edit, and prioritize tasks without context switching.
  - **Batch Mode (For Agents):** Allowing AI agents to read specs, create tasks and update task status programmatically.

- **Hierarchical Execution**
  - **Task Dependencies:** Define task/task and task parent/task child relationships.
  - **Agent Decomposition:** If a task is too risky or complex for a single run, the Agent can "explode" a parent task into child files.
  - **Parallelism:** Thanks to task status stored in git, and AI agent workflows that support git worktrees.

- **Visual Management**
  - **TUI Board:** A terminal-based visual interface (Kanban style) for visualizing and organizing tasks without leaving the terminal. See the [Board Documentation]({{< relref "board" >}}) for full details.

- **Battle tested:** Not a research experiment. Actively developed and used in real projects.

- **Claude Code optimized.**

- **Fully customizable workflow:** All the scripts and workflow skills live in your project repo — modify them for your needs. You can still merge new features and capabilities as they are added to the framework, with the included AI agent-based framework update skill.
