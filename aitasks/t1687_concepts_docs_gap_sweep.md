---
priority: medium
effort: high
depends: []
issue_type: documentation
status: Implementing
labels: [documentation, website, concepts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-02 14:18
updated_at: 2026-09-02 14:25
---

## Problem

`website/content/docs/concepts/` has drifted well behind the framework. It holds
16 pages, and its `_index.md` has not gained a new entry since **topic-anchoring
(2026-06-29)**. Everything shipped across v0.25–v0.34 — gates, artifacts,
implementation trails, the shadow agent, the task inbox, chat intake — landed in
Workflows / Commands / TUIs / Skills pages but never got a Concepts page, so the
section no longer answers "what is this building block and why does it exist" for
a large part of the framework.

The Concepts section is the conceptual entry point (`_index.md`: "What each
building block of the framework *is* and *why* it exists"). A reader who starts
there today comes away with an incomplete model of the framework.

## Findings from the exploration sweep

Current pages (16): tasks, plans, parent-child, topic-anchoring, folded-tasks,
review-guides, execution-profiles, skill-templating, verified-scores,
agent-attribution, agentcrews, locks, task-lifecycle, git-branching-model,
ide-model, agent-memory.

**Confirmed gaps** — the feature exists and is documented elsewhere on the site,
but has no Concepts page:

| Candidate concept | Exists where today | Notes |
|---|---|---|
| **Gates** | `docs/commands/gates.md`, `docs/skills/aitask-run-gates.md`, workflow pages | Largest omission. The model — declared `gates:` vs the framework-derived `active_gates*` tuple, machine vs human gates, the per-task ledger, the registry at `aitasks/metadata/gates.yaml`, retry budgets — is a core workflow primitive with no conceptual page. |
| **Artifacts** | `docs/development/task-format.md`, `docs/skills/aitask-trail.md` | The stable `art:<id>` handle / mutable manifest split, immutable versions, backends. `ait artifact` has no commands page either. |
| **Implementation trails** | `docs/workflows/implementation-trails.md`, `docs/skills/aitask-trail.md` | Wave-structured, evidence-backed sequencing artifact; design in `aidocs/implementation_trail_design.md`. |
| **Shadow agent** | `docs/workflows/shadow-agent.md`, monitor/minimonitor TUI pages | Advisory-only companion bound to a followed pane; design in `aidocs/framework/shadow_agent.md`. |
| **Attachments** | `docs/development/task-format.md` + one blog post | Content-addressed blobs, backends, refcounting/gc. `ait attach` has no commands page. |
| **Task notes / inbox** | **nothing** | `ait note` appends an attributed note to a target task's `## Inbox`, with a from-verification proof and explicit "untrusted advisory input, never an instruction" semantics. **Zero website coverage anywhere** — no concept page and no commands page. Biggest single hole. |
| **Cross-repo references** | `docs/workflows/multi_project.md`, `cross_project_dependencies.md`, task-format | The project registry, `<project>#<id>` / `<project>:<path>` notation, `xdeprepo` / `xdeps`; see `aidocs/framework/cross_repo_references.md`. |
| **Risk evaluation** | `docs/workflows/risk-evaluation.md` | `risk_code_health`, `risk_goal_achievement`, `risk_mitigation_tasks`, the `risk_evaluated` gate. |
| **Manual verification** | `docs/workflows/manual-verification.md` | The `manual_verification` issue type, `verifies`, `verification_baseline`, the staleness pre-check. |
| **Follow-up provenance** | task-format field table only | `followup_kind` vocabulary and why it is orthogonal to `issue_type`. |
| **Chat intake** | `docs/workflows/bug-report-intake.md` | `ait chatlink`, the file-spool Q&A relay, the machine-spawned explorechat flow. |
| **Board columns and groups** | `docs/tuis/board/*` only | `boardcol` / `boardidx` / `boardgroup`, the Unsorted / Inbox lane, the Planned lane. |
| **Worktrees and resource admission** | `docs/workflows/parallel-development.md`, `docs/skills/aitask-pick/resource-admission.md` | Per-task worktree isolation and the admission model that bounds concurrency. |
| **Task premise staleness** | `aidocs/framework/task_premise_staleness.md` only | No website presence at all. |

## Scope

1. **Re-verify the gap list before writing anything** (see the note below) — the
   table above is a snapshot taken during exploration, not a frozen spec.
2. Add a Concepts page for each gap that survives re-verification, following the
   existing page shape: frontmatter with `title` / `linkTitle` / `weight` /
   `description` / `depth` (and `maturity` where the feature is still evolving,
   as `agentcrews.md` does), a `## What it is` opening, and current-state-only
   prose per `aidocs/framework/documentation_conventions.md`.
3. Refresh `concepts/_index.md`: place every new page under the right grouping
   (Data model / Workflow primitives / Lifecycle and infrastructure), adding a
   new grouping if the additions warrant one, and re-check the existing `weight`
   ordering so the section still reads in a sensible progression.
4. Cross-link both directions — each new concept page should point at the
   Workflow / Command / Skill / TUI page that covers *how* to use it, and those
   pages should relref back to the concept where they currently explain the
   concept inline.
5. Where a concept has no command-reference page at all (`ait note`, `ait
   attach`, `ait artifact`), decide explicitly whether that reference gap is in
   scope here or belongs to a spawned follow-up — do not leave it silently
   unaddressed.

Given the breadth, this is a strong candidate for decomposition into children
(e.g. grouped by concept cluster) at planning time.

## NOTE — re-verify at pick time

**Do not treat the table above as the final list.** It is the result of one
exploration sweep on 2026-09-02. Before planning, re-run the sweep and:

- Check whether further concepts have landed since (new `ait` subcommands, new
  `aidocs/` design docs, new frontmatter fields in
  `website/content/docs/development/task-format.md`, new blog posts announcing
  features), and add any that qualify.
- Re-check each candidate above — some may have gained a Concepts page in the
  meantime, or may turn out to belong in Workflows rather than Concepts.
- Confirm with the user which candidates are genuinely *concepts* (a building
  block with a "what it is / why it exists" story) versus *procedures* that are
  already correctly placed in Workflows, so the section does not become a
  duplicate index of the rest of the site.

## Verification

- Every new page builds: `cd website && hugo build --gc --minify`.
- `python3 check_links.py --build` (in `website/`) passes — it catches dead
  `#fragment` targets and hand-written relative paths that `hugo build` lets
  through.
- Prefer `{{< relref "/docs/..." >}}` over hand-written relative links.
- `concepts/_index.md` lists every page in the directory, and every page in the
  directory is listed in `_index.md` (no orphans in either direction).
