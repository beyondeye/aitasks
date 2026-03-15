---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [contribution]
folded_tasks: [373, 374]
assigned_to: dario-e@beyond-eye.com
issue: https://github.com/beyondeye/aitasks/issues/8
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
created_at: 2026-03-15 16:13
updated_at: 2026-03-15 16:21
---

## Merged Contribution Issues

Source issues: #5, #8

---

### Issue #5: [Contribution] Add verified skill stats for non-default skills in settings TUI

Issue created: 2026-03-12 11:00:11

## Contribution: Add verified skill stats for non-default skills in settings TUI

### Scope
enhancement

### Motivation
Skills without configured defaults still accumulate verified stats but have no way to view them in the TUI. This enhancement adds a read-only section to the agent tab showing top agent/model combos by verified score for non-default skills.

### Proposed Merge Approach
Maintainer should review integration with existing agent tab layout

### Framework Version
0.10.0

### Changed Files

| File | Status |
|------|--------|
| `.aitask-scripts/settings/settings_app.py` | Modified |

### Code Changes

#### `.aitask-scripts/settings/settings_app.py`

*Preview — full diff available in raw view of this issue*

```diff
--- c/.aitask-scripts/settings/settings_app.py
+++ w/.aitask-scripts/settings/settings_app.py
@@ -1796,6 +1796,54 @@ class SettingsApp(App):
         detail = _format_op_stats(op_agg, compact=True)
         return f" [dim]all providers: {detail}[/dim]"
 
+    def _collect_non_default_skill_stats(self) -> dict[str, list[dict]]:
+        """Collect verified stats for skills not in the operation defaults.
+
+        Returns {skill_name: [{agent, model, score, detail}, ...]} with at most
+        3 entries per skill, sorted by all-time average score descending.
+        """
+        project_defaults = self.config_mgr.codeagent_project.get("defaults", {})
+        local_defaults = self.config_mgr.codeagent_local.get("defaults", {})
+        default_keys = (
+            set(OPERATION_DESCRIPTIONS.keys())
+            | set(project_defaults.keys())
+            | set(local_defaults.keys())
+        )
+
+        skill_candidates: dict[str, list[dict]] = {}
+
+        for agent, pdata in self.config_mgr.models.items():
+            for m in pdata.get("models", []):
+                if m.get("status", "active") == "unavailable":
+                    continue
+                name = m.get("name", "?")
+                vs = m.get("verifiedstats", {})
+                for skill, buckets in vs.items():
+                    if skill in default_keys:
+                        continue
+                    if not isinstance(buckets, dict):
+                        continue
+                    at = buckets.get("all_time", {})
+                    runs = at.get("runs", 0)
+                    if runs <= 0:
+                        continue
+                    detail = _format_op_stats(buckets, compact=True)
+                    if skill not in skill_candidates:
+                        skill_candidates[skill] = []
+                    skill_candidates[skill].append({
+                        "agent": agent,
+                        "model": name,
+                        "score": _bucket_avg(at),
+                        "detail": detail,
+                    })
+
+        result: dict[str, list[dict]] = {}
+        for skill in sorted(skill_candidates.keys()):
+            entries = skill_candidates[skill]
```

