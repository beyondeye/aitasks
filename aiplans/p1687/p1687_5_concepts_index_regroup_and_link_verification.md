---
Task: t1687_5_concepts_index_regroup_and_link_verification.md
Parent Task: aitasks/t1687_concepts_docs_gap_sweep.md
Sibling Tasks: aitasks/t1687/t1687_1_concepts_gates_page.md, aitasks/t1687/t1687_2_concepts_attachments_and_attach_command.md, aitasks/t1687/t1687_3_concepts_task_notes_and_cross_repo.md, aitasks/t1687/t1687_4_concepts_trails_and_shadow_agent.md
Archived Sibling Plans: aiplans/archived/p1687/p1687_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-09-24 15:28
---

# t1687_5: Concepts index, reading chain, and verification

## Context

This is the final child of the t1687 Concepts docs sweep. Siblings t1687_1..4
added six concept pages, and each one landed with its back-links. None of them
touched `website/content/docs/concepts/_index.md`, because this task owns that
file. The task has three parts: index the six pages, repair the `**Next:**`
reading chain, and run the verification block for the whole sweep.

### Verification of the existing plan (2026-09-24)

- **Pre-flight passed.** All six pages exist with the expected weights: task-notes
  45, attachments 55, gates 85, implementation-trails 105, cross-repo-references
  115 and shadow-agent 125. None has a `**Next:**` footer; each ends at
  `## See also`.
- **`_index.md` has not changed since planning.** It lists 17 bullets in three
  groups. The contending tasks t1231_3 and t635_18 are both still `Ready`, so
  neither has landed an edit to it.
- **Correction to the task body:** `agentcrews.md` *does* have a footer
  (`**Next:** Agent attribution`). What keeps it off the chain is that no page
  points *to* it. The pages outside the chain are the three nobody links to:
  topic-anchoring, agentcrews and framework-session.
- **Chain rule, made concrete:** the existing chain follows **index (reading)
  order**, not raw weight order. For example, `ide-model` sits "past"
  `framework-session` only in index order. So the new chain is defined as
  **exactly the final `_index.md` order, top to bottom**, with one link per
  consecutive pair. This splices the new pages "in weight order within their
  group" (which is how their bullets are placed) and keeps the chain and the
  index from disagreeing.
- **Inbox notes applied:** `gates` is a fourth colliding slug (it clashes with
  `commands/gates`). Every relref therefore uses the full `/docs/concepts/<slug>`
  path. The note about the `multi_project.md` wording does not touch this task.
- **Other session's changes:** the worktree also holds uncommitted edits to
  `installation/terminal-setup.md` and `workflows/freeze-and-restore-agents.md`
  from another session. This task does not touch them, and they are excluded
  from this task's commit. If the build flags either file, that is reported
  back, not fixed here.

## Implementation

### 1. `_index.md`: add six bullets

Bullet shape (copy it exactly; `linkTitle` as the link text; blurb reworded from
`description`):

```
- **[Tasks]({{< relref "/docs/concepts/tasks" >}})** — Markdown files with YAML frontmatter, one per unit of work.
```

The final order is shown below; new bullets are marked ★. Existing bullets are
not modified.

**Data model** (8)
tasks · plans · parent-child · topic-anchoring · folded-tasks ·
★ task-notes · review-guides · ★ attachments

- ★ `- **[Task notes]({{< relref "/docs/concepts/task-notes" >}})** — Context sent between tasks, untrusted by construction, and what its provenance can and cannot prove.`
- ★ `- **[Attachments]({{< relref "/docs/concepts/attachments" >}})** — Content-addressed files attached to a task, identified by their hash rather than a path.`

**Workflow primitives** (8)
execution-profiles · skill-templating · verified-scores · agent-attribution ·
agentcrews · ★ gates · locks · ★ shadow-agent

- ★ `- **[Gates]({{< relref "/docs/concepts/gates" >}})** — Named checks a task must satisfy before it archives, and why the enforced set is fixed when the task is picked.`
- ★ `- **[Shadow agent]({{< relref "/docs/concepts/shadow-agent" >}})** — A companion agent bound to the agent it follows, and what keeps it advisory.`

**Lifecycle and infrastructure** (7)
task-lifecycle · ★ implementation-trails · git-branching-model ·
★ cross-repo-references · ide-model · framework-session · agent-memory

- ★ `- **[Implementation trails]({{< relref "/docs/concepts/implementation-trails" >}})** — Why a sequencing recommendation is kept as a versioned, task-owned artifact instead of being recomputed.`
- ★ `- **[Cross-repo references]({{< relref "/docs/concepts/cross-repo-references" >}})** — Why cross-repo work is identified by a logical project name resolved at call time, never by a path.`

No frontmatter weights change. `shadow-agent` (125) is listed in *Workflow
primitives* even though its weight falls outside that group's band. This is
deliberate: the file already hand-orders its groups (agentcrews 75 after
attribution 80; framework-session 95 after ide-model 120), so the mismatch is
noted rather than fixed.

