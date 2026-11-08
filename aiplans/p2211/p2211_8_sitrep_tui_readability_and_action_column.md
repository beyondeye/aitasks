---
Task: t2211_8_sitrep_tui_readability_and_action_column.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_3_*.md, aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md, aitasks/t2211/t2211_7_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
---

# t2211_8 — sitrep TUI readability: "What to do" column, click-selects, labelled details

## Context

t2211_1 shipped `ait sitrep tui`. Hands-on testing showed the data is hard to read:
- the list rows have no column header;
- the internal `kind` / `state` values are shown to the user;
- a left click opens an item instead of selecting it;
- detail labels look the same as their values;
- `task:` / `plan:` sources are shown as raw text;
- "ref" vs "referenced by" is confusing;
- the sources list exposes store plumbing (hex handles, KEY receipts).

This task fixes how the TUI presents the store. It changes nothing in the store
format, the writer or `lib/sitrep_*.py`.

**No documentation is written here.** That means no `website/` page, no
`aidocs/` edit and no doc prose beyond code docstrings: the `ait sitrep` feature
is still in flux. Docs belong to the planned sibling **t2211_6**
(`sitrep_tui_window_docs`), which only receives an advisory note listing what
changed. The siblings build on these screens:
t2211_3 and t2211_4 depend on this task.

Reality checks (done during planning, against HEAD a43795ceb):
- `git diff HEAD -- .aitask-scripts/sitrep_tui/ tests/test_sitrep_tui_app.py
  .aitask-scripts/lib/shortcut_scopes.py` is empty. Re-check it before editing.
- **Textual 8.2.7 click path.** `OptionList._on_click` sets the highlight and then
  calls `action_select()`, which posts `OptionSelected` (an open). Textual walks
  the MRO for `_on_click`/`on_click` handlers and stops once a handler calls
  `prevent_default()`. So a subclass `_on_click` that calls `prevent_default()`
  skips the base's select.
- **`Markdown(text, open_links=False)` renders store text literally.** Probed:
  `[b]x[/b]`, `[link=x]` and `$x` come out verbatim in `MarkdownParagraph`.
  The default `open_links=True` would open a browser on a link click, so it must
  be passed as `False`.
- **`Content.assemble(("Label ", "bold"), value)`** keeps a `str` value as plain
  text (probed: `[b]x[/b]` stays literal, one bold span on the label only).
- **Column offset.** OptionList has a `tall` border plus `padding: 0 1`, so row
  content starts at x=2. A header `Static` must use the same left inset. The
  test checks `content_region.x` equality instead of trusting this.
- **Triage is a batch.** The skill's `>t` triages every open wrap-up at once, and
  "Analyze unparsed agent output" reviews are handled inside `>t` (step 2b).
  Deviation from the task text: the "How" line says `>t`, not `>t c<N>`, because
  that is what works today. t2211_4/t2211_5 swap in the per-item form.
- Title grammars: harvest writes `Triage wrap-up of t<id> <name>: turn its
  closing notes into action/watch items` (`sitrep_harvest.py` ~L966). The corpus
  writes `sitrep_corpus.REVIEW_TITLE_PREFIX` + ` of t<id> (<who>): <codes>`.
  `sitrep_cli.is_triage` = question + derived=script.
- `st.parse_push_ref(ref)` gives `(branch, sha)` for `push:` action refs. A ref
  can also be `t<N>[_<M>]` or `<proj>#<N>[_<M>]` (`st.normalize_ref`).
- Capture kinds come from `sitrep_cli.capture_kind`: passage, banner, key, case,
  analysis, review. A review item's first capture is an excerpt whose file starts
  with `sitrep_corpus.EXCERPT_HEADER`; `capture_kind` calls it "passage".

## Implementation steps

### 1. `sitrep_tui_model.py`: the one "next step" table

Add `from sitrep_corpus import EXCERPT_HEADER, REVIEW_TITLE_PREFIX`. There is no
import cycle: `sitrep_corpus` imports only `sitrep_harvest` and `sitrep_todo` at
module top.