<!-- full-diff:.aitask-scripts/settings/settings_app.py
```diff
--- c/.aitask-scripts/settings/settings_app.py
+++ w/.aitask-scripts/settings/settings_app.py
@@ -1796,6 +1796,54 @@ class SettingsApp(App):
         detail = _format_op_stats(op_agg, compact=True)
         return f" [dim]all providers: {detail}[/dim]"
 
+    def _collect_non_default_skill_stats(self) -> dict[str, list[dict]]:
+        """Collect verified stats for skills not in the operation defaults.
+
+        Returns {skill_name: [{agent, model, score, detail}, ...]} with at most
+        3 entries per skill, sorted by all-time average score descending.
+        """
+        project_defaults = self.config_mgr.codeagent_project.get("defaults", {})
+        local_defaults = self.config_mgr.codeagent_local.get("defaults", {})
+        default_keys = (
+            set(OPERATION_DESCRIPTIONS.keys())
+            | set(project_defaults.keys())
+            | set(local_defaults.keys())
+        )
+
+        skill_candidates: dict[str, list[dict]] = {}
+
+        for agent, pdata in self.config_mgr.models.items():
+            for m in pdata.get("models", []):
+                if m.get("status", "active") == "unavailable":
+                    continue
+                name = m.get("name", "?")
+                vs = m.get("verifiedstats", {})
+                for skill, buckets in vs.items():
+                    if skill in default_keys:
+                        continue
+                    if not isinstance(buckets, dict):
+                        continue
+                    at = buckets.get("all_time", {})
+                    runs = at.get("runs", 0)
+                    if runs <= 0:
+                        continue
+                    detail = _format_op_stats(buckets, compact=True)
+                    if skill not in skill_candidates:
+                        skill_candidates[skill] = []
+                    skill_candidates[skill].append({
+                        "agent": agent,
+                        "model": name,
+                        "score": _bucket_avg(at),
+                        "detail": detail,
+                    })
+
+        result: dict[str, list[dict]] = {}
+        for skill in sorted(skill_candidates.keys()):
+            entries = skill_candidates[skill]
+            entries.sort(key=lambda c: (-c["score"], c["agent"], c["model"]))
+            result[skill] = entries[:3]
+        return result
+
     def _populate_agent_tab(self):
         container = self.query_one("#agent_content", VerticalScroll)
         container.remove_children()
@@ -1865,6 +1913,32 @@ class SettingsApp(App):
                     f"[dim italic]{desc}[/dim italic]", classes="op-desc",
                 ))
 
+        # --- Verified Skill Stats (non-default skills) ---
+        skill_stats = self._collect_non_default_skill_stats()
+        if skill_stats:
+            container.mount(Label(""))  # visual spacer
+            container.mount(Label(
+                "Verified Skill Stats [dim](read-only)[/dim]",
+                classes="section-header",
+            ))
+            container.mount(Label(
+                "[dim]Skills without defaults that have verified stats. "
+                "Top 3 agent/model combos by score.[/dim]",
+                classes="section-hint",
+            ))
+            for skill, entries in skill_stats.items():
+                container.mount(Label(
+                    f"  [bold]{skill}[/bold]",
+                    classes="model-row",
+                ))
+                for entry in entries:
+                    agent_model = f"{entry['agent']}/{entry['model']}"
+                    detail = entry["detail"]
+                    container.mount(Label(
+                        f"      {agent_model}  [dim]{detail}[/dim]",
+                        classes="op-desc",
+                    ))
+
         container.mount(Label(
             "[dim]Enter: edit  |  d: remove local preference  |  "
             "\u2191\u2193: navigate  |  a/b/c/m/p: switch tabs[/dim]",
```
-->


<!-- aitask-contribute-metadata
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
based_on_version: 0.10.0
fingerprint_version: 1
areas: scripts
file_paths: .aitask-scripts/settings/settings_app.py
file_dirs: .aitask-scripts/settings
change_type: enhancement
auto_labels: area:scripts,scope:enhancement
-->

---

### Issue #8: [Contribution] Add verify_build preset editor to settings TUI

Issue created: 2026-03-12 22:39:18, last updated: 2026-03-12 22:39:30

## Contribution: Add verify_build preset editor to settings TUI

### Scope
enhancement

### Motivation
Editing verify_build as a plain string is error-prone for multi-command configs; a dedicated YAML editor with presets improves usability

### Proposed Merge Approach
Needs companion file: verify_build_presets.yaml must be included alongside the Python changes for presets to work

### Framework Version
0.10.0

### Changed Files

| File | Status |
|------|--------|
| `.aitask-scripts/settings/settings_app.py` | Modified |
| `.aitask-scripts/settings/verify_build_presets.yaml` | Modified |

### Code Changes

#### `.aitask-scripts/settings/settings_app.py`

*Preview — full diff available in raw view of this issue*