After the edit, re-read each group's lead-in sentence against its members.
Shadow agent shapes agent behaviour and gates shape the workflow, so both fit
"building blocks that shape how skills and code agents behave". Trails and
cross-repo references fit "how tasks move through the system and how the
repository is laid out". A fourth group is not warranted.

### 2. `**Next:**` reading chain (follows the index order exactly)

The target chain, 23 pages with 22 links:

tasks → plans → parent-child → **topic-anchoring** → folded-tasks →
**task-notes** → review-guides → **attachments** → execution-profiles →
skill-templating → verified-scores → agent-attribution → **agentcrews** →
**gates** → locks → **shadow-agent** → task-lifecycle →
**implementation-trails** → git-branching-model → **cross-repo-references** →
ide-model → **framework-session** → agent-memory (end; no footer).

Footer shape, from `parent-child.md`:

```

---

**Next:** [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}})
```

**Retarget** these existing footers (change only the link text and target):

| File | Old → New |
|---|---|
| parent-child.md | Folded tasks → Topic anchoring |
| folded-tasks.md | Review guides → Task notes |
| review-guides.md | Execution profiles → Attachments |
| agent-attribution.md | Locks → Agentcrews |
| agentcrews.md | Agent attribution → Gates |
| locks.md | Task lifecycle → Shadow agent |
| task-lifecycle.md | Git branching model → Implementation trails |
| git-branching-model.md | The IDE model → Cross-repo references |
| ide-model.md | Agent memory → Framework session |

**Append** a `---` / `**Next:**` footer after `## See also`:

| File | Next |
|---|---|
| topic-anchoring.md | Folded tasks |
| task-notes.md | Review guides |
| attachments.md | Execution profiles |
| gates.md | Locks |
| shadow-agent.md | Task lifecycle |
| implementation-trails.md | Git branching model |
| cross-repo-references.md | The IDE model |
| framework-session.md | Agent memory |

The link text is always the target's `linkTitle`, and every target uses the full
`/docs/concepts/<slug>` relref. Before appending, check the end of each file for
a trailing blank line so the footer spacing matches `parent-child.md`.

Scope note: this step goes beyond a literal reading of t1687. It was approved at
planning as serving "the section reads in a sensible progression", so it is
kept. It touches the frontmatter of no page, and no page body outside its
footer.

### 3. Orphan check, both directions

```bash
cd website/content/docs/concepts
ls *.md | grep -v '^_index.md$' | sed 's/\.md$//' | sort > "$SCRATCH/pages.txt"
grep -o 'relref "/docs/concepts/[a-z-]*"' _index.md | sed 's|.*/||; s|"||' | sort > "$SCRATCH/bullets.txt"
diff "$SCRATCH/pages.txt" "$SCRATCH/bullets.txt" && echo "no orphans"   # expect 23 ↔ 23
```

The chain check parses every `**Next:**` target and walks from `tasks`. The walk
must visit all 23 pages exactly once, in `_index.md` order, and end at
`agent-memory`.

### Post-phase (risk mitigations)

1. [link_relevance_triage] Run `cd website && python3 check_link_relevance.py`,
   then walk **every** link added by t1687_1..5, not only the reported rows.
   **Derive the inventory from the diffs, not from the link map.** The map
   lists only back-links. The six new pages also carry many outgoing links to
   workflow, command, skill and TUI pages, and those must be walked too:

   **Extraction must be multiline-aware.** Link text is wrapped across lines
   in these pages, so a line-by-line `grep -o` silently drops links. Measured
   against the current tree: `cross-repo-references.md:78-79` (the link to
   `/docs/commands/note#sending-to-another-repository`) and two links in
   `task-notes.md` are missed. The single-line grep finds 13+11 links in those
   two pages, the multiline parse finds 15+12. So write a small Python
   extractor in the scratchpad:

   - Parse whole files with a `re.S` regex:
     `\[((?:[^\[\]]|\[[^\]]*\])+?)\]\(\s*({{<\s*relref\s+"…"\s*>}}[^)\s]*|[^)\s]+)\s*\)`.
     Collapse whitespace in the link text and record the start line of each
     match.
   - For each sibling commit (`15a1f9f66`, `63012375f`, `a9b93ff98`,
     `833ba3c13`, re-derived from `git log --grep='t1687_'`) and each file
     under `website/content/` it touched:
     - **Added file** (`git show --diff-filter=A --name-only`): take every
       link in the file as of that commit (`git show <c>:<path>`).
     - **Modified file:** parse the file as of that commit and keep the links
       whose line span (start line to end line of the match) overlaps an
       added line number taken from `git show -U0 <c> -- <path>` hunk
       headers.
   - For this task: apply the same overlap rule to `git diff -U0` of the
     working tree, which covers the index bullets and the Next footers.
   - **Cross-check before triage:** the inventory must contain
     `cross-repo-references.md:78` → `commands/note#sending-to-another-repository`
     and both split links in `task-notes.md`. For each of the six new pages,
     its inventory count must equal the full-file multiline count. If any
     check fails, the extractor is wrong. Fix it before triaging.

   Group the links by target page. For each distinct
   target+anchor, open the target and confirm it discusses what the link text
   names. The subject is the link text plus its surrounding sentence, so read
   the source line for context. Record a table in the Final Implementation
   Notes: total links, distinct targets, which ones were reported, and the
   verdict for each off-topic or doubtful case. Any link found off-topic is
   fixed in this task. A fix is a one-line retarget, and the whole sweep is
   documentation this task verifies, so the fix belongs here. Expected false
   positives are `concepts/task-notes.md:44` and the pre-existing
   leading-code-span rows. Also confirm that `ait artifact` is still unlinked
   in `development/task-format.md` and `skills/aitask-trail.md`.

