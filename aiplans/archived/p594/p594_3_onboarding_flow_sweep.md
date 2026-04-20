---
Task: t594_3_onboarding_flow_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{1,2,4,5,6}_*.md
Worktree: (none — work on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-20 09:14
---

# t594_3 — Onboarding flow sweep — VERIFIED

## Context

Child of t594. The original plan claimed "the website currently has no Next: pointers". **This premise is obsolete**: siblings t594_1 (TUIs sweep) and t594_2 (systemic consistency sweep) added Next: footers across the TUIs section and several main-reading-path pages. Current Next: footers on the onboarding path:

- `docs/_index.md` — **no Next pointer** (genuinely missing)
- `overview.md:95` — `Next: Installation`
- `getting-started.md:112` — `Next: The tmux IDE workflow`
- `installation/_index.md:97` — `Next: Getting Started`

Per user decision during plan verification (2026-04-20), the current main reading sequence is preserved: **overview → installation → getting-started → tmux-ide**. Only the missing `_index.md → overview` pointer and the installation-subfolder chain are added. No existing main-path Next: line is rewired.

## Scope

**In-bounds:**
- Add the one missing main-path Next: footer on `docs/_index.md`.
- Add Next: footers across the four installation subfolder pages (`windows-wsl.md`, `terminal-setup.md`, `known-issues.md`, `git-remotes.md`), ordered by their existing `weight` frontmatter.
- Add a "Start here" callout at the top of `skills/_index.md` pointing at `/aitask-pick` as the hub skill.
- Add "(Main concepts)" / "(Reference)" markers to the bullets in `concepts/_index.md` while preserving the existing thematic groupings (Data model / Workflow primitives / Lifecycle and infrastructure).
- Spot-verify install curl commands against `install.sh` (sibling t594_2 already byte-verified the three primary locations, so this is a light re-check rather than a pass).
- Hugo build check.

**Out-of-bounds:**
- Rewiring any existing main-path Next: line (explicitly rejected by user — keeps sibling t594_2's decisions intact).
- Polishing `skills/_index.md` category descriptions — explicitly reserved for t594_4.
- Removing content from `overview.md` or `getting-started.md` (self-contained completeness preserved).
- Reorganizing or reweighting sections.

## Concrete drift items

### 1. `docs/_index.md` — missing Next pointer (only genuinely missing link on the main path)

Current state: 10-line file, no Next footer.

Add at the bottom:

```markdown
---

**Next:** [Overview]({{< relref "overview" >}})
```

### 2. Installation subfolder Next chain (weight order)

Weights within `installation/`: `_index.md` (10), `windows-wsl.md` (20), `terminal-setup.md` (30), `known-issues.md` (30), `git-remotes.md` (40).

**Decision on tie:** `terminal-setup.md` and `known-issues.md` both weight 30. Terminal setup is a direct continuation of setup (needed by all users); known-issues is a reference-style caveat page. Order: terminal-setup → known-issues.

Resulting intra-installation chain: `_index` → `windows-wsl` → `terminal-setup` → `known-issues` → `git-remotes`. Since `_index.md` already links out to `getting-started`, this chain is a **secondary navigation aid** (installation-deep-dive readers) rather than the primary reading path.

Per-page actions:

- `windows-wsl.md` — currently ends with "Known Issues" H2 section (line 171+). Add a single "Next:" footer line below it pointing to `terminal-setup/`.
- `terminal-setup.md` — currently ends with an existing `## Next steps` H2 list linking to Getting Started, tmux-ide workflow, Monitor TUI. **Do not rewrite that list.** Add a concise one-line `**Next:** [Known Issues](../known-issues/)` footer below the H2 list to plug the intra-installation chain without deleting the curated multi-link list (which serves readers who want to jump straight to Getting Started or tmux-ide).
- `known-issues.md` — add `**Next:** [Git Remotes](../git-remotes/)` footer.
- `git-remotes.md` — terminal page of the installation chain. Add `**Next:** [Getting Started]({{< relref "getting-started" >}})` to bridge back to the main reading path (consistent with `installation/_index.md:97`'s existing pointer).

### 3. `skills/_index.md` — "Start here" callout

Current state: No top callout. Line 24 mentions `/aitask-pick` as "The central skill" inside the Task Implementation table only.

Add a short callout block at the top of the file (after the frontmatter and the existing lead paragraph at line 8, before the existing `> **Multi-agent support:**` block at line 12):

```markdown
> **Start here:** [`/aitask-pick`](aitask-pick/) is the hub skill — it drives the full pick → plan → implement → review → archive lifecycle. Read that first, then branch based on use case: creation with [`/aitask-explore`](aitask-explore/), batch/remote with [`/aitask-pickrem`](aitask-pickrem/) or [`/aitask-pickweb`](aitask-pickweb/), review with [`/aitask-review`](aitask-review/) and [`/aitask-qa`](aitask-qa/).
```

**Out-of-bounds for this child:** editing the category-table descriptions or reordering. t594_4 owns that.

### 4. `concepts/_index.md` — annotate bullets with "(Main concepts)" / "(Reference)"

Current state: thematic groupings (Data model / Workflow primitives / Lifecycle and infrastructure). Per user direction, **keep the groupings** and add per-bullet markers using the wording **"Main concepts"** (not "Required reading") and **"Reference"**.

Mapping (derived from the plan's original required/reference split, re-bucketed by the user's "main concepts" framing):

- **Main concepts** (what a first-time reader needs): tasks, plans, parent/child, task-lifecycle, locks.
- **Reference** (consulted as needed): folded-tasks, review-guides, execution-profiles, verified-scores, agent-attribution, git-branching-model, ide-model, agent-memory.

Apply as parenthetical suffix on each bullet line, e.g.:

```markdown
- **[Tasks]({{< relref "/docs/concepts/tasks" >}})** *(Main concepts)* — Markdown files with YAML frontmatter, one per unit of work.
- **[Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}})** *(Reference)* — How related tasks are merged into a single primary task.
```

Use italicized parenthetical `*(Main concepts)*` / `*(Reference)*` — a lightweight visual cue that does not visually compete with the link text. Apply to every bullet under all three H2 groupings.

### 5. Install command verification (spot-check)

Sibling t594_2 byte-verified the curl command at `installation/_index.md:17`, `getting-started.md:17`, `installation/windows-wsl.md:43` against `install.sh:5`. Re-run the byte-equality check as a safety net — if drift has been introduced since 2026-04-19, flag it for follow-up rather than silently fixing (fix is out-of-scope for this child, but a drift would be worth a flag). Command:

```bash
grep -n "curl -fsSL" website/content/docs/installation/_index.md website/content/docs/getting-started.md website/content/docs/installation/windows-wsl.md install.sh
```

All four lines should have identical URLs.

### 6. "Tighten prose where redundant" (deferred)

The original plan item 6 said "Tighten overview/getting-started prose where redundant with Installation — keep self-contained completeness per conservative dedup stance." Sibling t594_2 already applied the conservative dedup stance (unified lead sentences for the "Run from project root" warning and the TUI switcher phrasing). Further dedup between overview ↔ getting-started ↔ installation would either:

- repeat what t594_2 already did, or
- violate "keep self-contained completeness".

**Decision:** drop this item from t594_3. If later review identifies specific passages worth tightening, handle in a targeted follow-up task.

## Authoritative sources

| Claim | Source of truth |
|---|---|
| Install curl command | `install.sh:5` |
| Project summary / "what is aitasks" | `CLAUDE.md` §"Project Overview" |
| Hub skill identity | `.claude/skills/aitask-pick/SKILL.md` |
| Canonical shared-wording decisions (TUI switcher, project root, fast profile) | Sibling t594_2 final implementation notes |
| Thematic grouping of `concepts/_index.md` | Current file state (preserved per user direction) |

## Implementation plan

1. **Read `install.sh:5`** and diff against the three website curl locations (item 5) — read-only spot check. If drift is found, log it for a follow-up task; do not fix.
2. **Add Next: footer to `docs/_index.md`** (item 1).
3. **Add intra-installation Next chain** (item 2) — four edits across `windows-wsl.md`, `terminal-setup.md`, `known-issues.md`, `git-remotes.md`. For `terminal-setup.md`, **preserve the existing `## Next steps` H2 list** and add the intra-chain `**Next:**` line below it.
4. **Add "Start here" callout to `skills/_index.md`** (item 3) — a single blockquote inserted between the lead paragraph and the existing multi-agent-support blockquote.
5. **Annotate `concepts/_index.md` bullets** with "(Main concepts)" / "(Reference)" markers (item 4) — touch every bullet line under the three H2 groupings, using italicized parenthetical `*(Main concepts)*` / `*(Reference)*` suffix.
6. **Hugo build check:** `cd website && hugo build --gc --minify` — must succeed with no new warnings.
7. **Click-through verification:** read each modified page's Next: link to confirm it resolves to an existing page.

## Verification

- `grep -c "^\*\*Next:\*\*" website/content/docs/_index.md` returns 1.
- `grep -l "^\*\*Next:\*\*" website/content/docs/installation/*.md` returns all four subfolder pages plus `_index.md`.
- `grep "Start here" website/content/docs/skills/_index.md` returns the new callout.
- `grep -c "(Main concepts)" website/content/docs/concepts/_index.md` returns 5 (tasks, plans, parent-child, task-lifecycle, locks).
- `grep -c "(Reference)" website/content/docs/concepts/_index.md` returns 0 (Reference markers removed per post-review request; only Main concepts markers retained — see Post-Review Changes).
- `grep -c "curl -fsSL" install.sh` — the URL line exists; `diff <(grep "curl -fsSL" install.sh) <(grep "curl -fsSL" website/content/docs/installation/_index.md)` — mismatch flagged if any.
- `cd website && hugo build --gc --minify` — 0 new warnings.
- Read the onboarding path cold: `_index.md` → `overview.md` → `installation/_index.md` → `getting-started.md` → `workflows/tmux-ide.md`. Each Next: link resolves and reads coherently as a first-time user flow.

## Verification Updates (2026-04-20)

Performed during plan verification under fast-profile `plan_preference_child: verify`. Changes from the pre-verification plan:

- **Premise drift:** Original plan claimed "no Next: pointers exist" — false. Many exist (added by t594_1 and t594_2). Scope narrowed to only the genuinely missing pointers.
- **Main reading sequence:** Plan proposed `overview → getting-started → installation → tmux-ide`. User chose to keep the existing sequence `overview → installation → getting-started → tmux-ide`. No existing main-path Next: line is rewired.
- **`concepts/_index.md` intro:** Plan proposed replacing thematic groupings with Required/Reference lists. User directed to keep the groupings and add per-bullet "(Main concepts)" / "(Reference)" markers using the wording "Main concepts" rather than "Required reading".
- **Item 6 (prose tightening):** Dropped — sibling t594_2 already applied the conservative dedup stance; further dedup would either duplicate t594_2 or violate self-contained completeness.
- **Scope of `skills/_index.md` edit:** Narrowed to the top "Start here" callout only. Category-table description polishing is explicitly reserved for t594_4.
- **Install-command check:** Demoted from "verify and fix" to "spot-check and flag" because t594_2 already byte-verified on 2026-04-19; a fix would be out-of-scope for this child.

## Notes for sibling tasks (t594_4, t594_5, t594_6)

- **`skills/_index.md`** now has a top "Start here" callout pointing at `/aitask-pick`. When t594_4 polishes category descriptions, leave the callout in place (it sits between the lead paragraph and the existing multi-agent support blockquote).
- **`concepts/_index.md`** bullets now carry `*(Main concepts)*` markers on the five foundational concepts (tasks, plans, parent-child, task-lifecycle, locks). Other bullets are left unmarked (per post-review, `*(Reference)*` marker was removed — absence of marker implies reference material). If t594_6 (concepts/commands/development) reorders or adds bullets, preserve the asymmetric marker pattern: mark new foundational concepts with `*(Main concepts)*`; leave reference-tier bullets unmarked.
- **Main reading sequence** is fixed as: `docs/_index → overview → installation → getting-started → workflows/tmux-ide`. Do not rewire.
- **Installation subfolder Next chain** is now: `_index → windows-wsl → terminal-setup → known-issues → git-remotes → (back to getting-started)`. If new installation pages are added, splice them by weight.

## Step 9 reference

No worktree (`create_worktree: false`). `verify_build` in `project_config.yaml` is null, so Hugo build verification is this task's responsibility (run before committing). Archive via `./.aitask-scripts/aitask_archive.sh 594_3` after Step 8 approval.

## Post-Review Changes

### Change Request 1 (2026-04-20)

- **Requested by user:** Remove `*(Reference)*` markers from `concepts/_index.md`; keep only `*(Main concepts)*` markers. Rationale: asymmetric marking (mark the foundational subset, leave the rest unmarked) gives the same visual signal with less noise, and avoids labelling every reference concept twice.
- **Changes made:** Stripped 8 `*(Reference)*` occurrences from `concepts/_index.md` (folded-tasks, review-guides, execution-profiles, verified-scores, agent-attribution, git-branching-model, ide-model, agent-memory). Retained the 5 `*(Main concepts)*` markers on tasks, plans, parent-child, task-lifecycle, locks. Thematic groupings (Data model / Workflow primitives / Lifecycle and infrastructure) preserved. Hugo rebuild: 148 pages, 0 warnings, 749 ms.
- **Files affected:** `website/content/docs/concepts/_index.md`, `aiplans/p594/p594_3_onboarding_flow_sweep.md` (verification-section and sibling-notes updated to reflect the asymmetric marker scheme).

### Follow-up tasks spawned

- **t594_7** (sibling under t594) — "Docsy labels support": proper Hugo/Docsy taxonomy infrastructure so labels like `main-concepts`, `experimental-feature` (for brainstorm/agent-crews/diffviewer), and `reference` can be applied site-wide and rendered as pills / filterable taxonomy pages. Will supersede the manual `*(Main concepts)*` marker pattern introduced here.
- **t600** (new parent task, not a sibling) — "Hugo/Docsy upgrade review": audit whether the pinned Hugo/Docsy versions (local and GitHub Actions release workflow) are worth upgrading; upgrade if release notes show material payoff.

## Final Implementation Notes

- **Actual work done:** 7 website files touched under `website/content/docs/`:
  - `_index.md` — added a `**Next:** [Overview]` footer (previously no Next pointer — the single genuinely missing main-path link).
  - `installation/windows-wsl.md`, `installation/terminal-setup.md`, `installation/known-issues.md`, `installation/git-remotes.md` — added intra-installation `**Next:**` chain per weight order (`_index → windows-wsl → terminal-setup → known-issues → git-remotes → back to getting-started`). `terminal-setup.md`'s existing `## Next steps` H2 list was preserved; the one-line Next footer was appended after it.
  - `skills/_index.md` — inserted a `> **Start here:** /aitask-pick is the hub skill...` callout between the lead paragraph and the existing `> **Multi-agent support:**` blockquote.
  - `concepts/_index.md` — annotated 5 bullets with `*(Main concepts)*` markers (tasks, plans, parent-child, task-lifecycle, locks). After post-review, the 8 `*(Reference)*` markers were stripped (asymmetric marker scheme per user direction).
- **Plan deviations:** All deviations are captured in the `Verification Updates (2026-04-20)` section above (verify-path corrections before implementation) and the `Post-Review Changes` section (change request 1, mid-review). Main deviations from the original plan:
  - Premise correction: the original "no Next: pointers exist" claim was obsolete; scope narrowed to the genuinely missing links.
  - Main reading sequence: kept existing (`overview → installation → getting-started → tmux-ide`) rather than rewiring to the plan's proposal.
  - Concepts intro: kept existing thematic groupings; added `*(Main concepts)*` markers only (asymmetric after post-review).
  - Prose tightening and `skills/_index.md` category-description polishing: dropped (covered by t594_2 / reserved for t594_4).
- **Issues encountered:**
  1. During Hugo build verification, the Bash working directory persisted to `website/` after `cd website && hugo build`. Subsequent `aitask_create.sh` invocations failed with "No such file or directory". Resolved by prefixing `cd /home/ddt/Work/aitasks &&` on the next shell call (same issue documented by t594_2).
- **Key decisions:**
  - Intra-installation Next chain placed as a **secondary navigation aid** — `installation/_index.md`'s existing `**Next:** Getting Started` pointer was left intact (main path), while the installation-deep-dive chain loops back to Getting Started from `git-remotes.md`.
  - `terminal-setup.md`'s existing multi-link `## Next steps` H2 list was preserved verbatim — the one-line `**Next:**` footer was appended below it. Reason: the H2 list gives readers who finish terminal setup three meaningful onward directions (Getting Started / tmux-ide / Monitor TUI), which is more useful than a single-link footer. The footer adds the intra-installation chain without erasing that value.
  - `concepts/_index.md` marker scheme ended up asymmetric (mark the 5 foundational concepts, leave everything else unmarked). Cleaner than labelling both buckets, and matches the user's intuition that "reference" is the unmarked default.
- **Notes for sibling tasks (t594_4, t594_5, t594_6, t594_7):**
  - **`skills/_index.md`** carries a top "Start here" callout pointing at `/aitask-pick`. t594_4: do not remove it when polishing category descriptions.
  - **`concepts/_index.md`** uses an asymmetric marker scheme: 5 `*(Main concepts)*` markers, reference bullets unmarked. t594_6: preserve the scheme when reorganizing; t594_7 will likely supersede these manual markers with taxonomy-driven rendering once Docsy labels are configured.
  - **Main reading sequence** is fixed as `docs/_index → overview → installation → getting-started → workflows/tmux-ide`. Future sweeps should not rewire it.
  - **Installation subfolder Next chain** is `_index → windows-wsl → terminal-setup → known-issues → git-remotes → (loops back to getting-started)`. Splice new installation pages by weight if added.
  - **Follow-ups spawned:** t594_7 (Docsy labels support — sibling), t600 (Hugo/Docsy upgrade review — new parent).
- **Build verification:** `cd website && hugo build --gc --minify` — 148 pages, 0 warnings, 749 ms.
