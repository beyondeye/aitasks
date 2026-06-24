---
Task: t929_3_brainstorm_tui_code_verified_docs.md
Parent Task: aitasks/t929_brainstorm_decompose_prompt_iterate_carveout_and_docs.md
Sibling Tasks: aitasks/t929/t929_1_module_decompose_iterate_before_apply.md, aitasks/t929/t929_2_module_decompose_prompt_driven_inference.md
Archived Sibling Plans: aiplans/archived/p929/p929_1_*.md, aiplans/archived/p929/p929_2_*.md
Worktree: (none — profile 'fast' works on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-24 16:12
---

# t929_3 — Code-verified `ait brainstorm` TUI docs (incorporates folded t776)

## Context

The `ait brainstorm` TUI has **no website docs**: `website/content/docs/tuis/_index.md:24`
lists it with "Dedicated documentation is pending" — the only TUI without a page link.
`aidocs/brainstorming/` is design/architecture only. This task (last child of t929,
incorporating folded t776) writes a **code-verified** user guide mirroring the existing
per-TUI pages, and updates the TUI index to link it.

The original task body / pre-existing plan were authored against an **old** brainstorm
codebase and are stale: they list operations (`hybridize`, `detail`, `patch`) and DAG
footer keys (`j Next  k Prev …`) that **no longer exist** after the t983_* / t1018_*
refactors. A fresh code-verification pass (this session) established the current reality
below. **Recording that the task body's own assumptions were stale is itself the
"design-vs-implementation divergence" deliverable.** The docs are written from the verified
facts, not the stale plan bullets.

## Verified current state (read from code this session)

Sources: `.aitask-scripts/brainstorm/{brainstorm_app.py,brainstorm_dag_display.py,constants.py,
widgets.py,modals.py,brainstorm_op_refs.py,brainstorm_crew.py}`, `aitask_brainstorm_tui.sh`,
`aitask_brainstorm_init.sh`.

- **Launch.** `ait brainstorm <task_num>` (single positional arg; `brainstorm_app.py:5651`).
  Session init is a separate subcommand: `ait brainstorm init <task_num> [--proposal-file <path>]`
  (`aitask_brainstorm_init.sh:29-38`) — `--proposal-file` seeds the session from a markdown
  file via the initializer agent.
- **Design operations** (`constants.py:70-77`, the `A` → Operations dialog menu):
  `explore` (variants from a base node), `compare` (agent comparison across marked nodes),
  `synthesize` (merge nodes into a synthesis), `module_decompose`, `module_merge`,
  `module_sync`. **There is no `hybridize`/`detail`/`patch`** (`synthesize` is the current
  merge op; `hybridize` survives only as a legacy color alias). `bootstrap` is the
  root/initializer origin (dim badge), not a user-launched op.
- **Session-lifecycle operations** (`constants.py:80-85`, the Session tab):
  pause / resume / finalize (export HEAD proposal to `aiplans/`) / archive / delete.
- **Tabs / layout** (`brainstorm_app.py` BINDINGS `2044-2074`, compose `2239-2293`):
  - **Browse** (`b`) — left/center `DAGDisplay` graph **or** list view (toggle with `v`;
    `d`=Browse-as-list, `g`=Browse-as-graph muscle-memory aliases); right **detail pane**
    (session status, module status, marked-node list, `NodeDetailPanel`). The "dashboard"
    in old docs = this Browse detail pane.
  - **Session** (`s`) — lifecycle op rows.
  - **Running** (`r`) — live agent/group status (renamed from "Status").
  - The old **Compare tab** and **Actions/`a` tab** are **gone**: `c` opens a dimension-matrix
    overlay on the marked set; `A` opens the Operations dialog.
  - `space` marks a node; `f` toggles module "deferred".
- **DAG view** (`brainstorm_dag_display.py`):
  - 5-row node box (`NODE_ROWS = 5`: top border, title+mark checkbox, op badge, description,
    bottom border) — `dag_display.py:46`.
  - DAG-focus keys (`dag_display.py:468-479`): `↑/↓` layer, `←/→` column, `enter` Open,
    `h` Set HEAD, `o` Operation, `p` Proposal, `x` Compare-with. **Arrow keys, not `j/k`.**
  - **Operation-color legend** (`OP_BADGE_STYLES`, `dag_display.py:68-77`):
    cyan=explore, yellow=compare, magenta=synthesize, green=module_decompose,
    orange=module_merge, purple=module_sync, dim=bootstrap. (Red `#FF5555` is the
    `deferred` **module-status** overlay, `MODULE_STATUS_STYLES:83-90`, not an op color.)
- **Module decompose** (`brainstorm_app.py:1479-1535`) — launched via `A` on a node →
  Operations dialog → "Module Decompose":
  - **3-way RadioSet mode** (`rs_decompose_mode`, `1514-1520`): *Manual — I type the names* /
    *Agent-proposed — infer from the Plan* (t929_2) / *From section markers*. (Verified.)
  - **Review-before-apply gate** (t929_1): "Review before apply" checkbox default **on**
    (`1528-1532`); on completion the proposal opens in `ModulePreviewScreen`
    (`modals.py:1412-1488`) with **Accept / Re-run (steer) / Cancel**. Re-run collects a
    free-text steer that **overrides** the original Decomposition Plan on conflict (later
    revisions win) — see `aiplans/archived/p929/p929_1_*.md`.
  - **Fast-track preset** pre-arms "Create linked child tasks" (`1524`). Semantics:
    **decompose forks, never prunes** — the umbrella proposal stays whole; **module_merge**
    is the convergent path back. Document this as a deliberate design note.
- **Operation provenance UI:**
  - Dashboard detail "**Generated by**" block (operation + group + agents + when;
    `widgets.py:524-578`).
  - `o` on a focused node → `OperationDetailScreen` (`modals.py:851-950`): **Overview** tab +
    one **Input / Output / Log** tab group per agent.
  - `OpDataRef` primitive (`brainstorm_op_refs.py:35`) — frozen `(kind, target, section)`
    pointer to on-disk op data (no duplication in `br_groups.yaml`).

## Implementation steps

1. **Read conventions** — `aidocs/framework/documentation_conventions.md` (current-state-only,
   no version history in body, say "autonomous", genericize agent names, generic placeholder
   project names, no "sister" wording). Pattern-match `board/_index.md` +
   `codebrowser/_index.md` for the heading shape. *(Already done this session.)*

2. **Write `website/content/docs/tuis/brainstorm/_index.md`** — single comprehensive page
   (the full-tier `how-to.md`/`reference.md` split is **deferred** as optional follow-up;
   brainstorm is still `stabilizing`, so over-documenting keybinding tables now would go
   stale). Frontmatter: `title: "Brainstorm"`, `linkTitle: "Brainstorm"`, `weight: 25`
   (between codebrowser=20 and settings=30), `maturity: [stabilizing]`, `depth: [intermediate]`.
   Body, all verified against code:
   - Lead paragraph: `ait brainstorm`, Textual link, one-line "what it's for" (graph-structured
     design exploration that finalizes to an `aiplans/` proposal).
   - `> Customizable keys` callout (matches board/codebrowser) — keys are rebindable via `?`.
   - `## Tutorial` with `### Launching` (`ait brainstorm <task_num>`; `init … --proposal-file`),
     `### Understanding the Layout` (Browse / Session / Running tabs; Browse graph⇄list `v`;
     detail pane), `### The DAG view` (5-row node box, arrow-key navigation, the
     verified color legend as a list, `enter`/`h`/`o`/`p`/`x`), `### Operations`
     (explore/compare/synthesize + the module ops, each one line + which agent it spawns,
     from `_WIZARD_OP_TO_AGENT_TYPE`), `### Module decompose` (the 3 modes, the
     review/steer/accept gate, fast-track, and the **fork-not-prune** design note with
     module_merge as the convergent path), `### Operation provenance` (Generated-by block,
     `o`, OperationDetailScreen tabs, OpDataRef), `### Session lifecycle`
     (pause/resume/finalize/archive/delete).
   - Use `<!-- SCREENSHOT: … -->` HTML-comment placeholders (as board does for un-captured
     shots) rather than referencing non-existent SVGs.
   - Closing `**Next:**` nav line.
   - **Re-read each BINDINGS / color / op value at write time** and quote it verbatim — do
     not transcribe from this plan; the plan is a map, the code is the source of truth.

3. **Update the TUI index** — `website/content/docs/tuis/_index.md:24`: change the plain
   `**Brainstorm** (`ait brainstorm`) — … Dedicated documentation is pending.` bullet to a
   linked `**[Brainstorm](brainstorm/)** (`ait brainstorm`) — …` matching the other bullets,
   dropping the "pending" sentence. (Sidebar auto-builds from `weight`; only this hand-curated
   bullet needs the manual edit.)

4. **Record divergences** — include a short note in the page (current-state-positive, per
   conventions — frame as "how it works", not "it used to be X") and, more explicitly, in the
   plan's Final Implementation Notes: the stale `hybridize`/`detail`/`patch` ops and `j/k`
   footer from the task body do not exist; `synthesize` + arrow-key nav are the reality.

## Verification

1. `cd website && ./serve.sh` → browse `/docs/tuis/brainstorm/`; page renders; nav shows it
   under TUIs at the expected position.
2. `/docs/tuis/` brainstorm bullet links `brainstorm/` and no longer says "pending".
3. Cross-check every documented key/op/color against the cited `brainstorm_app.py` /
   `brainstorm_dag_display.py` / `constants.py` lines (done during writing; re-grep to confirm).
4. `hugo build --gc --minify` (in `website/`) succeeds with no broken-ref errors.

See parent task **Step 9 (Post-Implementation)** for cleanup, archival, merge.

## Notes for sibling tasks

- Last child of t929; on archival the parent t929 archives too (folded t776 is deleted).

## Risk

### Code-health risk: low
- No source code changes — only new markdown under `website/content/docs/tuis/brainstorm/`
  plus a one-line bullet edit in `tuis/_index.md`. Blast radius is the docs site only;
  worst case is a broken Hugo ref, caught by the `hugo build` verification step.

### Goal-achievement risk: low
- The dominant risk for a "code-verified" doc is documenting stale/incorrect behavior — which
  already bit the inherited plan. Mitigated: every op/key/color/layout fact was re-read from
  the current source this session (file:line cited above), the writer re-quotes from code at
  write time, and `hugo build` + a manual `./serve.sh` render gate the result. The deferral of
  the `how-to.md`/`reference.md` split is a deliberate scope choice (stabilizing TUI), logged
  here so it is an explicit decision, not a silent omission.

### Planned mitigations
- None — risks are low on both axes and covered in-plan by the verification step.
