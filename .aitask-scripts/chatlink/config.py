"""Shared chatlink gateway config: schema + fault-tolerant loader (t1120_2).

Loads ``aitasks/metadata/chatlink_config.yaml`` (pinned contract 10) into a
:class:`ChatlinkConfig`. Load policy (applink ``server.load_applink_config``
style):

- **Missing / unreadable / malformed-YAML / non-mapping file ⇒ ``None``** —
  fail-closed; the daemon refuses to start with a clear message.
- A present mapping with bad values ⇒ **each key degrades independently** to
  its clamped default with a warning on stderr (never raises).

Gateway-side, but deliberately ``chat``-import-free: ``intake_channel`` is
stored as the serialized ``ConversationRef.to_dict()`` dict, normalized to
exactly that shape so the daemon's ``ConversationRef.from_dict`` cannot raise
(``chat/model.py`` round-trip contract). The ceilings (pinned contract 11) are
defined here and enforced by t1120_3 (intake) and t1120_5 (container).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Ceiling defaults + clamp ranges (pinned contract 11; applink server.py
# ceilings-as-constants style). Values outside the range clamp to the nearest
# bound; non-int values fall back to the default.
DEFAULT_MAX_CONCURRENT_SANDBOXES = 2
RANGE_MAX_CONCURRENT_SANDBOXES = (1, 16)
DEFAULT_INTAKE_RATE_PER_USER_PER_HOUR = 4
RANGE_INTAKE_RATE_PER_USER_PER_HOUR = (1, 60)
DEFAULT_SANDBOX_MEMORY = "2g"
SANDBOX_MEMORY_RE = re.compile(r"^[0-9]+[kmg]$")
DEFAULT_SANDBOX_CPUS = 2
RANGE_SANDBOX_CPUS = (1, 16)
DEFAULT_SANDBOX_PIDS = 512
RANGE_SANDBOX_PIDS = (16, 4096)
DEFAULT_SANDBOX_WALL_CLOCK_S = 1800
RANGE_SANDBOX_WALL_CLOCK_S = (60, 14400)

DENY_MESSAGE_MODES = ("ignore", "ephemeral")
DEFAULT_DENY_MESSAGE_MODE = "ignore"

#: Env-var NAMES the gateway resolves from its own environment at launch
#: time and passes into the sandbox (contract 10: the LLM API key — never
#: the bot token, never git credentials). Values never live in the config
#: file. t1139 extends this surface — keep it a plain list of names.
ENV_PASSTHROUGH_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")

#: Required non-empty str keys of a serialized ConversationRef.
_INTAKE_REQUIRED = ("provider", "workspace_id", "conversation_id")


def _warn(msg: str) -> None:
    print(f"chatlink config: {msg}", file=sys.stderr)


@dataclass
class ChatlinkConfig:
    """Validated gateway config. All fields are safe to consume as-is."""

    #: Serialized ``ConversationRef.to_dict()`` of the bug-intake channel,
    #: normalized (see :func:`_normalize_intake_channel`) so
    #: ``ConversationRef.from_dict`` cannot raise. ``None`` ⇒ intake refused.
    intake_channel: dict | None = None
    allowed_user_ids: list[str] = field(default_factory=list)
    allowed_role_ids: list[str] = field(default_factory=list)
    deny_message_mode: str = DEFAULT_DENY_MESSAGE_MODE
    #: Optional logical project name for audit/display (contract 10 "repo
    #: linkage" — the operative repo is the one this config lives in).
    repo_name: str | None = None
    # Ceilings (pinned contract 11).
    max_concurrent_sandboxes: int = DEFAULT_MAX_CONCURRENT_SANDBOXES
    intake_rate_per_user_per_hour: int = DEFAULT_INTAKE_RATE_PER_USER_PER_HOUR
    sandbox_memory: str = DEFAULT_SANDBOX_MEMORY
    sandbox_cpus: int = DEFAULT_SANDBOX_CPUS
    sandbox_pids: int = DEFAULT_SANDBOX_PIDS
    sandbox_wall_clock_s: int = DEFAULT_SANDBOX_WALL_CLOCK_S
    #: Env-var names resolved from the gateway environment into
    #: ``SandboxSpec.env_allowlist`` at launch (see module constant).
    sandbox_env_passthrough: list[str] = field(default_factory=list)


def _clamped_int(raw: object, default: int, lo: int, hi: int, key: str) -> int:
    """``raw`` → int within ``[lo, hi]``; non-int ⇒ default, out-of-range ⇒
    clamped bound — each with a warning."""
    if raw is None:
        return default
    try:
        val = int(raw)  # bool is an int subclass but a config bool is a typo
        if isinstance(raw, bool):
            raise TypeError
    except (TypeError, ValueError):
        _warn(f"{key}: non-integer value {raw!r} — using default {default}")
        return default
    if val < lo or val > hi:
        clamped = min(max(val, lo), hi)
        _warn(f"{key}: {val} outside [{lo}, {hi}] — clamped to {clamped}")
        return clamped
    return val


def _str_list(raw: object, key: str) -> list[str]:
    """Coerce a YAML list of scalars to ``list[str]``; drop non-scalars."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        _warn(f"{key}: expected a list, got {type(raw).__name__} — using []")
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, (str, int)) and not isinstance(item, bool):
            text = str(item).strip()
            if text:
                out.append(text)
                continue
        _warn(f"{key}: dropping non-scalar/empty entry {item!r}")
    return out


