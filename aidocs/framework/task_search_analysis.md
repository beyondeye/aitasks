# Task search for code agents: analysis and direction

How code agents find tasks today, how that compares with GitHub Issues and
beads, where the real cost is, and what to build. Written as the reference for
the task-query engine task `aitasks_go#93` and as coordination input to t1981
(task relations and obsolescence design).

Measurements are from 2026-11-04 at aitasks `253608e67` on one 24-core host
(1-minute load about 7 during the runs). They describe that corpus and that
host only.

## The question

When a code agent has to find tasks (related work, note recipients, trail
neighbours, duplicates, obsolete tasks), it greps markdown files. Is that a
limitation compared with an issue tracker such as GitHub Issues or beads?

**Partly.** For exact and structured lookups, grep over plain files is not the
limitation. Three other things are:

1. **Cross-references are written but never recorded as edges.** Task bodies
   name other tasks constantly, but nothing answers "who references this task".
2. **Read amplification.** Grep returns candidate files; the agent must then
   read each one to judge it, and that costs context.
3. **No recall by meaning.** A task worded differently is missed.

## Three kinds of question

| Question | GitHub Issues | beads | aitasks |
|---|---|---|---|
| **Exact / structured**: status, labels, "mentions t1663", "cites `aitask_create.sh`" | Qualifier search; network and rate limits | `bd list` with many filters; SQL underneath (Dolt) | `ait ls` filters plus grep. `aitask_find_by_file.sh` reads only the `file_references:` field, which few tasks carry |
| **Graph**: what is ready, what blocks X, who points at X | Sub-issues and issue dependencies; an automatic "mentioned this" event on the cited issue whenever another issue cites it | Core strength: `bd ready`, `bd dep add`, typed links including `duplicates`, `supersedes`, `relates-to` | Explicit edges: `depends`, `anchor`, `verifies`, `folded_into`, `risk_mitigation_tasks`, note `from=`. Backlinks from prose do not exist |
| **By meaning**: "is there already a task for this?", duplicates, obsolescence | Semantic and hybrid search (GA 2026-04-02) over titles and bodies | `bd search` is text search; the README does not mention semantic search | Grep only |

Source notes:

- GitHub: the changelog entries listed under *Sources*. Lexical stays the
  default; semantic and hybrid are opt-in (`search_type=semantic|hybrid` on
  `/search/issues`), limited to 10 requests per minute, and the reported
  top-3 hit rate is 75% against 66% for lexical. The "mentioned this" timeline
  events and the dependency features come from general knowledge of the
  product, not re-verified for this document.
- beads: the README at `github.com/gastownhall/beads` as fetched on
  2026-11-04. The repository's badges still point at `steveyegge/beads`. A
  feature absent from the README may still exist in the code.

## Measurements

### Corpus

| Set | Files | Bytes |
|---|---|---|
| Active tasks (parents and children) | 661 | — |
| Active plans | 146 | — |
| Active tasks + plans | 807 | 4,946,237 |
| Archived tasks + plans (loose `.md`; no `old.tar.zst` bundle present) | 1,246 | 18,072,942 |

- `t<NNN>` / `t<NNNN>` tokens in active task files: 6,857 occurrences (regex
  `\bt[0-9]{3,4}(_[0-9]+)?\b`; not deduplicated; includes self-mentions).
- 171 labels in `aitasks/metadata/labels.txt`.

### Python scan cost

One process that imports `lib/plan_paths.py` and `lib/task_yaml.py`, then for
every file runs `parse_frontmatter`, `plan_paths.extract` and a task-id regex
(`python3 -I`, three runs):

| Phase | Time |
|---|---|
| Interpreter start | 11 ms |
| Imports | 14–16 ms |
| Active tasks + plans | 444–733 ms |
| Archive | 1,228–1,618 ms |
| Whole process | 1.8–2.4 s |

t1981's seed proposal (§2.4) measured a path-only index over 594 tasks and
130 plans at 0.15 s. The two numbers measure different work.

### Signal quality (from t1981's seed proposal, §2.3)

Replay against the 13 senders with at least 4 notes (143 notes):

- Task-id cross-references in both directions, task bodies only: 86% recall
  at about 23 candidates per sender (precision about 41%).
