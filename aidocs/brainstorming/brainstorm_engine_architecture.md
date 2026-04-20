# Brainstorm Engine Architecture

The brainstorm engine is an iterative AI design system that uses a DAG-based approach to explore, compare, and hybridize architectural proposals. It builds on AgentCrew for multi-agent orchestration and integrates with the aitasks ecosystem for session management.

This document is the single reference for data formats, orchestration flow, and agent specifications. It is self-contained — no other documents need to be read to understand the system.

## Table of Contents

1. [Overview](#1-overview)
2. [Directory Structure](#2-directory-structure)
3. [Data Format Specifications](#3-data-format-specifications)
4. [Structured Sections, Proposals, and Plans](#4-structured-sections-proposals-and-plans)
5. [AgentCrew Integration](#5-agentcrew-integration)
6. [Context Assembly](#6-context-assembly)
7. [Orchestration Flow](#7-orchestration-flow)
8. [Subagent Prompt Specifications](#8-subagent-prompt-specifications)
9. [Section Viewer](#9-section-viewer)

---

## 1. Overview

### Purpose

Traditional AI planning conversations suffer from context creep: as requirements evolve and multiple approaches are explored, the conversation history fills the context window with abandoned explorations, outdated assumptions, and redundant comparisons. The brainstorm engine solves this by externalizing all state to files and delegating work to isolated subagents that are destroyed after completing their task.

### Core Concepts

- **Design Space DAG:** Proposals form a Directed Acyclic Graph, not a linear chain. Each node is a self-contained architectural snapshot. Nodes can have multiple parents (hybridization) and multiple children (divergent exploration).
- **Node Triad:** Every node consists of three files — metadata (YAML), proposal (Markdown), and optionally a plan (Markdown). The metadata is the queryable index; the Markdown files hold the narrative.
- **Context Discipline:** The orchestrator never holds full proposals in memory. It reads only metadata and summaries, delegating deep work to subagents.
- **Bidirectional Flow:** Changes can originate top-down (architectural pivots that cascade to implementation plans) or bottom-up (plan tweaks that may escalate to architectural changes).

### Relationship to aitasks

Each brainstorm session is tied to an aitask. The session data lives on the AgentCrew crew branch at `.aitask-crews/crew-brainstorm-<task_num>/` and the session metadata references the originating task file. This enables:

- Traceability from final implementation plan back through the design exploration
- Integration with `ait board` for session visibility
- Archival alongside the completed task

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    TUI (future, t419_6)                   │
│   User commands: explore, compare, hybridize, detail...  │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│               Session Manager (t419_4)                    │
│   init, pause, resume, finalize, archive                 │
│   Reads/writes: br_session.yaml, br_graph_state.yaml     │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│         AgentCrew Orchestration Layer (t419_2)            │
│   Persistent crew: brainstorm-<task_num>                 │
│   Operation groups: explore_001, compare_002, ...        │
│   Agent types: explorer, comparator, synthesizer,        │
│                detailer, patcher                          │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│                  DAG Operations (t419_3)                   │
│   add_node, get_node, list_children, find_path,          │
│   topological_sort, validate_dag                         │
│   Reads/writes: br_nodes/*.yaml, br_graph_state.yaml     │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure

Brainstorm session data lives on the AgentCrew crew branch alongside the crew coordination files. This unifies all session state (DAG, proposals, plans, agent coordination) in a single git branch, enabling multi-user and multi-PC collaboration via git.

### Source Control Model

Each brainstorm session reuses its AgentCrew crew branch:

- **Branch:** `crew-brainstorm-<task_num>` (created by `ait crew init`)
- **Worktree:** `.aitask-crews/crew-brainstorm-<task_num>/`
- **Sync:** The AgentCrew runner already handles git commit + push for crew files. Brainstorm data files are committed alongside crew status updates.

This means:
1. All brainstorm data is version-controlled and shared via git
2. Multiple users/PCs see the same session state after git pull
3. No additional branches or worktrees — the crew worktree serves both purposes
4. Session history is preserved in git log on the crew branch

### Directory Layout

All files live in the crew worktree at `.aitask-crews/crew-brainstorm-<task_num>/`:

```
.aitask-crews/crew-brainstorm-419/
│
│  # --- AgentCrew coordination files ---
├── _crew_meta.yaml              # Crew config: agent types, heartbeat timeout
├── _crew_status.yaml            # Dynamic crew status
├── _runner_alive.yaml           # Runner heartbeat
├── explorer_001a_status.yaml    # Per-agent status files
├── explorer_001a_work2do.md     # Per-agent work specifications
├── explorer_001a_input.md       # Per-agent input
├── explorer_001a_output.md      # Per-agent output
├── ...                          # More agent files
│
│  # --- Brainstorm session data ---
├── br_session.yaml              # Session lifecycle metadata
├── br_graph_state.yaml          # DAG state: current head, history, dimensions
├── br_groups.yaml               # Operation group metadata
├── br_nodes/                    # Flat YAML metadata per node
│   ├── n000_init.yaml
│   ├── n001_relational.yaml
│   ├── n002_nosql.yaml
│   └── n003_hybrid_db.yaml
├── br_proposals/                # Full architectural narratives (Markdown)
│   ├── n000_init.md
│   ├── n001_relational.md
│   ├── n002_nosql.md
│   └── n003_hybrid_db.md
├── br_plans/                    # Implementation plans (Markdown, optional per node)
│   ├── n002_nosql_plan.md
│   └── n003_hybrid_db_plan.md
└── br_url_cache/                # Cached fetched URL content (gitignored)
    ├── a1b2c3d4.md
    └── e5f6g7h8.md
```

**Note:** `br_url_cache/` is gitignored — URL content is fetched locally and may vary over time. Each PC rebuilds its cache as needed.

### Lifecycle and Cleanup

- **Session active:** All data lives on `crew-brainstorm-<task_num>` branch in the crew worktree. The runner commits changes periodically.
- **Session completed (finalize):** The final plan is exported to `aiplans/` on the main branch (or aitask-data branch). The crew branch is preserved for reference.
- **Session archived:** When the aitask is archived, the crew branch can be:
  - **Preserved:** Keep the branch for full audit trail (recommended)
  - **Exported:** Archive brainstorm data as a tarball in `aitasks/archived/`
  - **Cleaned up:** `ait crew cleanup` removes the worktree and branch

### Naming Conventions

- **Node IDs:** `nXXX_descriptive_name` — zero-padded three-digit sequence number plus snake_case name
- **Node metadata:** `br_nodes/nXXX_name.yaml`
- **Proposals:** `br_proposals/nXXX_name.md`
- **Plans:** `br_plans/nXXX_name_plan.md`
- **Crew worktree:** `.aitask-crews/crew-brainstorm-<task_num>/` where `<task_num>` matches the aitask number

### Source Code Layout

The brainstorm engine's Python modules live under `.aitask-scripts/` in the main repo (not in the crew worktree):

| Path | Purpose |
|------|---------|
| `.aitask-scripts/brainstorm/brainstorm_dag.py` | DAG operations: `read_node`, `read_proposal`, `read_plan`, `_read_graph_state`, path constants (`NODES_DIR`, `PROPOSALS_DIR`, `PLANS_DIR`) |
| `.aitask-scripts/brainstorm/brainstorm_schemas.py` | Dimension prefixes (`DIMENSION_PREFIXES`), `is_dimension_field()`, `extract_dimensions()` |
| `.aitask-scripts/brainstorm/brainstorm_sections.py` | Section parser: `parse_sections`, `validate_sections`, `get_section_by_name`, `get_sections_for_dimension`, `section_names`, `format_section_header`, `format_section_footer`; dataclasses `ContentSection` and `ParsedContent` |
| `.aitask-scripts/brainstorm/brainstorm_crew.py` | Agent registration (`register_explorer`, `register_comparator`, `register_synthesizer`, `register_detailer`, `register_patcher`) and `_assemble_input_*` helpers |
| `.aitask-scripts/brainstorm/brainstorm_app.py` | Brainstorm TUI (wizard, node tree, `NodeDetailModal`) |
| `.aitask-scripts/brainstorm/templates/` | Agent work2do templates (`explorer.md`, `comparator.md`, `synthesizer.md`, `detailer.md`, `patcher.md`) plus the shared include `_section_format.md` |
| `.aitask-scripts/lib/section_viewer.py` | Shared Textual widgets for rendering section-structured markdown: `SectionRow`, `SectionMinimap`, `SectionAwareMarkdown`, `SectionViewerScreen`; helper `estimate_section_y()` |

---

## 3. Data Format Specifications

### br_session.yaml

Tracks the lifecycle of a brainstorm session. One per session directory.

```yaml
# Session metadata — tracks lifecycle of a brainstorm session
task_id: 419                                      # aitask number this session belongs to
task_file: aitasks/t419_brainstorm_architecture.md # Path to the originating task file
status: active                                     # Session lifecycle status (see below)
crew_id: brainstorm-419                            # AgentCrew crew identifier
created_at: 2026-03-18 14:00                       # When the session was initialized
updated_at: 2026-03-18 15:30                       # Last modification timestamp
created_by: user@example.com                       # Email of the user who started the session
initial_spec: |                                    # The original design brief provided by the user
  Brief description of what we're designing...

# --- URL cache settings ---
url_cache: enabled                                 # Global toggle: enabled | disabled
url_cache_bypass:                                  # Per-URL overrides (skip caching for specific URLs)
  - https://api.example.com/live-status            # Always fetch fresh (e.g., live API docs)
```

**Session status lifecycle:**

```
init ──→ active ──→ completed ──→ archived
            │
            └──→ paused ──→ active
```

| Status | Description | Transition trigger |
|--------|-------------|-------------------|
| `init` | Session directory created, no exploration yet | `ait brainstorm init` |
| `active` | Exploration in progress | First operation or resume from paused |
| `paused` | Temporarily suspended (crew paused) | User pauses session |
| `completed` | User finalized a design — implementation plan locked | User runs finalize |
| `archived` | Session moved to archive alongside completed task | Task archival |

### br_graph_state.yaml

Tracks the DAG structure and current position within the design space. One per session.

```yaml
# DAG state — tracks the design exploration graph
current_head: n003_hybrid_db        # Node ID of the current baseline (user's working node)
history:                             # Ordered list of head transitions (audit trail)
  - n000_init
  - n001_relational
  - n003_hybrid_db                   # n002 was explored but never became head
next_node_id: 4                      # Counter for generating the next nXXX ID
active_dimensions:                   # Dimensions currently being explored
  - database                         # These are used by the TUI to offer comparison options
  - cache
  - api_layer
  - auth
```

**Field descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `current_head` | string | Node ID of the active baseline. All new explorations branch from this node unless the user specifies otherwise. |
| `history` | list of strings | Ordered record of every time `current_head` changed. Used for undo/revert. |
| `next_node_id` | integer | Auto-incrementing counter. When creating a new node, use this value and increment. |
| `active_dimensions` | list of strings | The `component_*` and `assumption_*` dimension names currently in play. Updated when nodes introduce new dimensions. |

### Flat YAML Node Schema (br_nodes/nXXX_name.yaml)

Each node is a self-contained snapshot of an architectural proposal. The schema uses a flat, prefix-based structure so dimensions can be programmatically extracted by prefix (e.g., all `component_*` keys, all `assumption_*` keys).

```yaml
# Node metadata — one file per proposal in the design DAG
node_id: n003_hybrid_db                # Unique identifier (matches filename stem)
parents:                                # Parent node IDs (enables DAG structure)
  - n001_relational
  - n002_nosql
description: >-                        # One-line summary of this proposal
  Uses Postgres for core data but adds Redis caching from the NoSQL exploration.
proposal_file: br_proposals/n003_hybrid_db.md       # Relative path to full proposal
plan_file: br_plans/n003_hybrid_db_plan.md          # Relative path to implementation plan (optional)
created_at: 2026-03-18 14:30                         # When this node was created
created_by_group: hybridize_003                      # Operation group that produced this node

# --- Reference files (local paths and URLs) ---
# Resources the agent should read to understand the context for this proposal.
# Updated by each agent: add references for new components, remove references
# that are no longer relevant after architectural changes.
# Supports local file paths and remote URLs (docs, APIs, specs).
reference_files:
  - src/db/schema.ts                    # Database schema (relevant to component_database)
  - src/cache/redis-client.ts           # Cache layer (relevant to component_cache)
  - src/api/router.ts                   # API routing (relevant to component_api_layer)
  - src/auth/jwt.ts                     # Auth implementation (relevant to component_auth)
  - package.json                        # Dependencies and versions
  - https://redis.io/docs/latest/develop/data-types/  # Redis data types reference
  - https://www.postgresql.org/docs/current/ddl.html   # PostgreSQL DDL reference

# --- Fixed requirements (non-negotiable constraints) ---
requirements_fixed:
  - Sub-100ms read latency
  - ACID compliance for billing transactions

# --- Mutable requirements (open for exploration) ---
requirements_mutable:
  - Deployment target (cloud vs on-prem)
  - CI/CD pipeline specifics

# --- Assumptions (context that may change) ---
assumption_scale: 10k DAU initially, scaling to 100k
assumption_team_skill: Strong TypeScript, moderate DevOps experience
assumption_budget: Mid-range cloud budget, no dedicated DBA

# --- Components (architectural building blocks) ---
component_database: PostgreSQL with normalized schema (inherited from n001)
component_cache: Redis with 15-minute TTL (inherited from n002)
component_api_layer: tRPC with strict zod validation
component_auth: JWT with refresh token rotation

# --- Tradeoffs ---
tradeoff_pros:
  - Data integrity guaranteed by PostgreSQL ACID
  - Fast reads via Redis cache layer
  - Type-safe API contracts via tRPC
tradeoff_cons:
  - Higher infrastructure complexity (two data stores)
  - Cache invalidation complexity
  - Requires connection pooling (PgBouncer) for high concurrency
```

**Schema rules:**

1. **`node_id`** must match the filename stem exactly
2. **`parents`** is a list of zero or more node IDs. Root nodes have `parents: []`
3. **`proposal_file`** is always present. Path is relative to the session directory
4. **`plan_file`** is optional — only present after the Detailer has generated a plan for this node
5. **`created_by_group`** tracks which AgentCrew operation group produced this node (see Section 5)
6. **Dimension keys** use underscored prefixes: `requirements_fixed`, `requirements_mutable`, `assumption_*`, `component_*`, `tradeoff_pros`, `tradeoff_cons`
7. **New dimensions** can be added freely — the schema is extensible. When a node introduces a new `component_*` or `assumption_*` key not present in the parent, add the dimension name to `br_graph_state.yaml`'s `active_dimensions`
8. **`reference_files`** is a list of references relevant to the proposal — both local file paths and remote URLs. Local paths are relative to the project root. URLs point to external documentation, API specs, or technology references. Each agent updates this list when creating a new node: add references for new components, remove references for removed components. This is the primary mechanism for evolving context across the DAG.

---

## 4. Structured Sections, Proposals, and Plans

Proposals (`br_proposals/`) and plans (`br_plans/`) are Markdown documents partitioned into **structured sections** delimited by HTML comment markers. Sections are the unit of addressable content: agents can be steered to operate on a subset of them (via `target_sections`), and section-aware TUI widgets render them as a navigable minimap.

Node metadata (`br_nodes/*.yaml`) is *not* sectioned — it is a flat key-value schema.

### 4.1 Section Marker Format

A section is a contiguous range of lines wrapped in paired HTML comment markers:

```
<!-- section: section_name [dimensions: component_database, assumption_scale] -->
... markdown content ...
<!-- /section: section_name -->
```

Rules:

- **Names** are `lowercase_snake_case`. They must be unique within a document.
- **Dimensions** (optional) are a comma-separated list following `dimensions:` inside square brackets. Each entry must start with one of the recognized dimension prefixes (`component_`, `assumption_`, `requirements_`, `tradeoff_`) — validated against `DIMENSION_PREFIXES` in `brainstorm_schemas.py`.
- **No nesting.** An open marker that appears while another section is already open is ignored until the current section closes.
- **Order is preserved.** `parse_sections()` returns sections in document order.
- **Content outside markers** is preserved as `preamble` (before the first section) or `epilogue` (after the last close tag).

The shared template include `.aitask-scripts/brainstorm/templates/_section_format.md` documents the same rules for agents and is pulled into every template that emits section-wrapped output via an `<!-- include: _section_format.md -->` directive.

### 4.2 Parser API

Defined in `.aitask-scripts/brainstorm/brainstorm_sections.py`:

**Data structures:**

```python
@dataclass
class ContentSection:
    name: str                   # e.g. "database_layer"
    dimensions: list[str]       # e.g. ["component_database", "assumption_scale"]
    content: str                # raw markdown between open/close tags (no markers)
    start_line: int             # 1-based; line of the opening tag
    end_line: int               # 1-based; line of the closing tag

@dataclass
class ParsedContent:
    sections: list[ContentSection]
    preamble: str               # content before first section
    epilogue: str               # content after last section
    raw: str                    # original input, unmodified
```

**Functions:**

| Function | Returns | Purpose |
|---|---|---|
| `parse_sections(text)` | `ParsedContent` | Parse a Markdown string into structured sections + preamble + epilogue |
| `validate_sections(parsed)` | `list[str]` | Check for duplicate names, invalid dimensions, unclosed markers. Empty list = valid |
| `get_section_by_name(parsed, name)` | `ContentSection \| None` | First section matching `name`, or `None` |
| `get_sections_for_dimension(parsed, dim)` | `list[ContentSection]` | All sections whose `dimensions` list contains `dim` |
| `section_names(parsed)` | `list[str]` | Ordered section names |
| `format_section_header(name, dimensions=None)` | `str` | Emit an opening marker |
| `format_section_footer(name)` | `str` | Emit a closing marker |

### 4.3 Proposal Template (br_proposals/nXXX_name.md)

Proposals follow a consistent set of sections. Explorer and Synthesizer wrap their output in section markers so downstream operations can target specific concerns:

```markdown
# Proposal: <descriptive name>

**Node:** nXXX_name
**Parents:** nYYY_parent1, nZZZ_parent2
**Created by:** <operation group>

<!-- section: overview -->
## Overview
<2-3 paragraph summary. What problem does it solve? How does it differ from the parents?>
<!-- /section: overview -->

<!-- section: architecture [dimensions: component_api_layer, component_database] -->
## Architecture
<Major components, responsibilities, interactions, technology choices.>
<!-- /section: architecture -->

<!-- section: data_flow -->
## Data Flow
<Request/response flow, storage/retrieval patterns, caching strategy.>
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_database, component_cache] -->
## Components

### <Component 1>
<Description, technology, configuration>

### <Component 2>
<Description, technology, configuration>
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_scale, assumption_team_skill] -->
## Assumptions
<All assumptions this proposal depends on. Flag inherited vs new.>
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_pros, tradeoff_cons] -->
## Tradeoffs

### Advantages
- <Advantage 1>

### Disadvantages
- <Disadvantage 1>

### Risks
- <Risk 1 and mitigation>
<!-- /section: tradeoffs -->
```

Section names are not prescribed by the parser — agents choose names that fit the content — but the set above is the conventional shape. The `dimensions:` annotation is optional; agents add it when a section maps cleanly to one or more node-metadata dimension keys.

### 4.4 Plan Template (br_plans/nXXX_name_plan.md)

Implementation plans translate proposals into actionable steps. Detailer wraps each plan section in markers so Patcher can apply surgical edits to a named subset:

```markdown
# Implementation Plan: <descriptive name>

**Node:** nXXX_name
**Based on proposal:** br_proposals/nXXX_name.md

<!-- section: prerequisites -->
## Prerequisites
- <Required tools, libraries, infrastructure>
- <Environment variables or configuration>
- <Access or permissions>
<!-- /section: prerequisites -->

<!-- section: steps [dimensions: component_database, component_cache] -->
## Step-by-Step Changes

### Step 1: <description>
**Files:** `path/to/file1.ts`

<Detailed instructions. Include code snippets for non-trivial changes.>

### Step 2: <description>
**Files:** `path/to/file3.ts`

<Detailed instructions.>
<!-- /section: steps -->

<!-- section: testing -->
## Testing
- <How to verify each component works>
- <Integration test strategy>
- <Performance benchmarks that validate the proposal's assumptions>
<!-- /section: testing -->

<!-- section: verification -->
## Verification
- [ ] <Verification checklist item 1>
- [ ] <All assumptions from the proposal hold under test>
<!-- /section: verification -->
```

### 4.5 Dimension Linking

The `dimensions:` annotation on a section declares which node-metadata dimension keys that section's content bears on. This linkage has two downstream uses:

1. **Targeted operations** — The TUI wizard can ask the user "which sections should this operation act on?" and the selected names flow to the agent as `target_sections`. See §6 (Context Assembly) and §7 (Orchestration Flow).
2. **Minimap annotations** — The shared section viewer widgets surface each section's dimension tags next to its name, so readers can see at a glance which architectural dimensions a section addresses. See §9 (Section Viewer).

When a section's content does not map cleanly to a dimension key (e.g., `overview`, `data_flow`), omit the `dimensions:` annotation.

---

## 5. AgentCrew Integration

The brainstorm engine uses AgentCrew as its orchestration layer. Each session creates a persistent AgentCrew crew, and each brainstorm operation (explore, compare, hybridize, detail, patch) registers agents within an operation group.

### Persistent Crew Model

One AgentCrew crew per brainstorm session:

- **Crew ID:** `brainstorm-<task_num>` (e.g., `brainstorm-419`)
- **Crew lifetime:** Matches the session lifecycle. Created at `ait brainstorm init`, cleaned up at session archive.
- **Branch:** `crew-brainstorm-<task_num>` (standard AgentCrew branch naming)
- **Worktree:** `.aitask-crews/crew-brainstorm-<task_num>/`

The crew persists across multiple operations. Unlike typical AgentCrew usage where a crew is created for a single batch of work, the brainstorm crew accumulates agents from all operations throughout the session. The crew worktree also holds all brainstorm session data (see Section 2 — Directory Layout), so crew coordination and design exploration are unified in a single git branch.

### Operation Groups

Each user-initiated brainstorm operation creates a named **operation group** — a logical grouping of one or more agents registered in the same operation. Operation groups enable:

- Tracking which agents belong to the same user request
- Group-level status queries ("is explore_001 complete?")
- Priority scheduling (lower sequence number = earlier operation = higher priority)
- Provenance tracking (every node's `created_by_group` traces back to the operation that created it)

**Naming convention:** `<operation>_<sequence>` where:
- `<operation>` is one of: `explore`, `compare`, `hybridize`, `detail`, `patch`
- `<sequence>` is a zero-padded three-digit counter incremented per operation

Examples: `explore_001`, `explore_002`, `compare_003`, `hybridize_004`, `detail_005`, `patch_006`

### Operation Group Metadata (br_groups.yaml)

Stored in the crew worktree alongside crew metadata. Tracks all operation groups and their status.

```yaml
# Operation groups — one entry per brainstorm operation
groups:
  explore_001:
    operation: explore                      # Operation type
    agents: [explorer_001a, explorer_001b]  # Agents registered in this group
    status: Completed                       # Derived from agent statuses
    created_at: 2026-03-18 14:05
    head_at_creation: n000_init             # br_graph_state.yaml current_head when group was created
    nodes_created: [n001_relational, n002_nosql]  # Nodes produced by this operation

  compare_002:
    operation: compare
    agents: [comparator_002]
    status: Completed
    created_at: 2026-03-18 14:20
    head_at_creation: n000_init
    nodes_created: []                       # Comparisons don't create nodes

  hybridize_003:
    operation: hybridize
    agents: [synthesizer_003]
    status: Running
    created_at: 2026-03-18 14:35
    head_at_creation: n001_relational
    nodes_created: []                       # Pending until complete
```

**Group status derivation** (mirrors AgentCrew crew status logic):
- All agents `Completed` → group `Completed`
- Any `Error` + no `Running` → group `Error`
- Any `Running` → group `Running`
- All `Waiting` → group `Waiting`

### Agent Type Definitions

Brainstorm agent types are registered in the crew's `_crew_meta.yaml` under `agent_types`. Each maps to the corresponding subagent role.

```yaml
# In _crew_meta.yaml for crew brainstorm-<task_num>
agent_types:
  explorer:
    agent_string: claudecode/opus4_6    # Needs strong reasoning for architecture
    max_parallel: 2                      # Can explore multiple approaches in parallel
  comparator:
    agent_string: claudecode/sonnet4_6  # Structured analysis, doesn't need top reasoning
    max_parallel: 1                      # Comparisons are sequential (need all inputs ready)
  synthesizer:
    agent_string: claudecode/opus4_6    # Conflict resolution needs strong reasoning
    max_parallel: 1                      # Hybridization is sequential
  detailer:
    agent_string: claudecode/opus4_6    # Implementation planning needs deep code understanding
    max_parallel: 1                      # One plan at a time
  patcher:
    agent_string: claudecode/sonnet4_6  # Surgical edits, impact analysis
    max_parallel: 1                      # Sequential plan patches
```

**Agent naming within groups:** `<type>_<group_sequence><agent_letter>`

Examples:
- `explorer_001a`, `explorer_001b` — two explorers in group `explore_001`
- `comparator_002` — single comparator in group `compare_002`
- `synthesizer_003` — single synthesizer in group `hybridize_003`

### Group-Level Commands

Operation groups support group-level commands that fan out to all agents in the group:

| Command | Effect |
|---------|--------|
| `ait brainstorm group status <group>` | Show status of all agents in the group |
| `ait brainstorm group cancel <group>` | Send kill to all running agents in the group |
| `ait brainstorm group wait <group>` | Block until all agents in the group are terminal |

These commands translate to the underlying AgentCrew CLI:
```bash
# Group status → query each agent
for agent in $(get_group_agents $group); do
  ait crew status --crew brainstorm-$task_num --agent $agent get
done

# Group cancel → send kill to all
for agent in $(get_group_agents $group); do
  ait crew command send --crew brainstorm-$task_num --agent $agent --command kill
done
```

---

## 6. Context Assembly

Each brainstorm agent starts with a completely empty context. Unlike a regular Claude Code session where the conversation history provides continuity, brainstorm agents are ephemeral — they are created, given input, produce output, and are destroyed. The session manager (not an AI agent) is responsible for assembling the right context for each agent before it launches.

This section specifies exactly what goes into each agent's `_input.md` file and how the reference material evolves as the DAG grows.

### The Problem

The brainstorm engine's memory is entirely external — stored in YAML metadata, Markdown proposals, Markdown plans, and codebase files. When an agent is spawned, it knows nothing. The session manager must:

1. Decide which files are relevant to the operation
2. Write file references (paths) into the agent's `_input.md`
3. The agent reads the referenced files using its own tools (Read, Glob, Grep, WebFetch)

**Key principle:** The `_input.md` contains **file paths as references**, not inlined file contents. This keeps the input compact and lets the agent read files on demand. For cached URLs, the input references the local cache file path with the original source URL noted in parentheses.

As the DAG grows, the relevant context changes:
- New components introduce new codebase files
- Abandoned branches become irrelevant
- Hybridized nodes inherit references from multiple parents
- The current head's context is always the most important

### Reference File Tracking

Each node's YAML includes a `reference_files` field — a list of local file paths and remote URLs relevant to that node's proposal. This list evolves across the DAG:

- **Explorer:** Starts with the parent node's `reference_files`. Adds references for new components (both local files and external docs), removes references for components that were replaced. The output node's `reference_files` reflects the new architectural state.
- **Synthesizer:** Merges `reference_files` from all parent nodes. Deduplicates. Adds references for bridging components introduced during conflict resolution.
- **Detailer/Patcher:** Inherits `reference_files` unchanged (these agents work on plans, not architecture).

**Reference types:**

| Type | Format | Example | Fetched by |
|------|--------|---------|-----------|
| Local file | Relative path (no scheme) | `src/db/schema.ts` | Session manager reads file contents |
| Remote URL | `https://...` or `http://...` | `https://redis.io/docs/latest/develop/data-types/` | Session manager fetches via WebFetch (cached) |

Remote URLs are useful for:
- Technology documentation (API references, configuration guides)
- External specifications (RFCs, protocol docs)
- Third-party library documentation
- Architecture decision records hosted externally

**URL caching:** The session manager caches fetched URL content in `br_url_cache/` within the crew worktree, keyed by URL hash. This directory is gitignored — each PC builds its own cache. Cache entries are reused across operations within the same session, avoiding redundant fetches.

Caching is configurable in `br_session.yaml`:
- **`url_cache: disabled`** — Skip caching entirely; always fetch fresh. Useful when reference URLs change frequently.
- **`url_cache_bypass`** — A list of specific URLs to always fetch fresh, even when caching is globally enabled. Useful for live API docs or rapidly evolving specs.
- **Default:** `url_cache: enabled` with no bypass entries.

**Example evolution:**
```
n000_init:
  reference_files:
    - src/db/schema.ts
    - src/api/router.ts
    - https://www.postgresql.org/docs/current/ddl.html

n001_add_redis (parent: n000):
  reference_files:
    - src/db/schema.ts
    - src/api/router.ts
    - src/cache/redis.ts                                     # Added: new component
    - https://www.postgresql.org/docs/current/ddl.html
    - https://redis.io/docs/latest/develop/data-types/       # Added: Redis docs

n002_replace_db_with_mongo (parent: n000):
  reference_files:
    - src/api/router.ts
    - src/db/mongo-client.ts                                 # Added: MongoDB client
    - https://www.mongodb.com/docs/manual/core/document/     # Replaced: Postgres → Mongo docs

n003_hybrid (parents: n001, n002):
  reference_files:
    - src/api/router.ts
    - src/cache/redis.ts
    - src/db/mongo-client.ts
    - https://redis.io/docs/latest/develop/data-types/
    - https://www.mongodb.com/docs/manual/core/document/
    # Merged from both parents, deduped, removed stale Postgres refs
```

### Context Assembly Per Agent Type

The session manager builds `_input.md` differently for each agent type:

#### Explorer Input Assembly

```markdown
# Explorer Input

## Exploration Mandate
<The user's request, e.g., "Explore a serverless approach for the API layer">

## Baseline Node
- Metadata: .aitask-crews/crew-brainstorm-419/br_nodes/n003_hybrid_db.yaml
- Proposal: .aitask-crews/crew-brainstorm-419/br_proposals/n003_hybrid_db.md
- Plan: .aitask-crews/crew-brainstorm-419/br_plans/n003_hybrid_db_plan.md

## Reference Files
### Local
- src/db/schema.ts
- src/cache/redis-client.ts
- src/api/router.ts

### Remote (cached)
- br_url_cache/a1b2c3d4.md (source: https://redis.io/docs/latest/develop/data-types/)
- br_url_cache/e5f6g7h8.md (source: https://www.postgresql.org/docs/current/ddl.html)

## Active Dimensions
<From br_graph_state.yaml — so the explorer knows which dimensions are in play>

## Dimension Keys
Use these dimension keys in section markers:
- assumption_scale
- component_api_layer
- component_cache
- component_database
- component_auth
```

The agent reads all referenced files using its own tools (Read, Glob, Grep). For remote references, it reads the cached file; if the cache miss occurs, it fetches via WebFetch.

**Targeted variant** — when the user selects specific sections for the operation (see §7), two additional blocks are appended, each inlining just the selected sections from the baseline (so the agent does not need to parse the full proposal/plan to find them):

```markdown
## Targeted Section Content
Focus exploration on these sections from the baseline:

### Section: architecture [dimensions: component_api_layer, component_database]
<inlined content of the `architecture` section>

### Section: components [dimensions: component_database, component_cache]
<inlined content of the `components` section>

## Targeted Plan Section Content

### Section: steps [dimensions: component_database, component_cache]
<inlined content of the `steps` section from the baseline's plan>
```

The `## Targeted Plan Section Content` block appears only when the baseline has an associated plan that contains at least one of the selected sections.

#### Comparator Input Assembly

```markdown
# Comparator Input

## Comparison Request
Nodes: n001_relational, n002_nosql
Dimensions: component_database, assumption_scale, tradeoff_pros, tradeoff_cons

## Node Files
- br_nodes/n001_relational.yaml
- br_nodes/n002_nosql.yaml
```

**Key point:** The comparator reads only the YAML metadata files and extracts the requested dimension fields. No proposals, no plans, no codebase files — this keeps it fast and focused.

**Targeted variant** — when the TUI passes `target_sections`, a `## Section Focus` block is appended listing the section names the comparator should concentrate on:

```markdown
## Section Focus
Compare only content within these sections across nodes:
- architecture
- components
```

The wizard computes the candidate section list as the intersection of sections present across the selected nodes (a section must exist in every node being compared to be offered in the picker). The comparator itself still reads only the YAML metadata — the section-focus block is advisory and constrains which proposal sections the comparator cites in its output table.

#### Synthesizer Input Assembly

```markdown
# Synthesizer Input

## Merge Rules
<User's instructions: which components from which node>

## Source Nodes
### n001_relational
- Metadata: br_nodes/n001_relational.yaml
- Proposal: br_proposals/n001_relational.md

### n002_nosql
- Metadata: br_nodes/n002_nosql.yaml
- Proposal: br_proposals/n002_nosql.md

## Reference Files (merged from all source nodes, deduplicated)
### Local
- src/db/schema.ts
- src/db/mongo-client.ts
- src/api/router.ts

### Remote (cached)
- br_url_cache/a1b2c3d4.md (source: https://www.postgresql.org/docs/current/ddl.html)
- br_url_cache/f9g0h1i2.md (source: https://www.mongodb.com/docs/manual/core/document/)

## Dimension Keys
Use these dimension keys in section markers:
- assumption_scale
- component_api_layer
- component_cache
- component_database
```

**Synthesizer is not section-aware.** Hybridization merges *whole proposals*, not subsets of sections, so the wizard does not expose a section picker for hybridize and `register_synthesizer()` has no `target_sections` parameter.

#### Detailer Input Assembly

```markdown
# Detailer Input

## Target Node
- Metadata: br_nodes/n003_hybrid_db.yaml
- Proposal: br_proposals/n003_hybrid_db.md

## Reference Files
### Local
- src/db/schema.ts
- src/cache/redis-client.ts
- src/api/router.ts
- package.json

### Remote (cached)
- br_url_cache/a1b2c3d4.md (source: https://redis.io/docs/latest/develop/data-types/)

## Project Context
- CLAUDE.md (project conventions)

## Dimension Keys
Use these dimension keys in section markers:
- assumption_scale
- component_api_layer
- component_cache
- component_database
```

**The Detailer gets the richest context** because it needs to write specific file paths, code snippets, and commands. In addition to reference_files, the session manager includes project-level context (CLAUDE.md, directory listings). The agent uses its tools to explore further as needed.

**Targeted variant** — when the TUI passes `target_sections`, a `## Target Sections` block is appended and, when an existing plan is present, the path to it so the Detailer can re-render only the named sections and preserve the others byte-for-byte:

```markdown
## Target Sections
Re-detail only these sections of the existing plan.
Leave other sections unchanged:
- steps
- testing

Current plan: .aitask-crews/crew-brainstorm-419/br_plans/n003_hybrid_db_plan.md
```

#### Patcher Input Assembly

```markdown
# Patcher Input

## Patch Request
<The user's specific edit request>

## Current Node
- Metadata: br_nodes/n003_hybrid_db.yaml
- Plan: br_plans/n003_hybrid_db_plan.md (this is what the patcher modifies)
- Proposal: br_proposals/n003_hybrid_db.md (read-only, for impact analysis)
```

**Targeted variant** — when the TUI passes `target_sections`, a `## Target Sections` block is appended so the Patcher's surgical edits are constrained to the named sections:

```markdown
## Target Sections
Focus the patch on these sections only.
Leave all other sections unchanged:
- steps
```

### Context Window Management

Since `_input.md` contains **file references (paths)**, not inlined contents, the input itself is always compact. The agent's context window is consumed when it reads the referenced files using its tools.

The session manager lists references in priority order (highest first):

1. **Operation-specific data** (mandate, merge rules, patch request) — always included
2. **Target/baseline node YAML path** — always included
3. **Target/baseline proposal path** — always included
4. **Target/baseline plan path** — included when relevant to the operation
5. **Local reference file paths** — all listed
6. **Remote reference cache paths** — all listed with source URLs
7. **Parent/sibling node YAML paths** — included as supplementary context
8. **Graph state path** — included

The agent's work2do instructs it to read files in priority order and manage its own context budget. If the agent determines it cannot fit all referenced files, it reads metadata files first (compact YAML) and selectively reads full proposals/plans as needed.

---

## 7. Orchestration Flow

### 7.1 Initialization

**Trigger:** User runs `ait brainstorm init <task_num>` or equivalent TUI action.

**What happens:**
1. Initialize AgentCrew crew: `ait crew init --id brainstorm-<task_num>` (creates branch and worktree)
2. Register brainstorm agent types in `_crew_meta.yaml`
3. Create subdirectories in crew worktree: `br_nodes/`, `br_proposals/`, `br_plans/`
4. Write `br_session.yaml` with status `init`, linking to the task file
5. Write `br_graph_state.yaml` with empty history, `next_node_id: 0`, no head
6. Write `br_groups.yaml` with empty groups
7. Update session status to `active`

**Inputs:** Task number, task file path, user email, initial spec text
**Outputs:** Session directory populated, crew branch created

### 7.2 Explore

**Trigger:** User requests architectural exploration (e.g., "explore two approaches for the data layer").

**What the TUI does:**
1. Parse the user's exploration request through the brainstorm wizard
2. Determine how many explorers to spawn (one per approach)
3. If the baseline node's proposal or plan has structured sections, insert a **section-select step** in the wizard so the user can narrow the exploration to specific sections (skipped when no sections exist)
4. Create a new operation group: `explore_<seq>`
5. For each explorer, call `register_explorer(..., target_sections=<selected>)`; `_assemble_input_explorer()` inlines the selected sections into the agent's `_input.md`

**Agents created:**
- Type: `explorer`
- Count: 1 per requested approach (typically 1-3)
- Dependencies: None (explorers are independent within a group)
- Input: HEAD node's `.yaml` and `.md` files, the exploration mandate, and — when sections were selected — inlined `## Targeted Section Content` and `## Targeted Plan Section Content` blocks. All parallel explorers in the same group receive identical `target_sections`.

**Agent work2do (per explorer):**

```markdown
# Task: Explorer — <mandate summary>

## Phase 1: Read Baseline
- Read the baseline node YAML and proposal from _input.md
- Understand the current architectural state and constraints

### Checkpoint 1
- report_alive: "Read baseline — understanding constraints"
- update_progress: 15
- check_commands

## Phase 2: Generate Proposal
- Design a new architectural approach based on the mandate
- Write the proposal markdown following the template (Overview, Architecture,
  Data Flow, Components, Assumptions, Tradeoffs)
- Ensure all assumptions are explicit and all tradeoffs are documented

### Checkpoint 2
- report_alive: "Proposal drafted — writing metadata"
- update_progress: 60
- check_commands

## Phase 3: Generate Metadata
- Write the flat YAML node file with all dimension fields
- Ensure node_id, parents, description, proposal_file are correct
- Add any new dimensions to active_dimensions list

### Checkpoint 3
- report_alive: "Metadata written — finalizing output"
- update_progress: 85
- check_commands

## Phase 4: Output
- Write both files (YAML + MD) to _output.md in a structured format
- Include the new node_id and any updated graph_state fields

## Completion
- update_status: Completed
- update_progress: 100
- report_alive: "Exploration complete"
```

**What outputs are produced:**
- New node YAML file(s) in `br_nodes/`
- New proposal Markdown file(s) in `br_proposals/`
- Updated `br_graph_state.yaml` (incremented `next_node_id`, possibly new `active_dimensions`)
- Updated `br_groups.yaml` with the new group entry

**What the user decides next:**
- Compare the new proposals against existing nodes
- Select one as the new head
- Explore further from any node
- Hybridize nodes

### 7.3 Compare

**Trigger:** User requests comparison of specific nodes across specific dimensions.

**What the TUI does:**
1. Collect the node IDs to compare and the dimensions of interest
2. Compute the candidate section list as the intersection of sections present across all selected nodes; display checkboxes for the user to pick any subset (the list updates live as nodes are added or removed from the selection, preserving previously-checked values for sections that remain in the intersection)
3. Extract only the requested dimension fields from each node's YAML
4. Create operation group: `compare_<seq>`
5. Register a single comparator agent via `register_comparator(..., target_sections=<selected>)`; `_assemble_input_comparator()` appends a `## Section Focus` block when sections are selected

**Agents created:**
- Type: `comparator`
- Count: 1
- Dependencies: None
- Input: Extracted dimension fields from target nodes (not full proposals)

**Agent work2do:**

```markdown
# Task: Comparator — Compare <node_list> on <dimensions>

## Phase 1: Parse Input
- Read the extracted dimension data from _input.md
- Identify the nodes and dimensions being compared

### Checkpoint 1
- report_alive: "Input parsed — analyzing dimensions"
- update_progress: 20
- check_commands

## Phase 2: Generate Comparison Matrix
- Create a Markdown table comparing nodes across each dimension
- For each dimension row: summarize each node's approach, identify the key tradeoff

### Checkpoint 2
- report_alive: "Comparison matrix generated — writing delta summary"
- update_progress: 60
- check_commands

## Phase 3: Delta Summary
- Write a bulleted "Delta Summary" highlighting:
  - The most critical assumption differences between nodes
  - Hidden risks or infrastructure complexities
  - Which requirements would need to change if each approach is chosen
- Do NOT declare a winner unless the user specified a scoring metric

### Checkpoint 3
- report_alive: "Delta summary complete"
- update_progress: 90
- check_commands

## Phase 4: Output
- Write the comparison matrix and delta summary to _output.md

## Completion
- update_status: Completed
- update_progress: 100
- report_alive: "Comparison complete"
```

**What outputs are produced:**
- Comparison matrix (Markdown table) in the agent's output
- Delta summary with risk analysis
- No new nodes are created — comparisons are informational

**What the user decides next:**
- Select a node as the new head
- Hybridize specific components from compared nodes
- Explore new approaches informed by the comparison

### 7.4 Hybridize

**Trigger:** User requests merging components from two or more nodes into a new hybrid node.

**What the TUI does:**
1. Collect source node IDs and merge rules (which components from which node)
2. Read full YAML metadata and proposals for all source nodes
3. Create operation group: `hybridize_<seq>`
4. Register a single synthesizer agent

**Hybridize is not section-aware:** the wizard does not present a section-select step, and `register_synthesizer()` does not accept `target_sections`. Hybridization always operates on whole proposals.

**Agents created:**
- Type: `synthesizer`
- Count: 1
- Dependencies: None (all source data is provided as input)
- Input: Full YAML + proposal Markdown for each source node, plus user merge rules

**Agent work2do:**

```markdown
# Task: Synthesizer — Hybridize <node_list>

## Phase 1: Read Source Nodes
- Read all source node metadata and proposals from _input.md
- Understand the user's merge rules

### Checkpoint 1
- report_alive: "Source nodes loaded — analyzing conflicts"
- update_progress: 15
- check_commands

## Phase 2: Conflict Resolution
- Identify component incompatibilities between source nodes
- For each conflict: propose a bridging component or updated assumption
- Document all conflict resolutions

### Checkpoint 2
- report_alive: "Conflicts resolved — generating hybrid proposal"
- update_progress: 40
- check_commands

## Phase 3: Generate Hybrid Proposal
- Write the unified proposal following the template
- Clearly mark which components are inherited from which parent
- Document new bridging components and updated assumptions

### Checkpoint 3
- report_alive: "Hybrid proposal complete — writing metadata"
- update_progress: 70
- check_commands

## Phase 4: Generate Hybrid Metadata
- Write the flat YAML node with parents listing all source nodes
- Ensure all dimensions are correctly populated
- Mark inherited components with their source node

### Checkpoint 4
- report_alive: "Metadata complete — finalizing"
- update_progress: 90
- check_commands

## Phase 5: Output
- Write both files (YAML + MD) to _output.md
- Include conflict resolution summary for user review

## Completion
- update_status: Completed
- update_progress: 100
- report_alive: "Hybridization complete"
```

**What outputs are produced:**
- New hybrid node YAML in `br_nodes/`
- New hybrid proposal Markdown in `br_proposals/`
- Updated `br_graph_state.yaml` (new node, hybrid node typically becomes new head)
- Updated `br_groups.yaml`

**What the user decides next:**
- Review the hybrid for correctness
- Proceed to detail/implement
- Further refine via exploration or additional hybridization

### 7.5 Detail

**Trigger:** User locks in an architecture and requests a granular implementation plan.

**What the TUI does:**
1. Confirm the target node (usually current head)
2. Gather the node's YAML, proposal, and relevant codebase context
3. If the node's proposal has structured sections, offer a section-select step (for re-detailing only specific sections of an existing plan); skipped when no sections exist
4. Create operation group: `detail_<seq>`
5. Register a single detailer agent via `register_detailer(..., target_sections=<selected>)`; `_assemble_input_detailer()` appends a `## Target Sections` block and the current plan path when sections are selected

**Agents created:**
- Type: `detailer`
- Count: 1
- Dependencies: None
- Input: Target node's YAML + proposal + codebase file paths and contents

**Agent work2do:**

```markdown
# Task: Detailer — Implementation Plan for <node_id>

## Phase 1: Read Architecture
- Read the node metadata and full proposal from _input.md
- Read the relevant codebase files provided as context
- Understand the current code structure and what needs to change

### Checkpoint 1
- report_alive: "Architecture and codebase analyzed"
- update_progress: 15
- check_commands

## Phase 2: Prerequisites
- Identify all prerequisites (dependencies, tools, environment setup)
- Document any infrastructure provisioning needed

### Checkpoint 2
- report_alive: "Prerequisites identified — planning steps"
- update_progress: 30
- check_commands

## Phase 3: Step-by-Step Plan
- Write sequential, specific implementation steps
- For each step: list files to modify, describe exact changes, include
  code snippets for non-trivial modifications
- Ensure steps respect dependency order

### Checkpoint 3
- report_alive: "Implementation steps written — adding tests"
- update_progress: 70
- check_commands

## Phase 4: Testing and Verification
- Write testing strategy for each component
- Define verification checklist
- Include performance benchmarks that validate the node's assumptions

### Checkpoint 4
- report_alive: "Plan complete — writing output"
- update_progress: 90
- check_commands

## Phase 5: Output
- Write the complete plan following the plan template to _output.md
- Include the plan_file path for the node's YAML update

## Completion
- update_status: Completed
- update_progress: 100
- report_alive: "Detailing complete"
```

**What outputs are produced:**
- New plan Markdown in `br_plans/`
- Updated node YAML with `plan_file` field populated

**What the user decides next:**
- Accept the plan and proceed to implementation
- Request bottom-up tweaks to specific plan steps
- Go back to architectural exploration

### 7.6 Patch (Bottom-Up Plan Editing)

**Trigger:** User requests a specific change to an existing implementation plan (e.g., "change the variable name", "use a different library for step 3").

**What the TUI does:**
1. Identify the target node and its current plan
2. If the plan has structured sections, offer a section-select step so the patch is scoped to the named sections; skipped when the plan has no sections
3. Assess whether this is a purely local change or might have architectural impact
4. Create operation group: `patch_<seq>`
5. Register a single patcher agent via `register_patcher(..., target_sections=<selected>)`; `_assemble_input_patcher()` appends a `## Target Sections` block when sections are selected

**Agents created:**
- Type: `patcher`
- Count: 1
- Dependencies: None
- Input: Current node YAML + plan + the user's specific patch request

**Agent work2do:**

```markdown
# Task: Plan Patcher — <patch description>

## Phase 1: Read Current State
- Read the node metadata, proposal, and current plan from _input.md
- Read the user's patch request

### Checkpoint 1
- report_alive: "Current state loaded — analyzing patch"
- update_progress: 20
- check_commands

## Phase 2: Apply Patch
- Make the requested changes to the plan
- Keep all unaffected steps exactly as they were
- Minimize changes — surgical edits only

### Checkpoint 2
- report_alive: "Patch applied — running impact analysis"
- update_progress: 50
- check_commands

## Phase 3: Impact Analysis
- Analyze whether the patch changes any high-level dimensions
- Check each dimension prefix: does this patch change any component_*,
  assumption_*, or requirements_* values?
- Output one of:
  - NO_IMPACT: The patch is purely local to the plan
  - IMPACT_FLAG: List which dimensions changed and how

### Checkpoint 3
- report_alive: "Impact analysis complete — writing output"
- update_progress: 80
- check_commands

## Phase 4: Output
- If NO_IMPACT: Output the patched plan + a copy of the parent's YAML and
  proposal (renamed to the new node ID)
- If IMPACT_FLAG: Output the patched plan + the impact details so the
  orchestrator can trigger an Explorer to update the architecture

## Completion
- update_status: Completed
- update_progress: 100
- report_alive: "Patch complete"
```

**What outputs are produced:**
- New plan Markdown in `br_plans/` (patched version)
- New node YAML in `br_nodes/` (either identical to parent or flagged for architectural update)
- If `IMPACT_FLAG`: the orchestrator automatically triggers an Explorer to reconcile the architecture

**What the user decides next:**
- Accept the patched plan
- If architectural impact was flagged: review the Explorer's updated architecture
- Continue with further patches or proceed to implementation

**Future: Interactive Patching Mode**

Bottom-up plan editing is often iterative — the user may want to make multiple adjustments before committing. A future enhancement is to support an **interactive patching mode** where:

1. The code agent is started in interactive mode with the same inputs as batch mode (node metadata, plan, proposal)
2. The user interactively requests changes to the plan through conversation
3. The agent applies changes incrementally, showing diffs after each edit
4. Only when the user confirms all changes are done, the patcher procedure triggers from Phase 3 onward (impact analysis, output generation, node creation)

This avoids creating a new DAG node for every small tweak and gives the user a tighter feedback loop during plan refinement. The batch mode (current design) remains the default for non-interactive workflows.

### 7.7 Finalize

**Trigger:** User is satisfied with the current head node and its plan. Ready to convert to an aitask implementation plan.

**What happens:**
1. Verify the current head has both a proposal and a plan
2. Update session status to `completed`
3. Stop the AgentCrew crew runner (if running)
4. Export the final plan to `aiplans/` in aitask format
5. Link the brainstorm session in the task's metadata

### Top-Down vs Bottom-Up Flow Summary

```
┌─────────────────────────────────────────────────────────┐
│                    TOP-DOWN FLOW                         │
│  (Architectural changes cascade to implementation)       │
│                                                          │
│  User changes a dimension (component, assumption, req)   │
│          │                                               │
│          ▼                                               │
│  Explorer: generates new node (YAML + proposal)          │
│          │                                               │
│          ▼                                               │
│  Detailer: generates/updates plan for new node           │
│          │                                               │
│          ▼                                               │
│  New node becomes HEAD                                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   BOTTOM-UP FLOW                         │
│  (Plan tweaks may escalate to architectural changes)     │
│                                                          │
│  User requests specific plan edit                        │
│          │                                               │
│          ▼                                               │
│  Plan Patcher: applies surgical edit + impact analysis   │
│          │                                               │
│      ┌───┴───┐                                           │
│      │       │                                           │
│  NO_IMPACT  IMPACT_FLAG                                  │
│      │       │                                           │
│      ▼       ▼                                           │
│  New node   Explorer: updates architecture to reflect    │
│  (plan      the plan change, then Detailer reconciles    │
│   only)     the full plan                                │
│      │       │                                           │
│      ▼       ▼                                           │
│  New node becomes HEAD                                   │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Subagent Prompt Specifications

These are the system prompts for each brainstorm subagent role. They are designed to enforce consistent output formats and strict context discipline.

### 8.1 Explorer

**Role:** Architecture Explorer — generates structured proposals based on a specific exploration mandate.

```
You are an Architecture Explorer for the brainstorm engine. Your job is to
generate a new architectural proposal based on a specific mandate provided by
the user through the orchestrator.

## Input

You will receive in _input.md (assembled by the session manager):
1. The baseline node's YAML metadata path (flat key-value dimensions)
2. The baseline node's proposal Markdown path (full architectural narrative)
3. An exploration mandate describing what to explore or change
4. Codebase context: the baseline node's reference_files (local paths and cached URL paths)
5. Active dimensions from br_graph_state.yaml
6. Dimension Keys: the list of dimension keys you may reference from section markers
7. (Optional) Targeted Section Content: if the user selected specific sections, their content is inlined under this heading; focus exploration on those sections
8. (Optional) Targeted Plan Section Content: when the baseline has an associated plan, the selected sections from that plan are inlined under this heading

## Output

Your output must be section-wrapped using the shared section marker format
(see the `_section_format.md` include in the explorer template). Section
names are `lowercase_snake_case`; dimensions (when present) must come from the
"Dimension Keys" block above.

You must produce exactly two items (YAML metadata and a Markdown proposal)
written to `_output.md` with clear delimiters between them:

### File 1: Node Metadata (YAML)
A flat YAML file following the node schema. Requirements:
- node_id: Use the ID assigned by the orchestrator
- parents: List the baseline node as parent
- description: One-line summary of your approach
- proposal_file: Path to your proposal Markdown
- All dimension fields (requirements_fixed, requirements_mutable,
  assumption_*, component_*, tradeoff_pros, tradeoff_cons)
- created_by_group: The operation group ID provided in the mandate
- reference_files: Updated list of codebase files relevant to this proposal.
  Start with the baseline's reference_files. Add files for new components,
  remove files for components that were replaced or dropped.

Every dimension from the baseline node must appear in your output. You may
modify values, add new dimensions, or keep them unchanged — but never silently
drop a dimension.

### File 2: Proposal (Markdown)
A complete proposal with each major concern wrapped in a section marker.
Required sections (each wrapped in `<!-- section: name [dimensions: ...] -->`
... `<!-- /section: name -->`):
- `overview`: What this approach does and how it differs from the baseline
- `architecture` (dimensions: relevant `component_*` keys): Detailed system
  design with component responsibilities
- `data_flow`: How data moves through the system
- `components` (dimensions: `component_*` keys): One subsection per component
  with technology and configuration
- `assumptions` (dimensions: `assumption_*` keys): All assumptions, flagging
  which are inherited vs new
- `tradeoffs` (dimensions: `tradeoff_pros`, `tradeoff_cons`): Advantages,
  disadvantages, and risks with mitigations

## Rules

1. Be specific and concrete — name technologies, specify configurations,
   describe data schemas. Avoid vague phrases like "a suitable database."
2. Every assumption must be explicit. Do not hide assumptions inside
   component descriptions.
3. Every tradeoff must be actionable. "Slightly more complex" is not useful.
   "Requires a connection pooler like PgBouncer to handle >1000 concurrent
   connections" is useful.
4. If the mandate asks you to change a component, trace the impact to all
   other components and update assumptions accordingly.
5. Do not reference the orchestrator, other agents, or the brainstorm engine
   itself in your output — write as if this proposal stands alone.
6. Update reference_files to reflect your proposal's architecture. If you
   add a new component, add the relevant local files and external docs
   (URLs to technology references, API docs, etc.). If you remove a
   component, remove its references. Use your tools (Read, Grep, Glob,
   WebFetch) to discover additional relevant references not in the
   baseline's list.
7. Wrap each major concern in a section marker using `lowercase_snake_case`
   names. Dimensions on the marker must come from the "Dimension Keys" block
   in the input.
8. When `Targeted Section Content` is present, focus your exploration on
   those sections; reuse the same section names in your output so downstream
   operations can target the same concerns.
```

### 8.2 Comparator

**Role:** Tradeoff Analyst — creates focused comparison matrices across specified dimensions.

```
You are a Tradeoff Analyst for the brainstorm engine. Your job is to compare
architectural proposals across specific dimensions without getting lost in
implementation details.

## Input

You will receive:
1. Extracted dimension fields from 2+ nodes (YAML key-value pairs, not full
   proposals)
2. The list of dimensions to compare
3. Optional: a scoring metric from the user (e.g., "optimize for lowest
   latency")
4. Optional: a `Section Focus` block listing section names that are present
   across all nodes being compared. When present, scope your comparison to
   content within those sections.

## Output

### Part 1: Comparison Matrix (Markdown Table)

Create a table with:
- Rows: one per dimension being compared
- Columns: one per node, plus a "Key Tradeoff" column

Example:
| Dimension | n001 (Relational) | n002 (NoSQL) | Key Tradeoff |
|-----------|-------------------|--------------|--------------|
| component_database | PostgreSQL, normalized | DynamoDB, single-table | Flexibility vs scale |
| assumption_scale | Read-heavy, <1k writes/s | >10k concurrent writes | n002 over-engineers if writes stay low |

### Part 2: Delta Summary (Bulleted List)

After the table, write a "Delta Summary" that highlights:
- The most critical assumption differences between nodes
- Hidden risks or infrastructure complexities unique to each approach
- Which requirements would need to change if each approach is selected
- Dependency or integration risks (e.g., "n002 introduces DynamoDB which
  requires new IAM policies and a different deployment pipeline")

## Rules

1. Do NOT declare a winner unless the user explicitly provided a scoring
   metric. If a metric is provided, score each node and state the winner with
   the reasoning.
2. Focus on differences, not similarities. If two nodes share a dimension
   value, either omit the row or note "Same across all nodes."
3. Be specific about risks — "more complex" is not useful; "requires managing
   two data stores with separate backup strategies" is useful.
4. Keep the output concise. The comparison should fit on a single screen for
   2-3 nodes across 4-6 dimensions.
```

### 8.3 Synthesizer

**Role:** Architecture Synthesizer — merges components from multiple nodes and resolves conflicts.

```
You are an Architecture Synthesizer for the brainstorm engine. Your job is to
merge components from multiple architectural proposals into a single, cohesive
new node following the user's merge rules.

## Input

You will receive:
1. Full YAML metadata paths for each source node
2. Full proposal Markdown paths for each source node
3. The user's merge rules: which components to take from which node
4. The new node ID assigned by the orchestrator
5. Reference files: merged and deduplicated from all source nodes
6. Dimension Keys: merged union of dimension keys from all parents, for use in
   section markers

The synthesizer does not accept `target_sections` — hybridization always
operates on whole proposals.

## Output

You must produce exactly two items (same structure as the Explorer), written
to `_output.md` with clear delimiters. The proposal must be section-wrapped
using the same marker conventions as the Explorer.

### File 1: Node Metadata (YAML)
- parents: List ALL source nodes
- All dimension fields populated according to the merge rules
- created_by_group: The operation group ID
- reference_files: Merged from all parents, deduplicated, with references for
  bridging components added and references for dropped components removed

### File 2: Proposal (Markdown)
A unified proposal with the same required sections as the Explorer output
(`overview`, `architecture`, `data_flow`, `components`, `assumptions`,
`tradeoffs`), each wrapped in a section marker. Add a `conflict_resolutions`
section (no dimensions) documenting how incompatibilities between parents
were resolved.

## Conflict Resolution Process

When merging, conflicts are inevitable. Follow this process:

1. **Identify conflicts:** For each component being merged, check if it has
   dependencies on components from a different source node that won't be
   present in the hybrid.

2. **Resolution strategies (in priority order):**
   a. **Adapter/Bridge:** Introduce a bridging component (e.g., an ORM
      between a document-style API and a relational database)
   b. **Assumption update:** Change an assumption to make the components
      compatible (document explicitly which assumption changed and why)
   c. **Component replacement:** If the conflict is irreconcilable, propose
      a different component that satisfies both sides

3. **Document everything:** Every conflict resolution must appear in both the
   proposal (under a dedicated "Conflict Resolutions" subsection) and the
   metadata (as updated dimension values).

## Rules

1. Never silently drop a dimension from any source node. If a dimension
   exists in any parent, it must appear in the hybrid.
2. For each component in the hybrid, annotate its source in the proposal:
   "(inherited from nXXX)" or "(new: introduced to bridge nXXX and nYYY)."
3. If you introduce a bridging component, add it as a new component_* field
   and include its tradeoffs.
4. If the user's merge rules create an impossible combination, explain why
   and propose the closest feasible alternative. Do not silently deviate from
   the rules.
5. Merge reference_files from all source nodes. Deduplicate. Add references
   (local files and URLs) for bridging components. Remove references for
   components dropped during merge.
```

### 8.4 Detailer

**Role:** Implementation Planner — translates a locked-in architecture into a granular execution plan.

```
You are an Implementation Planner for the brainstorm engine. Your job is to
translate a finalized high-level architecture into a concrete, step-by-step
implementation plan that a developer can follow without ambiguity.

## Input

You will receive:
1. The finalized node's YAML metadata path
2. The finalized node's proposal Markdown path
3. Relevant codebase context: file listings, existing code that needs
   modification, project conventions
4. Dimension Keys: the list of dimension keys you may reference from section
   markers
5. Optional: a `Target Sections` block and a path to an existing plan.
   When present, re-render only the named sections of that plan and leave
   all other sections byte-for-byte identical.

## Output

A single Markdown file written to `_output.md`. Each major section of the
plan must be wrapped in a section marker using the shared format (see the
`_section_format.md` include). Required sections:

<!-- section: prerequisites -->
### Prerequisites
- Tools, libraries, and versions required
- Environment variables and configuration
- Infrastructure provisioning (if needed)
- Access or permissions
<!-- /section: prerequisites -->

<!-- section: steps [dimensions: relevant component_* keys] -->
### Step-by-Step Changes
For each step:
- **Step number and description**
- **Files:** exact paths to create or modify
- **Changes:** specific instructions with code snippets for non-trivial
  modifications
- **Why:** brief rationale linking this step to the architectural proposal

Steps must be in dependency order — no step should reference a file or
component created in a later step.
<!-- /section: steps -->

<!-- section: testing -->
### Testing
- Unit test strategy per component
- Integration test strategy
- Performance benchmarks that validate the node's assumptions
  (e.g., "Verify sub-100ms latency under 1000 concurrent connections")
<!-- /section: testing -->

<!-- section: verification -->
### Verification Checklist
A checkable list of criteria that confirm the implementation matches the
architecture.
<!-- /section: verification -->

Additional sections may be added with `lowercase_snake_case` names and
optional `dimensions:` annotations.

## Rules

1. Be maximally specific. Instead of "create the database schema," write
   "create migrations/001_create_users.sql with columns: id (UUID PK),
   email (VARCHAR(255) UNIQUE NOT NULL), created_at (TIMESTAMPTZ DEFAULT
   NOW())."
2. Reference exact file paths from the codebase context. Do not invent paths
   that don't match the project's conventions.
3. Every assumption from the node's YAML must map to at least one
   verification step.
4. If the codebase context reveals patterns (naming conventions, directory
   structure, testing framework), follow them exactly.
5. Do not include architectural discussion — that belongs in the proposal.
   The plan is purely operational: what to do, in what order, how to verify.
```

### 8.5 Plan Patcher

**Role:** Surgical Plan Editor — makes targeted changes to implementation plans with impact analysis.

```
You are a Plan Patcher for the brainstorm engine. Your job is to make
surgical, targeted modifications to an existing implementation plan based on
the user's request, and to assess whether those changes have any architectural
impact.

## Input

You will receive:
1. The current node's YAML metadata path
2. The current node's implementation plan path (this is what you modify)
3. The current node's proposal path (read-only, for impact analysis)
4. The user's specific patch request
5. Optional: a `Target Sections` block listing section names. When present,
   confine edits to those sections and leave every other section
   byte-for-byte unchanged.

## Output

### Part 1: Patched Plan

The modified implementation plan. Rules:
- Change ONLY what the user requested
- Keep all unaffected steps exactly as they were (byte-for-byte identical)
- If the patch adds a new step, insert it in the correct dependency order
- If the patch removes a step, verify no later steps depend on it

### Part 2: Impact Analysis

Analyze whether the patch affects any high-level architectural dimensions.
Check specifically:

1. Does this patch change a component_* value? (e.g., swapping a library
   effectively changes the component)
2. Does this patch invalidate an assumption_* value? (e.g., removing a
   connection pooler invalidates the assumption about high concurrency)
3. Does this patch violate a requirements_fixed constraint?

Output one of:
- **NO_IMPACT** — The patch is purely local to the implementation plan.
  Include a one-line justification (e.g., "Variable rename does not affect
  any architectural dimensions.")
- **IMPACT_FLAG** — The patch has architectural implications. Include:
  - Which dimensions are affected (list the YAML keys)
  - How they changed (old value → new value)
  - Recommended action (e.g., "Explorer should regenerate the proposal
    with component_cache changed from Redis to Memcached")

### Part 3: Updated Metadata (conditional)

- If NO_IMPACT: Output a copy of the parent's YAML with only node_id and
  parents updated (new node ID, parent = current node).
- If IMPACT_FLAG: Output the YAML with affected dimensions updated to
  reflect the patch. Flag updated fields with a comment
  "# UPDATED BY PATCH — verify with Explorer."

## Rules

1. Minimize changes. If the user asks to "rename variable X to Y in step 3,"
   change only that variable name in that step. Do not reformat, restructure,
   or "improve" surrounding steps.
2. The impact analysis must be conservative. When in doubt, flag IMPACT_FLAG.
   A false positive (unnecessary Explorer trigger) is far less costly than a
   false negative (architectural inconsistency).
3. Never change the proposal Markdown — only the plan. If architectural
   changes are needed, that's the Explorer's job.
4. If the user's request is ambiguous (e.g., "make step 3 faster"), ask for
   clarification in the output rather than guessing.
```

---

## 9. Section Viewer

Section-structured proposals and plans are rendered in three aitasks TUIs (codebrowser, brainstorm, board) by a single shared library: `.aitask-scripts/lib/section_viewer.py`. Centralising the widgets keeps the keyboard contract and visual behaviour identical across hosts and avoids each TUI reinventing minimap rendering.

### 9.1 Widgets

| Widget | Base | Role |
|---|---|---|
| `SectionRow` | `Static` | One focusable row in a minimap — shows section name and italicised dimension tags |
| `SectionMinimap` | `VerticalScroll` | Vertical list of `SectionRow` widgets; exposes `populate(parsed)` and `focus_first_row()` |
| `SectionAwareMarkdown` | `VerticalScroll` | Markdown renderer with a `scroll_to_section(name)` helper that uses `estimate_section_y()` to position the view |
| `SectionViewerScreen` | `ModalScreen` | Full-screen split-layout modal (minimap on the left, markdown on the right) |

**Helper:** `estimate_section_y(parsed, name, total_lines, virtual_height) -> float | None` approximates the Y scroll offset of a section by the ratio `section.start_line / total_lines` against the virtual content height. Textual's `Markdown` widget does not expose per-line offsets, so the position is intentionally approximate.

### 9.2 Events

`SectionMinimap` emits two messages that the host screen consumes:

- `SectionMinimap.SectionSelected(section_name)` — the user pressed Enter or clicked on a row; the host scrolls the companion markdown to that section.
- `SectionMinimap.ToggleFocus()` — the user pressed Tab while focused on the minimap; the host moves focus to the companion markdown widget.

`SectionRow` emits `SectionRow.Selected(section_name)` internally, which `SectionMinimap` re-emits as `SectionSelected`.

### 9.3 Keyboard Contract

Hosts that embed `SectionMinimap` must honour the following bindings:

| Key | Target | Effect |
|---|---|---|
| `up` / `down` | On a `SectionRow` | Move focus to previous / next sibling row |
| `enter` | On a `SectionRow` | Select the section (emit `SectionSelected`) |
| `tab` | On a `SectionRow` / minimap | Emit `ToggleFocus` — host moves focus to the companion content widget |
| `tab` | On the companion content widget | Host returns focus to the minimap via `focus_first_row()` |

Inside `SectionViewerScreen` the bindings are self-contained:

| Key | Effect |
|---|---|
| `tab` | Cycle focus between minimap and markdown (priority binding) |
| `escape` | Close the modal |

### 9.4 Host Integrations

All three hosts bind `V` (shift+v) to open `SectionViewerScreen` for the plan they are currently showing:

| Host | File | Where section widgets appear | Fullscreen binding |
|---|---|---|---|
| Codebrowser | `.aitask-scripts/codebrowser/detail_pane.py`, `codebrowser/codebrowser_app.py`, `codebrowser/history_detail.py` | Minimap above the detail pane's plan view; minimap above the history-screen plan detail | `V` → `action_view_plan` |
| Brainstorm | `.aitask-scripts/brainstorm/brainstorm_app.py` | Minimap in `NodeDetailModal`'s Proposal and Plan tabs | `V` → `action_fullscreen_plan` |
| Board | `.aitask-scripts/board/aitask_board.py` | Minimap in `TaskDetailScreen`'s plan view | `V` → `action_fullscreen_plan` |

### 9.5 Graceful Fallback

When a proposal or plan has **no** section markers:

- The minimap is hidden (its `display` attribute is set to `False`) and the markdown renders in full width.
- `SectionViewerScreen` opens as usual; the minimap is hidden and focus goes directly to the content pane.
- Hosts fall back to their pre-section rendering — no minimap, normal markdown, scroll keys behave as usual.

This keeps the widgets safe to embed in detail panes and modals that might receive either structured or unstructured content.

---

## References

This document is self-contained, but the following source documents provide deeper background on the underlying systems:

- **`aidocs/agentcrew/agentcrew_architecture.md`** — AgentCrew reference architecture: file layout, YAML schemas, status state machines, DAG dependency model, runner orchestration loop, concurrency enforcement, command and control, and CLI reference.
- **`aidocs/agentcrew/agentcrew_work2do_guide.md`** — Work2do authoring guide: abstract lifecycle operations, checkpoint patterns, template structure, and the instructions.md mapping layer.
- **`aidocs/brainstorming/building_an_iterative_ai_design_system.md`** — Original design conversation that defined the conceptual model for the brainstorm engine: Orchestrator-Subagent architecture, DAG structure, flat YAML nodes, subagent roles, bidirectional flow.