def _env_name_list(raw: object, key: str) -> list[str]:
    """Coerce to a list of valid env-var names; drop invalid entries.

    Per-entry degradation (same policy as the other keys): a non-list ⇒
    ``[]`` with a warning; each entry must match
    :data:`ENV_PASSTHROUGH_NAME_RE`, else it is dropped with a warning.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        _warn(f"{key}: expected a list, got {type(raw).__name__} — using []")
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and ENV_PASSTHROUGH_NAME_RE.match(item):
            out.append(item)
        else:
            _warn(f"{key}: dropping invalid env-var name {item!r}")
    return out


def _normalize_intake_channel(raw: object) -> dict | None:
    """Normalize to exactly the ``ConversationRef.to_dict()`` shape.

    Required non-empty str keys ``provider`` / ``workspace_id`` /
    ``conversation_id``; ``thread_id`` str-or-None; ``metadata`` dict (a
    scalar/list would crash ``ConversationRef.from_dict``'s
    ``dict(d.get("metadata", {}))`` in the daemon — dropped to ``{}``);
    unknown extra keys dropped. Invalid required shape ⇒ ``None``.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        _warn(f"intake_channel: expected a mapping, got {type(raw).__name__}")
        return None
    ref: dict = {}
    for key in _INTAKE_REQUIRED:
        val = raw.get(key)
        if not isinstance(val, str) or not val.strip():
            _warn(f"intake_channel.{key}: missing/empty — intake channel unset")
            return None
        ref[key] = val.strip()
    thread_id = raw.get("thread_id")
    if thread_id is not None and not isinstance(thread_id, str):
        _warn(f"intake_channel.thread_id: non-string {thread_id!r} — using null")
        thread_id = None
    ref["thread_id"] = thread_id
    metadata = raw.get("metadata")
    if metadata is None:
        metadata = {}
    elif not isinstance(metadata, dict):
        _warn(f"intake_channel.metadata: non-mapping {metadata!r} — using {{}}")
        metadata = {}
    ref["metadata"] = metadata
    dropped = set(raw) - set(ref)
    if dropped:
        # repr-map before sorting: YAML mapping keys may mix types (int vs
        # str), and sorting raw mixed keys raises TypeError — which would
        # break the never-raises degradation contract.
        _warn(f"intake_channel: dropping unknown key(s) {sorted(map(repr, dropped))}")
    return ref


