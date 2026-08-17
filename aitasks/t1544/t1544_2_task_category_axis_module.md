---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [reporting, metrics, python]
gates: [risk_evaluated]
anchor: 1544
created_at: 2026-08-17 22:04
updated_at: 2026-08-17 22:04
---

## Context

Second child of t1544 (backlog level + net flow by category in `ait stats`).
Parent plan: `aiplans/p1544_stats_backlog_and_net_flow_by_category.md`
(archived under `aiplans/archived/` once the parent closes).

t1544 needs one **category axis** that unifies two vocabularies — auto-spawned
follow-up kinds and ordinary issue types — so a backlog table can show
"risk mitigation / manual verification / upstream defect / … / Features /
Bug Fixes" as a single readable dimension.

This child delivers only that axis, plus the frontmatter-body split the
classifier needs. It touches **no renderer and no counter**, so it is a pure,
independently testable unit and lands before anything consumes it. It is
parallel with t1544_1 (no dependency either way).

## Deliverable 1 — `lib/task_category.py` (new, pure)

`resolve_category(metadata, body, filename) -> str` returns a **namespaced** key:

1. `kind:<k>` where `k` is `followup_kind` from frontmatter — `_unquote()`d,
   then clamped through `followup_kinds.followup_kind_field()`. A real kind
   wins; the `unknown` (absent) and `invalid` sentinels fall through.
2. otherwise `kind:<k>` where `k` is
   `followup_backfill_classify.classify(metadata, body, filename)["kind"]`,
   when that is not `None`.
3. otherwise `type:<issue_type>` — the task is genuine new work. Use
   `type:unknown` when `issue_type` is missing.

### Why namespaced rather than a flat string — do not "simplify" this away

`manual_verification` is a member of **both** vocabularies. A flat axis would
depend on the argument "classify()'s `manual_verification` rule fires on
`issue_type == 'manual_verification'`, so an MV task never reaches step 3" —
true today, but `aitasks/metadata/task_types.txt` is **user-extensible**, so a
user adding `docs_gap` or `review_finding` as an issue type would silently merge
two categories. The namespace removes the whole class of ambiguity and turns
display dispatch into a prefix check instead of a precedence rule.

It also protects existing output — see Deliverable 2.

### Rest of the public surface

- `category_display_name(cat) -> str` — prefix dispatch:
  `kind:` -> `followup_kinds.label_for()` (lowercase, e.g. `risk mitigation`);
  `type:` -> `type_display_name()` (Title Case, e.g. `Bug Fixes`).
  The case difference is what visually separates the two halves of the axis in
  the CLI table.
- `type_display_name(raw) -> str` — the issue-type display map, **moved here**
  from `aitask_stats.py::get_type_display_name`.
- `is_followup_category(cat) -> bool` — `cat.startswith("kind:")`. Drives the
  follow-up / genuine subtotal rows downstream.

### `_unquote()`

A single private helper: strips surrounding `'` / `"` and whitespace. It exists
**only** to compensate for the flat frontmatter scanner (which keeps quotes
verbatim, so `followup_kind: "carry_over"` would otherwise clamp to `invalid`).
Give it a comment saying exactly that, and that it is deleted when t1304
(consolidate the two `lib/` `parse_frontmatter` functions) lands. Measured:
**zero** quoted values exist in the corpus today, so this is purely defensive.

### Surface an invalid value, do not swallow it

When a **present but `invalid`** `followup_kind` falls through to `classify()`,
that must be *counted*, not silently absorbed — `followup_kind_field`'s own
docstring says a bad value that vanishes is indistinguishable from a task that
was never a follow-up. `resolve_category` therefore needs a way to report it.
Prefer an optional `tally: Optional[Counter] = None` parameter incremented with
`invalid_followup_kind`, so the caller (t1544_3) can fold it into
`backlog_excluded` without this module importing anything stateful. Zero today,
so it is a free tripwire.

## Deliverable 2 — `get_type_display_name` becomes a thin delegator

`aitask_stats.py::get_type_display_name` keeps its name and signature and
delegates to `task_category.type_display_name`. Its only caller
(`aitask_stats.py`, the `### By Task Type` section) and its tests are unaffected.

**This must be byte-identical, and there is a live trap.** The existing map has
**no entry** for `manual_verification` or `enhancement`, so today it renders
`Manual_verification` and `Enhancement` via `raw.capitalize()` (verified). If
`get_type_display_name` were pointed at a kind-first resolver, those rows would
silently become `manual verification`, breaking t1544's acceptance criterion
*"Existing stats output for the current categories is unchanged."* Delegating to
`type_display_name` — **not** to `category_display_name` — is what keeps it
exact. Assert this in a test.

## Deliverable 3 — `split_frontmatter` in `lib/stats_data.py`

`classify()` needs the task **body**, and `stats_data.parse_frontmatter` (the
flat scanner, ~:249) returns only a `Dict[str, str]`.