```python
@dataclass(frozen=True)
class NextStep:
    key: str    # the table row (internal; tests and t2211_3/4 key on it)
    what: str   # the "What to do" cell / details line (one line)
    how: str    # the details "How" line

#: internal classification -> user-facing "What to do" + "How". THE single
#: source (t2211_3 / t2211_4 replace the "how" texts with their keys).
NEXT_STEPS = {
  "triage":     ("Triage {task}'s wrap-up: decide which closing notes become actions or watches",
                 "In the sitrep agent pane (beside this one) type  >t  -- it triages every open wrap-up, this one included."),
  "review":     ("Review unparsed agent output{rest}",
                 "In the sitrep agent pane type  >t  -- open reviews are handled with the triage."),
  "decide":     ("Decide: {title}",
                 "Ask the sitrep agent: type  >q {cid} <your question or decision>  in its pane."),
  "pick":       ("Pick {ref}{status}: {rest}",
                 "Run  /aitask-pick {pick_id}  in a code-agent window (or open it with  ait board)."),
  "pick_xref":  ("Pick {ref}{status}: {rest}",
                 "It lives in project {project}: run  /aitask-pick {pick_id}  there."),
  "pick_noref": ("Pick: {title}{status}",
                 "The title names the task; pick it with  /aitask-pick <id>."),
  "push":       ("Do: {title}",
                 "Push branch {branch} (commit {sha}) yourself; refresh marks this done once the commit is on the remote. Shown only -- the TUI never runs it."),
  "do":         ("Do: {title}",
                 "Do it yourself; when it is done or no longer needed, dismiss it (in the agent pane:  >x {cid} <reason>)."),
  "watch":      ("Waiting on: {title} -- nothing to do now{outcome}",
                 "A refresh re-checks its trail (in the agent pane:  >r ); the outcome shows what changed."),
  "watch_manual": ("Waiting on: {title} -- nothing to do now{outcome}",
                 "Refresh does not check this one (it has no trail to follow). To see where it stands, ask the sitrep agent:  >q {cid} <question>  -- it reads the item's sources."),
  "done":       ("Done: {title}{outcome}", "Nothing to do."),
  "dismissed":  ("Dismissed: {title}{outcome}", "Nothing to do."),
  "unknown":    ("Unknown -- needs a re-check: {title}",
                 "Refresh re-checks it: in the agent pane type  >r ."),
  "unknown_manual": ("Unknown -- needs a re-check: {title}",
                 "Refresh has no automatic check for this item. Ask the sitrep agent to look at its sources ( >q {cid} <question> ), or dismiss it ( >x {cid} <reason> )."),
  "raw":        ("{kind} / {state}: {title}",
                 "No guidance for this kind of item -- read its context below."),
}
```

(Use real em dashes in the code to match the current UI. The plain `--` above
is only for this plan.)

- **What refresh checks comes from one place.** `refresh_checks(store) ->
  {num: check}` is built from `sitrep_refresh.select_targets(store)`, the
  refresh's own rule, reused rather than copied. Under that rule refresh checks
  only task items with a ref, push actions, and watches that carry `trail:`
  sources. Every other item is left byte-identical (`sitrep_refresh.py`
  module docstring and `select_targets` ~L218).
  - The app computes the map once per `_apply` and passes
    `refresh_check = checks.get(num)` into `classify` / `next_step`.
  - A failure yields `{}`, which is the conservative side: every watch or
    unknown item gets the "manual" guidance.
- `classify(item, refresh_check=None) -> str`, a pure function:
  - state `done` / `dismissed` → that key; state `unknown` → `unknown` when
    `refresh_check` is set, else `unknown_manual`; any other non-`open`
    state → `raw`.
  - open `question`: title starts with `REVIEW_TITLE_PREFIX` → `review`; else
    `is_triage` and title matches `_TRIAGE_RE = ^Triage wrap-up of
    (t[0-9]+(?:_[0-9]+)?)\b` → `triage`; else `decide`.
  - open `task`: local ref → `pick`, `<proj>#…` → `pick_xref`, empty → `pick_noref`.
  - open `action`: push ref → `push`, else `do`.
  - open `watch`: `refresh_check == "trail"` → `watch`, else `watch_manual`;
    any other kind → `raw`.
