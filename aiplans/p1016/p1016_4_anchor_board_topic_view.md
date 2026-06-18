---
Task: t1016_4_anchor_board_topic_view.md
Parent Task: aitasks/t1016_anchor_task_topic_grouping.md
Sibling Tasks: aitasks/t1016/t1016_1_*.md, aitasks/t1016/t1016_2_*.md, aitasks/t1016/t1016_3_*.md
Archived Sibling Plans: aiplans/archived/p1016/p1016_*_*.md
Worktree: aiwork/t1016_4_anchor_board_topic_view
Branch: aitask/t1016_4_anchor_board_topic_view
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-18 16:44
---

# Plan — t1016_4 Board: anchor field + by-topic view

## Context

Final **code** child of t1016 (anchor task topic grouping). t1016_1 (landed)
added the `anchor` frontmatter field + `aitask_create.sh --anchor/--followup-of`
+ `aitask_update.sh --anchor` + the `merge_frontmatter` newer-wins rule;
t1016_2 (landed) consolidated the docs; t1016_3 (landed) wired `--followup-of`
into the framework's follow-up spawn sites so carryover / mitigation /
verification follow-ups now carry an `anchor:` line pointing at their topic root.

This child surfaces `anchor` on the board — **where tasks are picked** — by
adding (1) a group-by-anchor **"by-topic"** base view modeled on the existing
**inflight** alternate-layout view, and (2) an **editable anchor field** in the
task detail screen. It also ships the board-reference doc **row** and the headless
board test. After it lands, only the manual-verification sibling t1016_5 remains,
and t1016 archives automatically.

**Scope boundary — narrative website docs are a separate follow-up.** The two
website touches in the t1016 family are both single table rows: t1016_2 added the
`anchor` schema-field row (`docs/development/task-format.md`); this child adds the
board `by-topic` base-filter row (`docs/tuis/board/reference.md`). Neither writes
a *narrative* user-facing page explaining the anchor / topic-grouping concept
(`--followup-of` / `--anchor`, the flatten-to-root inheritance rule, when to use
vs parent-child / `depends` / `labels`, and the by-topic board workflow). Per the
planning decision, that page is a **standalone `--followup-of 1016` documentation
task** (NOT in this child's scope, NOT a child of t1016 — so it does not block
t1016's archival; it stays anchored to the archived root 1016, dogfooding the
"archived anchor root is a stable group key" case). It is created right after
plan approval, before implementation of this child begins — see **Pre-impl
follow-up** below.

## Pre-impl follow-up (standalone website-docs task)

Immediately after this plan is approved (Step 7, before implementing the board
view), create the standalone narrative-docs task, anchored to t1016:

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --name document_anchor_topic_grouping \
  --type documentation --priority medium --effort medium \
  --followup-of 1016 \
  --desc "<narrative-docs scope below>" --commit