def load_config(path: str | Path | None) -> ChatlinkConfig | None:
    """Load and validate the gateway config; ``None`` ⇒ caller fails closed."""
    if path is None:
        _warn("no config path resolved — refusing (fail-closed)")
        return None
    try:
        import yaml

        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except OSError:
        _warn(f"{path}: missing/unreadable — refusing (fail-closed)")
        return None
    except yaml.YAMLError:
        _warn(f"{path}: malformed YAML — refusing (fail-closed)")
        return None
    if data is None:
        data = {}
    if not isinstance(data, dict):
        _warn(f"{path}: top level is not a mapping — refusing (fail-closed)")
        return None

    deny_mode = data.get("deny_message_mode", DEFAULT_DENY_MESSAGE_MODE)
    if deny_mode not in DENY_MESSAGE_MODES:
        _warn(
            f"deny_message_mode: unknown value {deny_mode!r} — "
            f"using {DEFAULT_DENY_MESSAGE_MODE!r}"
        )
        deny_mode = DEFAULT_DENY_MESSAGE_MODE

    repo_name = data.get("repo_name")
    if repo_name is not None and (
        not isinstance(repo_name, str) or not repo_name.strip()
    ):
        _warn(f"repo_name: non-string/empty {repo_name!r} — using null")
        repo_name = None
    elif isinstance(repo_name, str):
        repo_name = repo_name.strip()

    memory = data.get("sandbox_memory", DEFAULT_SANDBOX_MEMORY)
    if not isinstance(memory, str) or not SANDBOX_MEMORY_RE.match(memory):
        _warn(
            f"sandbox_memory: invalid {memory!r} (want e.g. '2g') — "
            f"using {DEFAULT_SANDBOX_MEMORY!r}"
        )
        memory = DEFAULT_SANDBOX_MEMORY

    return ChatlinkConfig(
        intake_channel=_normalize_intake_channel(data.get("intake_channel")),
        allowed_user_ids=_str_list(data.get("allowed_user_ids"), "allowed_user_ids"),
        allowed_role_ids=_str_list(data.get("allowed_role_ids"), "allowed_role_ids"),
        deny_message_mode=deny_mode,
        repo_name=repo_name,
        max_concurrent_sandboxes=_clamped_int(
            data.get("max_concurrent_sandboxes"),
            DEFAULT_MAX_CONCURRENT_SANDBOXES,
            *RANGE_MAX_CONCURRENT_SANDBOXES,
            key="max_concurrent_sandboxes",
        ),
        intake_rate_per_user_per_hour=_clamped_int(
            data.get("intake_rate_per_user_per_hour"),
            DEFAULT_INTAKE_RATE_PER_USER_PER_HOUR,
            *RANGE_INTAKE_RATE_PER_USER_PER_HOUR,
            key="intake_rate_per_user_per_hour",
        ),
        sandbox_memory=memory,
        sandbox_cpus=_clamped_int(
            data.get("sandbox_cpus"),
            DEFAULT_SANDBOX_CPUS,
            *RANGE_SANDBOX_CPUS,
            key="sandbox_cpus",
        ),
        sandbox_pids=_clamped_int(
            data.get("sandbox_pids"),
            DEFAULT_SANDBOX_PIDS,
            *RANGE_SANDBOX_PIDS,
            key="sandbox_pids",
        ),
        sandbox_wall_clock_s=_clamped_int(
            data.get("sandbox_wall_clock_s"),
            DEFAULT_SANDBOX_WALL_CLOCK_S,
            *RANGE_SANDBOX_WALL_CLOCK_S,
            key="sandbox_wall_clock_s",
        ),
        sandbox_env_passthrough=_env_name_list(
            data.get("sandbox_env_passthrough"), "sandbox_env_passthrough"
        ),
    )