```diff
--- c/.aitask-scripts/settings/settings_app.py
+++ w/.aitask-scripts/settings/settings_app.py
@@ -49,6 +49,7 @@ from textual.widgets import (  # noqa: E402
     Static,
     TabbedContent,
     TabPane,
+    TextArea,
 )
 
 # ---------------------------------------------------------------------------
@@ -329,6 +330,39 @@ def _safe_id(name: str) -> str:
     return name.replace(".", "_").replace(" ", "_").replace("-", "_")
 
 
+_PRESETS_FILE = Path(__file__).resolve().parent / "verify_build_presets.yaml"
+_BUILD_VERIFY_DOCS = "https://aitasks.io/docs/skills/aitask-pick/build-verification/"
+
+
+def _load_verify_build_presets() -> list[dict]:
+    """Load verify_build presets from the YAML file."""
+    if not _PRESETS_FILE.is_file():
+        return []
+    try:
+        with open(_PRESETS_FILE, "r", encoding="utf-8") as f:
+            data = yaml.safe_load(f)
+        if isinstance(data, dict) and "presets" in data:
+            return data["presets"]
+    except Exception:
+        pass
+    return []
+
+
+def _match_preset_name(raw_value: str, presets: list[dict]) -> str | None:
+    """Return preset name if raw_value matches a preset's value, else None."""
+    if not raw_value or not presets:
+        return None
+    try:
+        parsed = yaml.safe_load(raw_value)
+    except yaml.YAMLError:
+        parsed = raw_value
+    for preset in presets:
+        pval = preset["value"]
+        if parsed == pval:
+            return preset["name"]
+    return None
+
+
 def _normalize_model_id(cli_id: str) -> str:
     """Strip provider/ prefix from cli_id for all_providers grouping."""
     if "/" in cli_id:
```

