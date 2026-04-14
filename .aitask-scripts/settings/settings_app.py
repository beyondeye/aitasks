#!/usr/bin/env python3
"""aitasks Settings TUI — centralized config viewer/editor.

Browse and edit all aitasks configuration: code agent defaults, board
settings, model lists, and execution profiles.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Add .aitask-scripts/lib to path for config_utils
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
# Add .aitask-scripts to path for sibling packages (e.g. brainstorm)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tui_switcher import TuiSwitcherMixin  # noqa: E402
from agent_launch_utils import detect_git_tuis  # noqa: E402

from agent_model_picker import (  # noqa: E402
    AgentModelPickerScreen,
    FuzzySelect,
    LaunchModePickerScreen,
    MODEL_FILES,
    _bucket_avg,
    _format_op_stats,
)

from config_utils import (  # noqa: E402
    EXPORT_EXTENSION,
    _load_json,
    deep_merge,
    export_all_configs,
    import_all_configs,
    load_layered_config,
    load_yaml_config,
    local_path_for,
    save_local_config,
    save_project_config,
    save_yaml_config,
    split_config,
    validate_export_bundle,
)

from textual import on  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, Horizontal, VerticalScroll  # noqa: E402
from textual.message import Message  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import (  # noqa: E402
    Button,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
METADATA_DIR = Path("aitasks") / "metadata"
CODEAGENT_CONFIG = METADATA_DIR / "codeagent_config.json"
BOARD_CONFIG = METADATA_DIR / "board_config.json"
PROJECT_CONFIG = METADATA_DIR / "project_config.yaml"
PROFILES_DIR = METADATA_DIR / "profiles"
LOCAL_PROFILES_DIR = PROFILES_DIR / "local"
_DATA_WORKTREE = Path(".aitask-data")


def _task_git_cmd() -> list[str]:
    """Return git command prefix for task data operations."""
    if _DATA_WORKTREE.exists() and (_DATA_WORKTREE / ".git").exists():
        return ["git", "-C", str(_DATA_WORKTREE)]
    return ["git"]


_BOARD_PROJECT_KEYS = {"columns", "column_order"}
_BOARD_USER_KEYS = {"settings"}

DEFAULT_REFRESH_OPTIONS = ["0", "1", "2", "5", "10", "15", "30"]

# Profile schema: key -> (type, options)
# type: "bool", "enum", "string"
PROFILE_SCHEMA: dict[str, tuple[str, list[str] | None]] = {
    "name": ("string", None),
    "description": ("string", None),
    "skip_task_confirmation": ("bool", None),
    "default_email": ("enum", ["userconfig", "first"]),
    "create_worktree": ("bool", None),
    "base_branch": ("string", None),
    "plan_preference": ("enum", ["use_current", "verify", "create_new"]),
    "plan_preference_child": ("enum", ["use_current", "verify", "create_new"]),
    "post_plan_action": ("enum", ["start_implementation"]),
    "enableFeedbackQuestions": ("bool", None),
    "test_followup_task": ("enum", ["yes", "no", "ask"]),
    "explore_auto_continue": ("bool", None),
    "force_unlock_stale": ("bool", None),
    "done_task_action": ("enum", ["archive", "skip"]),
    "orphan_parent_action": ("enum", ["archive", "skip"]),
    "complexity_action": ("enum", ["single_task", "create_children"]),
    "review_action": ("enum", ["commit", "need_changes", "abort"]),
    "issue_action": ("enum", ["close_with_notes", "comment_only", "close_silently", "skip"]),
    "abort_plan_action": ("enum", ["keep", "discard"]),
    "abort_revert_status": ("enum", ["Ready", "Editing"]),
    "qa_mode": ("enum", ["ask", "create_task", "implement", "plan_only"]),
    "qa_run_tests": ("bool", None),
}

_UNSET = "(unset)"

# Operation descriptions shown in the Agent Defaults tab
OPERATION_DESCRIPTIONS: dict[str, str] = {
    "pick": "Model used for picking and implementing tasks (used when launching tasks from the Board TUI)",
    "explain": "Model used for explaining/documenting code (used when running explain from the Code Browser TUI)",
    "batch-review": "Model used for batch code review operations",
    "qa": "Model used for QA analysis on completed tasks (used when launching QA from the Code Browser TUI history screen)",
    "raw": "Model used for direct/ad-hoc code agent invocations (passthrough mode)",
    "explore": "Model used for interactive codebase exploration (launched via TUI switcher shortcut 'x')",
    "brainstorm-explorer": "Model for exploring solution space in brainstorming sessions",
    "brainstorm-comparator": "Model for comparing and analyzing design proposals",
    "brainstorm-synthesizer": "Model for merging and synthesizing design proposals",
    "brainstorm-detailer": "Model for creating detailed implementation plans from designs",
    "brainstorm-patcher": "Model for applying targeted tweaks to brainstorm plans",
    "brainstorm-explorer-launch-mode": "Default launch mode (headless | interactive) for the explorer brainstorm agent type",
    "brainstorm-comparator-launch-mode": "Default launch mode (headless | interactive) for the comparator brainstorm agent type",
    "brainstorm-synthesizer-launch-mode": "Default launch mode (headless | interactive) for the synthesizer brainstorm agent type",
    "brainstorm-detailer-launch-mode": "Default launch mode (headless | interactive) for the detailer brainstorm agent type",
    "brainstorm-patcher-launch-mode": "Default launch mode (headless | interactive) for the patcher brainstorm agent type",
}

# Config file descriptions shown during import
CONFIG_FILE_DESCRIPTIONS: dict[str, str] = {
    "board_config.json": "Board columns and display settings (shared/project)",
    "board_config.local.json": "Board user preferences (auto-refresh, sync)",
    "codeagent_config.json": "Default AI models per operation (shared/project)",
    "codeagent_config.local.json": "User-specific AI model overrides",
    "models_claudecode.json": "Claude Code model list and verification scores",
    "models_codex.json": "Codex CLI model list and verification scores",
    "models_geminicli.json": "Gemini CLI model list and verification scores",
    "models_opencode.json": "OpenCode model list and verification scores",
}

# Export subset categories: label -> patterns
EXPORT_CATEGORIES: dict[str, list[str]] = {
    "Agent defaults": ["*_config.json", "*_config.local.json"],
    "Model configs": ["models_*.json", "models_*.local.json"],
}

# Profile field info: key -> (short_description, detailed_description)
PROFILE_FIELD_INFO: dict[str, tuple[str, str]] = {
    "name": (
        "Display name shown when selecting a profile",
        "The profile name appears in the selection prompt when picking a task. "
        "Choose a short, descriptive name (e.g., 'fast', 'worktree', 'remote')."
    ),
    "description": (
        "Description shown below profile name during selection",
        "A brief sentence explaining the profile's purpose. Shown alongside the name "
        "in the profile selection prompt at the start of aitask-pick/aitask-explore."
    ),
    "skip_task_confirmation": (
        "Auto-confirm task selection without asking",
        "When true, skips the 'Is this the correct task?' confirmation in aitask-pick (Step 0b). "
        "The task summary is still displayed but the workflow proceeds immediately. "
        "When false or unset, the user must confirm before proceeding."
    ),
    "default_email": (
        "Email for task assignment: userconfig, first, or literal",
        "Controls how the email is resolved when claiming a task (Step 4):\n"
        "  'userconfig': from aitasks/metadata/userconfig.yaml (falls back to first in emails.txt)\n"
        "  'first': first email from aitasks/metadata/emails.txt\n"
        "  A literal email address: uses that exact email\n"
        "  (unset): prompts the user to select or enter an email"
    ),
    "create_worktree": (
        "Create a separate git worktree for the task",
        "When true, creates a new branch and worktree in aiwork/<task_name>/ (Step 5). "
        "When false, works directly on the current branch. "
        "Worktrees are useful for parallel work on multiple tasks."
    ),
    "base_branch": (
        "Branch to base new task branches on (e.g., main)",
        "Only used when create_worktree is true. Specifies the branch the new task branch "
        "is created from. Common values: 'main', 'develop'. "
        "When unset, the user is asked to choose."
    ),
    "plan_preference": (
        "Existing plan handling: use_current / verify / create_new",
        "Controls what happens when a plan file already exists (Step 6.0):\n"
        "  'use_current': skip planning, use existing plan as-is\n"
        "  'verify': enter plan mode to check if the plan is still valid\n"
        "  'create_new': discard existing plan and start fresh\n"
        "  (unset): ask the user interactively"
    ),
    "plan_preference_child": (
        "Override plan_preference for child tasks only",
        "Same values as plan_preference but only applies to child tasks. "
        "Takes priority over plan_preference when the current task is a child. "
        "Useful for e.g. always verifying child plans while reusing parent plans."
    ),
    "post_plan_action": (
        "After plan approval: start_implementation = skip checkpoint",
        "Controls what happens after the plan is approved (Step 6 checkpoint):\n"
        "  'start_implementation': proceed directly to implementation\n"
        "  (unset): ask the user whether to start, revise, or abort\n"
        "Note: plan approval via ExitPlanMode is always required and cannot be skipped."
    ),
    "enableFeedbackQuestions": (
        "Ask satisfaction feedback questions at the end of supported skills",
        "Controls whether supported skills ask for a quick satisfaction rating after completion. "
        "When false, the Satisfaction Feedback Procedure is skipped. "
        "When true or unset, feedback questions remain enabled. "
        "Use false for unattended or non-interactive workflows such as remote profiles."
    ),
    "test_followup_task": (
        "Create a testing follow-up task before archival",
        "Controls whether a follow-up task is created for testing after implementation (Step 8b):\n"
        "  'yes': always create a testing follow-up task\n"
        "  'no': never create a testing follow-up task\n"
        "  'ask': prompt the user to decide\n"
        "  (unset): same as 'ask'"
    ),
    "explore_auto_continue": (
        "Auto-continue to implementation in exploration mode",
        "Used by aitask-explore. When true, automatically continues to the implementation "
        "phase after exploration completes. When false or unset, asks the user."
    ),
    "force_unlock_stale": (
        "Auto force-unlock stale task locks without asking",
        "When true, automatically overrides stale locks held by other users/machines (Step 4). "
        "When false or unset, prompts the user to decide how to handle locked tasks."
    ),
    "done_task_action": (
        "(Remote) Done-but-unarchived tasks: archive or skip",
        "Only used by aitask-pickrem (remote/autonomous mode). Controls what happens "
        "when a picked task already has status 'Done' but hasn't been archived:\n"
        "  'archive': proceed to archive automatically\n"
        "  'skip': leave the task as-is and end the workflow"
    ),
    "orphan_parent_action": (
        "(Remote) Orphaned parent tasks: archive or skip",
        "Only used by aitask-pickrem. Controls what happens when a parent task has "
        "all children completed but the parent itself isn't archived:\n"
        "  'archive': archive the parent automatically\n"
        "  'skip': leave the parent as-is"
    ),
    "complexity_action": (
        "(Remote) Complex tasks: single_task or create_children",
        "Only used by aitask-pickrem. When a task is assessed as complex:\n"
        "  'single_task': implement as a single task regardless of complexity\n"
        "  'create_children': break into child subtasks automatically"
    ),
    "review_action": (
        "(Remote) Review decision: commit, need_changes, or abort",
        "Only used by aitask-pickrem. After implementation completes:\n"
        "  'commit': auto-commit changes without review\n"
        "  'need_changes': flag for additional changes (unusual for autonomous mode)\n"
        "  'abort': discard changes and revert task status"
    ),
    "issue_action": (
        "(Remote) Linked issue handling after archival",
        "Only used by aitask-pickrem. When the task has a linked issue:\n"
        "  'close_with_notes': post implementation notes and close the issue\n"
        "  'comment_only': post notes but leave the issue open\n"
        "  'close_silently': close without posting a comment\n"
        "  'skip': don't touch the linked issue"
    ),
    "abort_plan_action": (
        "(Remote) On abort: keep or discard plan file",
        "Only used by aitask-pickrem. When a task is aborted:\n"
        "  'keep': preserve the plan file for future reference\n"
        "  'discard': delete the plan file"
    ),
    "abort_revert_status": (
        "(Remote) Status to revert to on abort: Ready or Editing",
        "Only used by aitask-pickrem. When a task is aborted, the task status "
        "is reverted to this value:\n"
        "  'Ready': task goes back to the Ready queue\n"
        "  'Editing': task stays in Editing state"
    ),
    "qa_mode": (
        "Action after QA test plan proposal",
        "Controls what happens after /aitask-qa generates a test plan.\n"
        "  ask         — Prompt with AskUserQuestion (default)\n"
        "  create_task — Auto-create a follow-up test task\n"
        "  implement   — Implement proposed tests in current session\n"
        "  plan_only   — Export test plan to file without further action\n\n"
        "Omitting this key shows the interactive prompt.",
    ),
    "qa_run_tests": (
        "Run discovered tests during QA analysis",
        "When true (default), /aitask-qa executes discovered tests and lints.\n"
        "Set to false to skip test execution and only analyze coverage gaps.\n\n"
        "Useful when tests are slow or require special setup.",
    ),
}

# Logical grouping of profile fields for display
PROFILE_FIELD_GROUPS: list[tuple[str, list[str]]] = [
    ("Identity", ["name", "description"]),
    ("Task Selection", ["skip_task_confirmation", "default_email"]),
    ("Branch & Worktree", ["create_worktree", "base_branch"]),
    ("Planning", ["plan_preference", "plan_preference_child", "post_plan_action"]),
    ("Feedback", ["enableFeedbackQuestions"]),
    ("Post-Implementation", ["test_followup_task"]),
    ("QA Analysis", ["qa_mode", "qa_run_tests"]),
    ("Exploration", ["explore_auto_continue"]),
    ("Lock Management", ["force_unlock_stale"]),
    ("Remote Workflow", [
        "done_task_action", "orphan_parent_action", "complexity_action",
        "review_action", "issue_action", "abort_plan_action", "abort_revert_status",
    ]),
]

# Tab shortcut keys -> TabPane IDs
_TAB_SHORTCUTS = {
    "a": "tab_agent",
    "b": "tab_board",
    "c": "tab_project",
    "m": "tab_models",
    "p": "tab_profiles",
    "t": "tab_tmux",
}

PROJECT_CONFIG_SCHEMA: dict[str, dict[str, str]] = {
    "codeagent_coauthor_domain": {
        "summary": "Email domain used for custom code-agent commit coauthors",
        "detail": (
            "Stored in aitasks/metadata/project_config.yaml and shared with the team. "
            "The task workflow uses it to build code-agent coauthor emails such as "
            "codex_gpt5_3codex@aitasks.io."
        ),
    },
    "verify_build": {
        "summary": "Build verification command(s) run after implementation",
        "detail": (
            "Accepts a single shell command string or a YAML list of commands. "
            "Leave blank to disable build verification for task-workflow, "
            "aitask-pickrem, and aitask-pickweb."
        ),
    },
    "test_command": {
        "summary": "Test command(s) for QA analysis (used by /aitask-qa)",
        "detail": (
            "Shell command(s) used by /aitask-qa to run project tests. "
            "Accepts a single string or YAML list. Leave blank for auto-detection."
        ),
    },
    "lint_command": {
        "summary": "Lint command(s) for QA analysis (used by /aitask-qa)",
        "detail": (
            "Shell command(s) used by /aitask-qa to lint changed files. "
            "Accepts a single string or YAML list. Leave blank to skip."
        ),
    },
    "default_profiles": {
        "summary": "Default execution profile for each skill",
        "detail": (
            "Maps skill names to profile names (without .yaml). "
            "Valid skills: pick, fold, review, pr-import, revert, explore, pickrem, pickweb, qa. "
            "Users can override in userconfig.yaml. The --profile argument overrides both."
        ),
    },
}

VALID_PROFILE_SKILLS = {
    "pick", "fold", "review", "pr-import", "revert",
    "explore", "pickrem", "pickweb", "qa",
}

TMUX_CONFIG_SCHEMA: dict[str, dict[str, str]] = {
    "default_session": {
        "summary": "Default tmux session name",
        "detail": (
            "Session name used when creating new tmux sessions "
            "from agent launch dialog (default: aitasks)"
        ),
        "type": "string",
        "default": "aitasks",
    },
    "default_split": {
        "summary": "Default pane split direction",
        "detail": (
            "Split direction when creating new pane in existing window: "
            "horizontal or vertical (default: horizontal)"
        ),
        "type": "enum",
        "options": "horizontal,vertical",
        "default": "horizontal",
    },
    "prefer_tmux": {
        "summary": "Prefer tmux tab in launch dialogs",
        "detail": (
            "When enabled, agent launch dialogs (pick, explain, QA, create) "
            "will start with the tmux tab pre-selected instead of the "
            "terminal tab (default: false)"
        ),
        "type": "bool",
        "default": "false",
    },
    "git_tui": {
        "summary": "Git management TUI",
        "detail": (
            "External git TUI to integrate in the TUI switcher (j/g shortcut). "
            "Only one instance runs per tmux session. "
            "Set to 'none' to disable."
        ),
        "type": "enum",
        "options": "lazygit,gitui,tig,none",
        "default": "none",
    },
}


def _format_yaml_value(value) -> str:
    """Render a YAML value into a compact single-line editor string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return yaml.safe_dump(
        value, default_flow_style=True, sort_keys=False, allow_unicode=True,
    ).strip()


