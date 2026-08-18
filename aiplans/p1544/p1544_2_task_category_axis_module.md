---
Task: t1544_2_task_category_axis_module.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_3_backlog_flow_collection.md, aitasks/t1544/t1544_4_cli_backlog_sections_and_csv.md, aitasks/t1544/t1544_5_stats_tui_backlog_panes.md, aitasks/t1544/t1544_6_backlog_stats_documentation.md, aitasks/t1544/t1544_7_manual_verification_stats_backlog.md, aitasks/t1544/t1544_8_backlog_stats_retrospective.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_1_session_discovery_dedupe.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-18 22:09
---

# p1544_2 — Category axis module

## Context

`ait stats` today answers "how much did we complete?" but not "how much is
outstanding, of what kind, and is it growing faster than we burn it down?".
Parent t1544 adds a backlog-level and net-flow dimension to answer that, split
by a **category axis** that unifies two vocabularies — auto-spawned follow-up
kinds (`risk_mitigation`, `manual_verification`, `upstream_defect`, …) and
ordinary issue types (`bug`, `feature`, …).

This child delivers **only that axis**, plus the frontmatter/body split the
retro-classifier needs. It touches no renderer and no counter, so it is a pure,
independently testable unit that lands before anything consumes it. It is
parallel with t1544_1 (already archived); t1544_3/_4/_5 consume it.

## Verification pass (2026-08-18)

Re-verified against live source before implementation. The plan is sound; three
findings refine it. Each is evidence-backed and is the single rationale for its
point.

### Finding 1 — the byte-identity trap is real and visible in live output

`./ait stats` right now prints:

```
| Enhancement    | 19    | 6   | 8   | 4   | 1         |
| Manual_verification | 29    | 10  | 8   | 8   | 3         |
```

Confirmed: the display map has no entry for either, so both render through the
`raw.capitalize()` fallback. Delegating `get_type_display_name` to
`category_display_name` would turn the second into `manual verification` and
break the parent's "existing stats output unchanged" criterion. Delegation
target is `type_display_name`. Step 7 and its test stand as written.

`get_type_display_name` has exactly **one** Python caller
(`aitask_stats.py:365`), so the delegation blast radius is that one row set.

### Finding 2 — the `_unquote` rationale is stronger than "defensive"

Measured on the current corpus: **442 live tasks + 1844 archived, zero quoted
`followup_kind` or `issue_type` values.** So `_unquote` is indeed dead-defensive
today, as the plan says.

But there is a nearby helper that must **not** be reused for it:
`followup_backfill_classify._norm_scalar` (:184) does `strip().strip("'\"")`
*and then strips a leading `t` from id-shaped strings*. It is an **identity-key
canonicalizer for task ids**, not a general unquoter. Reusing it for a
vocabulary key would silently mangle any future kind that looked id-ish. Keep
`_unquote` local and private to `task_category.py`, and say *this* in its
comment alongside the flat-scanner reason — a local private `_unquote` is
already the house pattern (`agent_launch_utils.py` has three).

### Finding 3 — `label_for()` is **not** uniformly lowercase

Plan step 5 justifies the display split as "`kind:` → lowercase, `type:` → Title
Case, and the case difference is what visually separates the two halves of the
axis". The vocabulary table does not support that as a rule:

```python
"manual_verification":  ("◇", "cyan",    "manual verification"),
"risk_mitigation":      ("▲", "yellow",  "risk mitigation"),
"carry_over":           ("↻", "cyan",    "carry-over"),      # hyphen, not space
"qa_test_gap":          ("◐", "magenta", "QA test gap"),     # capitalised
```

`QA test gap` is capitalised and `carry-over` is hyphenated. Keep the dispatch
as designed — `label_for` is the single source of truth for these strings and
must not be re-cased here — but **demote the rationale**: the namespace prefix,
not the casing, is what separates the halves. Do not write a test asserting a
uniform lowercase shape (it fails on `QA test gap`), and tell t1544_4 the same.