<!-- full-diff:.aitask-scripts/settings/settings_app.py
```diff
--- c/.aitask-scripts/settings/settings_app.py
+++ w/.aitask-scripts/settings/settings_app.py
@@ -49,6 +49,7 @@ from textual.widgets import (  # noqa: E402
     Static,
     TabbedContent,
     TabPane,
+    TextArea,
 )
 
 # ---------------------------------------------------------------------------
@@ -329,6 +330,39 @@ def _safe_id(name: str) -> str:
     return name.replace(".", "_").replace(" ", "_").replace("-", "_")
 
 
+_PRESETS_FILE = Path(__file__).resolve().parent / "verify_build_presets.yaml"
+_BUILD_VERIFY_DOCS = "https://aitasks.io/docs/skills/aitask-pick/build-verification/"
+
+
+def _load_verify_build_presets() -> list[dict]:
+    """Load verify_build presets from the YAML file."""
+    if not _PRESETS_FILE.is_file():
+        return []
+    try:
+        with open(_PRESETS_FILE, "r", encoding="utf-8") as f:
+            data = yaml.safe_load(f)
+        if isinstance(data, dict) and "presets" in data:
+            return data["presets"]
+    except Exception:
+        pass
+    return []
+
+
+def _match_preset_name(raw_value: str, presets: list[dict]) -> str | None:
+    """Return preset name if raw_value matches a preset's value, else None."""
+    if not raw_value or not presets:
+        return None
+    try:
+        parsed = yaml.safe_load(raw_value)
+    except yaml.YAMLError:
+        parsed = raw_value
+    for preset in presets:
+        pval = preset["value"]
+        if parsed == pval:
+            return preset["name"]
+    return None
+
+
 def _normalize_model_id(cli_id: str) -> str:
     """Strip provider/ prefix from cli_id for all_providers grouping."""
     if "/" in cli_id:
@@ -701,6 +735,12 @@ class FuzzySelect(Container):
         """Posted when user presses Escape."""
         pass
 
+    class Highlighted(Message):
+        """Posted when highlight changes (up/down arrow or filter)."""
+        def __init__(self, value: str):
+            super().__init__()
+            self.value = value
+
     def __init__(self, options: list[dict], placeholder: str = "Type to filter...",
                  id: str | None = None):
         """
@@ -740,6 +780,8 @@ class FuzzySelect(Container):
         ]
         self.highlight_index = 0
         self._render_options()
+        if self.filtered:
+            self.post_message(self.Highlighted(self.filtered[0]["value"]))
 
     def _render_options(self):
         container = self.query_one(f"#{self._list_id}", VerticalScroll)
@@ -785,6 +827,8 @@ class FuzzySelect(Container):
         # Scroll highlighted item into view
         if options and 0 <= self.highlight_index < len(options):
             options[self.highlight_index].scroll_visible()
+        if self.filtered and 0 <= self.highlight_index < len(self.filtered):
+            self.post_message(self.Highlighted(self.filtered[self.highlight_index]["value"]))
 
 
 # ---------------------------------------------------------------------------
@@ -1305,6 +1349,156 @@ class EditStringScreen(ModalScreen):
         self.dismiss(None)
 
 
+class EditVerifyBuildScreen(ModalScreen):
+    """Modal for editing verify_build with multi-line TextArea and preset support."""
+
+    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]
+
+    def __init__(self, key: str, current_value: str, presets: list[dict] | None = None):
+        super().__init__()
+        self.key = key
+        self.current_value = current_value
+        self.presets = presets or []
+
+    @staticmethod
+    def _to_block_yaml(value: str) -> str:
+        """Convert compact YAML to readable block-style for editing."""
+        if not value:
+            return ""
+        try:
+            parsed = yaml.safe_load(value)
+            if isinstance(parsed, list):
+                return yaml.safe_dump(parsed, default_flow_style=False).strip()
+        except yaml.YAMLError:
+            pass
+        return value
+
+    @staticmethod
+    def _to_compact_yaml(text: str) -> str:
+        """Convert edited text back to compact storage format."""
+        text = text.strip()
+        if not text:
+            return ""
+        try:
+            parsed = yaml.safe_load(text)
+            if isinstance(parsed, list):
+                return yaml.safe_dump(
+                    parsed, default_flow_style=True, sort_keys=False,
+                ).strip()
+            if isinstance(parsed, str):
+                return parsed
+        except yaml.YAMLError:
+            pass
+        return text
+
+    def compose(self) -> ComposeResult:
+        display_value = self._to_block_yaml(self.current_value)
+        with Container(id="edit_dialog"):
+            yield Label(f"Edit: [bold]{self.key}[/bold]", id="edit_title")
+            yield Label(
+                "[dim]Enter a single command string, or a YAML list "
+                "(one command per line, prefix each with '- ')[/dim]",
+                classes="section-hint",
+            )
+            yield TextArea(display_value, id="edit_textarea", language="yaml")
+            with Horizontal(id="edit_buttons"):
+                if self.presets:
+                    yield Button("Load Preset", variant="primary", id="btn_load_preset")
+                yield Button("Save", variant="success", id="btn_edit_ml_save")
+                yield Button("Cancel", variant="default", id="btn_edit_ml_cancel")
+
+    @on(Button.Pressed, "#btn_edit_ml_save")
+    def do_save(self):
+        text = self.query_one("#edit_textarea", TextArea).text
+        value = self._to_compact_yaml(text)
+        self.dismiss({"key": self.key, "value": value})
+
+    @on(Button.Pressed, "#btn_edit_ml_cancel")
+    def do_cancel(self):
+        self.dismiss(None)
+
+    @on(Button.Pressed, "#btn_load_preset")
+    def do_load_preset(self):
+        self.app.push_screen(
+            VerifyBuildPresetScreen(self.presets),
+            callback=self._handle_preset_selected,
+        )
+
+    def _handle_preset_selected(self, result):
+        if result is None:
+            return
+        value = result["value"]
+        if isinstance(value, list):
+            text = yaml.safe_dump(value, default_flow_style=False).strip()
+        else:
+            text = str(value)
+        self.query_one("#edit_textarea", TextArea).load_text(text)
+
+    def action_cancel(self):
+        self.dismiss(None)
+
+
+class VerifyBuildPresetScreen(ModalScreen):
+    """Modal for selecting a verify_build preset with fuzzy search and preview."""
+
+    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]
+
+    def __init__(self, presets: list[dict]):
+        super().__init__()
+        self.presets = presets
+        self._preset_map = {p["name"]: p for p in presets}
+
+    def compose(self) -> ComposeResult:
+        options = [
+            {
+                "value": p["name"],
+                "display": p["name"],
+                "description": p.get("description", ""),
+            }
+            for p in self.presets
+        ]
+        with Container(id="picker_dialog"):
+            yield Label("Select Build Preset", id="picker_title")
+            yield FuzzySelect(
+                options, placeholder="Type to filter presets...",
+                id="preset_picker",
+            )
+            yield Static("", id="preset_preview")
+
+    def on_mount(self):
+        if self.presets:
+            self._show_preview(self.presets[0]["name"])
+
+    def _show_preview(self, name: str):
+        preset = self._preset_map.get(name)
+        if not preset:
+            return
+        value = preset["value"]
+        if isinstance(value, list):
+            formatted = yaml.safe_dump(value, default_flow_style=False).strip()
+        else:
+            formatted = str(value)
+        try:
+            preview = self.query_one("#preset_preview", Static)
+            preview.update(f"[bold]Preview:[/bold]\n[dim]{formatted}[/dim]")
+        except Exception:
+            pass
+
+    def on_fuzzy_select_highlighted(self, event: FuzzySelect.Highlighted):
+        self._show_preview(event.value)
+
+    def on_fuzzy_select_selected(self, event: FuzzySelect.Selected):
+        preset = self._preset_map.get(event.value)
+        if preset:
+            self.dismiss(preset)
+
+    def on_fuzzy_select_cancelled(self, event: FuzzySelect.Cancelled):
+        self.dismiss(None)
+
+    def action_cancel(self):
+        self.dismiss(None)
+
+
 class NewProfileScreen(ModalScreen):
     """Modal for creating a new profile based on an existing one."""
 
@@ -1506,6 +1700,19 @@ class SettingsApp(App):
 
     /* Operation descriptions */
     .op-desc { padding: 0 0 0 5; height: 1; }
+
+    /* Verify build multi-line editor */
+    #edit_textarea { height: 10; min-height: 5; max-height: 15; }
+
+    /* Preset preview */
+    #preset_preview {
+        padding: 1 2;
+        height: auto;
+        max-height: 8;
+        background: $surface-darken-1;
+        border: tall $accent;
+        margin: 1 0 0 0;
+    }
     """
 
     TITLE = "aitasks settings"
@@ -1670,10 +1877,20 @@ class SettingsApp(App):
             # Project config editing
             if fid.startswith("project_cfg_"):
                 self._editing_project_key = focused.row_key
-                self.push_screen(
-                    EditStringScreen(focused.row_key, focused.raw_value),
-                    callback=self._handle_project_config_edit,
-                )
+                self._editing_project_row_id = focused.id
+                if focused.row_key == "verify_build":
+                    presets = _load_verify_build_presets()
+                    self.push_screen(
+                        EditVerifyBuildScreen(
+                            focused.row_key, focused.raw_value, presets=presets,
+                        ),
+                        callback=self._handle_project_config_edit,
+                    )
+                else:
+                    self.push_screen(
+                        EditStringScreen(focused.row_key, focused.raw_value),
+                        callback=self._handle_project_config_edit,
+                    )
                 event.prevent_default()
                 event.stop()
                 return
@@ -2013,18 +2230,29 @@ class SettingsApp(App):
             classes="section-hint",
         ))
 
+        vb_presets = _load_verify_build_presets()
         for key, info in PROJECT_CONFIG_SCHEMA.items():
             raw_value = self.config_mgr.project_config.get(key)
-            display_value = _format_yaml_value(raw_value) or "(not set)"
+            formatted = _format_yaml_value(raw_value)
+            display_value = formatted or "(not set)"
+            if key == "verify_build" and raw_value is not None:
+                preset_name = _match_preset_name(formatted, vb_presets)
+                if preset_name:
+                    display_value = f"{display_value}  [dim](preset: {preset_name})[/dim]"
             container.mount(ConfigRow(
                 key, display_value, config_layer="project", row_key=key,
                 id=f"project_cfg_{_safe_id(key)}_{rc}",
-                raw_value=_format_yaml_value(raw_value),
+                raw_value=formatted,
             ))
             container.mount(Label(
                 f"      [dim]{info['summary']}[/dim]",
                 classes="section-hint",
             ))
+            if key == "verify_build":
+                container.mount(Label(
+                    f"      [dim]Docs: {_BUILD_VERIFY_DOCS}[/dim]",
+                    classes="section-hint",
+                ))
 
         hbox = Horizontal(classes="tab-buttons")
         container.mount(hbox)
@@ -2073,16 +2301,24 @@ class SettingsApp(App):
         key = result["key"]
         value = result["value"]
 
-        rc = self._repop_counter
-        row_id = f"project_cfg_{_safe_id(key)}_{rc}"
+        row_id = getattr(self, "_editing_project_row_id", None)
+        if not row_id:
+            rc = self._repop_counter
+            row_id = f"project_cfg_{_safe_id(key)}_{rc}"
         try:
             row = self.query_one(f"#{row_id}", ConfigRow)
             row.raw_value = value
-            row.value = value or "(not set)"
+            display = _format_yaml_value(value) or "(not set)"
+            if key == "verify_build" and value:
+                presets = _load_verify_build_presets()
+                preset_name = _match_preset_name(value, presets)
+                if preset_name:
+                    display = f"{display}  [dim](preset: {preset_name})[/dim]"
+            row.value = display
             row.refresh()
             self.notify(f"Updated {key} — press Save to persist")
-        except Exception:
-            self.notify(f"Could not update {key}", severity="error")
+        except Exception as exc:
+            self.notify(f"Could not update {key}: {exc}", severity="error")
 
     # -------------------------------------------------------------------
     # Models tab (read-only)
```
-->


