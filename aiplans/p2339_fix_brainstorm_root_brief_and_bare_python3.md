---
Task: t2339_fix_brainstorm_root_brief_and_bare_python3.md
Base branch: main
Output branch: main
---

# t2339 — Fix brainstorm root brief (frontmatter) and bare-python3 shell bridges

## Context

Both bugs turned up while t2278_5 drove the real TUIs for the docs screenshots.

1. **Brainstorm brief shows YAML frontmatter.** `aitask_brainstorm_init.sh:166`
   copies the whole task file into the spec, and two readers take "the first
   non-empty lines that don't start with `---`". Those lines are the
   frontmatter, so the brief reads `priority: medium | effort: medium`:
   - `brainstorm_session.py:154-161`: `init_session` derives the root node's
     `description`, which is **persisted** into `n000_init`.
   - `brainstorm_app.py:5068-5074`: the Browse tab's `Brief:` line, re-derived
     from the stored `initial_spec` on every render.

   Sessions that already exist keep the bad persisted `n000_init` description.
   Four render sites read it as stored: `brainstorm_app.py:1150` (operation
   rows), `brainstorm_app.py:5130` (Browse node list),
   `brainstorm_dag_display.py:136` (graph labels) and `widgets.py:557` (node
   detail). Fixing only init and `Brief:` would put a clean Brief next to a
   root still labelled `priority: medium`.
2. **Shell bridges ignore `AIT_PYTHON`.** `lib/launch_modes_sh.sh:24` uses
   `${_AIT_RESOLVED_PYTHON:-python3}`. Under a scratch `HOME`, `python3` on PATH
   is the `~/.aitask/bin/python3` wrapper, which runs
   `$HOME/.aitask/venv/bin/python` and fails. That kills `aitask_crew_init.sh`,
   and so `ait brainstorm init`, even when `AIT_PYTHON` is set. **The same
   line is copied in `lib/followup_kinds_sh.sh:40` and
   `lib/plan_paths_sh.sh:45`**, so all three bridges are fixed together.

Spec storage (`initial_spec`, the `b` full-text view, the proposal body) is
unchanged. The task also asks for the `brainstorm_browse_tab` docs screenshot
to be regenerated once the fix is in. That is **in scope** (step 4).

## Implementation

### 1. Brainstorm: strict frontmatter detection + shared brief derivation

`.aitask-scripts/brainstorm/brainstorm_session.py` (it already imports `yaml`):

```python
def _split_spec_frontmatter(spec: str) -> list[str]:
    """Return the spec's lines with a leading YAML frontmatter block removed.

    A block counts as frontmatter only when ALL hold:
      - line 0 is exactly ``---`` (trailing whitespace ignored);
      - a later line is exactly ``---`` at column 0 (an indented ``---`` inside
        a YAML block scalar is content, not the closing delimiter);
      - the text between parses (yaml.safe_load) to a non-empty dict.
    Anything else (plain Markdown between two ``---`` rules, unclosed block,
    invalid YAML, a scalar/list) is returned unchanged.
    """
    lines = spec.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return lines
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            try:
                meta = yaml.safe_load("\n".join(lines[1:i]))
            except yaml.YAMLError:
                return lines
            return lines[i + 1:] if isinstance(meta, dict) and meta else lines
    return lines


def spec_brief_lines(spec: str) -> list[str]:
    """Non-empty body lines of a spec, used for brief/preview text."""
    return [ln for ln in _split_spec_frontmatter(spec)
            if ln.strip() and not ln.startswith("---")]


def _brief_from_lines(lines: list[str]) -> str:
    # exactly today's truncation rule (80 chars + "…", fallback text)
    ...

def root_brief(spec: str) -> str:
    return _brief_from_lines(spec_brief_lines(spec))


def _legacy_root_brief(spec: str) -> str:
    """The pre-t2339 derivation, frozen. Used ONLY to recognise a root
    description that the old init generated. Never used for new output."""
    return _brief_from_lines([ln for ln in spec.splitlines()
                              if ln.strip() and not ln.startswith("---")])


def display_node_description(session_path, node_id, node_data,
                             session_data=None) -> str:
    """Stored description, except a pre-t2339 generated n000_init brief.

    Returns ``root_brief(initial_spec)`` only when ALL hold: ``node_id`` is
    ``n000_init``; the session has no ``initial_proposal_file`` (an imported
    proposal's description is the initializer's, never rewritten); and the
    stored description is byte-equal to ``_legacy_root_brief(initial_spec)``.
    Byte equality is the identity rule: a description someone edited by hand,
    or one already correct, never matches. Anything else returns the stored
    value unchanged. ``session_data`` is read lazily (br_session.yaml), and
    only for ``n000_init``.

    Never raises for session trouble. If br_session.yaml is missing,
    unreadable or malformed (``agentcrew_utils.read_yaml`` raises), or not a
    dict, or ``initial_spec`` is not a non-empty str, or the stored description
    is not a str, it returns the stored description unchanged. A node that
    renders today keeps rendering.
    """
```