def _safe_id(name: str) -> str:
    """Sanitize a string for use as a Textual widget ID."""
    return name.replace(".", "_").replace(" ", "_").replace("-", "_")


_SETTINGS_DIR = Path(__file__).resolve().parent
_BUILD_VERIFY_DOCS = "https://aitasks.io/docs/skills/aitask-pick/build-verification/"


def _load_command_presets(key: str) -> list[dict]:
    """Load presets for a command-type config key (verify_build, test_command, lint_command)."""
    presets_file = _SETTINGS_DIR / f"{key}_presets.yaml"
    if not presets_file.is_file():
        return []
    try:
        with open(presets_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "presets" in data:
            return data["presets"]
    except Exception:
        pass
    return []


def _match_preset_name(raw_value: str, presets: list[dict]) -> str | None:
    """Return preset name if raw_value matches a preset's value, else None."""
    if not raw_value or not presets:
        return None
    try:
        parsed = yaml.safe_load(raw_value)
    except yaml.YAMLError:
        parsed = raw_value
    for preset in presets:
        pval = preset["value"]
        if parsed == pval:
            return preset["name"]
    return None


def _normalize_model_id(cli_id: str) -> str:
    """Strip provider/ prefix from cli_id for all_providers grouping."""
    if "/" in cli_id:
        return cli_id.split("/", 1)[1]
    return cli_id


def _aggregate_verifiedstats(
    all_models: dict[str, dict], target_cli_id: str,
) -> dict[str, dict]:
    """Aggregate verifiedstats across all providers for the same underlying LLM.

    Returns {operation: {all_time: {runs, score_sum}, month: {...}, week: {...}}}.
    """
    norm = _normalize_model_id(target_cli_id)
    result: dict[str, dict] = {}
    for _provider, pdata in all_models.items():
        for m in pdata.get("models", []):
            if _normalize_model_id(m.get("cli_id", "")) != norm:
                continue
            vs = m.get("verifiedstats", {})
            for op, buckets in vs.items():
                if not isinstance(buckets, dict):
                    continue
                if op not in result:
                    result[op] = {
                        "all_time": {"runs": 0, "score_sum": 0},
                        "month": {"period": "", "runs": 0, "score_sum": 0},
                        "week": {"period": "", "runs": 0, "score_sum": 0},
                    }
                agg = result[op]
                # all_time: always sum
                at = buckets.get("all_time", {})
                agg["all_time"]["runs"] += at.get("runs", 0)
                agg["all_time"]["score_sum"] += at.get("score_sum", 0)
                # month: sum only matching periods
                mo = buckets.get("month", {})
                mo_period = mo.get("period", "")
                if mo_period and mo.get("runs", 0) > 0:
                    if not agg["month"]["period"]:
                        agg["month"]["period"] = mo_period
                    if agg["month"]["period"] == mo_period:
                        agg["month"]["runs"] += mo.get("runs", 0)
                        agg["month"]["score_sum"] += mo.get("score_sum", 0)
                # week: sum only matching periods
                wk = buckets.get("week", {})
                wk_period = wk.get("period", "")
                if wk_period and wk.get("runs", 0) > 0:
                    if not agg["week"]["period"]:
                        agg["week"]["period"] = wk_period
                    if agg["week"]["period"] == wk_period:
                        agg["week"]["runs"] += wk.get("runs", 0)
                        agg["week"]["score_sum"] += wk.get("score_sum", 0)
    return result


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------
class ConfigManager:
    """Load and save all aitasks config files."""

    def __init__(self):
        self.codeagent: dict = {}
        self.codeagent_project: dict = {}
        self.codeagent_local: dict = {}
        self.board: dict = {}
        self.board_project: dict = {}
        self.board_local: dict = {}
        self.project_config: dict = {}
        self.models: dict[str, dict] = {}
        self.profiles: dict[str, dict] = {}
        self.profile_layers: dict[str, str] = {}  # filename -> "project" | "user"
        self.load_all()

    def load_all(self):
        # Codeagent config
        self.codeagent = load_layered_config(str(CODEAGENT_CONFIG), defaults={"defaults": {}})
        self.codeagent_project = _load_json(CODEAGENT_CONFIG)
        self.codeagent_local = _load_json(local_path_for(str(CODEAGENT_CONFIG)))

        # Board config
        defaults = {
            "columns": [],
            "column_order": [],
            "settings": {"auto_refresh_minutes": 5},
        }
        self.board = load_layered_config(str(BOARD_CONFIG), defaults=defaults)
        self.board_project = _load_json(BOARD_CONFIG)
        self.board_local = _load_json(local_path_for(str(BOARD_CONFIG)))

        # Project config (YAML, project-scoped only)
        self.project_config = load_yaml_config(PROJECT_CONFIG)

        # Model files (read-only)
        self.models = {}
        for provider, path in MODEL_FILES.items():
            data = _load_json(path)
            if data:
                self.models[provider] = data

        # Profiles
        self.load_profiles()

    def load_profiles(self):
        self.profiles = {}
        self.profile_layers = {}
        # Project profiles first
        if PROFILES_DIR.is_dir():
            for f in sorted(PROFILES_DIR.glob("*.yaml")):
                if f.parent.name == "local":
                    continue  # skip local/ subdir
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        data = yaml.safe_load(fh)
                    if isinstance(data, dict):
                        self.profiles[f.name] = data
                        self.profile_layers[f.name] = "project"
                except Exception:
                    pass
        # User (local) profiles — override project profiles with same name
        if LOCAL_PROFILES_DIR.is_dir():
            for f in sorted(LOCAL_PROFILES_DIR.glob("*.yaml")):
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        data = yaml.safe_load(fh)
                    if isinstance(data, dict):
                        self.profiles[f.name] = data
                        self.profile_layers[f.name] = "user"
                except Exception:
                    pass

    def save_codeagent(self, project_data: dict, local_data: dict):
        save_project_config(str(CODEAGENT_CONFIG), project_data)
        if local_data:
            save_local_config(str(local_path_for(str(CODEAGENT_CONFIG))), local_data)
        else:
            # Remove local file if empty
            lp = local_path_for(str(CODEAGENT_CONFIG))
            if lp.is_file():
                lp.unlink()

    def save_board(self, merged: dict):
        project_data, user_data = split_config(
            merged, project_keys=_BOARD_PROJECT_KEYS, user_keys=_BOARD_USER_KEYS
        )
        save_project_config(str(BOARD_CONFIG), project_data)
        if user_data:
            save_local_config(str(local_path_for(str(BOARD_CONFIG))), user_data)

    def save_project_settings(self, data: dict):
        save_yaml_config(str(PROJECT_CONFIG), data)

    def save_profile(self, filename: str, data: dict, layer: str = "project"):
        if layer == "user":
            LOCAL_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
            path = LOCAL_PROFILES_DIR / filename
        else:
            PROFILES_DIR.mkdir(parents=True, exist_ok=True)
            path = PROFILES_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        self.profiles[filename] = data
        self.profile_layers[filename] = layer

    def delete_profile(self, filename: str):
        """Delete a profile file from disk (handles both layers)."""
        layer = self.profile_layers.get(filename, "project")
        if layer == "user":
            path = LOCAL_PROFILES_DIR / filename
        else:
            path = PROFILES_DIR / filename
        if path.is_file():
            path.unlink()
        self.profiles.pop(filename, None)
        self.profile_layers.pop(filename, None)


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------
class CycleField(Static):
    """Focusable widget that cycles through options with Left/Right keys."""

    can_focus = True

    class Changed(Message):
        def __init__(self, field: "CycleField", value: str):
            super().__init__()
            self.field = field
            self.value = value

    def __init__(self, label: str, options: list, current: str, field_key: str,
                 id: str | None = None):
        super().__init__(id=id)
        self.label = label
        self.options = options
        self.field_key = field_key
        self.current_index = options.index(current) if current in options else 0

    @property
    def current_value(self) -> str:
        return self.options[self.current_index]

    def render(self) -> str:
        parts = []
        for i, opt in enumerate(self.options):
            if i == self.current_index:
                parts.append(f"[bold reverse] {opt} [/]")
            else:
                parts.append(f" {opt} ")
        options_str = " | ".join(parts)
        return f"  {self.label}:  [dim]\u25c0[/] {options_str} [dim]\u25b6[/]"

    def cycle_prev(self):
        self.current_index = (self.current_index - 1) % len(self.options)
        self.refresh()
        self.post_message(self.Changed(self, self.current_value))

    def cycle_next(self):
        self.current_index = (self.current_index + 1) % len(self.options)
        self.refresh()
        self.post_message(self.Changed(self, self.current_value))

    def _option_index_at(self, cx: int) -> int | None:
        """Map content x-coordinate to option index, -1 for ◀, -2 for ▶."""
        prefix_len = len(f"  {self.label}:  \u25c0 ")
        if cx == prefix_len - 2:
            return -1
        pos = prefix_len
        for i, opt in enumerate(self.options):
            opt_width = len(opt) + 2
            if pos <= cx < pos + opt_width:
                return i
            pos += opt_width
            if i < len(self.options) - 1:
                pos += 3
        if cx == pos + 1:
            return -2
        return None

    def on_click(self, event) -> None:
        """Select option directly when clicked."""
        content_offset = event.get_content_offset(self)
        if content_offset is None:
            return
        idx = self._option_index_at(content_offset.x)
        if idx == -1:
            self.cycle_prev()
        elif idx == -2:
            self.cycle_next()
        elif idx is not None and idx != self.current_index:
            self.current_index = idx
            self.refresh()
            self.post_message(self.Changed(self, self.current_value))

    def on_key(self, event):
        if event.key == "left":
            self.cycle_prev()
            event.prevent_default()
            event.stop()
        elif event.key == "right":
            self.cycle_next()
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("cycle-focused")

    def on_blur(self):
        self.remove_class("cycle-focused")


class ConfigRow(Static):
    """Focusable config key-value display with layer badge."""

    can_focus = True

    def __init__(self, key: str, value: str, config_layer: str = "project",
                 row_key: str = "", id: str | None = None,
                 subordinate: bool = False, raw_value: str | None = None):
        super().__init__(id=id)
        self.key = key
        self.value = value
        self.raw_value = raw_value if raw_value is not None else value
        self.config_layer = config_layer
        self.row_key = row_key or key
        self.subordinate = subordinate

    def render(self) -> str:
        if self.config_layer == "user":
            badge = "[#FFB86C][USER][/]"
        else:
            badge = "[#50FA7B][PROJECT][/]"

        if self.subordinate:
            # Indented subordinate row (user override under project)
            has_override = self.value not in ("(inherits project)", "(not set)", "")
            clear_hint = "  [dim](d to remove)[/dim]" if has_override else ""
            return f"      \u2514 {badge}  {self.value}{clear_hint}"

        return f"  {badge}  [bold]{self.key}:[/bold]  {self.value}"

    def on_focus(self):
        self.add_class("row-focused")

    def on_blur(self):
        self.remove_class("row-focused")


# ---------------------------------------------------------------------------
# Modal Screens
# ---------------------------------------------------------------------------
class ExportScreen(ModalScreen):
    """Modal for exporting configs with directory and subset selection."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Container(id="import_dialog"):
            yield Label("Export Config Bundle", id="import_title")
            yield Label("Output directory:", classes="edit-label")
            yield Input(value=".", placeholder="directory path", id="export_dir")
            yield Label("Select categories to export:", classes="edit-label")
            for cat_name in EXPORT_CATEGORIES:
                yield CycleField(cat_name, ["yes", "no"], "yes",
                                 cat_name, id=f"cf_exp_{cat_name.replace(' ', '_').lower()}")
            with Horizontal(id="edit_buttons"):
                yield Button("Export", variant="success", id="btn_export_ok")
                yield Button("Cancel", variant="default", id="btn_export_cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.do_export()

    @on(Button.Pressed, "#btn_export_ok")
    def do_export(self):
        directory = self.query_one("#export_dir", Input).value.strip() or "."
        patterns: list[str] = []
        for cat_name, cat_patterns in EXPORT_CATEGORIES.items():
            widget_id = f"cf_exp_{cat_name.replace(' ', '_').lower()}"
            try:
                cf = self.query_one(f"#{widget_id}", CycleField)
                if cf.current_value == "yes":
                    patterns.extend(cat_patterns)
            except Exception:
                patterns.extend(cat_patterns)
        self.dismiss({"directory": directory, "patterns": patterns})

    @on(Button.Pressed, "#btn_export_cancel")
    def do_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


def _scan_export_files() -> list[dict]:
    """Scan CWD for aitasks export bundles (.aitcfg.json and legacy .json)."""
    found: list[dict] = []
    seen: set[str] = set()
    cwd = Path.cwd()

    # New extension
    for p in sorted(cwd.glob(f"*{EXPORT_EXTENSION}"), reverse=True):
        if p.name not in seen:
            seen.add(p.name)
            found.append({"path": str(p), "name": p.name, "ext": "aitcfg"})

    # Legacy pattern
    for p in sorted(cwd.glob("aitasks_config_export_*.json"), reverse=True):
        if p.name not in seen and not p.name.endswith(EXPORT_EXTENSION):
            seen.add(p.name)
            found.append({"path": str(p), "name": p.name, "ext": "legacy"})

    return found


class ImportScreen(ModalScreen):
    """Two-step modal for importing config: file selection then per-file selection."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self):
        super().__init__()
        self._bundle: dict | None = None
        self._bundle_path: str = ""

    def compose(self) -> ComposeResult:
        with Container(id="import_dialog"):
            # Step 1: File selection
            with Container(id="import_step1"):
                yield Label("Import Config Bundle", id="import_title")
                discovered = _scan_export_files()
                if discovered:
                    yield Label("[dim]Discovered export files:[/dim]", classes="edit-label")
                    for i, f in enumerate(discovered[:8]):
                        tag = " [dim](legacy)[/dim]" if f["ext"] == "legacy" else ""
                        yield Button(
                            f"{f['name']}{tag}",
                            variant="default",
                            id=f"btn_discovered_{i}",
                        )
                    yield Label("")
                yield Label("Or enter file path manually:", classes="edit-label")
                yield Input(
                    placeholder=f"path/to/export{EXPORT_EXTENSION}",
                    id="import_path",
                )
                with Horizontal(id="edit_buttons"):
                    yield Button("Next", variant="success", id="btn_import_next")
                    yield Button("Cancel", variant="default", id="btn_import_cancel")

            # Step 2: Per-file selection (hidden initially)
            with Container(id="import_step2"):
                yield Label("Select files to import:", id="import_step2_title")
                yield VerticalScroll(id="import_file_list")
                yield CycleField(
                    "Overwrite existing", ["no", "yes"], "no",
                    "overwrite", id="cf_overwrite",
                )
                with Horizontal(id="import_step2_buttons"):
                    yield Button("Import", variant="success", id="btn_import_ok")
                    yield Button("Back", variant="default", id="btn_import_back")
                    yield Button("Cancel", variant="default", id="btn_import_cancel2")

        # Store discovered files for button click lookup
        self._discovered = _scan_export_files()

    def on_mount(self):
        self.query_one("#import_step2").display = False

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed):
        btn_id = event.button.id or ""
        if btn_id.startswith("btn_discovered_"):
            idx = int(btn_id.split("_")[-1])
            if idx < len(self._discovered):
                inp = self.query_one("#import_path", Input)
                inp.value = self._discovered[idx]["path"]

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.query_one("#import_step1").display:
            self.do_next()

    @on(Button.Pressed, "#btn_import_next")
    def do_next(self):
        path = self.query_one("#import_path", Input).value.strip()
        if not path:
            self.notify("Please enter or select a file path", severity="warning")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                bundle = json.load(f)
        except FileNotFoundError:
            self.notify(f"File not found: {path}", severity="error")
            return
        except json.JSONDecodeError as exc:
            self.notify(f"Invalid JSON: {exc}", severity="error")
            return

        warnings = validate_export_bundle(bundle)
        if any("Missing 'files'" in w for w in warnings):
            self.notify("Invalid bundle: missing 'files' key", severity="error")
            return

        self._bundle = bundle
        self._bundle_path = path
        self._populate_file_list(bundle)
        self.query_one("#import_step1").display = False
        self.query_one("#import_step2").display = True

    def _populate_file_list(self, bundle: dict):
        container = self.query_one("#import_file_list", VerticalScroll)
        container.remove_children()

        meta = bundle.get("_export_meta", {})
        meta_info = f"[dim]Bundle v{meta.get('version', '?')} — "
        meta_info += f"exported {meta.get('exported_at', 'unknown')[:19]} — "
        meta_info += f"{meta.get('file_count', '?')} files[/dim]"
        container.mount(Label(meta_info))
        container.mount(Label(""))

        warnings = validate_export_bundle(bundle)
        if warnings:
            for w in warnings:
                container.mount(Label(f"[yellow]Warning: {w}[/yellow]"))
            container.mount(Label(""))

        files = bundle.get("files", {})
        for name, data in files.items():
            if isinstance(data, dict) and "_error" in data:
                container.mount(Label(f"[red]  {name} — export error, skipped[/red]"))
                continue

            desc = CONFIG_FILE_DESCRIPTIONS.get(name, "Configuration file")
            exists = (METADATA_DIR / name).exists()
            status = "[yellow](exists — will overwrite)[/yellow]" if exists else "[green](new)[/green]"

            container.mount(CycleField(
                name, ["yes", "no"], "yes", name,
                id=f"cf_imp_{name.replace('.', '_')}",
            ))
            container.mount(Label(f"[dim]    {desc} {status}[/dim]"))

    @on(Button.Pressed, "#btn_import_ok")
    def do_import(self):
        if not self._bundle:
            return
        overwrite = self.query_one("#cf_overwrite", CycleField).current_value == "yes"
        selected: list[str] = []
        for name in self._bundle.get("files", {}):
            widget_id = f"cf_imp_{name.replace('.', '_')}"
            try:
                cf = self.query_one(f"#{widget_id}", CycleField)
                if cf.current_value == "yes":
                    selected.append(name)
            except Exception:
                selected.append(name)
        self.dismiss({
            "path": self._bundle_path,
            "overwrite": overwrite,
            "selected_files": selected,
        })

    @on(Button.Pressed, "#btn_import_back")
    def do_back(self):
        self.query_one("#import_step1").display = True
        self.query_one("#import_step2").display = False

    @on(Button.Pressed, "#btn_import_cancel")
    @on(Button.Pressed, "#btn_import_cancel2")
    def do_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class EditStringScreen(ModalScreen):
    """Modal for editing a single string value (profile fields)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, key: str, current_value: str):
        super().__init__()
        self.key = key
        self.current_value = current_value

    def compose(self) -> ComposeResult:
        with Container(id="edit_dialog"):
            yield Label(f"Edit: [bold]{self.key}[/bold]", id="edit_title")
            yield Input(value=self.current_value, id="edit_input")
            with Horizontal(id="edit_buttons"):
                yield Button("Save", variant="success", id="btn_edit_save")
                yield Button("Cancel", variant="default", id="btn_edit_cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.do_save()

    @on(Button.Pressed, "#btn_edit_save")
    def do_save(self):
        value = self.query_one("#edit_input", Input).value
        self.dismiss({"key": self.key, "value": value})

    @on(Button.Pressed, "#btn_edit_cancel")
    def do_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class EditVerifyBuildScreen(ModalScreen):
    """Modal for editing verify_build with multi-line TextArea and preset support."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, key: str, current_value: str, presets: list[dict] | None = None):
        super().__init__()
        self.key = key
        self.current_value = current_value
        self.presets = presets or []

    @staticmethod
    def _to_block_yaml(value: str) -> str:
        """Convert compact YAML to readable block-style for editing."""
        if not value:
            return ""
        try:
            parsed = yaml.safe_load(value)
            if isinstance(parsed, list):
                return yaml.safe_dump(parsed, default_flow_style=False).strip()
        except yaml.YAMLError:
            pass
        return value

    @staticmethod
    def _to_compact_yaml(text: str) -> str:
        """Convert edited text back to compact storage format."""
        text = text.strip()
        if not text:
            return ""
        try:
            parsed = yaml.safe_load(text)
            if isinstance(parsed, list):
                return yaml.safe_dump(
                    parsed, default_flow_style=True, sort_keys=False,
                ).strip()
            if isinstance(parsed, str):
                return parsed
        except yaml.YAMLError:
            pass
        return text

    def compose(self) -> ComposeResult:
        display_value = self._to_block_yaml(self.current_value)
        with Container(id="edit_dialog"):
            yield Label(f"Edit: [bold]{self.key}[/bold]", id="edit_title")
            yield Label(
                "[dim]Enter a single command string, or a YAML list "
                "(one command per line, prefix each with '- ')[/dim]",
                classes="section-hint",
            )
            yield TextArea(display_value, id="edit_textarea", language="yaml")
            with Horizontal(id="edit_buttons"):
                if self.presets:
                    yield Button("Load Preset", variant="primary", id="btn_load_preset")
                yield Button("Save", variant="success", id="btn_edit_ml_save")
                yield Button("Cancel", variant="default", id="btn_edit_ml_cancel")

    @on(Button.Pressed, "#btn_edit_ml_save")
    def do_save(self):
        text = self.query_one("#edit_textarea", TextArea).text
        value = self._to_compact_yaml(text)
        self.dismiss({"key": self.key, "value": value})

    @on(Button.Pressed, "#btn_edit_ml_cancel")
    def do_cancel(self):
        self.dismiss(None)

    @on(Button.Pressed, "#btn_load_preset")
    def do_load_preset(self):
        self.app.push_screen(
            VerifyBuildPresetScreen(self.presets),
            callback=self._handle_preset_selected,
        )

    def _handle_preset_selected(self, result):
        if result is None:
            return
        value = result["value"]
        if isinstance(value, list):
            text = yaml.safe_dump(value, default_flow_style=False).strip()
        else:
            text = str(value)
        self.query_one("#edit_textarea", TextArea).load_text(text)

    def action_cancel(self):
        self.dismiss(None)