<!-- aitask-contribute-metadata
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
based_on_version: 0.10.0
fingerprint_version: 1
areas: scripts
file_paths: .aitask-scripts/settings/settings_app.py,.aitask-scripts/settings/verify_build_presets.yaml
file_dirs: .aitask-scripts/settings
change_type: enhancement
auto_labels: area:scripts,scope:enhancement
-->

## Merged from t373: more verified stats in in ait settings tui

I would like to add more verified stats for all supported skills in the Agent Defaults tab in the ait settings tui, for skills that do not have default settings and have verified stats, for each skill show the stats of the 3 top agent/model. show only skills and models with stats. ask me questions if you need clarification.

## Merged from t374: better verify build settings

currently in ait settings tui we have in the Project Config tab, the option to set the verify_build settings. drr /docs/skills/aitask-pick/build-verification/ in website documentation. there are several issue with it

First, when editing it, it still continue to show it as not set. second, in the editing dialog, we should have a multine edit, third, we should have a button the modal dialog where we edit it, to choose it from some predefined defaults from common project types, make the list of this pre-configurations dynamic, storing it in a aitask-scripts/settings/ directory in some format (like yaml) that is easily parsable end editor, with a list of entries there with common project configuration. when pressing the button to select from predefined configurations, allow to fuzzy search for the configuration name, and use top down arrows to move between currenly fuzzy selected configs, when a config is selected, show also a preview of its content in side box.

also in the project config tab, in addition toe explanation of what the verify_build option is for, add a link with the link to the build verification page in the aitasks documentation: https://aitasks.io/docs/skills/aitask-pick/build-verification/

also in the project config tab, when some verify_build value is set, show, when used, which preset build config was selected

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t373** (`t373_more_verified_stats_in_in_ait_settings_tui.md`)
- **t374** (`t374_better_verify_build_settings.md`)