Add `split_frontmatter(content) -> Tuple[Dict[str, str], str]` that shares that
function's **exact** loop and returns `"\n".join(lines[i+1:])` at the `break`;
then make `parse_frontmatter` a thin caller that discards the body. One
boundary definition, zero behaviour change for existing callers.

**Do not** substring-split on `content.split('---', 2)[2]`, and **do not** switch
this path to `task_yaml.parse_frontmatter`:

- the substring split is data-dependent (it happens to agree on all 2246 files
  today, but the classifier's anti-false-positive guarantee rests on the body
  starting after the frontmatter *terminator*, which only the line scan knows);
- the YAML parser costs ~0.67s over the corpus versus the flat scanner's
  near-zero, and choosing between them is **t1304's** benchmark-gated decision.
  This task must not pre-empt it.

Measured during planning: `classify()` fed the flat parser's output versus
`task_yaml`'s typed output produced **0 disagreements** across the whole corpus,
and `classify`'s `_labels()` already branches on `isinstance(raw, str)` to
handle the flat `"[a, b]"` form.

## Deliverable 4 — a note for t1304

Per `aidocs/framework/planning_conventions.md` ("Dead code goes into the sibling
refactor task"), append one line to
`aitasks/t1304_consolidate_lib_frontmatter_parsers.md` under
`## Notes for sibling tasks` (create the heading if absent), naming
`lib/stats_data.py`'s `parse_frontmatter` / new `split_frontmatter` pair and
`lib/task_category.py::_unquote`, so t1304 collapses all of them together.
t1304 is `status: Ready`, so no sequencing gate is needed. Commit that file with
`./ait git`, separately from the code.

## Key files to modify

- `.aitask-scripts/lib/task_category.py` — **new**
- `.aitask-scripts/lib/stats_data.py` — add `split_frontmatter`, refactor
  `parse_frontmatter` to call it
- `.aitask-scripts/aitask_stats.py` — `get_type_display_name` -> delegator
- `tests/test_task_category.py` — **new**
- `aitasks/t1304_consolidate_lib_frontmatter_parsers.md` — one-line note
  (`./ait git`)

## Reference files for patterns

- `.aitask-scripts/lib/followup_kinds.py` — `FOLLOWUP_KINDS`,
  `followup_kind_field()` (the clamp: real kind | `unknown` | `invalid`),
  `label_for()`.
- `.aitask-scripts/lib/followup_backfill_classify.py` — `classify()`,
  `RULE_ORDER`, `_labels()`. Pure: no writes, no git, no subprocess.
- `.aitask-scripts/lib/work_report_gather.py` — the house precedent for clamping
  a vocabulary once at the read boundary (`followup_kind_field` on its
  `TaskRow`). Mirror it rather than writing a second clamping rule.
- `.aitask-scripts/lib/stats_data.py` — the module docstring declares its
  base-layer import set; update it when adding `task_category` as a sibling.
  `tests/test_no_lib_to_tui_import.sh` freezes the lib -> TUI direction.
- `tests/test_followup_backfill_classify.py` — plain unittest, no tempdirs; the
  closest style model for `tests/test_task_category.py`.

## Verification steps

```bash
bash tests/run_all_python_tests.sh --test-dir tests
bash tests/test_no_lib_to_tui_import.sh
./ait stats | diff - <(git stash && ./ait stats; git stash pop)   # or simply:
./ait stats > /tmp/after.txt   # compare against a pre-change capture,
                               # ignoring the `Generated:` line
```

`tests/test_task_category.py` must cover:

- **precedence** — a task with an explicit `followup_kind` beats a body that
  would classify differently; a body-only prose rule (no `followup_kind:` field)
  resolves via `classify()`; a plain task resolves to `type:<issue_type>`;
- **namespacing** — an `issue_type: manual_verification` task and a
  `followup_kind: manual_verification` task both resolve to
  `kind:manual_verification`, and a hypothetical user-defined
  `issue_type: review_finding` resolves to `type:review_finding`, **not**
  `kind:review_finding`;
- **unquote / clamp** — `"carry_over"` with literal quotes resolves to
  `kind:carry_over`; a trailing-space value works; a bogus value falls through
  **and** increments the `invalid_followup_kind` tally;
- **`split_frontmatter`** — a normal file; a file with **no** frontmatter at all
  (3 real archived tasks are like this: `t20`, `t21`, `t22`); an
  **unterminated** frontmatter block; a `---` line inside the body;
- **byte-identity** — `get_type_display_name("manual_verification") ==
  "Manual_verification"` and `get_type_display_name("enhancement") ==
  "Enhancement"`, i.e. the delegation changed nothing.

**Test-collection constraint:** `tests/test_collection_parity.py` enforces
unittest-count == pytest-count per module and specifically flags the
`def test_x(arg)` fixture-arg trap. `tests/test_task_category.py` must expose
only `unittest.TestCase` methods — no module-level `test_*(arg)` helper.

**Path resolution:** `lib/` modules are imported via a `sys.path` bootstrap, and
the stats data layer resolves task paths from the **process cwd**. Import
`task_category` the way the sibling tests do, and do not assume a cwd.