Also: `label_for` returns `""` for an unrecognised kind. `resolve_category` only
emits `kind:<k>` for values that passed the vocabulary clamp or came from
`RULE_ORDER`, so that path should be unreachable — but `category_display_name`
should still fall back to the bare `<k>` rather than render an empty cell.

### Finding 4 — the `split_frontmatter` test corpus is richer than stated

The plan says "a file with **no** frontmatter at all (`t20`, `t21`, `t22` are
real examples)". Measured across all 2286 task files, only **three** are
irregular, and they are **three different shapes**, not one:

| file | first line | shape |
|---|---|---|
| `t20_skill_creating_aitask.md` | `there is already a skill…` | genuinely no frontmatter |
| `t21_rewrite_aitask_create_as_script.md` | `--- effort:med pri:med` | **pseudo-delimiter** — starts with `---` but is not `---`; plus a bare `---` later in the body |
| `t22_task_attributes_in_task_create.md` | `--- effort:med pri:hi` | same |

Every other live and archived task starts with an exact `---`.

This *strengthens* the plan's rejection of the substring split: on t21/t22,
`content.split('---', 2)[2]` splits on the leading pseudo-delimiter and returns
garbage, whereas the line scan correctly reports "no frontmatter". Use all three
shapes as distinct test cases rather than three instances of one.

### Finding 5 — the extraction must preserve a stripped/unstripped asymmetry

The existing loop breaks on `stripped == "---"` but splits the **unstripped**
line:

```python
for line in lines[1:]:
    stripped = line.strip()
    if stripped == "---":
        break
    if ":" not in line:
        continue
    key, value = line.split(":", 1)
    result[key.strip()] = value.strip()
```

An "obvious" tidy-up to `stripped` throughout would change behaviour on
indented content. The extraction into `split_frontmatter` must move this body
**verbatim**. Confirmed too: an unterminated block falls out of the loop with
`result` populated, so returning `(out, "")` is a faithful extraction, and
`lines[0].strip() != "---"` (not `==`) is the entry guard.

### Finding 6 — blast radius of the `parse_frontmatter` refactor, and step 8 is a no-op here

`stats_data.parse_frontmatter` has exactly six references — small and bounded:

- `stats_data.py:1040` (the only internal call), `aitask_stats.py:66` (import),
  `aitask_stats.py:117` (`__all__` re-export);
- `tests/test_stats_data.sh:38` and `:75` (the latter asserts `aitask_stats`
  still exposes it), `tests/test_stats_multistage.py:75-121` (7 calls via an
  `importlib` file-load).

Both test files must be run, not just the Python suite — add
`bash tests/test_stats_data.sh` to verification. Keep the `__all__` re-export
exactly as it is; do not add `split_frontmatter` to it.

**Step 8 is a no-op in this child.** `stats_data` gains only
`split_frontmatter`; it does *not* import `task_category`, and `task_category`
does not import `stats_data` (it takes `metadata`/`body`/`filename` as
arguments). The docstring's sibling enumeration goes stale in **t1544_3**, when
the collection layer wires the two together. Leave the docstring alone here and
say so in the sibling note.

## Implementation steps

### Pre-phase (risk mitigations)

**P1. `capture_stats_baseline` — run before touching any file.**

```bash
./ait stats > /tmp/t1544_2_stats_before.txt
```

This must be the first action of implementation. Once `parse_frontmatter` is
edited the baseline can no longer be re-derived, and a "diff against a
pre-change capture" step that captures *after* the change proves nothing.

**P2. `characterize_parse_frontmatter` — pin current behaviour, green before the
extraction.**

Put this in a **new, stats-only module `tests/test_stats_split_frontmatter.py`**
that imports `stats_data` and nothing else:

```python
sys.path.insert(0, os.path.join(PROJECT_DIR, ".aitask-scripts", "lib"))
import stats_data  # noqa: E402
```

**It must not live in `tests/test_task_category.py`.** That file's bootstrap
imports `task_category`, which does not exist until main-phase step 2 — after
step 1 has already edited `stats_data.py`. A characterization test that can only
be imported *after* the change it guards is not a tripwire, and would fail on
import if run in the stated order. Isolating it by module is what makes the
pre-refactor run actually possible.