- `next_step(item, refresh_check=None) -> NextStep` fills the template with `str.format(**fields)`.
  Store values are format *arguments*, never format strings, so braces in a
  title are harmless; a test pins this. Fields:
  - `title`, `cid`, `kind`, `state`;
  - `task`: the triage regex group, else "this run";
  - `rest`: the review title after the prefix, or the task title with a leading
    `<ref> ` stripped;
  - `ref`, `pick_id` (ref without `t`, or the part after `#`), `project`;
  - `status`: when the outcome starts with `status:`, it is ` (<the outcome
    verbatim>)`, carrying the task's real live status. The store holds
    `status: Ready`, `status: Postponed` (c24) and `status: Implementing`
    (c49), so `Pick t2187 (status: Postponed): …`. Otherwise ` — <outcome>`
    when an outcome exists, else "". It is never a fixed word.
  - `outcome`: ` — <outcome>` or "";
  - `branch` and `sha` (first 12 hex) from `parse_push_ref`.
  - Never raises. Any exception falls back to the `raw` row.

### 2. `sitrep_tui_model.py`: columns, rows, labels

- `COLUMNS = (("Item", 5), ("Checked", 8), ("What to do", 0))`.
  `cid_width(store)` = max(5, longest cid).
  `header_text(cid_w)` and `row_text(item, now, cid_w=5)` both build from
  `COLUMNS`, so they align by construction.
  `row_text` = `f"{cid:<w} {age_cell:<8} {next_step(item).what}"`.
- `age_cell(checked_at, now)`: the list cell, at most 8 chars. `never` → `—`,
  invalid date → `invalid`, future → `future`, else the `age_text` value
  (`just now`, `5m ago`, …). The details keep the full `age_text`.
- `about_text(ref)`: `t2182` → "t2182"; `proj#12` → "task 12 in project proj";
  `push:b@sha` → "push of branch b (commit <sha12>)"; "" → "" (row omitted).
- `source_label(store_dir, stype, ptr) -> str | None`. `None` means hidden.
  - `capture`, by kind:
    - key → `None` (the store keeps it; the TUI hides it);
    - banner → "Workflow result";
    - passage → "Closing message", or "Excerpt of the unparsed output" when the
      file's first line is `EXCERPT_HEADER`;
    - case → "Review case: origin record"; analysis → "Review case: parser
      analysis"; review → "Review case: review record";
    - unlabelled → "Retained text";
    - each with ", lines a–b" from the fragment (no hex).
  - `task` → "Task t2175_2", from the basename `^t(\d+(?:_\d+)?)_`, plus
    " (archived)" under `/archived/`; otherwise "Task file <path>".
  - `plan` → "Plan of t2175_2", from `^p(…)_`, same archive suffix; otherwise
    "Plan file <path>".
  - `file` → "File <path>", plus ", line a" when there is a fragment.
  - `commit` → "Commit <sha≤12>". `trail` / `artifact` → "Trail <h>" /
    "Artifact <h>".
  - `url` → "Web link <url> (shown, never opened)".
  - unknown type → "<type>: <ptr>".
  - Never raises. Reuse `capture_label` / `sitrep_cli.capture_kind`.
- `ORIGIN_LABELS = {"agent": "Agent", "task": "Task", "commit": "Commit",
  "date": "Date", "skill": "Skill", "pane": "Pane"}`. An unknown key shows
  as itself.
- `PointerView` gets `markdown: bool = False`. `_follow_path` sets it for
  `task` / `plan`, and for `file` when the path (before `#`) ends in `.md`.
  The size cap and truncation note are unchanged.
- `markdown_source(text)`: a leading `---\n…\n---\n` front matter becomes a
  fenced `yaml` block, then the body. The fence is longer than the longest
  backtick run in the front matter. Anything else passes through unchanged.

### 3. `sitrep_tui_app.py`: lists where a click only selects