## Verification

```bash
set -o pipefail
cd website && hugo build --gc --minify            # dead or ambiguous relref fails
cd website && python3 check_links.py --build      # dead #fragments, relative paths
cd website && python3 check_link_relevance.py     # report only
grep -rn '](\.\./' website/content/docs/concepts/ | wc -l   # expect 0
grep -rn '```mermaid' website/content/ | wc -l              # expect 0
```

Also check that every `#anchor` named in the parent plan's reciprocal link map
still exists (`check_links.py --build` enforces this for linked ones; grep for
the rest).

## Deferred gaps, re-verified against the current site (2026-09-24)

The parent plan listed several gaps. Each was re-checked against the site as it
is today:

| Claimed gap | Current site | Verdict |
|---|---|---|
| `ait trails` has zero coverage | `tuis/trails/{_index,how-to,reference}.md` document it. `ait trails` has no subcommands, and TUIs live under `tuis/`, not `commands/` (same for board, monitor, codebrowser) | **Stale claim, dropped** |
| `ait chatlink` has no page | `tuis/_index.md:27` describes the status TUI; `workflows/bug-report-intake.md` covers `ait chatlink` and `--headless` | **Covered, no task** |
| `ait brainstorm` has no commands/ page | `tuis/brainstorm/` documents `init`, `status`, `list`, `archive` and `<num>`. **`delete`, `apply-initializer`, `apply-explorer` and `apply-synthesizer` appear nowhere on the site** (grep of `website/content/docs` is empty) | **Genuine gap: create a follow-up task** |
| Concept candidates (risk evaluation, manual verification, chat intake, backlog roadmap, follow-up provenance) | Each has a dedicated page: `workflows/risk-evaluation.md`, `workflows/manual-verification.md`, `workflows/bug-report-intake.md`, `skills/aitask-backlog-roadmap.md`, `workflows/follow-up-tasks.md` + `development/task-format.md` | Excluded on purpose as procedure-shaped; covered, **no task** |
| Board columns/groups, sync deferral | Covered in `tuis/board/reference.md`, `commands/sync.md`, `development/task-format.md` | Judged too thin for a concept page; **no task** |
| `diffviewer` absent | Intentional, per CLAUDE.md | Not a gap |

**Follow-up to create** (Step 8, after the commit, via `aitask_create.sh
--batch`, type `documentation`, labels `documentation,website`): *Document the
`ait brainstorm` recovery and deletion subcommands*.

- **Scope:** `delete`, `apply-initializer`, `apply-explorer` and
  `apply-synthesizer`, as defined in `ait` (lines ~283-289) and the
  `aitask_brainstorm_{delete,apply_*}.sh` scripts.
- **Target:** most likely a section in `tuis/brainstorm/how-to.md` next to the
  existing `status`/`list`/`archive` sentence (line ~133), or a
  `commands/brainstorm.md` page if the surface warrants one.
- **Workflow:** run `check_links.py` after editing.

Before creating it, re-run the `brainstorm (delete|apply-)` grep in case another
session has covered it in the meantime.

## Step 9 (Post-Implementation)

Standard Step 9: commit the website changes with
`documentation: ... (t1687_5)`, naming the paths explicitly. The
`risk_evaluated` gate must pass before archival. This is the last child, so
confirm the parent t1687 is complete before it is archived.

## Risk

### Code-health risk: low
- Nineteen concepts files are touched, but each change is additive: an index
  bullet or a footer line. No frontmatter weight or page body changes. The one
  place a mistake is possible is a mistyped relref slug, and `hugo build` fails
  on it. · severity: low · → mitigation: none
- Contention: t1231_3 and t635_18 (both `Ready`) plan to edit `_index.md`. One
  consolidated edit with no renumbering keeps their rebase to single-bullet
  inserts. · severity: low · → mitigation: none

### Goal-achievement risk: low
- A new link can resolve to a real page that is off-topic. `hugo build` and
  `check_links.py` both pass that class of defect. · severity: low (residual,
  addressed by inline post-phase link_relevance_triage) · →
  mitigation: inline post-phase link_relevance_triage

### Planned mitigations
- timing: post-phase | name: link_relevance_triage | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: resolve-but-off-topic links added by the t1687 sweep | desc: Run check_link_relevance.py and walk every link added by t1687_1..5 (inventory derived from the sibling diffs, including outgoing links inside the six new pages) for on-topic targets; fix off-topic ones; record the triage.