class VerifyBuildPresetScreen(ModalScreen):
    """Modal for selecting a verify_build preset with fuzzy search and preview."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, presets: list[dict]):
        super().__init__()
        self.presets = presets
        self._preset_map = {p["name"]: p for p in presets}

    def compose(self) -> ComposeResult:
        options = [
            {
                "value": p["name"],
                "display": p["name"],
                "description": p.get("description", ""),
            }
            for p in self.presets
        ]
        with Container(id="picker_dialog"):
            yield Label("Select Build Preset", id="picker_title")
            yield FuzzySelect(
                options, placeholder="Type to filter presets...",
                id="preset_picker",
            )
            yield Static("", id="preset_preview")

    def on_mount(self):
        if self.presets:
            self._show_preview(self.presets[0]["name"])

    def _show_preview(self, name: str):
        preset = self._preset_map.get(name)
        if not preset:
            return
        value = preset["value"]
        if isinstance(value, list):
            formatted = yaml.safe_dump(value, default_flow_style=False).strip()
        else:
            formatted = str(value)
        try:
            preview = self.query_one("#preset_preview", Static)
            preview.update(f"[bold]Preview:[/bold]\n[dim]{formatted}[/dim]")
        except Exception:
            pass

    def on_fuzzy_select_highlighted(self, event: FuzzySelect.Highlighted):
        self._show_preview(event.value)

    def on_fuzzy_select_selected(self, event: FuzzySelect.Selected):
        preset = self._preset_map.get(event.value)
        if preset:
            self.dismiss(preset)

    def on_fuzzy_select_cancelled(self, event: FuzzySelect.Cancelled):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class ProfilePickerScreen(ModalScreen):
    """Modal for selecting an execution profile name via fuzzy search."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, skill: str, current: str, profile_names: list[str]):
        super().__init__()
        self.skill = skill
        self.current = current
        self.profile_names = profile_names

    def compose(self) -> ComposeResult:
        options = [
            {"value": "", "display": "<not set>", "description": "Remove default profile"},
        ]
        for name in self.profile_names:
            options.append({"value": name, "display": name, "description": ""})
        with Container(id="picker_dialog"):
            yield Label(
                f"Default profile for [bold]{self.skill}[/bold]"
                f"  (current: {self.current or '<not set>'})",
                id="picker_title",
            )
            yield FuzzySelect(
                options, placeholder="Type to filter profiles...",
                id="profile_picker",
            )

    def on_fuzzy_select_selected(self, event: FuzzySelect.Selected):
        self.dismiss({"key": self.skill, "value": event.value})

    def on_fuzzy_select_cancelled(self, event: FuzzySelect.Cancelled):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class NewProfileScreen(ModalScreen):
    """Modal for creating a new profile based on an existing one."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, existing_profiles: list[str]):
        super().__init__()
        self.existing_profiles = existing_profiles

    def compose(self) -> ComposeResult:
        with Container(id="edit_dialog"):
            yield Label("Create New Profile", id="edit_title")
            yield Label("Profile filename (without .yaml):", classes="edit-label")
            yield Input(placeholder="my-profile", id="new_profile_name")
            yield Label("Profile scope:", classes="edit-label")
            yield CycleField(
                "Scope", ["project", "user"], "project",
                "profile_scope", id="cf_profile_scope",
            )
            yield Label(
                "[dim]project = git-tracked, shared  |  "
                "user = local-only, gitignored[/dim]",
                classes="section-hint",
            )
            base_options = list(self.existing_profiles) + ["(empty)"]
            yield Label("Base on existing profile:", classes="edit-label")
            yield CycleField(
                "Base profile", base_options,
                base_options[0] if base_options else "(empty)",
                "base_profile", id="cf_base_profile",
            )
            with Horizontal(id="edit_buttons"):
                yield Button("Create", variant="success", id="btn_new_profile_ok")
                yield Button("Cancel", variant="default", id="btn_new_profile_cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.do_create()

    @on(Button.Pressed, "#btn_new_profile_ok")
    def do_create(self):
        name = self.query_one("#new_profile_name", Input).value.strip()
        base = self.query_one("#cf_base_profile", CycleField).current_value
        scope = self.query_one("#cf_profile_scope", CycleField).current_value
        if not name:
            return
        if not name.endswith(".yaml"):
            name = name + ".yaml"
        self.dismiss({"filename": name, "base": base, "layer": scope})

    @on(Button.Pressed, "#btn_new_profile_cancel")
    def do_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class DeleteProfileConfirmScreen(ModalScreen):
    """Confirmation dialog to delete a profile."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, profile_name: str, filename: str):
        super().__init__()
        self.profile_name = profile_name
        self.filename = filename

    def compose(self) -> ComposeResult:
        with Container(id="edit_dialog"):
            yield Label(
                f"Delete profile [bold]{self.profile_name}[/bold] "
                f"({self.filename})?\nThis cannot be undone.",
                id="edit_title",
            )
            with Horizontal(id="edit_buttons"):
                yield Button("Delete", variant="error", id="btn_del_profile_ok")
                yield Button("Cancel", variant="default", id="btn_del_profile_cancel")

    @on(Button.Pressed, "#btn_del_profile_ok")
    def do_delete(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_del_profile_cancel")
    def do_cancel(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class SaveProfileConfirmScreen(ModalScreen):
    """Confirmation dialog before saving a profile."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, profile_name: str, filename: str):
        super().__init__()
        self.profile_name = profile_name
        self.filename = filename

    def compose(self) -> ComposeResult:
        with Container(id="edit_dialog"):
            yield Label(
                f"Save profile [bold]{self.profile_name}[/bold]?",
                id="edit_title",
            )
            with Horizontal(id="edit_buttons"):
                yield Button("Save", variant="success", id="btn_save_profile_ok")
                yield Button(
                    "Save and Commit", variant="primary",
                    id="btn_save_profile_commit",
                )
                yield Button(
                    "Cancel", variant="default", id="btn_save_profile_cancel",
                )

    @on(Button.Pressed, "#btn_save_profile_ok")
    def do_save(self):
        self.dismiss("save")

    @on(Button.Pressed, "#btn_save_profile_commit")
    def do_save_commit(self):
        self.dismiss("save_commit")

    @on(Button.Pressed, "#btn_save_profile_cancel")
    def do_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------
class SettingsApp(TuiSwitcherMixin, App):
    """aitasks Settings TUI."""

    CSS = """
    /* Tab panes */
    TabPane { padding: 1 2; }

    /* Config rows */
    ConfigRow { height: 1; width: 100%; padding: 0 1; }
    ConfigRow.row-focused { background: $primary 20%; }

    /* Cycle fields */
    CycleField { height: 1; width: 100%; padding: 0 1; }
    CycleField.cycle-focused { background: $primary 20%; }

    /* Section headers */
    .section-header {
        text-style: bold;
        padding: 1 0 0 1;
        color: $accent;
    }
    .section-hint {
        padding: 0 0 0 3;
        color: $text-muted;
    }

    /* Model rows */
    .model-row { height: auto; padding: 0 2; }
    .model-header { text-style: bold underline; padding: 0 2; }

    /* Profile section */
    .profile-header {
        text-style: bold;
        padding: 1 0 0 1;
        color: #50FA7B;
    }
    .profile-sep { color: $text-muted; padding: 0 1; }

    /* Modal dialogs */
    #edit_dialog, #import_dialog, #picker_dialog {
        width: 65%;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    .edit-label { padding: 1 0 0 1; }
    #edit_buttons { padding: 1 0 0 0; height: auto; }
    #edit_buttons Button { margin: 0 1; }
    #picker_step_label { padding: 0 0 1 1; color: $accent; }

    /* Buttons in tabs */
    .tab-buttons { padding: 1 0 0 0; height: auto; }
    .tab-buttons Button { margin: 0 1; }

    /* FuzzySelect */
    FuzzySelect { height: auto; max-height: 20; }
    FuzzySelect VerticalScroll { height: auto; max-height: 15; }
    FuzzyOption { height: 1; width: 100%; padding: 0 1; }

    /* Import step containers */
    #import_step2 { height: auto; }
    #import_step2_buttons { padding: 1 0 0 0; height: auto; }
    #import_step2_buttons Button { margin: 0 1; }
    #import_file_list { height: auto; max-height: 15; padding: 0 1; }

    /* Operation descriptions */
    .op-desc { padding: 0 0 0 5; height: 1; }

    /* Verify build multi-line editor */
    #edit_textarea { height: 10; min-height: 5; max-height: 15; }

    /* Preset preview */
    #preset_preview {
        padding: 1 2;
        height: auto;
        max-height: 8;
        background: $surface-darken-1;
        border: tall $accent;
        margin: 1 0 0 0;
    }
    """

    TITLE = "aitasks settings"

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        Binding("q", "quit", "Quit"),
        Binding("e", "export_configs", "Export"),
        Binding("i", "import_configs", "Import"),
        Binding("r", "reload_configs", "Reload"),
    ]

    def __init__(self):
        super().__init__()
        self.current_tui_name = "settings"
        self.config_mgr = ConfigManager()
        self._profile_id_map: dict[str, str] = {}  # safe_id -> filename
        self._selected_profile: str | None = None  # currently selected profile filename
        self._expanded_field: str | None = None  # field key with expanded description
        self._profiles_focus_target: str | None = None  # widget ID to focus after repop
        self._editing_layer: str = "project"  # track which layer is being edited
        self._editing_project_key: str | None = None
        self._repop_counter: int = 0  # ensures unique widget IDs across repopulations
        self._tmux_tab_rc: int = 0  # counter snapshot for tmux tab widgets
        self._profiles_tab_rc: int = 0  # counter snapshot for profiles tab widgets

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent("Agent Defaults", "Board", "Project Config", "Tmux", "Models", "Profiles"):
            with TabPane("Agent Defaults", id="tab_agent"):
                yield VerticalScroll(id="agent_content")
            with TabPane("Board", id="tab_board"):
                yield VerticalScroll(id="board_content")
            with TabPane("Project Config", id="tab_project"):
                yield VerticalScroll(id="project_content")
            with TabPane("Tmux", id="tab_tmux"):
                yield VerticalScroll(id="tmux_content")
            with TabPane("Models", id="tab_models"):
                yield VerticalScroll(id="models_content")
            with TabPane("Profiles", id="tab_profiles"):
                yield VerticalScroll(id="profiles_content")
        yield Footer()

    def on_mount(self):
        self._populate_agent_tab()
        self._populate_board_tab()
        self._populate_project_tab()
        self._populate_tmux_tab()
        self._populate_models_tab()
        self._populate_profiles_tab()

    # -------------------------------------------------------------------
    # Navigation helpers
    # -------------------------------------------------------------------
    def _nav_vertical(self, direction: str) -> None:
        """Move focus between focusable widgets in the active tab."""
        try:
            tabbed = self.query_one(TabbedContent)
            active_pane_id = tabbed.active
            pane = self.query_one(f"#{active_pane_id}", TabPane)
        except Exception:
            return
        # Exclude VerticalScroll containers — they are focusable by default
        # but have no visual indicator and steal focus from actual widgets.
        focusable = [
            w for w in pane.query("*")
            if w.can_focus and w.display and not isinstance(w, VerticalScroll)
        ]
        if not focusable:
            return
        focused = self.focused
        if focused in focusable:
            idx = focusable.index(focused)
            if direction == "up" and idx > 0:
                focusable[idx - 1].focus()
            elif direction == "up" and idx == 0:
                # Return focus to the tab bar
                try:
                    tabbed.query_one("Tabs").focus()
                except Exception:
                    pass
            elif direction == "down" and idx < len(focusable) - 1:
                focusable[idx + 1].focus()
        else:
            if direction == "down":
                focusable[0].focus()
            else:
                focusable[-1].focus()

    def _focus_first_in_tab(self, tab_id: str) -> None:
        """Focus the first focusable widget in the given tab pane."""
        try:
            pane = self.query_one(f"#{tab_id}", TabPane)
            focusable = [
                w for w in pane.query("*")
                if w.can_focus and w.display and not isinstance(w, VerticalScroll)
            ]
            if focusable:
                focusable[0].focus()
            else:
                self.query_one(TabbedContent).query_one("Tabs").focus()
        except Exception:
            pass

    # -------------------------------------------------------------------
    # Key handling
    # -------------------------------------------------------------------
    def on_key(self, event) -> None:
        # Guard: don't intercept keys when a modal is active
        if isinstance(self.screen, ModalScreen):
            return

        focused = self.focused

        # Guard: skip all custom handling when an Input has focus
        if isinstance(focused, Input):
            return

        # Tab switching: a/b/c/m/p/t
        if event.key in _TAB_SHORTCUTS:
            try:
                tabbed = self.query_one(TabbedContent)
                new_tab_id = _TAB_SHORTCUTS[event.key]
                tabbed.active = new_tab_id
                # Immediately move focus to the tab bar to prevent Textual
                # from reverting the tab switch (happens when the previously
                # focused widget becomes hidden and the new tab has no
                # focusable content, e.g. the Models tab).
                tabbed.query_one("Tabs").focus()
                self.call_after_refresh(self._focus_first_in_tab, new_tab_id)
            except Exception:
                pass
            event.prevent_default()
            event.stop()
            return

        # Up/Down navigation within active tab
        if event.key in ("up", "down"):
            self._nav_vertical(event.key)
            event.prevent_default()
            event.stop()
            return

        # Enter: open editors for ConfigRow widgets
        if event.key == "enter" and isinstance(focused, ConfigRow):
            fid = focused.id or ""

            # Agent Defaults rows (project or user)
            if fid.startswith("agent_proj_") or fid.startswith("agent_user_"):
                key = focused.row_key
                current_val = focused.raw_value
                self._editing_layer = (
                    "project" if fid.startswith("agent_proj_") else "user"
                )
                if "brainstorm_launch_" in fid:
                    # Launch mode picker for brainstorm-<type>-launch-mode rows
                    project_defaults = self.config_mgr.codeagent_project.get(
                        "defaults", {}
                    )
                    if current_val == "(inherits project)":
                        current_mode = str(project_defaults.get(key, "headless"))
                    else:
                        current_mode = current_val
                    if current_mode not in ("headless", "interactive"):
                        current_mode = "headless"
                    self.push_screen(
                        LaunchModePickerScreen(key, current_mode),
                        callback=self._handle_launch_mode_pick,
                    )
                    event.prevent_default()
                    event.stop()
                    return
                current_agent, current_model = "", ""
                if "/" in current_val and current_val != "(inherits project)":
                    current_agent, current_model = current_val.split("/", 1)
                self.push_screen(
                    AgentModelPickerScreen(
                        key, current_agent, current_model,
                        all_models=self.config_mgr.models,
                    ),
                    callback=self._handle_agent_pick,
                )
                event.prevent_default()
                event.stop()
                return

            # Default profiles per-skill editing
            if fid.startswith("project_dp_"):
                skill = focused.row_key
                current = focused.raw_value or ""
                profile_names = sorted(
                    pdata.get("name", fn.removesuffix(".yaml"))
                    for fn, pdata in self.config_mgr.profiles.items()
                )
                self._editing_project_row_id = focused.id
                self.push_screen(
                    ProfilePickerScreen(skill, current, profile_names),
                    callback=self._handle_default_profile_pick,
                )
                event.prevent_default()
                event.stop()
                return

            # Tmux config editing
            if fid.startswith("tmux_cfg_"):
                self._editing_tmux_row_id = focused.id
                self.push_screen(
                    EditStringScreen(focused.row_key, focused.raw_value),
                    callback=self._handle_tmux_config_edit,
                )
                event.prevent_default()
                event.stop()
                return

            # Project config editing
            if fid.startswith("project_cfg_"):
                self._editing_project_key = focused.row_key
                self._editing_project_row_id = focused.id
                if focused.row_key in ("verify_build", "test_command", "lint_command"):
                    presets = _load_command_presets(focused.row_key)
                    self.push_screen(
                        EditVerifyBuildScreen(
                            focused.row_key, focused.raw_value, presets=presets,
                        ),
                        callback=self._handle_project_config_edit,
                    )
                else:
                    self.push_screen(
                        EditStringScreen(focused.row_key, focused.raw_value),
                        callback=self._handle_project_config_edit,
                    )
                event.prevent_default()
                event.stop()
                return

            # Profile string editing
            if fid.startswith("profile_str_"):
                parts = fid.split("__", 1)
                if len(parts) == 2:
                    safe_fn_with_rc = parts[1]
                    # Strip _N repop counter suffix
                    last_underscore = safe_fn_with_rc.rfind("_")
                    if last_underscore > 0:
                        safe_fn = safe_fn_with_rc[:last_underscore]
                    else:
                        safe_fn = safe_fn_with_rc
                    profile_filename = self._profile_id_map.get(safe_fn, safe_fn)
                    key = focused.row_key
                    value = focused.value
                    self.push_screen(
                        EditStringScreen(key, value),
                        callback=lambda result, pf=profile_filename:
                            self._handle_profile_string_edit(result, pf),
                    )
                    event.prevent_default()
                    event.stop()
                    return

        # ?: toggle field detail on profile fields
        if event.key == "question_mark" and (
            isinstance(focused, CycleField) or isinstance(focused, ConfigRow)
        ):
            fid = focused.id or ""
            if fid.startswith("profile_") and "__" in fid:
                if isinstance(focused, CycleField):
                    field_key = focused.field_key
                elif isinstance(focused, ConfigRow):
                    field_key = focused.row_key
                else:
                    field_key = None
                if field_key and field_key in PROFILE_FIELD_INFO:
                    if self._expanded_field == field_key:
                        self._expanded_field = None
                    else:
                        self._expanded_field = field_key
                    # Compute the new widget ID after repopulation
                    sel = self._selected_profile or ""
                    sf = _safe_id(sel)
                    next_rc = self._repop_counter + 1
                    ktype = PROFILE_SCHEMA.get(field_key, ("", None))[0]
                    if ktype == "string":
                        new_wid = f"profile_str_{field_key}__{sf}_{next_rc}"
                    else:
                        new_wid = f"profile_{field_key}__{sf}_{next_rc}"
                    self._populate_profiles_tab(focus_widget_id=new_wid)
                    event.prevent_default()
                    event.stop()
                    return

        # d/Delete: clear user override on agent user rows
        if event.key in ("d", "delete") and isinstance(focused, ConfigRow):
            fid = focused.id or ""
            if fid.startswith("agent_user_"):
                key = focused.row_key
                self._clear_user_override(key)
                event.prevent_default()
                event.stop()
                return

    # -------------------------------------------------------------------
    # Agent Defaults tab
    # -------------------------------------------------------------------
    def _get_verified_label(self, operation: str, agent_model: str) -> str:
        """Return a verified score label for an agent/model/operation combo."""
        if "/" not in agent_model:
            return ""
        agent, model_name = agent_model.split("/", 1)
        provider_data = self.config_mgr.models.get(agent, {})
        for m in provider_data.get("models", []):
            if m.get("name") == model_name:
                # Try verifiedstats first for richer display
                vs = m.get("verifiedstats", {})
                op_buckets = vs.get(operation, {})
                at = op_buckets.get("all_time", {})
                if at.get("runs", 0) > 0:
                    detail = _format_op_stats(op_buckets, compact=True)
                    return f" [dim][{detail}][/dim]"
                # Fall back to flat verified dict
                verified = m.get("verified", {})
                op_score = verified.get(operation, 0)
                if op_score:
                    return f" [dim][score: {op_score}][/dim]"
                elif operation in verified:
                    return " [dim](not verified)[/dim]"
                return ""
        return ""

    def _get_all_providers_label(self, operation: str, agent_model: str) -> str:
        """Return all_providers aggregated label if it differs from provider-specific."""
        if "/" not in agent_model:
            return ""
        agent, model_name = agent_model.split("/", 1)
        provider_data = self.config_mgr.models.get(agent, {})
        cli_id = ""
        provider_runs = 0
        for m in provider_data.get("models", []):
            if m.get("name") == model_name:
                cli_id = m.get("cli_id", "")
                vs = m.get("verifiedstats", {})
                at = vs.get(operation, {}).get("all_time", {})
                provider_runs = at.get("runs", 0)
                break
        if not cli_id:
            return ""
        agg = _aggregate_verifiedstats(self.config_mgr.models, cli_id)
        op_agg = agg.get(operation, {})
        agg_at = op_agg.get("all_time", {})
        agg_runs = agg_at.get("runs", 0)
        if agg_runs <= 0 or agg_runs == provider_runs:
            return ""  # no cross-provider data
        detail = _format_op_stats(op_agg, compact=True)
        return f" [dim]all providers: {detail}[/dim]"

    def _collect_non_default_skill_stats(self) -> dict[str, list[dict]]:
        """Collect verified stats for skills not in the operation defaults.

        Returns {skill_name: [{agent, model, score, detail}, ...]} with at most
        3 entries per skill, sorted by all-time average score descending.
        """
        project_defaults = self.config_mgr.codeagent_project.get("defaults", {})
        local_defaults = self.config_mgr.codeagent_local.get("defaults", {})
        default_keys = (
            set(OPERATION_DESCRIPTIONS.keys())
            | set(project_defaults.keys())
            | set(local_defaults.keys())
        )

        skill_candidates: dict[str, list[dict]] = {}

        for agent, pdata in self.config_mgr.models.items():
            for m in pdata.get("models", []):
                if m.get("status", "active") == "unavailable":
                    continue
                name = m.get("name", "?")
                vs = m.get("verifiedstats", {})
                for skill, buckets in vs.items():
                    if skill in default_keys:
                        continue
                    if not isinstance(buckets, dict):
                        continue
                    at = buckets.get("all_time", {})
                    runs = at.get("runs", 0)
                    if runs <= 0:
                        continue
                    detail = _format_op_stats(buckets, compact=True)
                    if skill not in skill_candidates:
                        skill_candidates[skill] = []
                    skill_candidates[skill].append({
                        "agent": agent,
                        "model": name,
                        "score": _bucket_avg(at),
                        "detail": detail,
                    })

        result: dict[str, list[dict]] = {}
        for skill in sorted(skill_candidates.keys()):
            entries = skill_candidates[skill]
            entries.sort(key=lambda c: (-c["score"], c["agent"], c["model"]))
            result[skill] = entries[:3]
        return result

    def _populate_agent_tab(self):
        from brainstorm.brainstorm_crew import BRAINSTORM_AGENT_TYPES

        container = self.query_one("#agent_content", VerticalScroll)
        container.remove_children()

        # Increment counter to ensure unique widget IDs (remove_children is async)
        self._repop_counter += 1
        rc = self._repop_counter

        container.mount(Label("Default Code Agents for Skills", classes="section-header"))
        container.mount(Label(
            "[dim]Each operation shows the shared [#50FA7B]project[/] setting "
            "and your local [#FFB86C]user[/] preference below it.[/dim]",
            classes="section-hint",
        ))

        project_defaults = self.config_mgr.codeagent_project.get("defaults", {})
        local_defaults = self.config_mgr.codeagent_local.get("defaults", {})

        # Collect all operation keys (union, preserving order)
        all_keys = list(dict.fromkeys(
            list(project_defaults.keys()) + list(local_defaults.keys())
        ))

        launch_mode_emitted: set[str] = set()

        def _emit_launch_mode_rows(atype: str) -> None:
            if atype in launch_mode_emitted:
                return
            launch_mode_emitted.add(atype)
            lm_key = f"brainstorm-{atype}-launch-mode"
            framework_default = BRAINSTORM_AGENT_TYPES.get(atype, {}).get(
                "launch_mode", "headless"
            )
            proj_lm = project_defaults.get(lm_key)
            local_lm = local_defaults.get(lm_key)

            if proj_lm is not None:
                proj_raw_lm = str(proj_lm)
                proj_display_lm = proj_raw_lm
            else:
                proj_raw_lm = framework_default
                proj_display_lm = f"{framework_default}  [dim](framework default)[/dim]"
            container.mount(ConfigRow(
                "launch_mode", proj_display_lm,
                config_layer="project", row_key=lm_key,
                id=f"agent_proj_brainstorm_launch_{atype}_{rc}",
                raw_value=proj_raw_lm,
            ))

            if local_lm is not None:
                user_raw_lm = str(local_lm)
                user_display_lm = user_raw_lm
            else:
                user_raw_lm = "(inherits project)"
                user_display_lm = user_raw_lm
            container.mount(ConfigRow(
                "launch_mode", user_display_lm,
                config_layer="user", row_key=lm_key,
                id=f"agent_user_brainstorm_launch_{atype}_{rc}",
                subordinate=True,
                raw_value=user_raw_lm,
            ))

            desc_lm = OPERATION_DESCRIPTIONS.get(lm_key, "")
            if desc_lm:
                container.mount(Label(
                    f"[dim italic]{desc_lm}[/dim italic]", classes="op-desc",
                ))

        brainstorm_header_shown = False
        for key in all_keys:
            # Skip launch-mode keys — they render under their paired agent-string row
            if key.endswith("-launch-mode"):
                continue

            # Insert brainstorm section header before first brainstorm key
            if key.startswith("brainstorm-") and not brainstorm_header_shown:
                container.mount(Label(""))  # spacer
                container.mount(Label(
                    "Default Code Agents for Brainstorming",
                    classes="section-header",
                ))
                container.mount(Label(
                    "[dim]Models used by brainstorm agent types "
                    "during design exploration.[/dim]",
                    classes="section-hint",
                ))
                brainstorm_header_shown = True

            sk = _safe_id(key)

            # Project row
            proj_val = project_defaults.get(key, "(not set)")
            proj_raw = str(proj_val)
            proj_display = proj_raw
            if proj_val and proj_val != "(not set)":
                proj_display += self._get_verified_label(key, proj_raw)
            container.mount(ConfigRow(
                key, proj_display, config_layer="project", row_key=key,
                id=f"agent_proj_{sk}_{rc}",
                raw_value=proj_raw,
            ))

            # User row (subordinate, indented under project row)
            if key in local_defaults:
                user_raw = str(local_defaults[key])
                user_val = user_raw + self._get_verified_label(key, user_raw)
            else:
                user_raw = "(inherits project)"
                user_val = user_raw
            container.mount(ConfigRow(
                key, user_val, config_layer="user", row_key=key,
                id=f"agent_user_{sk}_{rc}",
                subordinate=True,
                raw_value=user_raw,
            ))

            # All-providers hint (show for the effective model)
            effective_model = (
                str(local_defaults[key]) if key in local_defaults
                else proj_raw if proj_val and proj_val != "(not set)" else ""
            )
            if effective_model:
                ap_label = self._get_all_providers_label(key, effective_model)
                if ap_label:
                    container.mount(Label(ap_label, classes="op-desc"))

            # Operation description
            desc = OPERATION_DESCRIPTIONS.get(key, "")
            if desc:
                container.mount(Label(
                    f"[dim italic]{desc}[/dim italic]", classes="op-desc",
                ))

            # Paired launch_mode rows for brainstorm agent types
            if key.startswith("brainstorm-") and key in (
                f"brainstorm-{t}" for t in BRAINSTORM_AGENT_TYPES
            ):
                atype = key[len("brainstorm-"):]
                _emit_launch_mode_rows(atype)

        # Safety-net: emit launch_mode rows for brainstorm types that have a
        # launch_mode override in config but no agent_string in either layer.
        for atype in BRAINSTORM_AGENT_TYPES:
            if atype in launch_mode_emitted:
                continue
            lm_key = f"brainstorm-{atype}-launch-mode"
            if lm_key not in project_defaults and lm_key not in local_defaults:
                continue
            if not brainstorm_header_shown:
                container.mount(Label(""))  # spacer
                container.mount(Label(
                    "Default Code Agents for Brainstorming",
                    classes="section-header",
                ))
                container.mount(Label(
                    "[dim]Models used by brainstorm agent types "
                    "during design exploration.[/dim]",
                    classes="section-hint",
                ))
                brainstorm_header_shown = True
            # Synthetic agent-string row pair so the launch_mode pair has
            # a visual parent.
            synth_key = f"brainstorm-{atype}"
            sk = _safe_id(synth_key)
            container.mount(ConfigRow(
                synth_key, "(not set)", config_layer="project", row_key=synth_key,
                id=f"agent_proj_{sk}_{rc}",
                raw_value="(not set)",
            ))
            container.mount(ConfigRow(
                synth_key, "(inherits project)", config_layer="user", row_key=synth_key,
                id=f"agent_user_{sk}_{rc}",
                subordinate=True,
                raw_value="(inherits project)",
            ))
            desc = OPERATION_DESCRIPTIONS.get(synth_key, "")
            if desc:
                container.mount(Label(
                    f"[dim italic]{desc}[/dim italic]", classes="op-desc",
                ))
            _emit_launch_mode_rows(atype)

        # --- Verified Skill Stats (non-default skills) ---
        skill_stats = self._collect_non_default_skill_stats()
        if skill_stats:
            container.mount(Label(""))  # visual spacer
            container.mount(Label(
                "Verified Skill Stats [dim](read-only)[/dim]",
                classes="section-header",
            ))
            container.mount(Label(
                "[dim]Skills without defaults that have verified stats. "
                "Top 3 agent/model combos by score.[/dim]",
                classes="section-hint",
            ))
            for skill, entries in skill_stats.items():
                container.mount(Label(
                    f"  [bold]{skill}[/bold]",
                    classes="model-row",
                ))
                for entry in entries:
                    agent_model = f"{entry['agent']}/{entry['model']}"
                    detail = entry["detail"]
                    container.mount(Label(
                        f"      {agent_model}  [dim]{detail}[/dim]",
                        classes="op-desc",
                    ))

        container.mount(Label(
            "[dim]Enter: edit  |  d: remove local preference  |  "
            "\u2191\u2193: navigate  |  a/b/c/m/p/t: switch tabs[/dim]",
            classes="section-hint",
        ))

    def _handle_agent_pick(self, result):
        if result is None:
            return
        key = result["key"]
        value = result["value"]
        layer = self._editing_layer

        if layer == "user":
            local_data = dict(self.config_mgr.codeagent_local)
            if "defaults" not in local_data:
                local_data["defaults"] = {}
            local_data["defaults"][key] = value
            self.config_mgr.save_codeagent(
                self.config_mgr.codeagent_project, local_data,
            )
        else:
            project_data = dict(self.config_mgr.codeagent_project)
            if "defaults" not in project_data:
                project_data["defaults"] = {}
            project_data["defaults"][key] = value
            local_data = dict(self.config_mgr.codeagent_local)
            if "defaults" in local_data and key in local_data["defaults"]:
                del local_data["defaults"][key]
                if not local_data["defaults"]:
                    del local_data["defaults"]
            self.config_mgr.save_codeagent(project_data, local_data)

        self.config_mgr.load_all()
        self._populate_agent_tab()
        self.notify(f"Saved {key} = {value} ({layer})")

    def _handle_launch_mode_pick(self, result):
        if result is None:
            return
        key = result["key"]
        value = result["value"]
        layer = self._editing_layer

        if layer == "user":
            local_data = dict(self.config_mgr.codeagent_local)
            if "defaults" not in local_data:
                local_data["defaults"] = {}
            local_data["defaults"][key] = value
            self.config_mgr.save_codeagent(
                self.config_mgr.codeagent_project, local_data,
            )
        else:
            project_data = dict(self.config_mgr.codeagent_project)
            if "defaults" not in project_data:
                project_data["defaults"] = {}
            project_data["defaults"][key] = value
            local_data = dict(self.config_mgr.codeagent_local)
            if "defaults" in local_data and key in local_data["defaults"]:
                del local_data["defaults"][key]
                if not local_data["defaults"]:
                    del local_data["defaults"]
            self.config_mgr.save_codeagent(project_data, local_data)

        self.config_mgr.load_all()
        self._populate_agent_tab()
        self.notify(f"Saved {key} = {value} ({layer})")

    def _clear_user_override(self, key: str):
        """Remove a user-level override for an operation."""
        local_data = dict(self.config_mgr.codeagent_local)
        if "defaults" in local_data and key in local_data["defaults"]:
            del local_data["defaults"][key]
            if not local_data["defaults"]:
                del local_data["defaults"]
            self.config_mgr.save_codeagent(
                self.config_mgr.codeagent_project, local_data,
            )
            self.config_mgr.load_all()
            self._populate_agent_tab()
            self.notify(f"Cleared user override for {key}")
        else:
            self.notify(f"No user override to clear for {key}", severity="warning")

    # -------------------------------------------------------------------
    # Board tab
    # -------------------------------------------------------------------
    def _populate_board_tab(self):
        container = self.query_one("#board_content", VerticalScroll)
        container.remove_children()

        # Increment counter to ensure unique widget IDs (remove_children is async)
        self._repop_counter += 1
        rc = self._repop_counter

        # Columns (read-only)
        container.mount(Label("Columns [dim](read-only — edit via board TUI)[/dim]",
                              classes="section-header"))
        columns = self.board_columns
        for col in columns:
            cid = col.get("id", "?")
            title = col.get("title", "?")
            color = col.get("color", "?")
            container.mount(Static(f"    {cid}: {title}  ({color})", classes="model-row"))

        # User settings (editable)
        container.mount(Label("User Settings", classes="section-header"))

        settings = self.config_mgr.board.get("settings", {})
        current_refresh = str(settings.get("auto_refresh_minutes", 5))
        if current_refresh not in DEFAULT_REFRESH_OPTIONS:
            current_refresh = "5"
        container.mount(CycleField("Auto-refresh (min)", DEFAULT_REFRESH_OPTIONS,
                                   current_refresh, "auto_refresh_minutes",
                                   id=f"board_cf_refresh_{rc}"))
        container.mount(Label("  [dim]0 = disabled[/dim]", classes="section-hint"))

        current_sync = "yes" if settings.get("sync_on_refresh", False) else "no"
        container.mount(CycleField("Sync on refresh", ["no", "yes"], current_sync,
                                   "sync_on_refresh", id=f"board_cf_sync_{rc}"))
        container.mount(Label("  [dim]Push/pull task data on each auto-refresh[/dim]",
                              classes="section-hint"))

        hbox = Horizontal(classes="tab-buttons")
        container.mount(hbox)
        hbox.mount(Button("Save Board Settings", variant="success",
                          id=f"btn_board_save_{rc}"))
        hbox.mount(Button("Revert Board Settings", variant="warning",
                          id=f"btn_board_revert_{rc}"))

        container.mount(Label(
            "[dim]\u2191\u2193: navigate  |  \u25c0\u25b6: cycle options  "
            "|  a/b/c/m/p/t: switch tabs[/dim]",
            classes="section-hint",
        ))

    @property
    def board_columns(self) -> list:
        return self.config_mgr.board.get("columns", [])

    def save_board_settings(self):
        container = self.query_one("#board_content", VerticalScroll)
        cycle_fields = list(container.query(CycleField))
        refresh_field = next(cf for cf in cycle_fields if cf.field_key == "auto_refresh_minutes")
        sync_field = next(cf for cf in cycle_fields if cf.field_key == "sync_on_refresh")

        merged = dict(self.config_mgr.board)
        if "settings" not in merged:
            merged["settings"] = {}
        merged["settings"]["auto_refresh_minutes"] = int(refresh_field.current_value)
        merged["settings"]["sync_on_refresh"] = sync_field.current_value == "yes"

        self.config_mgr.save_board(merged)
        self.config_mgr.load_all()
        self.notify("Board settings saved")

    def _revert_board_settings(self):
        """Revert board settings to their on-disk state."""
        self.config_mgr.load_all()
        self._populate_board_tab()
        self.notify("Board settings reverted")

    # -------------------------------------------------------------------
    # Project Config tab (editable)
    # -------------------------------------------------------------------
    def _populate_project_tab(self):
        container = self.query_one("#project_content", VerticalScroll)
        container.remove_children()

        self._repop_counter += 1
        rc = self._repop_counter

        container.mount(Label("Project Config", classes="section-header"))
        container.mount(Label(
            "[dim]Edit shared values stored in aitasks/metadata/project_config.yaml. "
            "These settings are git-tracked and apply to the full project.[/dim]",
            classes="section-hint",
        ))

        dp_values = self.config_mgr.project_config.get("default_profiles")
        if not isinstance(dp_values, dict):
            dp_values = {}
        for key, info in PROJECT_CONFIG_SCHEMA.items():
            if key == "default_profiles":
                # Render as section header + individual skill rows
                container.mount(Label(
                    f"  [bold]default_profiles:[/bold]", classes="section-hint",
                ))
                container.mount(Label(
                    f"      [dim]{info['summary']}[/dim]",
                    classes="section-hint",
                ))
                for skill in sorted(VALID_PROFILE_SKILLS):
                    profile_name = dp_values.get(skill, "")
                    display = profile_name or "(not set)"
                    container.mount(ConfigRow(
                        skill, display, config_layer="project", row_key=skill,
                        id=f"project_dp_{_safe_id(skill)}_{rc}",
                        raw_value=profile_name,
                    ))
                continue
            raw_value = self.config_mgr.project_config.get(key)
            formatted = _format_yaml_value(raw_value)
            display_value = formatted or "(not set)"
            if key in ("verify_build", "test_command", "lint_command") and raw_value is not None:
                cmd_presets = _load_command_presets(key)
                preset_name = _match_preset_name(formatted, cmd_presets)
                if preset_name:
                    display_value = f"{display_value}  [dim](preset: {preset_name})[/dim]"
            container.mount(ConfigRow(
                key, display_value, config_layer="project", row_key=key,
                id=f"project_cfg_{_safe_id(key)}_{rc}",
                raw_value=formatted,
            ))
            container.mount(Label(
                f"      [dim]{info['summary']}[/dim]",
                classes="section-hint",
            ))
            if key == "verify_build":
                container.mount(Label(
                    f"      [dim]Docs: {_BUILD_VERIFY_DOCS}[/dim]",
                    classes="section-hint",
                ))

        hbox = Horizontal(classes="tab-buttons")
        container.mount(hbox)
        hbox.mount(Button("Save Project Config", variant="success",
                          id=f"btn_project_save_{rc}"))
        hbox.mount(Button("Revert Project Config", variant="warning",
                          id=f"btn_project_revert_{rc}"))

        container.mount(Label(
            "[dim]Enter: edit  |  ↑↓: navigate  |  a/b/c/m/p/t: switch tabs[/dim]",
            classes="section-hint",
        ))

    def save_project_settings(self):
        container = self.query_one("#project_content", VerticalScroll)
        rows = list(container.query(ConfigRow))

        data = dict(self.config_mgr.project_config)

        # Collect default_profiles from individual skill rows
        dp = {}
        for row in rows:
            if not row.id or not row.id.startswith("project_dp_"):
                continue
            val = (row.raw_value or "").strip()
            if val:
                dp[row.row_key] = val
        if dp:
            data["default_profiles"] = dp
        else:
            data.pop("default_profiles", None)

        for row in rows:
            if not row.id or not row.id.startswith("project_cfg_"):
                continue
            key = row.row_key
            raw_value = row.raw_value.strip()
            if not raw_value:
                data.pop(key, None)
                continue
            try:
                data[key] = yaml.safe_load(raw_value)
            except yaml.YAMLError as exc:
                self.notify(f"Invalid YAML for {key}: {exc}", severity="error")
                return

        self.config_mgr.save_project_settings(data)
        self.config_mgr.load_all()
        self._populate_project_tab()
        self.notify("Project config saved")

    def _revert_project_settings(self):
        self.config_mgr.load_all()
        self._populate_project_tab()
        self.notify("Project config reverted")

    def _handle_project_config_edit(self, result):
        if result is None:
            return
        key = result["key"]
        value = result["value"]

        row_id = getattr(self, "_editing_project_row_id", None)
        if not row_id:
            rc = self._repop_counter
            row_id = f"project_cfg_{_safe_id(key)}_{rc}"
        try:
            row = self.query_one(f"#{row_id}", ConfigRow)
            row.raw_value = value
            display = _format_yaml_value(value) or "(not set)"
            if key in ("verify_build", "test_command", "lint_command") and value:
                presets = _load_command_presets(key)
                preset_name = _match_preset_name(value, presets)
                if preset_name:
                    display = f"{display}  [dim](preset: {preset_name})[/dim]"
            row.value = display
            row.refresh()
            self.notify(f"Updated {key} — press Save to persist")
        except Exception as exc:
            self.notify(f"Could not update {key}: {exc}", severity="error")

    def _handle_default_profile_pick(self, result):
        if result is None:
            return
        skill = result["key"]
        profile_name = result["value"]

        row_id = getattr(self, "_editing_project_row_id", None)
        if not row_id:
            rc = self._repop_counter
            row_id = f"project_dp_{_safe_id(skill)}_{rc}"
        try:
            row = self.query_one(f"#{row_id}", ConfigRow)
            row.raw_value = profile_name
            row.value = profile_name or "(not set)"
            row.refresh()
            self.notify(f"Updated {skill} — press Save to persist")
        except Exception as exc:
            self.notify(f"Could not update {skill}: {exc}", severity="error")

    # -------------------------------------------------------------------
    # Tmux tab (editable — writes to project_config.yaml tmux: section)
    # -------------------------------------------------------------------
    def _populate_tmux_tab(self):
        container = self.query_one("#tmux_content", VerticalScroll)
        container.remove_children()

        self._repop_counter += 1
        rc = self._repop_counter
        self._tmux_tab_rc = rc

        container.mount(Label("Tmux Settings", classes="section-header"))
        container.mount(Label(
            "[dim]Configure tmux defaults for agent launch dialogs. "
            "Stored in aitasks/metadata/project_config.yaml under the tmux: section.[/dim]",
            classes="section-hint",
        ))

        tmux = self.config_mgr.project_config.get("tmux")
        if not isinstance(tmux, dict):
            tmux = {}

        for key, info in TMUX_CONFIG_SCHEMA.items():
            stype = info.get("type", "string")
            current = tmux.get(key)

            if stype == "string":
                display = str(current) if current is not None else info["default"]
                container.mount(ConfigRow(
                    key, display, config_layer="project", row_key=key,
                    id=f"tmux_cfg_{_safe_id(key)}_{rc}",
                    raw_value=display,
                ))
            elif stype == "enum":
                options = info["options"].split(",")
                if key == "git_tui":
                    installed = detect_git_tuis()
                    if installed:
                        options = installed + ["none"]
                cur_val = str(current) if current is not None else info["default"]
                if cur_val not in options:
                    cur_val = info["default"]
                container.mount(CycleField(
                    key, options, cur_val, field_key=key,
                    id=f"tmux_cycle_{_safe_id(key)}_{rc}",
                ))
            elif stype == "bool":
                cur_val = str(current).lower() if current is not None else info["default"]
                if cur_val not in ("true", "false"):
                    cur_val = info["default"]
                container.mount(CycleField(
                    key, ["false", "true"], cur_val, field_key=key,
                    id=f"tmux_cycle_{_safe_id(key)}_{rc}",
                ))

            container.mount(Label(
                f"      [dim]{info['summary']}[/dim]",
                classes="section-hint",
            ))

        hbox = Horizontal(classes="tab-buttons")
        container.mount(hbox)
        hbox.mount(Button("Save Tmux Settings", variant="success",
                          id=f"btn_tmux_save_{rc}"))
        hbox.mount(Button("Revert Tmux Settings", variant="warning",
                          id=f"btn_tmux_revert_{rc}"))

        container.mount(Label(
            "[dim]Enter: edit  |  ←→: cycle  |  ↑↓: navigate  |  a/b/c/m/p/t: switch tabs[/dim]",
            classes="section-hint",
        ))

    def save_tmux_settings(self):
        container = self.query_one("#tmux_content", VerticalScroll)
        tmux_data: dict = {}
        rc = self._tmux_tab_rc

        for key, info in TMUX_CONFIG_SCHEMA.items():
            stype = info.get("type", "string")

            if stype == "string":
                widget_id = f"tmux_cfg_{_safe_id(key)}_{rc}"
                try:
                    row = self.query_one(f"#{widget_id}", ConfigRow)
                    val = (row.raw_value or "").strip()
                    if val:
                        tmux_data[key] = val
                except Exception:
                    pass
            elif stype in ("enum", "bool"):
                widget_id = f"tmux_cycle_{_safe_id(key)}_{rc}"
                try:
                    field = self.query_one(f"#{widget_id}", CycleField)
                    val = field.current_value
                    if stype == "bool":
                        tmux_data[key] = val == "true"
                    else:
                        tmux_data[key] = val
                except Exception:
                    pass

        data = dict(self.config_mgr.project_config)
        if tmux_data:
            existing_tmux = dict(data.get("tmux") or {})
            existing_tmux.update(tmux_data)
            data["tmux"] = existing_tmux
        else:
            existing_tmux = dict(data.get("tmux") or {})
            for key in TMUX_CONFIG_SCHEMA:
                existing_tmux.pop(key, None)
            if existing_tmux:
                data["tmux"] = existing_tmux
            else:
                data.pop("tmux", None)
        self.config_mgr.save_project_settings(data)
        self.config_mgr.load_all()
        self._populate_tmux_tab()
        self.notify("Tmux settings saved")

    def _revert_tmux_settings(self):
        self.config_mgr.load_all()
        self._populate_tmux_tab()
        self.notify("Tmux settings reverted")

    def _handle_tmux_config_edit(self, result):
        if result is None:
            return
        key = result["key"]
        value = result["value"]

        row_id = getattr(self, "_editing_tmux_row_id", None)
        if not row_id:
            rc = self._tmux_tab_rc
            row_id = f"tmux_cfg_{_safe_id(key)}_{rc}"
        try:
            row = self.query_one(f"#{row_id}", ConfigRow)
            row.raw_value = value
            row.value = value or "(not set)"
            row.refresh()
            self.notify(f"Updated {key} — press Save to persist")
        except Exception as exc:
            self.notify(f"Could not update {key}: {exc}", severity="error")

    # -------------------------------------------------------------------
    # Models tab (read-only)
    # -------------------------------------------------------------------
    def _populate_models_tab(self):
        container = self.query_one("#models_content", VerticalScroll)
        container.remove_children()

        if not self.config_mgr.models:
            container.mount(Label("No model files found.", classes="section-header"))
            container.mount(Label(
                "[dim]\u2191\u2193: navigate  |  a/b/c/m/p/t: switch tabs[/dim]",
                classes="section-hint",
            ))
            return

        for provider, data in sorted(self.config_mgr.models.items()):
            container.mount(Label(f"{provider.capitalize()} Models",
                                  classes="section-header"))
            models = data.get("models", [])
            if not models:
                container.mount(Static("    (no models)", classes="model-row"))
                continue

            # Header
            container.mount(Static(
                f"    {'Name':<16} {'CLI ID':<30} {'Status':<12} {'Notes'}",
                classes="model-header",
            ))

            for m in models:
                name = m.get("name", "?")
                cli_id = m.get("cli_id", "?")
                notes = m.get("notes", "")
                status = m.get("status", "active")
                # Build rich score string from verifiedstats or verified
                vs = m.get("verifiedstats", {})
                score_parts = []
                for op, buckets in vs.items():
                    if not isinstance(buckets, dict):
                        continue
                    detail = _format_op_stats(buckets, compact=False)
                    if detail:
                        score_parts.append(f"{op}: {detail}")
                if not score_parts:
                    # Fall back to flat verified dict
                    verified = m.get("verified", {})
                    for k, v in verified.items():
                        if v:
                            score_parts.append(f"{k}: {v}")
                score_str = (
                    f"  [dim]{' | '.join(score_parts)}[/dim]"
                    if score_parts else ""
                )
                if status == "unavailable":
                    container.mount(Static(
                        f"    [dim]{name:<16} {cli_id:<30} {'[UNAVAIL]':<12} {notes}{score_str}[/dim]",
                        classes="model-row",
                    ))
                else:
                    container.mount(Static(
                        f"    {name:<16} {cli_id:<30} {'active':<12} {notes}{score_str}",
                        classes="model-row",
                    ))
                # All-providers summary if model is shared across providers
                if cli_id != "?":
                    agg = _aggregate_verifiedstats(
                        self.config_mgr.models, cli_id,
                    )
                    # Check if agg has more runs than this provider alone
                    provider_total = sum(
                        vs.get(op, {}).get("all_time", {}).get("runs", 0)
                        for op in agg
                    )
                    agg_total = sum(
                        agg[op].get("all_time", {}).get("runs", 0)
                        for op in agg
                    )
                    if agg_total > 0 and agg_total > provider_total:
                        agg_parts = []
                        for op, buckets in agg.items():
                            detail = _format_op_stats(buckets, compact=False)
                            if detail:
                                agg_parts.append(f"{op}: {detail}")
                        if agg_parts:
                            container.mount(Static(
                                f"    [dim]  all providers: "
                                f"{' | '.join(agg_parts)}[/dim]",
                                classes="model-row",
                            ))

        container.mount(Label(""))
        container.mount(Label(
            "[dim]Model lists are managed by 'ait codeagent refresh'. "
            "Edit model files directly for manual changes.[/dim]",
            classes="section-hint",
        ))
        container.mount(Label(
            "[dim]\u2191\u2193: navigate  |  a/b/c/m/p/t: switch tabs[/dim]",
            classes="section-hint",
        ))

    # -------------------------------------------------------------------
    # Profiles tab (editable)
    # -------------------------------------------------------------------
    def _populate_profiles_tab(self, focus_widget_id: str | None = None):
        container = self.query_one("#profiles_content", VerticalScroll)
        container.remove_children()

        self._profile_id_map = {}
        self._repop_counter += 1
        rc = self._repop_counter
        self._profiles_tab_rc = rc
        self._profiles_focus_target = focus_widget_id

        # --- Explanation ---
        container.mount(Label("Execution Profiles", classes="section-header"))
        container.mount(Label(
            "[dim]Profiles pre-answer workflow questions to reduce interactive prompts.\n"
            "Used by: aitask-pick, aitask-explore, aitask-pickrem, "
            "aitask-pickweb, task-workflow\n\n"
            "Project-scoped profiles are git-tracked and shared with all users — "
            "changes affect everyone.\n"
            "User-scoped profiles (in profiles/local/) are gitignored and override "
            "project profiles with the same name.[/dim]",
            classes="section-hint",
        ))

        profiles = self.config_mgr.profiles
        if not profiles:
            container.mount(Label(
                "[dim]No profiles found in aitasks/metadata/profiles/[/dim]",
                classes="section-hint",
            ))
            container.mount(Button(
                "Create New Profile", variant="primary",
                id="btn_profile_add_new",
            ))
            container.mount(Label(
                "[dim]\u2191\u2193: navigate  |  a/b/c/m/p/t: switch tabs[/dim]",
                classes="section-hint",
            ))
            return

        # --- Profile selector ---
        profile_filenames = sorted(profiles.keys())
        selector_options = profile_filenames + ["+ Add new profile"]

        if self._selected_profile and self._selected_profile in profiles:
            current_selection = self._selected_profile
        else:
            current_selection = profile_filenames[0]
            self._selected_profile = current_selection

        container.mount(CycleField(
            "Profile", selector_options, current_selection,
            "profile_selector", id=f"cf_profile_selector_{rc}",
        ))

        if current_selection == "+ Add new profile":
            container.mount(Label(
                "[dim]Use \u25c0\u25b6 to select a profile or "
                "choose '+ Add new profile'[/dim]",
                classes="section-hint",
            ))
            container.mount(Label(
                "[dim]\u2191\u2193: navigate  |  \u25c0\u25b6: cycle options  "
                "|  a/b/c/m/p/t: switch tabs[/dim]",
                classes="section-hint",
            ))
            return

        # --- Profile detail area ---
        data = profiles[current_selection]
        safe_fn = _safe_id(current_selection)
        self._profile_id_map[safe_fn] = current_selection
        profile_name = data.get("name", current_selection)
        layer = self.config_mgr.profile_layers.get(current_selection, "project")
        if layer == "user":
            file_display = f"local/{current_selection}"
            scope_hint = "[dim](user-scoped, local only)[/dim]"
        else:
            file_display = current_selection
            scope_hint = "[dim](project-scoped, shared with team)[/dim]"

        container.mount(Label(""))
        container.mount(Label(
            f"Editing: [bold]{profile_name}[/bold] "
            f"[dim]({file_display})[/dim]  {scope_hint}",
            classes="profile-header",
        ))

        # Render fields grouped
        for group_label, field_keys in PROFILE_FIELD_GROUPS:
            container.mount(Label(f"  {group_label}", classes="section-header"))
            for key in field_keys:
                if key not in PROFILE_SCHEMA:
                    continue
                ktype, options = PROFILE_SCHEMA[key]
                current_raw = data.get(key)
                widget_id = f"profile_{key}__{safe_fn}_{rc}"

                if ktype == "bool":
                    if current_raw is True:
                        current = "true"
                    elif current_raw is False:
                        current = "false"
                    else:
                        current = _UNSET
                    container.mount(CycleField(
                        key, ["true", "false", _UNSET], current,
                        key, id=widget_id,
                    ))
                elif ktype == "enum":
                    opts = list(options or []) + [_UNSET]
                    current = str(current_raw) if current_raw is not None else _UNSET
                    if current not in opts:
                        opts.insert(0, current)
                    container.mount(CycleField(
                        key, opts, current, key, id=widget_id,
                    ))
                elif ktype == "string":
                    current = str(current_raw) if current_raw is not None else ""
                    row = ConfigRow(
                        key, current, config_layer="project", row_key=key,
                        id=f"profile_str_{key}__{safe_fn}_{rc}",
                    )
                    container.mount(row)

                # Field description
                info = PROFILE_FIELD_INFO.get(key)
                if info:
                    if self._expanded_field == key:
                        container.mount(Label(
                            f"      [dim]{info[1]}[/dim]",
                            classes="section-hint",
                        ))
                    else:
                        container.mount(Label(
                            f"      [dim]{info[0]}[/dim]",
                            classes="section-hint",
                        ))

        # --- Action buttons ---
        container.mount(Label(""))
        hbox = Horizontal(classes="tab-buttons")
        container.mount(hbox)
        hbox.mount(Button(
            f"Save {profile_name}", variant="success",
            id=f"btn_profile_save__{safe_fn}",
        ))
        hbox.mount(Button(
            f"Revert {profile_name}", variant="warning",
            id=f"btn_profile_revert__{safe_fn}",
        ))
        hbox.mount(Button(
            f"Delete {profile_name}", variant="error",
            id=f"btn_profile_delete__{safe_fn}",
        ))

        container.mount(Label(
            "[dim]\u2191\u2193: navigate  |  \u25c0\u25b6: cycle options  "
            "|  Enter: edit strings  |  ?: field details  "
            "|  a/b/c/m/p/t: switch tabs[/dim]",
            classes="section-hint",
        ))

        # Restore focus after repopulation
        if self._profiles_focus_target:
            target_id = self._profiles_focus_target
            self._profiles_focus_target = None
            self.call_after_refresh(self._focus_widget_by_id, target_id)

    def _focus_widget_by_id(self, widget_id: str) -> None:
        """Focus a widget by ID after refresh completes."""
        try:
            widget = self.query_one(f"#{widget_id}")
            if widget.can_focus:
                widget.focus()
        except Exception:
            pass

    @on(CycleField.Changed)
    def on_cycle_field_changed(self, event: CycleField.Changed):
        if event.field.field_key != "profile_selector":
            return
        new_value = event.value
        if new_value == "+ Add new profile":
            existing = sorted(self.config_mgr.profiles.keys())
            self.push_screen(
                NewProfileScreen(existing),
                callback=self._handle_new_profile,
            )
        else:
            self._selected_profile = new_value
            self._expanded_field = None
            rc = self._repop_counter + 1  # next repop counter
            self._populate_profiles_tab(
                focus_widget_id=f"cf_profile_selector_{rc}",
            )

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed):
        btn_id = event.button.id or ""
        if btn_id.startswith("btn_profile_save__"):
            safe_fn = btn_id.replace("btn_profile_save__", "")
            filename = self._profile_id_map.get(safe_fn, safe_fn)
            data = self.config_mgr.profiles.get(filename, {})
            profile_name = data.get("name", filename)
            self.push_screen(
                SaveProfileConfirmScreen(profile_name, filename),
                callback=lambda result, fn=filename:
                    self._handle_save_profile(result, fn),
            )
        elif btn_id.startswith("btn_profile_delete__"):
            safe_fn = btn_id.replace("btn_profile_delete__", "")
            filename = self._profile_id_map.get(safe_fn, safe_fn)
            data = self.config_mgr.profiles.get(filename, {})
            profile_name = data.get("name", filename)
            self.push_screen(
                DeleteProfileConfirmScreen(profile_name, filename),
                callback=lambda confirmed, fn=filename:
                    self._handle_delete_profile(bool(confirmed), fn),
            )
        elif btn_id.startswith("btn_profile_revert__"):
            safe_fn = btn_id.replace("btn_profile_revert__", "")
            filename = self._profile_id_map.get(safe_fn, safe_fn)
            self._revert_profile(filename)
        elif btn_id.startswith("btn_board_save"):
            self.save_board_settings()
        elif btn_id.startswith("btn_board_revert"):
            self._revert_board_settings()
        elif btn_id.startswith("btn_project_save"):
            self.save_project_settings()
        elif btn_id.startswith("btn_project_revert"):
            self._revert_project_settings()
        elif btn_id.startswith("btn_tmux_save"):
            self.save_tmux_settings()
        elif btn_id.startswith("btn_tmux_revert"):
            self._revert_tmux_settings()
        elif btn_id == "btn_profile_add_new":
            existing = sorted(self.config_mgr.profiles.keys())
            self.push_screen(
                NewProfileScreen(existing),
                callback=self._handle_new_profile,
            )

    def _save_profile(self, filename: str):
        data = dict(self.config_mgr.profiles.get(filename, {}))
        safe_fn = _safe_id(filename)
        rc = self._profiles_tab_rc

        for key, (ktype, options) in PROFILE_SCHEMA.items():
            widget_id = f"profile_{key}__{safe_fn}_{rc}"
            str_widget_id = f"profile_str_{key}__{safe_fn}_{rc}"

            if ktype in ("bool", "enum"):
                try:
                    field = self.query_one(f"#{widget_id}", CycleField)
                    val = field.current_value
                    if val == _UNSET:
                        data.pop(key, None)
                    elif ktype == "bool":
                        data[key] = val == "true"
                    else:
                        data[key] = val
                except Exception:
                    pass
            elif ktype == "string":
                try:
                    row = self.query_one(f"#{str_widget_id}", ConfigRow)
                    val = row.value
                    if val:
                        data[key] = val
                    else:
                        data.pop(key, None)
                except Exception:
                    pass

        layer = self.config_mgr.profile_layers.get(filename, "project")
        self.config_mgr.save_profile(filename, data, layer=layer)
        self.notify(f"Profile '{filename}' saved")

    def _handle_save_profile(self, result: str | None, filename: str):
        if result is None:
            return
        self._save_profile(filename)
        if result == "save_commit":
            self._commit_profile(filename)

    def _commit_profile(self, filename: str):
        layer = self.config_mgr.profile_layers.get(filename, "project")
        if layer == "user":
            path = LOCAL_PROFILES_DIR / filename
        else:
            path = PROFILES_DIR / filename
        data = self.config_mgr.profiles.get(filename, {})
        name = data.get("name", filename)
        git_cmd = _task_git_cmd()
        try:
            subprocess.run(
                [*git_cmd, "add", str(path)],
                capture_output=True, timeout=5,
            )
            result = subprocess.run(
                [*git_cmd, "commit", "-m",
                 f"ait: Updated execution profile {name}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                self.notify(f"Committed profile '{name}'")
            else:
                self.notify(
                    f"Commit failed: {result.stderr.strip()}",
                    severity="error",
                )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            self.notify(f"Git error: {exc}", severity="error")

    def _revert_profile(self, filename: str):
        """Revert a profile to its on-disk state, discarding unsaved changes."""
        layer = self.config_mgr.profile_layers.get(filename, "project")
        if layer == "user":
            path = LOCAL_PROFILES_DIR / filename
        else:
            path = PROFILES_DIR / filename
        if not path.is_file():
            self.notify(f"Profile file not found: {filename}", severity="error")
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if isinstance(data, dict):
                self.config_mgr.profiles[filename] = data
        except Exception as exc:
            self.notify(f"Failed to reload {filename}: {exc}", severity="error")
            return
        self._populate_profiles_tab()
        self.notify(f"Reverted '{filename}' to saved state")

    def _handle_new_profile(self, result):
        if result is None:
            # User cancelled — re-select previous profile
            if self._selected_profile == "+ Add new profile":
                profiles = sorted(self.config_mgr.profiles.keys())
                self._selected_profile = profiles[0] if profiles else None
            self._populate_profiles_tab()
            return

        filename = result["filename"]
        base = result["base"]
        layer = result.get("layer", "project")

        if filename in self.config_mgr.profiles:
            self.notify(f"Profile '{filename}' already exists", severity="error")
            self._populate_profiles_tab()
            return

        if base and base != "(empty)" and base in self.config_mgr.profiles:
            new_data = dict(self.config_mgr.profiles[base])
        else:
            new_data = {}

        new_data["name"] = filename.replace(".yaml", "")
        new_data["description"] = ""

        self.config_mgr.save_profile(filename, new_data, layer=layer)
        self._selected_profile = filename
        self.config_mgr.load_profiles()
        self._populate_profiles_tab()
        self.notify(f"Created {layer} profile '{filename}' (based on {base})")

    def _handle_delete_profile(self, confirmed: bool, filename: str):
        if not confirmed:
            return
        self.config_mgr.delete_profile(filename)
        remaining = sorted(self.config_mgr.profiles.keys())
        self._selected_profile = remaining[0] if remaining else None
        self._populate_profiles_tab()
        self.notify(f"Deleted profile '{filename}'")

    def _handle_profile_string_edit(self, result, profile_filename: str):
        if result is None:
            return
        key = result["key"]
        value = result["value"]

        rc = self._profiles_tab_rc
        str_widget_id = f"profile_str_{key}__{_safe_id(profile_filename)}_{rc}"
        try:
            row = self.query_one(f"#{str_widget_id}", ConfigRow)
            row.value = value
            row.refresh()
        except Exception:
            pass
        self.notify(f"Updated {key} — press Save to persist")

    # -------------------------------------------------------------------
    # Actions: Export, Import, Reload
    # -------------------------------------------------------------------
    def action_export_configs(self):
        self.push_screen(ExportScreen(), callback=self._handle_export)

    def _handle_export(self, result):
        if result is None:
            return
        try:
            directory = result.get("directory", ".")
            patterns = result.get("patterns") or None
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(
                directory, f"aitasks_config_export_{timestamp}{EXPORT_EXTENSION}",
            )
            bundle = export_all_configs(out_path, str(METADATA_DIR), patterns=patterns)
            count = bundle.get("_export_meta", {}).get("file_count", 0)
            self.notify(f"Exported {count} files to {out_path}")
        except Exception as exc:
            self.notify(f"Export failed: {exc}", severity="error")

    def action_import_configs(self):
        self.push_screen(ImportScreen(), callback=self._handle_import)

    def _handle_import(self, result):
        if result is None:
            return
        try:
            written = import_all_configs(
                result["path"], str(METADATA_DIR),
                overwrite=result.get("overwrite", False),
                selected_files=result.get("selected_files"),
            )
            self.config_mgr.load_all()
            self._populate_agent_tab()
            self._populate_board_tab()
            self._populate_project_tab()
            self._populate_models_tab()
            self._populate_profiles_tab()
            self.notify(f"Imported {len(written)} files")
        except Exception as exc:
            self.notify(f"Import failed: {exc}", severity="error")

    def action_reload_configs(self):
        self.config_mgr.load_all()
        self._populate_agent_tab()
        self._populate_board_tab()
        self._populate_project_tab()
        self._populate_models_tab()
        self._populate_profiles_tab()
        self.notify("Configs reloaded from disk")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = SettingsApp()
    app.run()
