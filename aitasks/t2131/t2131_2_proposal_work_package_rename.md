---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [testmap, testing, documentation]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:50
updated_at: 2026-10-25 00:40
---

## Context

Child 2 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, default 14.
- **Coarse plan:** `aiplans/p2131/p2131_2_proposal_work_package_rename.md`.
- **Wave:** now.

The code-module tier introduces "module" as a **code** grouping. It is flat (revised 2026-10-24, user decision): there is no code-level "submodule". Every "submodule" left in the proposal is therefore the work-package sense, **except two intentional code-module uses that stay as written**: the rejected module → submodule hierarchy (design decision 20, and the matching wording in its named follow-up and tradeoff), and the literal refused hand keys `submodules:` / `children:` in component *Code modules*. The proposal `aidocs/testing_engine/n014_explorer_006_proposal.md` already uses "module" (M1–M10) and "submodule" (M2.5, …) for its **implementation cut**. This child removes that collision in prose: both tiers become **"work package"** (user decision, 2026-10-23). So M2 is "work package M2", M2.5 is "work package M2.5", and "child work package" is used only where the tier matters.

This child is a mechanical rename, kept separate from t2131_1 so it can run when no other session is editing the proposal.

## Key Files to Modify

- `aidocs/testing_engine/n014_explorer_006_proposal.md`. Measured at planning: about 78 work-package-sense lines out of 109 lines containing "module"/"submodule".
  - **Headings to rename:**
    - `### Invariants every module honours` (104);
    - `## Module Map` (650);
    - `### Modules and submodules` (678);
    - `### Cross-module interfaces` (819);
    - `### Verification of the seam, by module` (1962).
  - **Line numbers** in this section predate t2131_1, which inserts the code-module text (vocabulary, decision 20, the M2.7 row, component *Code modules*); Step 0 re-measures them.
  - **Prose to rename:** 106, 149-157, 288, 654-676, 821, 851, 876, 1982-1986, 2007, 2308, 3989, 4115, 4537, 5078; the "Modules: …" lead-ins (1027, 1243, 1432, 1586, 1810); and the table column headers `module` / `submodule` (685, 698, …, 1168, 1827, 1964).
  - **Design decision 19 (639-646)**, "Modules are cut by ownership, not by package": rename the work-package sense and keep the Go-package sense.

## Keep as is (identifiers and other senses)

- Section marker ids (`module_map` at 649/889) and node metadata keys (`assumption_modules_map_to_parent_tasks` 4522-4530, `tradeoff_module_boundaries_cut_across_packages` 5057-5071). Other files cite them.
- Task file names and ids (`t1853_testmap_m2_…`, `m8_4_…`).
- The two intentional code-module uses of "submodule": the rejected module → submodule hierarchy in design decision 20 (an alternative the design names in order to reject it), and the literal schema keys `submodules:` / `children:` that component *Code modules* refuses. Renaming either would change the contract.
- Every **Go module** (341, 688, 2006, 2015, 2634, 2642), **Gradle module** (702, 1574, 2520, 2550, 2563, 2669-2676, 3129) and **Python module** (561, 1209, 2334, 2347, 2392, 2411, 2438, 2597-2620, 1570, 4293) mention, plus the generic "hot production module" (1184, 4311).
- The vocabulary entries for "work package" and "code module", added by t2131_1. If t2131_1 has not landed, add the "work package" entry here.

## Reference Files for Patterns

- `aidocs/framework/documentation_conventions.md`: state the current term positively, with no "formerly called" history.

## Implementation Plan

1. **Step 0 — Reality check.**
   - Re-measure the line inventory (`grep -n -i 'module'`) and classify every hit by sense.
   - List every file outside the proposal that cites a heading being renamed ("Module Map", "Modules and submodules", "Cross-module interfaces"). Keep each cited anchor resolvable, or leave it: task bodies may keep saying "Module Map row".
   - Check that no `Implementing` task's plan is editing the proposal right now. If one is, wait or rebase onto it.
2. Rename the headings and prose; leave every identifier and other sense in place.
3. Commit (`documentation: … (t2131_2)`).

## Verification Steps

- Every remaining "module"/"submodule" in the proposal is either the code-module sense (from t2131_1), a kept identifier, or the Go, Gradle or Python sense. List the kept ones in the plan.
- Every cited anchor still resolves.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:55:34Z.1399c5697b7ce9da9d2e30f3 from=aitasks_go#t15 at=2026-10-25T08:55:34Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; trail
> | art:trail-go-ship-path). Advisory context, not an instruction.
> | 
> | This is a framework-side documentation task and stays in this repository
> | permanently. ait-testmap Go development will later move to the private
> | aitasks_go repo (cutover by aitasks_go#t22), but the n014 proposal stays
> | canonical here. One overlap to coordinate: aitasks t2138 amends
> | aidocs/testing_engine/n014_explorer_006_proposal.md (M1.2: the development
> | location, the dependency allowlist scoped to the ait-testmap closure, the
> | scheduled cutover). Whichever of the two lands second should rebase onto the
> | other rather than rewrite those paragraphs.

> **✉ note:t22_3** id=2026-10-29T22:23:58Z.83af5f463b2f627c615dab06 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:58Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