`TestParseFrontmatterCharacterization` calls **`parse_frontmatter`** (the
existing public function, not `split_frontmatter`) over all six shapes and
asserts the metadata dict it returns today:

| # | shape | source |
|---|---|---|
| 1 | normal frontmatter | any current task |
| 2 | no frontmatter at all | `t20` |
| 3 | `--- effort:med pri:hi` pseudo-delimiter | `t21` / `t22` |
| 4 | unterminated block (never closes) | synthetic |
| 5 | bare `---` inside the body | `t21` / `t22` |
| 6 | **indented** `  key: value` inside the block | synthetic — pins Finding 5 |

Run this file green **before** editing `stats_data.py`. Case 6 is the tripwire:
it is the one that fails if the extraction "tidies" `line` to `stripped`, which
is the specific regression path the risk names. After the extraction, re-run
unchanged — no assertion may be edited to accommodate the refactor. If one
needs editing, the extraction changed behaviour and is wrong.

After step 1 lands, extend the **same** module with `TestSplitFrontmatter`,
which asserts the full `(metadata, body)` tuple — see "Body-boundary
assertions" under Verification. Characterizing only the metadata would let an
off-by-one terminator boundary pass every legacy assertion while handing the
classifier the wrong text.

### Main phase

1. **`.aitask-scripts/lib/stats_data.py` — add `split_frontmatter`.**

   Extract the existing `parse_frontmatter` loop into
   `split_frontmatter(content) -> Tuple[Dict[str, str], str]`, returning the
   metadata dict and `"\n".join(lines[i+1:])` at the closing-`---` `break`.
   Return `({}, content)` when `lines[0].strip() != "---"` (or content is
   empty), and `(out, "")` when the block never terminates. Move the loop body
   **verbatim**, preserving the stripped/unstripped asymmetry in Finding 5. Then
   make `parse_frontmatter` call it and discard the body, so there is exactly
   one boundary definition and zero behaviour change for its six existing
   references (Finding 6).

   Do **not** substring-split (`content.split('---', 2)[2]`) — see Finding 4.
   Do **not** switch to `task_yaml.parse_frontmatter` — that is t1304's
   benchmark-gated decision (~0.67s over the corpus vs the flat scanner's
   near-zero).