- New `class SelectOnClickList(OptionList)`. Its `async def _on_click(self, event)`:
  - calls `event.prevent_default()` (this skips `OptionList._on_click` →
    `action_select`);
  - reads `idx = event.style.meta.get("option")`;
  - when the option exists and is enabled, sets `self.highlighted = idx`.

  Its docstring states the rule: click selects, Enter (the footer-visible
  binding) opens, and `OptionSelected` stays the single open path, since Enter
  fires `action_select`.
- Use it for `#st-list`, `#sd-links`, `#ql-list` and `#qe-links`.

### 4. `sitrep_tui_app.py`: main list header

- Add `Static(id="st-columns")` between `#st-situation` and `#st-list`. It
  stays outside the OptionList, so it does not scroll.
- CSS: `#st-columns { height: 1; padding: 0 1 0 2; text-style: bold;
  text-wrap: nowrap; }`. The inset matches the list's border plus padding.
- `_rebuild_list` computes `cid_w = model.cid_width(store)`, updates the header
  with `Content(model.header_text(cid_w))` and passes `cid_w` to `row_text`.
  `_refresh_ages` uses the same `cid_w` (stored as `self._cid_w`).
- Group heading options stay ("Pick now (3)" etc.).

### 5. `sitrep_tui_app.py`: `ItemDetailScreen`

- `body_content(now) -> Content` built with `Content.assemble`. Labels are
  `("<label padded to 12>", "bold")`; values are plain `str`; section headings
  are `("Item" / "Context", "bold underline")`. Layout:
  ```
  Item
  What to do  <next_step.what>
  How         <next_step.how>
  About       <about_text>            (omitted when ref is empty)
  Checked     never | <ts> (<age_text>)
  Outcome     <outcome or —>

  Context
  Background  …
  Origin
    Agent     agent-pick-2175_2
    Task      t2175_2   …              (one line per origin key)
  Theme       sitrep                   (when set)
  Review case <hex> (<codes>) — read it with `ait sitrep case show <hex>`
  ```
  No kind, state, group, derived or rev. `body_text(now) = body_content(now).plain`
  is kept for tests. `refresh_ages` updates with the Content.
- Links: iterate `ctx.sources` with their original index (`src:<i>` ids
  unchanged) and skip entries whose `source_label` is `None`. Labels:
  - `raw:<i>` → "Raw input (review case)";
  - `rel:` → "Related: item c<N> — <title>";
  - `relx:` → "Related: item c<N> (no longer in the store)";
  - `ref:` → "Mentioned by item c<N> — <title>";
  - `qa:` → "Q&A entry <ts>".
  - The "No sources or links" placeholder stays.

### 6. `sitrep_tui_app.py`: `PointerViewerScreen` Markdown branch

- When `view.markdown` is set, also compose
  `VerticalScroll(Markdown(model.markdown_source(view.text), open_links=False),
  id="pv-md")`, which can take focus.
- Start in rendered mode, except when `view.focus_line` is set (a `#L` fragment
  needs line numbers): then start raw.
- Binding `Binding("m", "toggle_markdown", "Rendered/raw")`, shown only when
  `view.markdown` (`check_action`). It swaps `display` between `#pv-md` and
  `#pv-text` and focuses the visible one.
- Plain views (capture, commit, trail, artifact, raw, url, errors) are unchanged.
- No `shortcut_scopes.py` edit: the viewer scope already exists, and new
  bindings in this module are swept. Run `tests/test_shortcut_scopes.py` to
  confirm.

### 7. Tests: extend `tests/test_sitrep_tui_app.py`

Fixture additions, all through the real writer:
- a **triage** item: kind question, derived script, title "Triage wrap-up of t10
  demo: turn its closing notes into action/watch items". Its context has these
  captures:
  - a passage (closing message);
  - a retained `sitrep banner v1` file (BANNER);
  - two retained KEY files (`sitrep wrap-up complete v1`, `sitrep wrap-up run v2`);
  - also task, plan and commit sources.
- a **push** action with `--ref push:main@<fixture sha>`;
- a **cross-repo task** with ref `other#7`;
- a **trail watch**: kind watch, context source `trail: art:trail-demo`. The
  existing "CI on sitrep" watch stays the no-trail case;
