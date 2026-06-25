---
Task: t1072_triage_applink_backlog_labels_and_sequencing.md
Worktree: (none — fast profile, current branch)
Branch: current
Base branch: main
---

# t1072 — Triage AppLink backlog: labels + sequencing

## Context

The open AppLink backlog (~12 tasks) is hard to navigate: the same feature is
split across two labels (`applink` and the legacy synonym `ait_bridge`), one
AppLink task (t1002) carries no AppLink label at all, and no label says *which
aspect* of AppLink a task touches. There is also no recorded implementation
order — in particular, which tasks are best done before decomposing the t1061
outside-network roadmap. A key fact is currently mis-stated in t1061: its hard
gate **t985 is already DONE/archived**, so t1061 is unblocked, yet its body still
reads "t985 … Ready/high".

This task is pure organization — no AppLink feature code changes. Two
deliverables: (1) a consistent dual-label scheme applied across the AppLink
tasks; (2) the sequencing decision recorded as source-of-truth in t1061's body.

Decisions already taken with the user:
- **Dual labels**: keep umbrella `applink` on every AppLink task AND add one
  sub-area label. (`ait_bridge` consolidated into `applink`.)
- **4 sub-areas**: `applink_dataplane`, `applink_security`, `applink_control`,
  `applink_connectivity`. t1002 = umbrella only (hygiene bug, fits no sub-area).
- **Sequencing recorded in t1061's body** (`## Dependencies & sequencing`).

## Step 1 — Update the label catalog (`aitasks/metadata/labels.txt`)

The batch `--labels` (replace) path of `aitask_update.sh` does **not** register
new labels into `labels.txt` (only the `--add-label` path does), so the catalog
must be edited explicitly first. `history_label_filter.py` sorts on read, so
insertion order is cosmetic.

- **Add** four labels (insert after the `applink` line, alphabetical):
  `applink_connectivity`, `applink_control`, `applink_dataplane`,
  `applink_security`.
- **Remove** `ait_bridge` (legacy synonym; now unused on any active task — only
  2 archived tasks reference it, and the board derives filters from task
  frontmatter, not this pick-list, so archived references keep working).

## Step 2 — Relabel the AppLink tasks

Use `./.aitask-scripts/aitask_update.sh --batch <id> --labels "<csv>"` (replaces
all labels; auto-bumps `updated_at`). One call per task:

| Task | New labels |
|------|------------|
| t1007 | `applink,applink_dataplane` |
| t1011 | `applink,applink_control` |
| t1045 | `applink,applink_dataplane` |
| t1054 | `applink,applink_dataplane` |
| t1055 | `applink,applink_dataplane` |
| t1056 | `applink,applink_dataplane` |
| t1057 | `applink,applink_dataplane` |
| t1058 | `applink,applink_dataplane` |
| t1061 | `applink,applink_connectivity` |
| t1066 | `applink,applink_security` |
| t1067 | `applink,applink_security` |
| t1068 | `applink,applink_security` |
| t1002 | `verification,bug,applink` |

t1072 (this task) stays `applink` (organizational — no sub-area). No change.

## Step 3 — Record sequencing + t985 correction in t1061's body

Edit `aitasks/t1061_applink_outside_network_connectivity_roadmap.md`, replacing
its `## Dependencies & sequencing` section so it (a) states t985 is **DONE /
archived → public-exposure work unblocked**, and (b) records the tiered order:

- **Tier 0 — before t1061 (correct + usable remote link), cheap-first:**
  t1054 (HIGH bug, viewport-only rows — do first) → t1055 (pause verb, cheap) →
  t1007 (data-plane DoS caps, cheap) → t1045 (roster-vs-focused, the cellular
  bandwidth win).
- **Tier 1 — strongly recommended, larger:** t1057 (history RPC, follows t1054)
  → t1056 (viewport_hint clipping).
- **Tier 2 — pair with t1061's PUBLIC-EXPOSURE phases (Alt B / Phase 3-4), not
  the cheap Phase-2 tunnel:** t1068 (rate limit), t1066 (cert rotation),
  t1067 (bearer rotation).
