"""Layered config for the stats TUI.

Runtime saves write ONLY the user layer (`stats_config.local.json`, gitignored).
The project-level `stats_config.json` is treated as read-only at runtime — it
ships with the repo and is edited only via explicit, out-of-TUI actions.
"""
from __future__ import annotations

from lib.config_utils import (
    load_layered_config,
    local_path_for,
    save_local_config,
)

METADATA_FILE = "aitasks/metadata/stats_config.json"

DEFAULT_PRESETS: dict[str, list[str]] = {
    "overview": ["overview.summary", "overview.daily", "overview.weekday"],
    "labels":   ["labels.top", "labels.issue_types", "labels.heatmap"],
    "agents":   ["agents.per_agent", "agents.per_model", "agents.verified", "agents.usage"],
    "velocity": ["velocity.daily", "velocity.rolling", "velocity.parent_child"],
    "sessions": ["sessions.totals", "overview.summary", "overview.daily"],
}

DEFAULTS: dict = {
    "presets": DEFAULT_PRESETS,
    "active": "overview",
    "days": 7,
    "week_start": "mon",
    "custom": {},
}

_USER_KEYS = ("active", "days", "week_start", "custom")


def load() -> dict:
    return load_layered_config(METADATA_FILE, defaults=DEFAULTS)


def save(config: dict) -> None:
    user_data = {k: config[k] for k in _USER_KEYS if k in config}
    save_local_config(str(local_path_for(METADATA_FILE)), user_data)


def resolve_active_layout(config: dict) -> list[str]:
    active = config.get("active", "overview")
    presets = config.get("presets", DEFAULT_PRESETS)
    customs = config.get("custom", {})
    if active in customs:
        return list(customs[active])
    if active in presets:
        return list(presets[active])
    return list(presets.get("overview", DEFAULT_PRESETS["overview"]))