- `init_session` uses `brief = root_brief(initial_spec)` in its non-proposal
  branch.
- `brainstorm_app.py:~5070`: `preview_lines = spec_brief_lines(spec)[:2]`.
- **Display-time, no writes.** Route all four description render sites through
  `display_node_description`, passing the app's `self.session_data` where it
  is in scope:
  `brainstorm_app.py:1150`, `brainstorm_app.py:5130`,
  `brainstorm_dag_display.py:136` (it already has `session_path`) and
  `widgets.py:557`. Display-time keeps read-only (completed/archived) sessions
  correct too, and it leaves the session worktree untouched. Agents read the
  full spec, not this label.
  `brainstorm_session.py:484`'s `Imported proposal (awaiting reformat):` check
  keeps reading the raw stored value; it is control flow, not display. In the
  app, read the session data as `getattr(self, "session_data", None)`: smoke
  apps such as `test_brainstorm_browse_view.py` never set it.

### 1b. Render task-derived text literally at the presentation boundary

This fix puts task-body lines into widgets that parse markup. Checked against
the installed Textual 8.2.7: `- [x] done` renders as `-  done`, and
`` use `[/]` here `` raises `MarkupError`, backticks included. Agent-written
node descriptions already reach the same sites. `rich.markup.escape` and
`textual.markup.escape` both double a backslash that sits before `[`
(`path\[x]` → `path\\[x]`). So the fix is **Textual's literal substitution**,
`Content.from_markup("<fixed markup> $desc", desc=text)`. It rendered every
probe exactly, including `$`, `\` and `[/]`, and it coexists with theme
variables (`[bold $accent]…[/] $desc` → correct span). Sites:

- `widgets.py` `NodeRow.render`: return
  `Content.from_markup(f"{mark} [bold]$nid[/]{head_marker}  $desc", nid=…, desc=self.node_description)`.
  `mark` and `head_marker` are fixed framework markup and stay interpolated.
- `widgets.py:~557` node detail: `Static(Content.from_markup("[bold $accent]Description:[/] $desc", desc=desc), classes="meta_field")`.
- `brainstorm_app.py:~1157` (operation rows built from node descriptions):
  `OperationRow` is shared with callers that pass intentional markup
  (`modals.py:1333`, `brainstorm_app.py:929/1104/5322`), so it must not escape
  globally. Add an opt-in `literal_description: bool = False` to
  `OperationRow`. When it is True, `render()` builds `Content.from_markup` with
  `$desc` (in both the enabled and disabled forms). Pass it only from the
  node-description call site.
- `brainstorm_app.py:~5074` `Brief:` line. The hint `[press b for full text]`
  is itself bracketed text: today's markup parse consumes it, and so would a
  fixed-markup template (probe: `'Brief: x  '`). Substitute both pieces:
  `Content.from_markup("Brief: $preview  $hint", preview=…, hint="[press b for full text]")`.
  Assemble the label as `Content("\n").join([...])` over the other info lines.
  Those are framework-generated and keep today's rendering, as `Content(line)`
  or markup.
- `brainstorm_app.py:~5159` `_show_brief_in_detail` (the `b` full-brief
  view): `Static(preview)` parses the raw spec as markup and raises on `[/]`.
  Use `Static(preview, markup=False)`. That also keeps the
  `… (truncated — see n000_init proposal …)` suffix literal.
- `brainstorm_dag_display.py` already renders through `rich.text.Text(...)`
  (literal). No change.

Grep `tests/` for `NodeRow(...).render()`
and `OperationRow(...).render()` consumers. `test_markup_colour_contract.py`
passes `render()` into `Static(...)`, which accepts `Content`. Adjust any
`str`-only assertion, keeping what it checks.

### 2. Shell bridges: resolve through `python_resolve.sh` when available

The bridges deliberately avoid a startup dependency on `python_resolve.sh`:
crew/brainstorm test scaffolds copy `launch_modes_sh.sh` on its own. So the fix
is a **lazy, indented, conditional** source, the
`if [[ -r … ]]; then source …; fi` form that `shell_conventions.md` accepts.
It keeps today's `python3` fallback when the file is absent. In each bridge,
replace the `${_AIT_RESOLVED_PYTHON:-python3}` line with:

```bash
    local pycmd="${_AIT_RESOLVED_PYTHON:-}"
    if [[ -z "$pycmd" ]]; then
        local _lib_dir
        _lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [[ -r "$_lib_dir/python_resolve.sh" ]]; then
            # shellcheck source=python_resolve.sh
            source "$_lib_dir/python_resolve.sh"
            resolve_python >/dev/null
            pycmd="${_AIT_RESOLVED_PYTHON:-}"
        fi
    fi
    pycmd="${pycmd:-python3}"
