---
Task: t2371_escape_configrow_render_markup.md
Base branch: main
Output branch: main
---

# t2371 — Render `ConfigRow` data literally (no markup parsing of values)

## Context

`ConfigRow.render` (`.aitask-scripts/lib/profile_editor.py:619-641`) interpolates
`self.key` / `self.value` into a markup string. Profile YAML values (`description`,
`default_email`, CSV lists) reach it unchanged, so `[/bold]x` raises `MarkupError` in
the settings TUI Profiles tab and in the wide `ProfileEditScreen`.

**Escaping is not a sufficient fix (verified by probe, Textual 8.2.7).** Passing a
value through `rich.markup.escape` before Textual's `Content.from_markup` still
corrupts it:

| value | drawn |
|---|---|
| `[ on red]note` | `note` |
| `trail\` | `trail\\` |

The same loss would hit a preset name inside the `(preset: …)` annotation. So data
must **never pass through the markup parser**. `Content.from_markup(template, var=…)`
substitution and `Content.assemble((text, style), …)` both keep every probed value
literal: `[/bold]x`, `[ on red]note`, `trail\`, `$key`, `\[x]`, `[dim]`.

**Second constraint: intentional markup on `value`.** Some settings_app callers append
trusted annotations to `value`:
- `settings_app.py:2865` `(framework default)`
- `:2933` / `:2944` `_get_verified_label()`
- `:3498` / `:3601` `(preset: …)`

The artifacts branch row pre-escapes at `:4227` / `:4368`. Data contract (verified):
profile rows treat `row.value` as raw data (`collect_profile_values`
`profile_editor.py:827/837`, edit seeds `profile_editor.py:1105`,
`settings_app.py:2626`). Non-profile settings rows read `row.raw_value`.

**Pre-existing, kept as-is (user decision):** the `[PROJECT]` / `[USER]` badge has
never drawn. Textual parses it as an unknown tag, so a mounted row shows `    k:  v`.
This task **preserves today's drawn output exactly**. Restoring the badge is
recorded as an upstream defect for a follow-up (Step 8b).

## Design

- `ConfigRow.render` returns a `textual.content.Content` built with
  `Content.assemble`. `key` and `value` are literal text segments with explicit
  styles, and are never parsed.
- New kwarg/attribute `suffix: str | Content = ""`. A `Content` is appended as is. A
  `str` is **trusted static markup**, parsed with `Content.from_markup`. A caller
  embedding data in a suffix must build a `Content` with
  `Content.from_markup("…$var…", var=data)`.
- Drawn output for ordinary values stays identical to today in **text and style**.
  In today's markup (`[#50FA7B][PROJECT][/]`), `[/]` closes the bogus `[PROJECT]`
  tag, so the layer color stays open to the end of the line. Probe spans:
  wide `Span(2, end, '#50FA7B')` over `  k:  v`, then `bold` on `k:`; subordinate
  `Span(8, end, '#FFB86C')` over `  uv  (d to remove)`, then `dim` on the hint;
  compact has no layer color. So the non-compact forms build the post-badge tail as
  `Content` and apply `tail.stylize_before(layer_color)`, where `layer_color` is
  `#FFB86C` for `user` and `#50FA7B` otherwise. Probe-verified, this yields the same
  span list and order: color first, then the inner bold/dim spans. The badge text
  stays empty, and a comment points at the follow-up.

## Steps

1. **`.aitask-scripts/lib/profile_editor.py` — `ConfigRow`**
   - Import `from textual.content import Content`.
   - `__init__`: add `suffix: str | Content = ""` → `self.suffix`. Docstring explains
     the literal-value / trusted-suffix contract.
   - Helper `_suffix_content()`: return `self.suffix` if it is a `Content`, else
     `Content.from_markup(self.suffix)` (`Content("")` when empty).
   - `render` (one `Content.assemble` per form, same spacing as today):
     - compact: `"  ", (f"{key}:", "bold"), "\n    ", value, suffix`
     - subordinate: `Content.assemble("      ", pad, "└ ", tail)` with
       `tail = Content.assemble("  ", value, suffix, hint).stylize_before(layer_color)`.
       `hint` is `"  "` + `("(d to remove)", "dim")` when `has_override` (the check
       stays on raw `self.value`).
     - wide: `Content.assemble("  ", pad, tail)` with
       `tail = Content.assemble("  ", (f"{key}:", "bold"), "  ", value, suffix).stylize_before(layer_color)`
     - Comment at the badge position: `[PROJECT]`/`[USER]` text has never drawn
       (parsed as a markup tag), and only its color leaked onto the rest of the row.
       It is kept that way to preserve output; see the follow-up.
2. **`.aitask-scripts/settings/settings_app.py` — move annotations into `suffix`:**
   - `_emit_launch_mode_rows` (~2862): `value=framework_default`,
     `suffix="  [dim](framework default)[/dim]"` (static markup, str OK).
   - Agent defaults rows (~2930 / ~2942): `value=proj_raw` / `user_raw`,
     `suffix=self._get_verified_label(...)`. The label is a derived numeric string, so
     it stays as `str` markup and its return contract is unchanged (pinned by
     `tests/test_settings_verifiedstats_windows.py`). It is `""` for the
     `(not set)` / `(inherits project)` rows.
   - Project config row (~3492) and `_handle_project_config_edit` (~3595): plain
     `display` in `value`, and
     `suffix=Content.from_markup("  [dim](preset: $p)[/dim]", p=preset_name)` when
     a preset matches. The edit handler **resets `row.suffix = ""`** when none
     matches.
   - Artifacts branch row (`:4227`) and edit (`:4368`): drop the call-site
     `escape()`, because the value is now literal. Keep `escape(str(exc))` in the
     notify, which is a markup sink.
   - Other sites (tmux, default_profiles, synth `(not set)` rows, artifacts default,
     profile string edits) pass plain text and need no change.
3. **`tests/test_profile_editor_narrow.py:211`**: `assertIn("[PROJECT]", row.render())`
   asserted against the raw markup string, which never matched the drawn row. Replace
   it with an assertion on the drawn wide row (`drawn_rows(row)`), which shows
   `description:` and the value on one line.
4. **New `tests/test_configrow_markup_escape.py`** (unittest + Textual `run_test`).
   Hostile set: `[/bold]x`, `[ on red]note`, `trail\`, `[b]k`, `\[x]`, `$key`.
   Assertions use **drawn text** (`render_lines`) on mounted rows:
   - **Exact display, every form:** wide, subordinate and compact rows with each
     hostile value as key and as value draw the value exactly once and verbatim. The
     wide row draws exactly `f"    {key}:  {value}"` (rstripped), which also pins
     today's layout.
   - **Style equivalence oracle (safe values):** for each form (wide project, wide
     user, subordinate with and without the hint, with `extra_indent`, with a str
     suffix, compact), mount the new `ConfigRow` beside a reference `Static`. The
     reference returns `Content.from_markup(<today's exact format string>)` built
     from the same safe key and value. Assert that the drawn `render_lines`
     segments are equal in **text and style**, cell for cell. Do the same on raw
     `Content`, with equal `plain` and equal `spans` lists including order.
   - **Suffix:** a str suffix `"  [dim](framework default)[/dim]"` draws
     `(framework default)` without a literal `[dim]`. A `Content` suffix with a
     hostile preset name draws `(preset: [ on red]note)` literally.
   - **ProfileEditScreen wide:** `description` set to each hostile value. The
     `#profile_str_description__modal` row draws it verbatim, and `collect_profile_values`
     returns it unchanged.
   - **Settings Profiles tab:** a tmp project with `aitasks/metadata/profiles/p.yaml`
     (`description: "[/bold]x"`), following the fixture pattern of
     `tests/test_settings_default_profiles_unknown_keys.py`. Mount `SettingsApp` and
     open the Profiles tab. The description row draws `[/bold]x`, and its `value`
     is raw.
   - **Preset annotation lifecycle (real Project Config row):** with
     `test_command: [pytest]`, the row draws `(preset: Python (pytest))`. Then set
     `_editing_project_row_id` and call `_handle_project_config_edit({"key": "test_command",
     "value": "make check"})`. The redrawn row shows `make check` and no `(preset:`
     (catches a stale suffix).
   - **Artifacts branch, no double escape:** the YAML-load case uses malformed
     branch text `backends.gitbranch.branch: "a[b]"`. Loading does not validate, and
     the row draws `a[b]` with no backslash. The edit case goes through the real
     `EditArtifactBranchScreen` with a valid replacement (`my-store`, since git
     refuses `[`, `\` and the like, and the screen validates before the handler runs).
     The redrawn row shows `my-store` and no escape residue. Literal trailing
     backslashes are covered by the profile tests.
   - **Pre-fix control:** write the test file first and run it against the unmodified
     code. Expected: the hostile wide/subordinate/ProfileEditScreen/Profiles-tab cases
     fail (`MarkupError` or corrupted text), and the plain-layout, style-oracle and
     preset-lifecycle cases pass. The oracle passing on old code proves the
     reference strings really are today's output. Record each case's pre-fix outcome in Final Implementation Notes.
     Nothing is stashed or restored.
### Post-phase (risk mitigations)

- **configrow_render_caller_audit:** grep `.aitask-scripts/`, `tests/` and `website/`
  for `ConfigRow` instances whose `.render()` result is string-handled: `in`,
  `str()` compared to markup, `+`, or `.startswith`. That covers direct calls and
  rows found via `query(ConfigRow)`. Fix every hit and list the inventory in Final
  Implementation Notes.

5. **Regression runs:**
   - `python3 -m pytest tests/test_configrow_markup_escape.py tests/test_profile_editor_narrow.py tests/test_settings_superseded_models.py tests/test_settings_artifacts_tab.py tests/test_settings_project_config_value_types.py tests/test_settings_default_profiles_unknown_keys.py tests/test_settings_learn_skill_guide.py tests/test_settings_verifiedstats_windows.py -q`
   - Full suite: `bash tests/run_all_python_tests.sh --test-dir tests`. Read only the
     final verdict line.

## Verification

- New tests pass, and the pre-fix control shows the hostile cases failing on the old
  code.
- Existing settings and profile-editor tests pass. That includes the superseded-note
  clipping control, whose row layout is unchanged, and the artifacts hostile-value
  tests.
- Final Implementation Notes list the badge as an upstream defect:
  `profile_editor.py ConfigRow.render — [PROJECT]/[USER] badge never draws (parsed as markup tag)`.

## Step 9 (Post-Implementation)

Current-branch mode: no merge step. Standard Step 9 archival after the Step 8
commit.

## Risk

### Code-health risk: low
- Return type changes from `str` to `Content`. Any external caller that string-ops
  `ConfigRow.render()` breaks. Inventory: only `tests/test_profile_editor_narrow.py:211`
  (updated in step 3). · severity: low · → mitigation: inline post-phase configrow_render_caller_audit

### Goal-achievement risk: low
None identified. The probe shows the chosen primitives keep every hostile value
literal, and drawn-text assertions test what users see rather than intermediate
strings.

### Planned mitigations
- timing: post-phase | name: configrow_render_caller_audit | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: render() str→Content return-type change | desc: repo-wide grep for ConfigRow .render() consumers that treat the result as str; fix any found
