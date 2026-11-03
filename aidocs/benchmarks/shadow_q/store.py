"""Public / private sinks for the t2179 shadow ``>q`` experiment.

aitasks (this repository) is public; the fixtures and every model output that
quotes them are private and live in the aitasks_go repository's
``aidocs/shadow_q_store/``. Two sinks keep the split mechanical:

* :class:`PublicSink` appends JSONL records whose keys are all in a frozen
  per-kind whitelist, and whose string values are short. Any other key, or a
  long string, raises :class:`LeakError` *before* anything is written — the
  whitelist is a hard guard, not a convention.
* :class:`PrivateSink` writes anything, but only under the store root.

The store is resolved by logical project name (``ait projects resolve
aitasks_go``), never by a sibling-directory path.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
STORE_PROJECT = "aitasks_go"
STORE_SUBDIR = "aidocs/shadow_q_store"
MAX_PUBLIC_STR = 160

# Nested dicts are allowed only for these keys, with the listed sub-keys.
_NESTED = {
    "cell": {"scenario", "variant", "agent", "condition", "rep", "order", "conversation_id"},
    "usage": {
        "input_tokens", "cached_input_tokens", "output_tokens", "cache_creation_input_tokens",
        "cache_read_input_tokens", "cost_usd", "tool_calls", "turns",
    },
    "reasoning": {
        "codex_model_reasoning_effort", "codex_plan_mode_reasoning_effort", "codex_personality",
        "codex_rollout_effort", "claude_effortLevel", "claude_env_ANTHROPIC_REASONING_EFFORT",
        "claude_modelSettings_effortLevel", "claude_settings_sha256",
    },
    "hashes": None,  # free keys (relative file names), values must be sha256 hex
    "flags": None,   # free keys, values must be bool/int
    "scores": None,  # free keys (rubric dimensions), values numbers/bools/None
    "counts": None,  # free keys, values ints
}

PUBLIC_FIELDS: dict[str, set[str]] = {
    "session": {
        "kind", "run_id", "batch", "cell", "seed", "order_index", "started_at", "ended_at",
        "latency_s", "agent", "agent_string", "cli_id", "cli_version", "reported_model",
        "model_source", "reasoning", "profile", "hashes", "codex_trust_override",
        "codex_memories", "usage", "exit_codes", "status", "attempt", "outcome", "flags",
        "helpers_called", "off_path_helpers", "turns", "invocations", "store_commit",
        "freeze_sha", "dry_run_line_sha256", "notes_code",
    },
    "trial": {
        "kind", "run_id", "batch", "trial_id", "cell", "turn_index", "position", "scenario",
        "variant", "agent", "condition", "outcome", "flags", "helpers_called",
        "answer_sha256", "answer_chars", "judged", "blind_id",
    },
    "score": {
        "kind", "batch", "blind_id", "judge", "scenario", "scores", "failure_flag",
        "disputed", "control", "calibrated", "judge_prompt_sha256", "rubric_sha256",
        "attempt", "outcome", "latency_s", "usage",
    },
    "invocation": {
        "kind", "batch", "seq", "purpose", "agent", "run_id", "turn_index", "outcome",
        "latency_s", "usage", "started_at",
    },
    "preflight": {"kind", "batch", "agent", "form", "mode", "ok", "outcome", "hashes"},
    "budget": {"kind", "batch", "at", "event", "seq", "purpose", "agent", "cost_usd", "tokens", "estimated"},
    "reclass": {"kind", "batch", "run_id", "trial_id", "turn_index", "agent", "variant", "condition",
                "scenario", "recorded", "reclassified", "changed", "flags"},
}


class LeakError(ValueError):
    """A record would put non-whitelisted (possibly private) data in public."""


def _check_scalar(key: str, value) -> None:
    if value is None or isinstance(value, (bool, int, float)):
        return
    if isinstance(value, str):
        if len(value) > MAX_PUBLIC_STR:
            raise LeakError(f"public string for {key!r} is {len(value)} chars (max {MAX_PUBLIC_STR})")
        return
    raise LeakError(f"public value for {key!r} has type {type(value).__name__}")


def validate_public(kind: str, record: dict) -> None:
    allowed = PUBLIC_FIELDS.get(kind)
    if allowed is None:
        raise LeakError(f"unknown public record kind {kind!r}")
    for key, value in record.items():
        if key not in allowed:
            raise LeakError(f"key {key!r} is not whitelisted for public {kind} records")
        if isinstance(value, dict):
            if key not in _NESTED:
                raise LeakError(f"key {key!r} may not hold a mapping")
            sub_allowed = _NESTED[key]
            for sk, sv in value.items():
                if sub_allowed is not None and sk not in sub_allowed:
                    raise LeakError(f"sub-key {key}.{sk} is not whitelisted")
                if isinstance(sk, str) and len(sk) > MAX_PUBLIC_STR:
                    raise LeakError(f"sub-key in {key!r} too long")
                if isinstance(sv, (list, dict)):
                    raise LeakError(f"{key}.{sk} must be a scalar")
                _check_scalar(f"{key}.{sk}", sv)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (list, dict)):
                    raise LeakError(f"list {key!r} must hold scalars")
                _check_scalar(key, item)
        else:
            _check_scalar(key, value)


class PublicSink:
    def __init__(self, path: Path, kind: str):
        self.path = Path(path)
        self.kind = kind

    def append(self, record: dict) -> None:
        record = {"kind": self.kind, **record}
        validate_public(self.kind, record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())


class PrivateSink:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def path(self, rel: str | Path) -> Path:
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise LeakError(f"private path escapes the store: {rel}")
        return p

    def write_text(self, rel: str | Path, text: str) -> Path:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def write_bytes(self, rel: str | Path, data: bytes) -> Path:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p


def resolve_store(explicit: str | Path | None = None, repo: Path = REPO) -> Path:
    """The private store root. ``explicit`` (or ``$AIT_SHADOW_Q_STORE``) wins."""
    explicit = explicit or os.environ.get("AIT_SHADOW_Q_STORE")
    if explicit:
        return Path(explicit).resolve()
    out = subprocess.run(
        ["./ait", "projects", "resolve", STORE_PROJECT],
        cwd=repo, capture_output=True, text=True, check=False,
    ).stdout
    for line in out.splitlines():
        if line.startswith("RESOLVED:"):
            return (Path(line[len("RESOLVED:"):].strip()) / STORE_SUBDIR).resolve()
    raise SystemExit(f"store: cannot resolve project {STORE_PROJECT!r}: {out.strip() or 'no output'}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


MANIFEST_DIRS = ("fixtures", "instructions", "skill_listing")


def build_manifest_files(store: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for d in MANIFEST_DIRS:
        base = store / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file():
                files[str(p.relative_to(store))] = sha256_file(p)
    return files


def check_manifest(store: Path, manifest: dict) -> list[str]:
    """Return a list of mismatches (empty = the store matches the manifest)."""
    want = manifest.get("files", {})
    have = build_manifest_files(store)
    problems = []
    for rel, digest in want.items():
        if rel not in have:
            problems.append(f"missing:{rel}")
        elif have[rel] != digest:
            problems.append(f"changed:{rel}")
    for rel in have:
        if rel not in want:
            problems.append(f"unlisted:{rel}")
    return problems


def untracked_files(store: Path, rels) -> list[str]:
    """Manifest files the store's git does not track (e.g. silently ignored). [] when not a git repo."""
    top = subprocess.run(["git", "-C", str(store), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if top.returncode != 0:
        return []
    tracked = set(subprocess.run(["git", "-C", str(store), "ls-files", "--", "."],
                                 capture_output=True, text=True, check=True).stdout.splitlines())
    return sorted(r for r in rels if r not in tracked)