```

`resolve_python` (`lib/python_resolve.sh`) is the single source of the order:
`$AIT_PYTHON` → venv → wrapper → `command -v python3`. Sites:
`lib/launch_modes_sh.sh` (`_ait_launch_modes_compute_pipe`; the lib dir comes
from `BASH_SOURCE`, never from the `AIT_LAUNCH_MODES_DIR` hook),
`lib/followup_kinds_sh.sh` (`followup_kinds_pipe`) and `lib/plan_paths_sh.sh`
(`_plan_paths_python`, which assigns `_AIT_PLAN_PATHS_PY`). Update each
"Defensive: … python3 from PATH" comment to match.
`website/screenshots/sample_project.py`'s `python3` shim stays. It covers
other bare-`python3` callers.

### 3. Tests

- **`tests/test_brainstorm_cli_python.py`** (it already builds a crew
  worktree and calls `init_session`):
  - `spec_brief_lines`:
    - task frontmatter → body lines only;
    - **plain Markdown `---\nFix the widget.\n---\nmore`** → keeps
      `Fix the widget.`;
    - **YAML block scalar with an indented `---`**
      (`---\ndesc: |\n  a\n  ---\nprio: x\n---\nBody`) → `["Body"]`;
    - unclosed block, invalid YAML and a no-frontmatter spec → old filtering;
    - frontmatter only → `[]`, so `init_session` gives
      `"Initial specification"`.
  - `init_session` with a task-file spec gives the body brief in `n000_init`.
  - `display_node_description`:
    - (a) a session whose `n000_init` holds the exact legacy brief → returns
      the new brief;
    - (b) the same session with `initial_proposal_file` set, and a
      description of `Imported proposal (awaiting reformat): x.md` → unchanged;
    - (c) a hand-edited description → unchanged;
    - (d) a non-root node whose description equals the legacy string →
      unchanged;
    - (e) **no `br_session.yaml`** (and, separately, a malformed one or a
      non-str `initial_spec`) with `session_data=None` → stored description,
      no exception.
  - **Browse pilot** (extend `tests/test_brainstorm_browse_view.py`, whose
    `_make_session` writes nodes without a `br_session.yaml`):
    - a root `n000_init` with no session file renders its stored description
      in the node list and in the node-detail panel (exercises (e) through the
      real widgets);
    - a legacy session (`br_session.yaml` with a frontmatter `initial_spec`,
      and `n000_init` holding the legacy brief) shows the clean root label in
      the Browse `NodeRow`;
    - a **bracketed task line**: an `initial_spec` body and a node description
      of `` - [x] done; use `[/]` here; path\[x] `` render verbatim, with no
      `MarkupError`, in the `NodeRow`, the node-detail Description field and
      the `Brief:` line. The `Brief:` line also ends with the literal
      `[press b for full text]`. Then, on the Browse tab, **press `b`** and
      assert that the `Task Brief` panel's Static shows the full spec
      verbatim, bracketed line included, with no `MarkupError`. Assert on
      rendered plain text, not the source string.
  - Unit: `OperationRow(..., literal_description=True)` renders `[/]`
    verbatim in both enabled and disabled forms. The default
    (`literal_description=False`) still interprets markup, so existing callers
    are unchanged.
- **New `tests/test_shell_bridge_python_resolve.sh`** (`tests/lib/asserts.sh`).
  Environment: a scratch `HOME` with no `.aitask`; a `python3` stub that exits
  1 placed first on `PATH`; `AIT_PYTHON` set to the real interpreter;
  `_AIT_RESOLVED_PYTHON` unset. Each case runs in a `bash -c` child:
  - `launch_modes_sh.sh`: sources, and `LAUNCH_MODES_PIPE` equals the Python
    value.
  - `followup_kinds_sh.sh`: `is_valid_followup_kind risk_mitigation` → 0.
  - `plan_paths_sh.sh`, through the **public** `plan_paths_references`: a plan
    file mentioning `` `foo/bar.py` ``, with candidates `printf 'foo/bar.py\0'`
    on stdin → output contains `foo/bar.py`.
  - Fallback control, per bridge, through the same public entry point. Copy
    the bridge into a temp lib dir **without** `python_resolve.sh`, and keep
    its Python module reachable: point the existing hook
    (`AIT_LAUNCH_MODES_DIR` / `AIT_FOLLOWUP_KINDS_DIR` / `AIT_PLAN_PATHS_DIR`)
    at the real `.aitask-scripts/lib`, so a failure can only come from the
    interpreter. Two runs of the copied bridge:
    1. **Positive control:** a working `python3` first on `PATH`, a symlink to
       the real interpreter → succeeds with the same output as the real
       bridge. This proves the copy and the hook are sound.
    2. **Negative:** the failing stub first on `PATH` → launch_modes exits
       non-zero with "failed to load launch_modes vocabulary",
       `is_valid_followup_kind` → non-zero, `plan_paths_references` →
       non-zero with empty output.
  - Pre-fix control: run once, by hand, during implementation (original lines
    under the same env → fail). The output is recorded in Final
    Implementation Notes.

### 4. Regenerate the docs screenshot (in scope)

After steps 1–3 pass, run `/aitask-docs-screenshots brainstorm_browse_tab`.
Follow its preview/apply loop and approve only the batch whose image shows a
body-text `Brief:` and root node (no `priority:`/`effort:`). Read the
resulting `website/static/imgs/aitasks_brainstorm_browse_tab.svg` to confirm
it, then run `python3 website/check_screenshots.py`. If the skill cannot run
here (tmux/env failure), stop and agree a tracked follow-up with the user
before calling the requirement deferred.

## Verification

- `bash tests/test_shell_bridge_python_resolve.sh`
- `python3 -m pytest tests/test_brainstorm_cli_python.py tests/test_brainstorm_session.py tests/test_launch_modes.py tests/test_plan_paths.py -q`,
  plus the brainstorm TUI tests that touch the edited render sites
  (`ls tests | grep brainstorm` → the `*_browse_view`, `*_node_detail_panel`,
  `*_tab_switch`, `*_dag*`, `*node_action*`, `*operation*` modules), plus
  `tests/test_markup_colour_contract.py` (NodeRow/OperationRow mark colours
  must still paint after `render()` returns `Content`).
- Bridge consumers: `bash tests/test_crew_init.sh`,
  `bash tests/test_crew_setmode.sh`, `bash tests/test_brainstorm_cli.sh`,
  `bash tests/test_plan_paths_seam.sh`,
  `python3 -m pytest tests/test_shell_startup_closure.py -q`, and the
  followup-kind tests (`ls tests | grep -i followup`).
- `shellcheck` on the three bridges.
- Manual repro from the task: `HOME=<scratch>` and
  `AIT_PYTHON=<real venv python>`, then
  `bash -c 'source .aitask-scripts/lib/launch_modes_sh.sh'` succeeds.
- Step 4's screenshot check.

## Step 9 (Post-Implementation)

Current-branch mode: commit the code and the regenerated screenshot
(`bug: … (t2339)`), commit the plan with `aitask_task_commit.sh`, then archive
per task-workflow Step 9.

## Risk

### Code-health risk: medium
- `NodeRow.render` (and `OperationRow` in literal mode) change from returning
  a markup `str` to returning `Content`. The mark/HEAD colour spans and any
  test that compares `render()` as a `str` could break. Bounded to two
  widgets, and checked by `test_markup_colour_contract.py` plus the Browse
  pilots in step 3 · severity: medium · → mitigation: none needed (in-plan
  tests)
- The three bridges are on hot paths (`ait create`/`ait update`, crew
  scripts), and the change can pick a different interpreter than before. On
  standard installs the venv and the wrapper reach the same Python, and the
  absent-file fallback is unchanged. Covered by step 3's tests and the
  existing consumer tests · severity: low · → mitigation: none needed
  (in-plan tests)
- `display_node_description` adds a branch at four render sites. It is pure,
  byte-equality gated, and limited to `n000_init` · severity: low · →
  mitigation: none needed (in-plan tests)

### Goal-achievement risk: low
- Residual: a plain-Markdown spec whose `---`-fenced block happens to parse as
  a YAML mapping (e.g. `---\nNote: x\n---`) is still read as frontmatter.
  Brainstorm specs come from task files, so this is accepted · severity: low ·
  → mitigation: none needed

## Post-Review Changes

### Change Request 1 (2026-11-22 09:20)
- **Requested by user:** (1) `_split_spec_frontmatter` caught only
  `yaml.YAMLError`, but `yaml.safe_load` raises `ValueError` for an impossible
  date (`review_on: 2026-02-29`); `init_session` wrote `br_session.yaml` before
  failing on `n000_init`, and display raised on an older session with that
  spec. (2) The bridges sourced `python_resolve.sh` before checking
  `AIT_PYTHON`; its top-level `$HOME` expansion aborts a `set -u` caller with
  HOME unset — `aitask_crew_init.sh --help` with `PATH=/usr/bin:/bin
  AIT_PYTHON=/usr/bin/python3` and no HOME went from exit 0 (baseline) to 1.
  Both reproduced and confirmed.
- **Changes made:**
  - `_split_spec_frontmatter` treats any exception from `yaml.safe_load` as
    "not usable frontmatter" (the documented fallback; never raises).
  - `init_session` derives the root node's brief/body/reference files BEFORE
    writing any session file.
  - Bridges: order is now cached resolution → executable `$AIT_PYTHON` →
    `python_resolve.sh` (only when HOME is set and the file is present) →
    bare `python3`. AIT_PYTHON no longer depends on the resolver file.
  - Tests: impossible-date cases (`spec_brief_lines`, `init_session`, display);
    a write-order test (patched `root_brief` raising → no session files); shell
    test now 24 checks incl. three HOME-unset cases through the real
    `aitask_crew_init.sh --help` entry point and "AIT_PYTHON honoured without
    the resolver". Mutation checks: the previous bridge version fails 7 of the
    new checks; the narrowed `except yaml.YAMLError` fails the 3 date tests.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_session.py`,
  `.aitask-scripts/lib/{launch_modes_sh,followup_kinds_sh,plan_paths_sh}.sh`,
  `tests/test_brainstorm_cli_python.py`,
  `tests/test_shell_bridge_python_resolve.sh`