2. **`.aitask-scripts/lib/task_category.py` — new module.** Follow the house
   sibling-import convention exactly as `followup_backfill_classify.py` does:

   ```python
   sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
   from followup_kinds import followup_kind_field, label_for  # noqa: E402
   ```

   **`classify` is imported lazily, inside `resolve_category`** — not at module
   scope:

   ```python
   def resolve_category(metadata, body, filename, tally=None):
       from followup_backfill_classify import classify
   ```

   This keeps the **display half** of the module (`type_display_name`,
   `category_display_name`, `is_followup_category`) dependency-free. Two
   consumers need only that half: `aitask_stats.get_type_display_name` (step 7)
   and t1544_5's stats TUI panes. Neither should transitively load the
   classifier to render a string map.

   **Note on the runtime premise:** this is a *layering* choice, not a
   dependency fix. `./ait stats` already imports PyYAML today —
   `stats_data` → `config_utils` → `import yaml` (verified by import trace), and
   `task_yaml` subclasses `yaml.SafeLoader` at class-definition time so its own
   import can never be deferred. The delegation therefore introduces **no new
   external requirement and no new failure mode**, and the measured cost of the
   classifier chain is 0.6 ms (`task_yaml` 281 µs + `followup_backfill_classify`
   345 µs) against `stats_data`'s 38 ms. Do not document PyYAML as new — it is
   not.

   ```python
   def resolve_category(metadata, body, filename, tally=None) -> str
   ```

   - `raw = _unquote(metadata.get("followup_kind"))`; clamp via
     `followup_kinds.followup_kind_field(raw)`. A real kind → `f"kind:{k}"`.
   - `unknown` (absent) → fall through silently.
   - `invalid` (present but bogus) → fall through **and**, when `tally` is not
     `None`, `tally["invalid_followup_kind"] += 1`. Rationale (`followup_kinds`,
     in `marker_for`): *"a bad value that silently vanishes is indistinguishable
     from a task that was never a follow-up."* Cite `marker_for` — the
     verification pass found this sentence is **not** in `followup_kind_field`,
     which the earlier draft claimed.
   - else `k = classify(metadata, body, filename)["kind"]`; **`k` is `None` for
     residue** (no rule fired), so guard on truthiness — when truthy it is
     always a member of `RULE_ORDER`, making `f"kind:{k}"` namespace-safe.
   - else `f"type:{_unquote(metadata.get('issue_type')) or 'unknown'}"`.

   **Ordering matters and is deliberate:** `_unquote` runs *before*
   `followup_kind_field`, so `'"carry_over"'` clamps to `carry_over` rather than
   `invalid`. The tally therefore counts genuinely bogus values, not quoting.

   **Known limitation, recorded not fixed:** `_unquote` is applied to
   `followup_kind` and to the final `issue_type` fallback, but `classify()`
   compares `metadata.get("issue_type")` internally against unquoted literals.
   A quoted `issue_type: "manual_verification"` would therefore miss classify's
   rule. The corpus has **zero** quoted values, and un-quoting the whole dict
   before handing it to `classify` would mean mutating a caller's mapping — so
   leave it, and name it in the t1304 note as another thing the parser
   consolidation removes.

   `tally` is an optional `Counter` so this module stays stateless and t1544_3
   can fold the count into `backlog_excluded` without a shared global.

3. **`_unquote(value)`** — strip surrounding `'`/`"` and whitespace; `None`-safe.
   Comment it with **both** reasons from Finding 2: it exists only to compensate
   for the flat frontmatter scanner (deleted when t1304 lands), and
   `_norm_scalar` is deliberately not reused because it is an id canonicalizer.

4. **`TYPE_DISPLAY_NAMES` + `type_display_name(raw)`** — move the mapping dict
   out of `aitask_stats.py::get_type_display_name` verbatim, keeping the
   `raw.capitalize()` fallback exactly as it is.

5. **`category_display_name(cat)`** — prefix dispatch: `kind:` →
   `followup_kinds.label_for(k)`, falling back to the bare `k` if that returns
   `""`; `type:` → `type_display_name(t)`. Do **not** re-case either side:
   `label_for` owns those strings, and they are not uniformly lowercase
   (Finding 3). The **namespace prefix**, not the casing, is what separates the
   two halves of the axis.

6. **`is_followup_category(cat)`** — `cat.startswith("kind:")`.

7. **`.aitask-scripts/aitask_stats.py`** — `get_type_display_name` keeps its name
   and signature and delegates to `task_category.type_display_name`. Delegate to
   **that**, never to `category_display_name` — see Finding 1.

8. **`lib/stats_data.py` module docstring — leave it alone.** Per Finding 6 this
   child creates no new import edge in either direction, so the docstring's
   sibling enumeration is still accurate. `tests/test_no_lib_to_tui_import.sh`
   passes unchanged (`followup_kinds` and `followup_backfill_classify` are
   `lib/` siblings, not TUI packages).

9. **Note for t1304.** Append one line to
   `aitasks/t1304_consolidate_lib_frontmatter_parsers.md` under
   `## Notes for sibling tasks` (create the heading if absent) naming
   `stats_data.parse_frontmatter` / `split_frontmatter` and
   `task_category._unquote` as things to collapse together. Commit that file
   with `./ait git`, separately from the code.

## Out of scope (recorded, not done)