- an **unknown task** with ref `t10` (`--state unknown`). The existing
  `unknown` question stays the no-check case;
- three task items with outcomes `status: Ready` / `status: Postponed` /
  `status: Implementing`, set with `set-state … --outcome`;
- a `task:` file whose body holds `HOSTILE`, and front matter `---\nstatus: Ready\n---\n`.

Then update the existing assertions that this changes: group counts ("Pick now
(N)"), "kind: task" / "ref: t10" body strings, the `capture [CAPTURE]` /
`url: …` / `related c…` / `asked about in Q&A …` link labels, and the
"(invalid date)" row text, which becomes "invalid" in the list. The details
keep the full form.

New tests:
- **Model, `NextStepTests`.**
  - One subTest per `NEXT_STEPS` key, using real fixture items where they exist
    and constructed `st.Item`s otherwise. Each asserts `classify` and the
    `what` / `how` text: triage names `t10`, pick says `/aitask-pick 10`, push
    names the branch and sha, xref names the project.
  - Pick status interpolation: outcomes `status: Ready`, `status: Postponed`
    and `status: Implementing` each appear verbatim in `what`, and no other
    status word appears. An outcome without `status:` shows as ` — <outcome>`;
    an empty outcome adds nothing.
  - Refresh-aware guidance, through the real fixture store and
    `refresh_checks`, never a hand-built map:
    - a watch with a `trail:` source → `watch`, and its How names `>r`;
    - a watch without one ("CI on sitrep") → `watch_manual`, whose How says
      refresh does not check it, points at `>q c<N>`, and does not mention
      `>r`;
    - an `unknown` task with a ref → `unknown`;
    - the `unknown` question → `unknown_manual`.
    - Control: `refresh_checks` returning `{}` makes the trail watch
      `watch_manual`, which proves the key follows the refresh rule and not
      `kind` alone.
  - An unknown kind and an unknown state → `raw`, showing the raw values, no
    exception.
  - A title containing `{0}` / `{title}` renders literally.
  - Completeness: every key `classify` can return is in `NEXT_STEPS`, and every
    `NEXT_STEPS` key is produced by at least one case. This catches an orphan or
    a parallel copy.
- **Model, columns.** `header_text` and `row_text` column offsets are equal for
  each column (cid widths 5 and 7); `age_cell` table (never → `—`, invalid,
  future, 5m); `about_text` per ref form; `source_label` per type, with KEY →
  `None` and BANNER → "Workflow result"; `markdown_source` turns front matter
  into a fenced block, picks a longer fence when the front matter holds
  backticks, and passes text without front matter through unchanged.
- **App, header.**
  - `#st-columns` exists, is not an option, and shows "Item", "Checked" and
    "What to do".
  - Its `content_region.x == #st-list.content_region.x`.
  - After highlighting the last row (the list scrolls, `scroll_y > 0`), the
    header's region is unchanged and still displayed.
  - Rows show "What to do" text, and the internal words (`question`, `open`)
    are absent from the triage row.
- **App, click selects; Enter opens.** On each of the four lists (main, details
  links, Q&A log, Q&A entry links):
  - `pilot.click(<list>, offset=(content_x + 2, content_y + row))` on a
    selectable row → the highlight moves to that row, and the screen stack is
    unchanged (no screen pushed, no viewer worker);
  - then `enter` → the expected screen is pushed.
- **Control.** A minimal App with a plain `OptionList` handling the same
  `pilot.click` posts `OptionSelected`. This proves the click actually reaches
  the list, so the "no push" result above is not vacuous.
- **App, labels and markup safety.**
  - On the hostile item's details: `HOSTILE` appears verbatim in `.plain`.
  - Every bold span covers only label text ("What to do", "How", …), and no
    span overlaps a value.
  - No `MarkupError`.
- **App, sources.**
  - Triage item links: "Closing message…" and "Workflow result" are present;
    no "KEY" label, no `sources/<hex>` text, no hex handle in any label.
  - The task link reads "Task t10"; the commit link reads "Commit <sha12>".
  - "About: t10" appears on the task item; no About line on the triage item.
  - "Mentioned by item c<task>" appears on the related question's details.
- **App, Markdown viewer.**
  - `task:` / `plan:` pointers push a viewer with a displayed `Markdown`
    (`open_links` false), and the hostile text shows literally in a
    `MarkdownParagraph`.
  - `m` toggles to the TextArea and back.
  - `file: docs/notes.md#L3` starts in raw mode with the cursor on line 3 (the
    existing test still passes).
  - A capture pointer has no Markdown and no `m` binding.
- Every App test still ends with `assert_no_workers`.

### Mutant checks (manual, scratch copy; record in Final Implementation Notes)

For each mutant, confirm the named test turns red:
- `SelectOnClickList` without `prevent_default` → the click tests;
- `#st-columns` inset changed → the alignment test;
- the KEY filter removed → the sources test;
- `Content.assemble` replaced by an f-string with `[b]` markup → the markup
  test;
- `open_links=False` dropped → the Markdown test;
- a `NEXT_STEPS` key removed → the completeness test;
- `status` pinned to the literal "Ready" → the Postponed/Implementing
  interpolation tests;
- `watch` classified by kind alone (ignoring `refresh_check`) → the
  watch_manual test and its `{}` control.

### Step 9 (post-implementation)

Commit `enhancement: Make the sitrep TUI readable: What-to-do column, click
selects, labelled details (t2211_8)`. Archive through the normal Step 9 flow.

Final Implementation Notes for siblings:
- **t2211_3 / t2211_4:** `model.NEXT_STEPS` is the table to edit: change the
  `how` texts of the triage, review, decide, pick, push and do rows to name your
  keys. `classify` keys are stable. Click-selects lists are `SelectOnClickList`.
- **t2211_6** (the docs sibling; nothing is documented in this task): when its
  docs are written, they should cover the "What to do" column and the source
  labels, and that KEY receipts are hidden.
- **t2211_7:** add checklist items: a readable header, click selects, Markdown
  for task/plan, and c1 shows "Closing message" and "Workflow result" only.

Send these as `ait note`s at Step 8e.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_sitrep_tui_app.py
  tests/test_shortcut_scopes.py -q`.
- `bash tests/run_all_python_tests.sh --test-dir tests`; read the last-line
  verdict only.
- Manual, `./ait sitrep tui` on the real store:
  - the list reads without docs;
  - c1 says "Triage t2175_2's wrap-up…", and its How names `>t`;
  - c1's sources show "Closing message", "Workflow result", "Task t2175_2
    (archived)", "Plan of t2175_2 (archived)" and "Commit d0c48e88d", with no
    KEY lines;
  - a click selects and Enter opens;
  - the task source renders as Markdown, and `m` shows the raw text.

## Risk

### Code-health risk: low
- `SelectOnClickList` overrides OptionList's private `_on_click` / `event.style.meta["option"]` contract (Textual 8.2.7); a Textual upgrade could change it and silently restore click-opens or break click-highlight · severity: low · → mitigation: none (in-plan: the click tests on all four lists plus the plain-OptionList control fail on either regression)
- The header alignment depends on OptionList's border+padding CSS · severity: low · → mitigation: none (in-plan: the `content_region.x` equality test, not a hard-coded offset)

### Goal-achievement risk: medium
- "Readable without docs" is subjective; the wording of the What-to-do/How texts may still not land for the user · severity: medium · → mitigation: none (the user's manual check on the real store in Verification; the texts live in one table, so revisions are one-line edits; t2211_7 re-checks)
- Guidance that promises more than refresh does (watches and `unknown` items refresh never checks) · severity: medium · → mitigation: none (in-plan: guidance keyed on `sitrep_refresh.select_targets` itself — no copied rule — with per-case tests and a `{}` control)
- The How lines name today's agent codes (`>t` batch, `>q`, `>r`, `>x`), which t2211_4/t2211_5 will change; deviates from the task's `>t c<N>` wording because per-item triage does not exist yet · severity: low · → mitigation: none (siblings told via notes to edit `NEXT_STEPS`)