### Change Request 2 (2026-11-22 09:35)
- **Requested by user:** the 24 shell checks all still passed with the
  `python_resolve.sh` call disabled in every bridge — the resolver branch was
  uncovered. Confirmed.
- **Changes made:** added a "resolver branch" section: no `AIT_PYTHON`, the
  failing `python3` stub first on PATH, and a working
  `$HOME/.aitask/venv/bin/python` — reachable only through
  `python_resolve.sh`. 28 checks now; a mutant with `resolve_python` disabled
  in all three bridges fails exactly the 4 new checks.
- **Files affected:** `tests/test_shell_bridge_python_resolve.sh`

## Final Implementation Notes
- **Actual work done:**
  - `brainstorm_session.py`: `_split_spec_frontmatter` (strict: column-0
    closing `---`, non-empty YAML mapping, any parse/construct failure → no
    frontmatter), `spec_brief_lines`, `root_brief`, frozen `_legacy_root_brief`,
    and `display_node_description` (byte-equal legacy `n000_init` brief →
    corrected brief at display time; imported proposals, edited descriptions,
    non-root nodes and any session-file trouble → stored value). `init_session`
    derives the root content before writing any file.
  - Display sites routed through the helper: Browse node list, Actions-wizard
    node rows, DAG graph labels, node-detail panel.
  - Literal rendering of task/agent text: `NodeRow.render` and the node-detail
    Description use `Content.from_markup(... $var ...)`; `OperationRow` gained
    opt-in `literal_description`; the session-status label is a literal
    `Content`; the `b` Task Brief view uses `Static(..., markup=False)`.
  - Bridges (`launch_modes_sh.sh`, `followup_kinds_sh.sh`, `plan_paths_sh.sh`):
    cached resolution → executable `$AIT_PYTHON` → lazily sourced
    `python_resolve.sh` (only with HOME set) → `python3`.
  - Tests: `tests/test_shell_bridge_python_resolve.sh` (new, 28 checks),
    `tests/test_brainstorm_cli_python.py` (+brief/display/date/write-order),
    `tests/test_brainstorm_browse_view.py` (+Browse pilots incl. bracketed text
    and `b`, +OperationRow literal tests).
  - Docs screenshot `brainstorm_browse_tab` replayed (recipe unchanged, no
    repair) and applied from reviewed batch `20261122T085803Z-959ef1`; root and
    Brief now show the task body. `check_links.py --build` and
    `check_screenshots.py` pass.
  - **Where the screenshot landed:** the applied
    `website/static/imgs/aitasks_brainstorm_browse_tab.svg` was committed by a
    concurrent session in `f7367ae8a` (t2278_6), which committed its whole
    `website/` change set before this task's code commit `6e6724c20`. The
    committed bytes are identical to reviewed batch
    `20261122T085803Z-959ef1` (verified with `cmp`), so the fixed image is on
    main; it is simply not in the `(t2339)` commit. History on shared main
    was not rewritten.
