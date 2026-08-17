---
Task: t1544_2_task_category_axis_module.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_1_*.md, aitasks/t1544/t1544_3_*.md, aitasks/t1544/t1544_4_*.md, aitasks/t1544/t1544_5_*.md, aitasks/t1544/t1544_6_*.md, aitasks/t1544/t1544_7_*.md, aitasks/t1544/t1544_8_*.md
Archived Sibling Plans: aiplans/archived/p1544/p1544_*_*.md
Base branch: main
Output branch: main
---

# p1544_2 — Category axis module

## Goal

One unified, namespaced category axis over two vocabularies (auto-spawned
follow-up kinds and ordinary issue types), plus the frontmatter/body split the
retro-classifier needs. Pure — no renderer, no counter, no writes.

## Implementation steps

1. **`.aitask-scripts/lib/stats_data.py` — add `split_frontmatter`.**

   Extract the existing `parse_frontmatter` loop into
   `split_frontmatter(content) -> Tuple[Dict[str, str], str]`, returning the
   metadata dict and `"\n".join(lines[i+1:])` at the closing-`---` `break`.
   Return `({}, content)` when line 0 is not `---`, and `(out, "")` when the
   block never terminates. Then make `parse_frontmatter` call it and discard the
   body, so there is exactly one boundary definition and zero behaviour change
   for existing callers.

   Do **not** substring-split (`content.split('---', 2)[2]`) — it agrees on
   today's corpus by luck, and the classifier's anti-false-positive guarantee
   depends on the body starting after the frontmatter *terminator*, which only
   the line scan knows. Do **not** switch to `task_yaml.parse_frontmatter` —
   that is t1304's benchmark-gated decision (~0.67s over the corpus vs the flat
   scanner's near-zero).

2. **`.aitask-scripts/lib/task_category.py` — new module.**

   ```python
   def resolve_category(metadata, body, filename, tally=None) -> str
   ```

   - `raw = _unquote(metadata.get("followup_kind"))`; clamp via
     `followup_kinds.followup_kind_field(raw)`. A real kind → `f"kind:{k}"`.
   - `unknown` (absent) → fall through silently.
   - `invalid` (present but bogus) → fall through **and**, when `tally` is not
     `None`, `tally["invalid_followup_kind"] += 1`. `followup_kind_field`'s own
     docstring is explicit that a bad value which silently vanishes is
     indistinguishable from a task that was never a follow-up.
   - else `k = classify(metadata, body, filename)["kind"]`; if truthy →
     `f"kind:{k}"`.
   - else `f"type:{_unquote(metadata.get('issue_type')) or 'unknown'}"`.

   `tally` is an optional `Counter` so this module stays stateless and t1544_3
   can fold the count into `backlog_excluded` without a shared global.

3. **`_unquote(value)`** — strip surrounding `'`/`"` and whitespace; `None`-safe.
   Comment it as existing **only** to compensate for the flat frontmatter
   scanner, and as deleted when t1304 lands. Zero quoted values exist in the
   corpus today; this is defensive.

4. **`TYPE_DISPLAY_NAMES` + `type_display_name(raw)`** — move the mapping dict
   out of `aitask_stats.py::get_type_display_name` verbatim, keeping the
   `raw.capitalize()` fallback exactly as it is.

5. **`category_display_name(cat)`** — prefix dispatch: `kind:` →
   `followup_kinds.label_for(k)` (lowercase); `type:` → `type_display_name(t)`.
   The case difference is the visual separator between the two halves of the
   axis in the CLI table, so do not normalize it.

6. **`is_followup_category(cat)`** — `cat.startswith("kind:")`.

7. **`.aitask-scripts/aitask_stats.py`** — `get_type_display_name` keeps its name
   and signature and delegates to `task_category.type_display_name`. Delegate to
   **that**, never to `category_display_name`: the map has no entry for
   `manual_verification` or `enhancement`, so those render as
   `Manual_verification` / `Enhancement` today, and a kind-first resolver would
   silently turn the first into `manual verification` — breaking the parent's
   "existing stats output unchanged" criterion.

8. **Update `lib/stats_data.py`'s module docstring** if it now imports
   `task_category`, since that docstring enumerates its base-layer siblings.
   `tests/test_no_lib_to_tui_import.sh` must still pass.

9. **Note for t1304.** Append one line to
   `aitasks/t1304_consolidate_lib_frontmatter_parsers.md` under
   `## Notes for sibling tasks` (create the heading if absent) naming
   `stats_data.parse_frontmatter` / `split_frontmatter` and
   `task_category._unquote` as things to collapse together. Commit that file
   with `./ait git`, separately from the code.

## Files

- `.aitask-scripts/lib/task_category.py` (new)
- `.aitask-scripts/lib/stats_data.py`
- `.aitask-scripts/aitask_stats.py`
- `tests/test_task_category.py` (new)
- `aitasks/t1304_consolidate_lib_frontmatter_parsers.md` (`./ait git`)

## Verification

`tests/test_task_category.py` — plain `unittest.TestCase` methods only, no
module-level `test_*(arg)` helper (`tests/test_collection_parity.py` flags that
fixture-arg trap):

- **Precedence** — an explicit `followup_kind` beats a body that would classify
  differently; a body-only prose rule with no `followup_kind:` field resolves via
  `classify()`; a plain task resolves to `type:<issue_type>`.
- **Namespacing** — `issue_type: manual_verification` and
  `followup_kind: manual_verification` both give `kind:manual_verification`; a
  user-defined `issue_type: review_finding` gives `type:review_finding`, **not**
  `kind:review_finding`.
- **Unquote / clamp** — `"carry_over"` with literal quotes → `kind:carry_over`;
  a trailing-space value works; a bogus value falls through **and** increments
  `tally["invalid_followup_kind"]`.
- **`split_frontmatter`** — a normal file; a file with **no** frontmatter at all
  (`t20`, `t21`, `t22` are real examples); an **unterminated** block; a `---`
  line inside the body.
- **Byte-identity** — `get_type_display_name("manual_verification") ==
  "Manual_verification"` and `get_type_display_name("enhancement") ==
  "Enhancement"`.

Then:

```bash
bash tests/run_all_python_tests.sh --test-dir tests
bash tests/test_no_lib_to_tui_import.sh
./ait stats > /tmp/after.txt   # diff against a pre-change capture,
                               # ignoring the `Generated:` line
```

## Notes for sibling tasks

Record the final `resolve_category` signature (especially the `tally`
parameter's name and the exact reason string) — t1544_3 wires it into
`backlog_excluded`, and t1544_4 / t1544_5 call `category_display_name` and
`is_followup_category` directly.