```

Scope to capture in its description: a new user-facing page under
`website/content/docs/workflows/` covering the anchor concept — `--followup-of` /
`--anchor` flags, the flattened-to-root inheritance rule (child auto-inherit;
follow-up never chains; mutual exclusion with `--parent`), anchor vs
parent-child / `depends` / `labels`, and the board by-topic view workflow — plus
the **hand-curated `workflows/_index.md` bullet** the new page requires, and
cross-links from `docs/development/task-format.md` and `docs/tuis/board/reference.md`.
(`--followup-of 1016` sets `anchor: 1016` since t1016 is a root with no anchor.)

**Verified against current code (2026-06-18, verify path):**
- `aitask_update.sh --anchor` exists (help L191, batch parse L301, read L478,
  process L1761-1765, `normalize_anchor_id` validate L1959-1963) — the
  persistence dependency is met.
- `merge_frontmatter` already resolves scalar `anchor` (newer `updated_at` wins);
  `tests/test_aitask_merge.py` L136-150 covers it — **no merge work in this child.**
- All inflight-view precedent pieces in `aitask_board.py` are present at the
  refreshed line numbers listed under **Reference points** below.
- The new-frontmatter-field checklist
  (`aidocs/framework/aitasks_extension_points.md` L19-22) **mandates** the board
  pattern used here: add a `<FieldName>Field` mirroring `DependsField` /
  `ChildrenField`, wire it into `TaskDetailScreen.compose()`, and have it
  **shell out to `aitask_update.sh --batch … --<flag>`**.

## Key design rules (resolved during planning, unchanged)

- **`topic_key`(task)** = `anchor` if set; **elif the task is a child → its
  parent's topic_key** (= parent.anchor or parent id) — a *display-time* fallback
  so legacy parent+children trees cluster with **NO file migration**; else the
  task's own id. (The child→parent fallback is intentional: legacy children have
  no `anchor:` line; this is what lets them group.)
- **Grouping rule:** bucket all tasks by `topic_key`. A bucket of **size ≥ 2**
  becomes a topic lane (label = title of the task whose own-id == key; if that
  task is archived/absent, fall back to the id or first member's title — the id
  stays a stable lane key). **Singleton buckets collapse into one "Ungrouped"
  lane.** Avoids both a lane-per-root and hidden roots.
- **Editable anchor persists via** `aitask_update.sh --batch <id> --anchor <val>`
  (task-id field shells out, per the extension-points mandate — NOT the
  `CycleField` → `save_with_timestamp` path).
- Defer a "re-anchor whole group" action (out of v1).

## Reference points (current line numbers — refreshed on verify path)

`task_yaml.py`:
- `_normalize_task_ids` **L51-66** (list version: t-prefix `^\d+_\d+$` child ids,
  preserve parent ints / already-`t` ids) — write the **scalar analog**.
- `parse_frontmatter` **L69-90** (normalizes `depends`/`children_to_implement`/
  `folded_tasks` at L85-88 — add `anchor`).
- `BOARD_KEYS` **L44** = `("boardcol","boardidx")` — keep `anchor` OUT (semantic,
  not layout).

`aitask_board.py` (inflight precedent to model on):
- `ViewSelector.BASES` **L906-911** — list of `(action_id, label, target_id)`.
- binding `i` **L4214**; `action_view_inflight` **L4655-4656**.
- `_set_base_filter` **L4697-4728** (inflight reload branch **L4718-4720**).
- `refresh_board` inflight re-bucket + early-return branch **L4402-4411**.
- `InFlightColumn` **L1186-1226** (VerticalScroll; TITLES/COLORS; compose; on_mount).
- `InFlightTaskCard` **L1153-1183** (extends `TaskCard`; `_priority_border_color`
  override **L1178-1183**).
- `apply_filter` inflight branch **L4514-4541** (sentinel `visible=None` →
  always-visible **L4516-4517**).
- Detail-screen task-id fields: `DependsField` **L1443-1509**, `ChildrenField`
  **L1652-1707**, `FoldedTasksField` **L1710-1775** (this one **shells out** via
  `subprocess.run([... aitask_update.sh, --batch, …])` at **L1765** — the closest
  *editable-scalar-shells-out* model; child/dep edit shell-outs are at
  **L6144 / L6224 / L6234**).
- Priority-border infra on `TaskCard`: `_priority_border_color` **L1116-1120**,
  `_idle_border_style` **L1122-1123**, `on_mount` **L1125-1131**, `on_blur`
  **L1137-1138**.

## Steps

1. **`task_yaml.py`** — add scalar `anchor` normalization in `parse_frontmatter`
   (a `_normalize_task_id` scalar analog of `_normalize_task_ids`: t-prefix a
   bare `^\d+_\d+$` child id, preserve a bare parent int and an already-`t` id;
   pass through empty/absent). Apply it alongside the L85-88 list normalizations.
   Keep `anchor` OUT of `BOARD_KEYS`.

2. **`aitask_board.py` — pure core (keep import-testable, no widget deps):**
   - `topic_key(task)` with the `anchor → child-parent fallback → own-id` rule.
   - `group_tasks_by_topic(tasks)` → ordered `[(label, [tasks])]` lanes per the
     grouping rule, with singletons folded into a trailing `"Ungrouped"` lane.
     Resolve a lane label from the task whose own-id == key, falling back to id /
     first member's title for an archived/absent root.

3. **`aitask_board.py` — by-topic base view (mirror inflight at every site):**
   - `ViewSelector.BASES`: add `("view_bytopic", "By-Topic", "bytopic")`.
   - Binding `y` + `action_view_bytopic` → `_set_base_filter("bytopic")`.
   - `_set_base_filter`: add a `bytopic` branch (reload like inflight if the
     grouping needs fresh on-disk anchors).
   - `refresh_board`: add a `bytopic` early-return branch that builds
     `TopicColumn`s from `group_tasks_by_topic(...)`, then
     `call_after_refresh(self.apply_filter)` (+ refocus), mirroring L4402-4411.
   - `TopicColumn` (model on `InFlightColumn`): header = lane label, one
     `TaskCard`/`TopicTaskCard` per member.
   - Optional `TopicTaskCard` (extends `TaskCard`) overriding
     `_priority_border_color` for a per-topic border (reuse priority-border infra)
     — keep optional; plain `TaskCard` is acceptable for v1 if borders add noise.
   - `apply_filter`: add a `bytopic` branch (all eligible cards visible, then
     search filter applies — same shape as the inflight `visible=None` sentinel).

4. **`aitask_board.py` — editable `AnchorField`:** add an `AnchorField`
   (structure mirrors `DependsField`; **persistence mirrors `FoldedTasksField`'s
   `subprocess.run` shell-out**) to `TaskDetailScreen.compose()`. On edit, run
   `./.aitask-scripts/aitask_update.sh --batch <id> --anchor <val>` (empty value
   clears), then reload the task/detail screen so the new value renders.

5. **`website/content/docs/tuis/board/reference.md`** — add a `By-Topic` row
   (key `y`, selector label `y By-Topic`) to the Base filters table at L136-143,
   matching the existing `In-Flight` row format exactly.

## Verification

- **`tests/test_board_topic_group.py`** (new, pure — no widgets): a root + its
  `--followup-of` followups + inherited children cluster in one lane; a LEGACY
  anchorless child groups with its parent via the fallback; an anchorless
  singleton → "Ungrouped"; an archived/absent root id remains a stable lane key.
- **`tests/test_board_topic_view.py`** (new, headless pilot — mirror
  `tests/test_board_view_filter.py`: `REPO_ROOT` sys.path insert for `board/` +
  `lib/`, `setUpClass` chdir-to-REPO_ROOT then import, `app.run_test(size=(160,48))`,
  `pilot.press("y")` + double `pilot.pause()`, assert `TopicColumn`s render and
  `apply_filter` hides non-matching `TaskCard`s under search via `styles.display`).
- **`task_yaml.py` scalar-normalization unit test** — add a small dedicated test
  (no existing `parse_frontmatter`/normalization test exists to extend).
- Run **`bash tests/run_all_python_tests.sh`** (auto-globs `test_*.py`; PYTHONPATH
  already includes `board/` + `lib/` — the two new files are auto-discovered).
- Live multi-screen UX (visual grouping, detail-edit round-trip, archived-root
  rendering) → covered by the aggregate manual-verification sibling **t1016_5**,
  not this child.

## Risk

### Code-health risk: medium
- `aitask_board.py` is a large (~6440-line) load-bearing TUI; the by-topic view
  threads through ~6 insertion points (BASES, binding, action, `_set_base_filter`,
  `refresh_board`, `apply_filter`) plus new `TopicColumn`/`TopicTaskCard` and an
  editable `AnchorField` — surface area for an integration/wiring bug. Each change
  is **additive** and mirrors the recently-landed inflight precedent (t635_9 /
  t1024) one-to-one. · severity: medium · → mitigation: in-task headless-pilot
  test (`test_board_topic_view.py`) exercising the real `y` keypress + render +
  search-filter path, plus the pure-core unit test.
- The pure/widget split is the maintainability lever: if grouping logic leaks into
  widgets it becomes untestable. · severity: low · → mitigation:
  `group_tasks_by_topic` / `topic_key` kept import-testable (no widget deps),
  unit-tested in isolation (`test_board_topic_group.py`).
- Scalar `anchor` normalization in `parse_frontmatter` runs on every board load. ·
  severity: low · → mitigation: dedicated scalar-normalization test; logic is a
  thin analog of the proven `_normalize_task_ids`.

### Goal-achievement risk: low
- None identified. Approach verified against current code on the verify path:
  inflight precedent present at refreshed line numbers; the persistence dependency
  (`aitask_update.sh --anchor`) and merge rule already landed in t1016_1; all
  sibling spawn-site anchors landed in t1016_3; the parent AC (editable anchor
  persists + by-anchor grouping view clustering root+subtree+followups) is fully
  covered. The only deferred surface (live multi-screen UX) is explicitly owned by
  t1016_5, not a gap.

(No `### Planned mitigations` — the medium code-health risk is fully mitigated
in-task by the testability-first design; a separate before/after task would be
redundant, consistent with landed siblings p1016_1 / p1016_2 / p1016_3.)

## Post-Implementation
Step 9 applies on completion. This is the last **code** child — before archival,
verify the parent's `children_to_implement` (currently `[t1016_4, t1016_5]`); the
parent archives automatically only when that list empties, so t1016 will **not**
auto-archive here (t1016_5 manual verification remains). Record in Final
Implementation Notes the final keybinding chosen (`y`), any inflight-view
divergences, whether `TopicTaskCard` borders were kept or dropped, and notes for
t1016_5.