- Including plans raises recall to 97%, but **contaminates the measurement**:
  a sender's archived plan is written after its notes and often lists the
  recipients. Any evaluation must read task bodies only, or separate the two.
- File overlap: 95% recall at about 290 candidates per sender. Labels: 24%.
  Metadata edges alone: 26%.
- Misses that no static signal reaches: a review finding about another task's
  in-flight work, and a consumer of a verdict vocabulary with no shared path.

## Where the cost actually is

Speed is not the main cost at this corpus size. Reading is:

- t1794_9 was a whole child task spent grepping 103 candidates to send 63
  notes.
- Building `art:trail-task-relations-and-premise` on 2026-11-04 needed eleven
  separate reads to judge drift neighbours, and the shared-file collisions
  between members came from reading each task's "Key files" section by hand.
  The trail gatherer already extracts paths, but only for in-flight tasks.
- The first search in that session (for obsolescence and note-routing tasks)
  returned about fifty grep hits with no ranking.

A tool that returns compact, structured, source-tagged records cuts this cost
whatever language it is written in.

## What exists today

| Piece | Gives | Limit |
|---|---|---|
| `ait ls` (`aitask_ls.sh`) | Status, labels, type, board column, follow-up kind, plan-approved, children, tree | Frontmatter only; no text, no references |
| `aitask_find_by_file.sh` | Pending tasks naming a path | Reads only `file_references:` |
| `aitask_query_files.sh` | Task, plan, child and sibling file locations | Locations, not content |
| `lib/plan_paths.py` | The path grammar (`extract`), task/framework section split, `find_references` / `find_suffix_references` | Extension allowlist `sh py md yaml yml json toml`; Python only |
| `lib/trail_gather.py` | Member snapshots, in-flight path surfaces, drift reasons | Scoped to one trail |
| `lib/parallel_admission*.py` | Overlap with in-flight tasks | In-flight only |
| `aitask_explain_context.sh` | Source files → archived plans that touched them | Archive direction, not pending tasks |
| `/aitask-note` Related Task Discovery | Candidate recipients | Titles, labels and the first ~5 body lines |
| `goengines/internal/testmap/deps` (`Graph.Reverse`) | Static import graph: changed file → dependent files | No task mapping, no CLI |

## What to take from GitHub and beads, and what not to

**Take: record edges when the text is written.** GitHub records a
cross-reference on the cited issue the moment it is cited. beads makes
`duplicates` and `supersedes` first-class. aitasks recomputes the same
answers at question time, by judgement. Recording them is t1981's thesis; a
query engine is the layer under it.

**Do not take:**

- **A database as the source of truth.** beads keeps issues in Dolt, with
  `issues.jsonl` as an export only. That would break the aitasks premise:
  markdown in git, `./ait git`, branch and legacy modes, plans beside tasks.
  Any index is a derived cache, keyed on file contents, never the authority.
- **Semantic results as decisions.** Embeddings raise recall and lower
  precision, and over-notification is a measured defect (t1981 §1). Semantic
  output may only ever be candidates for the agent to judge. It also needs a
  model dependency that an offline bash + Python framework does not have.

**Already ahead in aitasks:** plans and archived plans hold rationale history
that GitHub's index does not cover (titles and bodies only); no rate limits;
offline; cross-repository; every claim can be checked against a file.

## Direction

| Layer | What | Owner |
|---|---|---|
| L1 | A query engine: one scan of tasks, plans, notes and optionally the archive; frontmatter plus task ids and paths extracted from bodies; `mentions`, `cites`, text search with BM25 ranking; compact per-task cards | `aitasks_go#93` (Go) + a framework-side counterpart in this repository |
| L2 | Backlinks: the reverse of `mentions` (and of `cites`) | Same task |
| L3 | A store of confirmed, typed relations written in the background | t1981 |
| L4 | Semantic re-ranking | Deferred; only if a measurement justifies it |

L1 and L2 are the query layer of t1981's D6 (static candidate generation), so
t1981 consumes them rather than building its own. Other consumers: note
recipient discovery, trail neighbour and shared-file checks, fold candidates,
and a "does this already exist?" check at task creation.

## Constraints on the implementation

