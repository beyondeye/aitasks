---
priority: medium
effort: medium
depends: [t2211_2]
issue_type: enhancement
status: Implementing
labels: [sitrep, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
created_at: 2026-11-08 10:39
updated_at: 2026-11-08 10:48
---

## Context

Child 8 of t2211, ordered BEFORE t2211_3 (t2211_3 and therefore t2211_4 depend on it).
t2211_1 shipped the sitrep TUI (`ait sitrep tui`, `.aitask-scripts/sitrep_tui/`) and
t2211_2 placed it in the `agent-sitrep` window. Hands-on testing by the user (2026-11-08)
found the TUI "works but it is very difficult to understand anything of the data shown".
The remaining siblings only add actions (t2211_3), agent request keys (t2211_4), the skill
slim-down (t2211_5) and docs (t2211_6) on top of the same screens, so the presentation is
fixed here, first. The store format (`.aitask-sitrep/todo.md`, `lib/sitrep_todo.py`) is NOT
changed: every fix is in how the TUI presents the store.

## User-reported issues (all in scope)

1. **Main list columns are unexplained.** A row is
   `c<N> kind state checked-age title — outcome` (`sitrep_tui_model.row_text`, ~L155) with no
   header: "what is question, what is task, what is open?". → A FIXED header row naming each
   column, kept visible while the list scrolls.
2. **The internal `kind` must not be user-facing.** User requirement: "if specific user action
   are waiting, it should be clear what those action should be so that the user know where and
   how he can act according to his decision. As an internal classification it can stay but not
   as user facing." → Replace the kind/state columns with a **"What to do"** column, and show
   the **how** in the details. Mapping agreed with the user (internal → user-facing → how):

   | internal | "What to do" | how (details) |
   |---|---|---|
   | `question`, `derived=script`, "Triage wrap-up of tX…" | Triage tX's wrap-up: decide which closing notes become actions/watches | ask the sitrep agent `>t c<N>` (t2211_4 turns it into a key) |
   | `question`, review case ("Analyze unparsed agent output…") | Review unparsed agent output | ask the sitrep agent (same) |
   | `question`, other | Decide: <title> | ask the sitrep agent `>q c<N> …` |
   | `task`, open (`ref=t<N>`) | Pick t<N> (+ its status from `outcome`, e.g. "status: Ready") | `/aitask-pick <N>` (t2211_3 adds pick / open-in-board keys) |
   | `action` | Do: <title> | the command, shown never run (t2211_3's push key) |
   | `watch` | Waiting on: <title> — nothing to do now | a refresh re-checks it; the outcome shows changes |
   | state `done` / `dismissed` | Done / Dismissed (no action) | — |
   | state `unknown` | Unknown — needs a re-check | refresh |

   The "how" names TODAY's means (agent request codes, `/aitask-pick`); t2211_3 / t2211_4 swap
   in their keys (they receive notes). Keep the mapping in ONE table in
   `sitrep_tui_model.py` (no parallel copies), unit-tested per row incl. the fallback for an
   unrecognised kind/state (never crash, show the raw value).
   Also: `checked: never` → `—` in the list; age column header e.g. "Checked".
3. **Left click opens details — wrong.** Click must only SELECT (highlight) a row; Enter (and a
   footer-visible "Details" binding) opens. Same rule for the details screen's links list and
   the Q&A list: click selects, Enter opens. `OptionList` posts `OptionSelected` on click —
   override/suppress that path (check how other framework TUIs do it; see
   `aidocs/framework/tui_conventions.md`), keep keyboard Enter as the one open path, and pin it
   with tests (`App.run_test` + `pilot.click` → no screen pushed; Enter → pushed).
4. **Details: labels indistinguishable from values.** `ItemDetailScreen.body_text` (~L179)
   renders `label: value` plain lines. → Style labels distinctly, like the `ait board` task
   detail (`board/board_detail_screen.py`, e.g. `[b]Depends:[/b]` ~L184). BUT store strings are
   untrusted: keep the TUI markup-safe — build `rich.text.Text` / `Content` with styled label
   spans and plain value spans, never interpolate store text into a markup string (the
   t2211_1 rule; see the "markup sinks" memory). Group: Item (what to do, how, checked,
   outcome), Context (background, origin as labelled sub-fields, theme), review line.
5. **Details links list: click opens — wrong.** Same as 3.
6. **`task:` / `plan:` sources must render as Markdown.** `PointerViewerScreen` (~L278) shows
   every pointer as numbered plain text. → `task:` and `plan:` (and `file:` when `.md`) use
   Textual's `Markdown` widget; captures, commits, trails/artifacts, raw input stay plain text
   with line numbers. Keep the size cap / truncation note; Markdown rendering must not
   interpret store text as Rich markup.
7. **"References" are unclear.** Two things sound alike: the item's `ref:` field (the ONE thing
   the item is about — task id, trail handle; empty for triage items) and "referenced by c<N>"
   (other items whose context lists this one as `related`; `sitrep_tui_model.referenced_by`).
   → Plain-language labels, e.g. "About: t2182" and "Mentioned by item c12 — <title>"; omit
   `ref` when empty.
8. **Source lines are store plumbing.** An item's sources list shows raw handles, e.g. c1:
   `capture [CAPTURE]: sources/160dca7417cac02c.txt#L1-L10`, `capture [BANNER]: …`, and two
   `capture [KEY]: …` lines. The harvest stores a finished agent's output as separate pieces:
   CAPTURE = the closing message (useful), BANNER = the parsed workflow-end banner (outcome,
   commit, follow-ups), KEY = machine receipts ("sitrep wrap-up complete v1", "sitrep wrap-up
   run v2" — dedupe / consumed-proof bookkeeping). User decision: **HIDE the KEY receipts** in
   the TUI (they stay in the store). Label the rest in plain language ("Closing message",
   "Workflow result", "Task t2175_2", "Plan", "Commit d0c48e88d", "Raw input (review case)",
   "Q&A entry <ts>"), no hex handles in the label. Kinds come from
   `sitrep_cli.capture_kind` / `KIND_LABEL` (already used by `sitrep_tui_model.capture_label`).

## Key files

- `.aitask-scripts/sitrep_tui/sitrep_tui_model.py` — `row_text`, the new kind→"what to do"
  table, plain source labels, `capture_label`, `referenced_by`.
- `.aitask-scripts/sitrep_tui/sitrep_tui_app.py` — main list (header row), click handling for
  the three lists, `ItemDetailScreen` body + links, `PointerViewerScreen` Markdown branch.
- `lib/shortcut_scopes.py` (scopes `sitrep_tui*`) if a binding is added/renamed.
- `tests/test_sitrep_tui_app.py` (42 tests from t2211_1) — extend.
- Reference patterns: `board/board_detail_screen.py` (labels), `board/trails_app.py` and other
  TUIs for list headers and click-vs-Enter, `aidocs/framework/tui_conventions.md`.

## Gate and first step

Re-read the landed t2211_1 / t2211_2 notes (archived plans `aiplans/archived/p2211/`). Confirm
`git diff HEAD -- .aitask-scripts/sitrep_tui/ tests/test_sitrep_tui_app.py` is empty before
editing (other sessions share the tree).

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (read the last-line verdict); new tests:
  header row present and pinned; every mapping row incl. unknown fallback; click selects /
  Enter opens on all three lists; labels styled and markup-safe with a hostile store string
  (e.g. a title containing `[b]` / `[/]`); task/plan pointers rendered via Markdown; KEY
  receipts absent from the links list while CAPTURE/BANNER are present; "About"/"Mentioned by".
- Manual: `ait sitrep tui` on the real store — the list is readable without docs; a triage
  item says what to do and how; c1's sources show "Closing message" and "Workflow result" only.

## Notes for siblings

- t2211_3 / t2211_4: replace the "how" lines with your keys; keep the mapping table the single
  source.
- t2211_6: document the "What to do" column and the plain source labels.
- t2211_7: add checklist items for the above.