- **Independent of t1061 (any time):** t1011 (launch policy), t1002 (shellcheck
  bug), t1058 (cursor frames, low).

Keep the existing "Phase-1 foundation (DONE)" bullet. The change is additive
prose; no other section of t1061 is touched.

## Step 4 — Commit (Step 8 review first)

All edits are task-data-branch files → commit via `./ait git`, staging explicit
paths only (concurrent-writer hygiene — do not blanket-add):

- `./ait git add aitasks/metadata/labels.txt aitasks/t1002_*.md aitasks/t1007_*.md
  aitasks/t1011_*.md aitasks/t1045_*.md aitasks/t1054_*.md aitasks/t1055_*.md
  aitasks/t1056_*.md aitasks/t1057_*.md aitasks/t1058_*.md aitasks/t1061_*.md
  aitasks/t1066_*.md aitasks/t1067_*.md aitasks/t1068_*.md`
- Commit message: `chore: Relabel AppLink backlog and record sequencing (t1072)`
  — issue_type-tagged for traceability even though the deliverable is task-data
  (this is the task's real work product, not bookkeeping). The plan file commits
  separately as `ait: Add plan for t1072`.

## Verification

- `grep -n 'ait_bridge' aitasks/metadata/labels.txt` → empty (removed).
- `grep -nE 'applink_(connectivity|control|dataplane|security)' aitasks/metadata/labels.txt`
  → all four present.
- For each relabeled task: `grep '^labels:' aitasks/t<id>_*.md` matches the table.
- `grep -rl 'labels:.*ait_bridge' aitasks/*.md` → empty (no active task still on
  the legacy label).
- t1061 body: read the revised `## Dependencies & sequencing` — t985 shown DONE,
  tiers present, rest of file unchanged (`git diff` scoped to that section).
- `./ait ls --label applink` (or board) shows all AppLink tasks under the
  umbrella; sub-area labels filter the slices.
- No shell/code files changed → no shellcheck/test run needed.

## Risk

### Code-health risk: low
- Metadata/doc-only edits (label catalog, task frontmatter labels, one task's
  prose). No code paths, no scripts, no behavioral surface. Blast radius is
  task-data files, each edited via the sanctioned `aitask_update.sh` /
  `./ait git` path. · severity: low · → mitigation: none

### Goal-achievement risk: low
- Scope and label scheme were confirmed with the user up front; the mapping is
  enumerated explicitly and verified by grep. Only residual: the sequencing tiers
  are a judgement call the user can adjust at Step 8 review. · severity: low ·
  → mitigation: none

risk_mitigations_planned: false

## Final Implementation Notes

- **Actual work done:** Exactly as planned. (1) `labels.txt`: removed legacy
  `ait_bridge`, added `applink_connectivity`, `applink_control`,
  `applink_dataplane`, `applink_security`. (2) Relabeled 13 tasks to the dual
  scheme via `aitask_update.sh --batch <id> --labels` (t1002 → umbrella only;
  t1007/t1045/t1054-58 → dataplane; t1011 → control; t1061 → connectivity;
  t1066-68 → security). (3) Rewrote t1061's `## Dependencies & sequencing` —
  t985 corrected to DONE/unblocked, added a `### Suggested implementation order`
  subsection with Tiers 0/1/2 + independent.
- **Deviations from plan:** None.
- **Issues encountered:** The `aitask_update.sh --labels` calls re-wrote each
  task file (frontmatter `updated_at` bump), which invalidated an in-flight Edit
  on t1061 ("file modified since read") — re-read the section and re-applied; the
  body text was unmodified by the label op. No data lost.
- **Key decisions:** Dual labels (umbrella + sub-area) over replace-only, to keep
  one-filter roll-up of all AppLink work; 4 sub-area buckets; sequencing recorded
  in t1061's body (source-of-truth next to the roadmap) rather than a separate
  aidocs note. All confirmed with the user before implementing.
- **Upstream defects identified:** None.