- **One grammar, or a pinned differential.** `lib/plan_paths.py` is the
  centralized path grammar, and `task_yaml.parse_frontmatter` is the
  frontmatter parser. A Go engine is a second implementation. Pin parity with
  a differential test over the live corpus. Any deliberate extension (for
  example `.go`, `.kt`, `.ts`, or suffix resolution of bare basenames) is a
  stated, tested difference, never accidental drift.
- **Section awareness.** Separate the description from framework sections
  (`## Inbox` notes, `## Gate Runs` ledgers, folded history) the way
  `plan_paths.split_task_framework_sections` does, and tag every hit with its
  source section.
- **Identity.** Emit canonical `<project>#<id>` refs. Accept every id shape
  the corpus uses (`depends`/`verifies` vary: `[1039]`, `['1074_2']`,
  `[t1018_1]`; see t1635).
- **Evidence, not verdicts.** Ranking orders candidates; no threshold decides
  relevance. Every record says where it came from.
- **No persisted index in v1.** Scan per query; measure before adding a cache.
  A cache, if added, is keyed on content hashes of every input it reads and is
  never the authority.
- **Read-only and visible failure.** Tolerate concurrent writers. An
  unreadable file is reported, never silently skipped. Exit status follows the
  engine conventions.
- **Every storage shape.** Branch mode (task data on its own branch) and
  legacy mode; loose archive files and `old.tar.zst` bundles; `--project` for
  sibling repositories.
- **Optional engine.** The engine install can be skipped (`--no-testmap`,
  `AIT_TESTMAP_FETCH=0`), so every consumer needs a fallback. The framework
  shim says which path answered.
- **Evaluation.** Use t1981's replay: recall and candidate count against real
  note history, task bodies only.

## Why Go, and what Go does not fix

Go fits the distribution and reuse side:

- Interpreter start is not the issue (11 ms), but an archive-wide scan is
  1.2–1.6 s in Python. A parallel Go scan should make archive-wide backlinks
  cheap enough to run on every query. That is an expectation; the engine task
  must measure it.
- Reuse: `internal/testmap/deps` (`Graph.Reverse`) for file → dependents
  widening, `internal/gitx`, `internal/lineproto`.
- Distribution: a static binary through the existing engine slot and
  SHA256SUMS verification.

Costs:

- It is a second implementation of the grammar and the parser (see
  *Constraints*).
- The engine is optional, so the fallback path stays.
- `lib/engine_install.sh` installs `ait-testmap` only, so a second binary
  needs framework-side install, prune and setup work.
- Development happens in the private `aitasks_go` repository.

The largest saving, fewer tokens per candidate, comes from the output shape
and does not depend on the language.

## Open questions

- One new binary (for example `ait-taskquery`) or a verb inside an existing
  engine?
- Is the grammar extended (more extensions, suffix resolution) in the engine
  first, or in `plan_paths.py` first so that both stay identical?
- Do notes (`## Inbox`) count as a mentions source? They are claims, and
  t1981's D8 decides whether past note edges are a signal.
- Does the archive scan include `old.tar.zst` bundles by default, or only on
  request?

## Owners

- Query engine (L1, L2), Go: `aitasks_go#93`.
- Relations store (L3) and consumption: t1981.

## Sources

- GitHub changelog: [Improved search for GitHub Issues is now generally available (2026-04-02)](https://github.blog/changelog/2026-04-02-improved-search-for-github-issues-is-now-generally-available/)
- GitHub changelog: [Improved search for GitHub Issues in public preview (2026-01-29)](https://github.blog/changelog/2026-01-29-improved-search-for-github-issues-in-public-preview/)
- GitHub changelog: [Semantic issue search in Copilot Chat (2026-05-20)](https://github.blog/changelog/2026-05-20-semantic-issue-search-in-copilot-chat/)
- beads: [github.com/gastownhall/beads](https://github.com/gastownhall/beads) (README, fetched 2026-11-04)
- t1981 seed proposal: `task_relations_proposal.md`, attached to t1981
  (`ait attach get 1981 task_relations_proposal.md`), §2.3, §2.4, §2.5, D6, D13
- `aidocs/framework/plan_path_reference_extraction_findings.md`