- **Deviations from plan:**
  - The whole session-status label renders literally (not only the Brief line):
    no line in it is markup, and `[READ ONLY]` was being swallowed by the markup
    parser as well.
  - Bridges honour `AIT_PYTHON` themselves, before and without the resolver
    (Change Request 1); the plan's "fallback unchanged when python_resolve.sh is
    absent" now holds only when `AIT_PYTHON` is unset.
- **Issues encountered:**
  - `rich`/`textual` `escape()` double a backslash before `[`; `Content.from_markup`
    variable substitution renders every probe verbatim, so it was used instead.
  - A `str`-render helper in the pilots compared markup source, not rendered
    text, and let the pre-fix NodeRow pass its first assertion; it now parses
    `str` renders with `textual.markup.to_content` like Textual does.
  - Review rounds: impossible YAML date (`ValueError`), HOME-unset `set -u`
    abort, uncovered resolver branch — see Post-Review Changes.
- **Pre-fix control (bridges, scratch HOME, failing `python3` stub first on
  PATH, `AIT_PYTHON` set):** `launch_modes_sh.sh` → "stub python3: broken
  wrapper / error: failed to load launch_modes vocabulary"; `followup_kinds_sh`
  → `is_valid_followup_kind risk_mitigation` rc=1; `plan_paths_sh` →
  `_plan_paths_python` = `python3`. Post-fix all three succeed.
- **Key decisions:** display-time correction (no writes) so read-only sessions
  are fixed too; byte equality to the frozen legacy derivation as the identity
  rule; `OperationRow` literal mode opt-in because other callers pass markup.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/python_resolve.sh:38 — top-level `$HOME` expansion (PYPY_VENV_DIR default) aborts any `set -u` script that sources it at startup when HOME is unset (bridges now guard it; direct sourcers still crash)`