`aitask_stats_legacy.sh:59` carries a **duplicate** shell `get_type_display_name`
with the same 8 entries and a `${_w^}` fallback. It is **unreachable** — nothing
in the repo invokes `aitask_stats_legacy.sh`. Do not touch it here; record it in
the t1304 note as dead parallel code, per
`aidocs/framework/planning_conventions.md` ("dead code goes into the sibling
refactor task").

## Files

- `.aitask-scripts/lib/task_category.py` (new)
- `.aitask-scripts/lib/stats_data.py`
- `.aitask-scripts/aitask_stats.py`
- `tests/test_stats_split_frontmatter.py` (new — stats-only, imports no
  `task_category`, so the pre-phase characterization can run before step 1)
- `tests/test_task_category.py` (new)
- `aitasks/t1304_consolidate_lib_frontmatter_parsers.md` (`./ait git`)

## Verification

`tests/test_task_category.py` — copy the import bootstrap and in-memory
string-fixture style of `tests/test_followup_backfill_classify.py` verbatim:

```python
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, ".aitask-scripts", "lib"))
import task_category  # noqa: E402
```

Expose **only** `unittest.TestCase` methods — no module-level `def test_*`.
`tests/test_collection_parity.py` catches that shape as a *count mismatch*, not
a collection error, and it is **skipped entirely when pytest is absent** — so on
a default install the guard is inert and cannot be relied on locally.

Cases:

- **Precedence** — an explicit `followup_kind` beats a body that would classify
  differently; a body-only prose rule with no `followup_kind:` field resolves via
  `classify()`; a plain task (classify returns `kind: None`) resolves to
  `type:<issue_type>`; a task with no `issue_type` resolves to `type:unknown`.
- **Namespacing** — `issue_type: manual_verification` and
  `followup_kind: manual_verification` both give `kind:manual_verification`; a
  user-defined `issue_type: review_finding` gives `type:review_finding`, **not**
  `kind:review_finding`.
- **Unquote / clamp** — `"carry_over"` with literal quotes → `kind:carry_over`;
  a trailing-space value works; a bogus value falls through **and** increments
  `tally["invalid_followup_kind"]`.
- **`split_frontmatter`** — see "Body-boundary assertions" below; these live in
  `tests/test_stats_split_frontmatter.py` beside the characterization.
- **Byte-identity** — `get_type_display_name("manual_verification") ==
  "Manual_verification"` and `get_type_display_name("enhancement") ==
  "Enhancement"`.
- **Display dispatch** — `category_display_name("kind:qa_test_gap") ==
  "QA test gap"` (pins Finding 3: no re-casing) and
  `category_display_name("type:bug") == "Bug Fixes"`.

### Body-boundary assertions (`tests/test_stats_split_frontmatter.py`)

Metadata assertions alone cannot see the body boundary: an off-by-one at
`lines[i+1:]`, or returning the whole document, preserves every metadata
assertion while feeding the retro-classifier frontmatter or dropping the first
line of prose. So assert the **exact `(metadata, body)` tuple** — string
equality on the body, not a substring check — for: a normal file; no
frontmatter at all (body must be `content` verbatim); the pseudo-delimiter
shape; an unterminated block (`(out, "")`); and a bare `---` inside the body
(which must stay *in* the body, not truncate it).

Then pin the boundary from **both sides** with two classifier-sensitive cases,
each of which fails on exactly one defect direction:

| fixture | correct result | defect it catches |
|---|---|---|
| body's **first** line is `## Upstream defect` | `kind:upstream_defect` | a `lines[i+2:]` slice drops the line → falls through to `type:…` |
| **frontmatter** carries `note: Risk-mitigation ("before") for t123`, body has no trigger | `type:<issue_type>` | frontmatter leaking into the body (`lines[i:]` or full document) → `RE_RISK_MITIGATION` fires → `kind:risk_mitigation` |

Both are needed. The first alone does not discriminate a leak: `^## Upstream
defect` is `re.MULTILINE`, so it still matches when the body is prefixed with
the frontmatter. `RE_RISK_MITIGATION` is unanchored, which is what makes the
second case fire on leaked frontmatter text. Together they are the executable
form of the anti-false-positive property the whole "no substring split"
argument rests on.

Keep the second fixture's *other* rule inputs inert or it passes for the wrong
reason: `issue_type` must not be `manual_verification`, `labels` must contain
neither `review` nor `qa`, and the filename must not contain
`docs_gaps_since_`. Verify each discriminator by temporarily introducing its
defect and confirming the named case — and only that case — fails.

Then:

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
bash tests/test_stats_data.sh          # direct parse_frontmatter consumer
bash tests/test_no_lib_to_tui_import.sh
./ait stats > /tmp/after.txt   # diff against a pre-change capture,
                               # ignoring the `Generated:` line
```

`tests/test_stats_data.sh` and `tests/test_stats_multistage.py` are the two
tests that touch `parse_frontmatter` directly (Finding 6) — the second is inside
the Python suite, the first is a bash test that the suite does **not** run.

The `### By Task Type` block quoted in Finding 1 is the specific rows to diff —
`Enhancement` and `Manual_verification` must survive verbatim.

## Risk

Levels below are the **post-inline reassessment** (risk-evaluation.md Step 3):
code-health was `medium` on the pre-phase-free plan and drops to `low` because
P2's case-6 tripwire plus P1's whole-corpus baseline diff convert the extraction
from "reviewed" to "proven behaviour-preserving". Goal-achievement is unchanged.

### Code-health risk: low
- The `parse_frontmatter` → `split_frontmatter` extraction sits on the
  load-bearing archived-task stats collection path (`stats_data.py:1040`, the
  source of *every* existing counter). A subtle behaviour change during the
  extraction — most plausibly "tidying" the stripped/unstripped asymmetry of
  Finding 5 — would silently skew all stats output, not just the new axis, and
  the flat parser has no schema to catch it. · severity: medium · → mitigation: inline pre-phase capture_stats_baseline, inline pre-phase characterize_parse_frontmatter
- `_unquote` is dead-defensive code (zero quoted values across 2286 task files)
  added to a base-layer module; its only justification is a parser quirk that
  t1304 removes. Abstraction debt, tracked but real. · severity: low · → mitigation: implementation step 9 (t1304 note)

### Goal-achievement risk: low
- `classify()` was written against `task_yaml`'s typed metadata and is fed the
  flat scanner's all-string metadata here. Measured 0 disagreements across the
  corpus and `_labels()` handles the string form, but the quoted-`issue_type`
  gap (step 2's recorded limitation) means a rule could silently not fire on a
  future quoted value. · severity: low · → mitigation: recorded limitation + t1304 note

### Planned mitigations
- timing: pre-phase | name: capture_stats_baseline | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (silent skew of existing counters) | desc: capture ./ait stats output to a file before any edit, so the post-change diff compares against genuinely pre-change output
- timing: pre-phase | name: characterize_parse_frontmatter | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (silent skew of existing counters) | desc: in a new stats-only module tests/test_stats_split_frontmatter.py (importing no task_category, so it can run before step 1), pin parse_frontmatter's current behaviour over all six input shapes and run green before the extraction, so the refactor is provably behaviour-preserving

## Notes for sibling tasks

Record the final `resolve_category` signature (especially the `tally`
parameter's name and the exact reason string) — t1544_3 wires it into
`backlog_excluded`, and t1544_4 / t1544_5 call `category_display_name` and
`is_followup_category` directly.

t1544_3 owns the `stats_data` ↔ `task_category` wiring, and with it the module
docstring's sibling enumeration (Finding 6) — that edge does not exist yet.

t1544_4 should note two rendering facts: the existing `| Type | ...` column is
14 chars wide and `Manual_verification` (19) already overflows it, so the
backlog table needs its own width rather than a copy; and `label_for` labels are
not uniformly lowercase (Finding 3), so no column may assume a case convention.

For the **t1304** note, name four things to collapse together:
`stats_data.parse_frontmatter` / `split_frontmatter`, `task_category._unquote`,
the quoted-`issue_type` gap in `classify()`'s internal comparison (step 2's
recorded limitation), and the **dead** duplicate `get_type_display_name` in
`aitask_stats_legacy.sh:59`.
