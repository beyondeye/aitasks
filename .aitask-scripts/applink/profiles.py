"""Permission-profile gating for the ait applink server (t822_7).

Loads the permission profiles from ``aitasks/metadata/applink_profiles/*.yaml``
and answers two questions the frame router asks per command verb: is this verb
allowed for the session's profile, and (when denied) what is the lowest profile
that would allow it — for the ``PERMISSION_DENIED`` ``detail.required_profile``
field (``aidocs/applink/permissions.md``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Tier order (low → high) for required_profile resolution.
PROFILE_TIERS = ["read_only", "monitor_control", "full"]

# Built-in fallback allowed_verbs (cumulative), aligned with the canonical verb
# table in aidocs/applink/monitor_port_design.md. Used only when the on-disk
# applink_profiles/ directory is missing or unreadable.
DEFAULT_ALLOWED = {
    "read_only": ["snapshot", "task_detail"],
    "monitor_control": [
        "snapshot", "task_detail",
        "send_enter", "send_keys", "forward_key", "focus", "cycle_compare_mode",
    ],
    "full": [
        "snapshot", "task_detail",
        "send_enter", "send_keys", "forward_key", "focus", "cycle_compare_mode",
        "kill_pane", "kill_window", "spawn_tui",
    ],
}


@dataclass
class Profile:
    name: str
    description: str
    allowed_verbs: frozenset


class ProfileGate:
    def __init__(self, profiles: dict[str, Profile]) -> None:
        self._profiles = profiles

    @classmethod
    def load(cls, profiles_dir: Path) -> "ProfileGate":
        profiles = cls._load_from_dir(profiles_dir)
        if not profiles:
            profiles = {
                name: Profile(name, "(built-in default)", frozenset(verbs))
                for name, verbs in DEFAULT_ALLOWED.items()
            }
        return cls(profiles)

    @staticmethod
    def _load_from_dir(profiles_dir: Path) -> dict[str, Profile]:
        if not profiles_dir.is_dir():
            return {}
        try:
            import yaml
        except ImportError:
            return {}
        out: dict[str, Profile] = {}
        for path in sorted(profiles_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text()) or {}
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            name = str(data.get("name") or path.stem)
            verbs = data.get("allowed_verbs") or []
            if not isinstance(verbs, list):
                continue
            out[name] = Profile(
                name=name,
                description=str(data.get("description", "")),
                allowed_verbs=frozenset(str(v) for v in verbs),
            )
        return out

    def names(self) -> list[str]:
        return list(self._profiles)

    def get(self, name: str) -> Profile | None:
        return self._profiles.get(name)

    def is_allowed(self, profile_name: str, verb: str) -> bool:
        profile = self._profiles.get(profile_name)
        return bool(profile and verb in profile.allowed_verbs)

    def required_profile(self, verb: str) -> str | None:
        """Lowest-tier profile whose allowed_verbs contains *verb* (or None)."""
        ordered = [n for n in PROFILE_TIERS if n in self._profiles]
        ordered += [n for n in self._profiles if n not in PROFILE_TIERS]
        for name in ordered:
            if verb in self._profiles[name].allowed_verbs:
                return name
        return None
