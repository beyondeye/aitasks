---
Task: t2131_2_proposal_work_package_rename.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md, aitasks/t2131/t2131_3_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_2 — Proposal prose rename: modules → work packages (coarse)

## Context

- **Parent goal.** The code-module tier makes "module" / "submodule" mean
  **code** groupings.
- **This child.** It removes the collision with the proposal's implementation
  cut (M1–M10 and Mx.y) in prose. Both tiers become **"work package"** (user
  decision, 2026-10-23); "child work package" is used only where the tier
  matters. This is default 14.
- **Wave:** now. It is a mechanical change, timed so that no other session is
  editing the proposal.

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first:** not applicable. This is a documentation edit.

## Reading list

- Parent plan default 14.
- `aidocs/framework/documentation_conventions.md`: state the term positively,
  with no version history.
- The inventory measured at planning, main @ ee468201f: about 78
  work-package-sense lines out of 109 lines containing "module"/"submodule".

## Owned files / provides / consumes

- **Owns:** `aidocs/testing_engine/n014_explorer_006_proposal.md`, for this
  change.
- **Provides:** an unambiguous "module" for t2131_1's new component and for
  every later child.
- **Consumes:** nothing.

## Step 0 — Reality check

1. Re-run `grep -n -i 'module' aidocs/testing_engine/n014_explorer_006_proposal.md`.
   Classify each hit as one of:
   - the work-package sense;
   - the code-module sense (from t2131_1);
   - Go, Gradle or Python;
   - a generic file;
   - a kept identifier.
2. List every file outside the proposal that cites a heading being renamed
   ("Module Map", "Modules and submodules", "Cross-module interfaces"). Task
   bodies may keep saying "Module Map row"; anchor-based links must keep
   resolving.
3. Check that no `Implementing` task's plan is editing the proposal right now.
   If one is, wait or rebase onto it.
4. Record the outcome here.

## Implementation steps (coarse)

1. **Headings.**
   - `### Invariants every module honours`;
   - `## Module Map` → `## Work-Package Map`;
   - `### Modules and submodules` → `### Work packages`;
   - `### Cross-module interfaces`;
   - `### Verification of the seam, by module`.
2. **Prose and table column headers in the work-package sense.** Includes
   design decision 19's work-package sense; its Go-package sense stays.
3. **Keep as is:**
   - section marker ids (`module_map`);
   - node metadata keys (`assumption_modules_map_to_parent_tasks`,
     `tradeoff_module_boundaries_cut_across_packages`);
   - task names and ids;
   - the Go, Gradle and Python "module" senses;
   - "hot production module".
4. **Vocabulary.** If t2131_1 has not landed, add the "work package" entry
   here.
5. **Commit.** `documentation: Rename work-package prose in the test-map
   proposal (t2131_2)`.

## Verification / acceptance

- Every remaining "module"/"submodule" is either the code-module sense, a kept
  identifier, or the Go, Gradle or Python sense. List the kept identifiers in
  this plan.
- Every cited anchor resolves.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
