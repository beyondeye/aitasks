"""cross_repo_settings - Read, diff and push the default code agent across repos.

The headless seam behind the syncer's Settings tab (t1223_4). No Textual: the
TUI half lives in `syncer/syncer_app.py` and only renders what this module
returns.

Public API:
- read_operation_defaults(root)  -> {operation: OperationValue}
- diff_across_repos(roots)       -> {operation: {repo_key: OperationValue}}
- plan_push(value, dest_root, operation, layer) -> PushOutcome
- apply_push(value, dest_root, operation, layer, clear_mask=False)

Two properties are load-bearing and easy to lose:

1. **Every value describes one specific repo.** `lib/agent_string.sh` documents
   METADATA_DIR / TASK_DIR / DEFAULT_AGENT_STRING as caller overrides, and they
   outrank `cwd`, so a resolver subprocess that inherits the parent environment
   can read someone else's config while reporting on this root. Everything here
   goes through `resolver_env()` and `dest_metadata_dir()`.
2. **`effective` is ground truth, not our own merge.** It comes from
   `resolve_agent_string`, an independent path. When the layers imply something
   else, the answer is `conflict` — never a guess.
"""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_launch_utils import resolve_agent_string
from config_utils import MODEL_FILES, save_local_config, import_all_configs

# Keys in `defaults` that hold a launch mode (headless|interactive), not an
# agent string. They share the map with the agent operations and must not appear
# in the agent matrix.
AGENT_OPERATIONS_EXCLUDE_SUFFIX = "-launch-mode"

PROJECT_CONFIG_NAME = "codeagent_config.json"
LOCAL_CONFIG_NAME = "codeagent_config.local.json"

# Environment variables `lib/agent_string.sh` treats as caller overrides. They
# take precedence over the target repo's own files, so resolving a foreign root
# with them inherited silently collapses every root onto one config.
RESOLVER_ENV_OVERRIDES = (
    "METADATA_DIR",
    "TASK_DIR",
    "DEFAULT_AGENT_STRING",
    "OPT_AGENT_STRING",
)

# <agent>/<model>, mirroring parse_agent_string in lib/agent_string.sh. There is
# no Python equivalent of that function; the supported-agent set is taken from
# config_utils.MODEL_FILES rather than restated, and a drift guard in
# tests/test_cross_repo_settings.py pins it against the shell list.
_AGENT_STRING_RE = re.compile(r"^([a-z]+)/([a-z0-9_]+)$")

PROVENANCE_LOCAL = "local"
PROVENANCE_PROJECT = "project"
PROVENANCE_BUILTIN = "builtin"
PROVENANCE_CONFLICT = "conflict"

REASON_MALFORMED_AGENT_STRING = "malformed_agent_string"
REASON_MODEL_NOT_IN_DEST_CATALOG = "model_not_in_dest_catalog"
REASON_DEST_CONFIG_UNREADABLE = "dest_config_unreadable"


class DestConfigUnreadable(ValueError):
    """A repo's config or model catalog exists but cannot be trusted.

    Covers a non-regular file at the path, an unreadable file, invalid JSON, and
    valid JSON that is not an object. Absent is *not* an error.
    """


class PushPartialError(RuntimeError):
    """A `clear_mask` push applied its project write but not the local clear.

    The destination's *effective* value is unchanged — the local override still
    masks — so the repo behaves exactly as it did before. Retrying converges:
    `plan_push` still reports `masked`, and the project write is idempotent.
    """

    def __init__(self, operation: str, masking_value: str | None,
                 cause: BaseException) -> None:
        super().__init__(
            f"project layer updated for {operation!r} but the local override "
            f"could not be cleared (still {masking_value!r}): {cause}"
        )
        self.operation = operation
        self.applied = "project"
        self.failed = "clear_local"
        self.masking_value = masking_value
        self.cause = cause


@dataclass(frozen=True)
class OperationValue:
    """One repo's answer for one operation."""

    operation: str
    effective: str | None
    project_value: str | None
    local_value: str | None
    provenance: str


@dataclass(frozen=True)
class PushOutcome:
    """Typed result of planning a push — never a bare bool."""

    kind: str  # 'ok' | 'noop' | 'masked' | 'rejected'
    masking_value: str | None = None
    reason: str | None = None

    @property
    def is_rejected(self) -> bool:
        return self.kind == "rejected"


def resolver_env() -> dict[str, str]:
    """The environment to resolve a *foreign* root with.

    A copy of os.environ minus every variable that would outrank the target
    repo's own configuration, so the destination resolves with its own defaults.
    """
    return {
        k: v for k, v in os.environ.items() if k not in RESOLVER_ENV_OVERRIDES
    }


def dest_metadata_dir(root: str | Path) -> Path:
    """The one place this module answers "where is this repo's metadata".

    Deliberately the literal framework default rather than the ambient TASK_DIR:
    it must agree with what the env-scrubbed resolver subprocess will use, and
    with the catalog lookup. Deriving any of the three from caller state is what
    lets them drift apart.
    """
    return Path(root) / "aitasks" / "metadata"


def repo_key(root: str | Path) -> str:
    """Stable identity for a repo, matching AitasksSession.key exactly.

    Keeping these identical is what lets the syncer index this module's output
    by `sess.key` with no mapping layer.
    """
    try:
        return os.path.realpath(root)
    except OSError:
        return str(root)


def _read_layer(path: Path) -> dict | None:
    """Read one config layer strictly. Returns None when absent.

    config_utils._load_json is too lossy for this: it reports a directory as
    `{}` (indistinguishable from absent) and returns None for a file holding
    `null`. Both must be errors here — a repo whose config cannot be read must
    never be reported as "using the builtin default".
    """
    if not path.exists():
        return None
    if not path.is_file():
        raise DestConfigUnreadable(f"{path} exists but is not a regular file")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise DestConfigUnreadable(f"{path} could not be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DestConfigUnreadable(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DestConfigUnreadable(
            f"{path} holds {type(data).__name__}, expected a JSON object"
        )
    return data


def _layer_defaults(root: str | Path, name: str) -> dict:
    """The `defaults` map of one layer, or {} when the layer is absent."""
    data = _read_layer(dest_metadata_dir(root) / name)
    if data is None:
        return {}
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        raise DestConfigUnreadable(
            f"{name} in {root}: 'defaults' holds "
            f"{type(defaults).__name__}, expected an object"
        )
    return defaults


def _is_agent_operation(key: Any) -> bool:
    """Whether a `defaults` key names an agent-string operation."""
    return isinstance(key, str) and not key.endswith(AGENT_OPERATIONS_EXCLUDE_SUFFIX)


def _resolve_effective(root: str | Path, operation: str) -> str | None:
    """Ground truth for one (root, operation), resolved in the root's own terms."""
    return resolve_agent_string(Path(root), operation, env=resolver_env())


def _classify(operation: str, project: dict, local: dict,
              effective: str | None) -> OperationValue:
    """Combine raw layers with ground truth into one answer."""
    project_value = project.get(operation)
    local_value = local.get(operation)

    if local_value is not None:
        provenance, derived = PROVENANCE_LOCAL, local_value
    elif project_value is not None:
        provenance, derived = PROVENANCE_PROJECT, project_value
    else:
        provenance, derived = PROVENANCE_BUILTIN, None

    # The layers say one thing, the resolver another. Report the disagreement;
    # never pick a side. `builtin` has no derived value to compare, so only an
    # unresolvable effective makes it a conflict.
    if derived is not None:
        if effective != derived:
            provenance = PROVENANCE_CONFLICT
    elif effective is None:
        provenance = PROVENANCE_CONFLICT

    return OperationValue(
        operation=operation,
        effective=effective,
        project_value=project_value,
        local_value=local_value,
        provenance=provenance,
    )


def read_operation_defaults(root: str | Path) -> dict[str, OperationValue]:
    """Per-operation defaults for one repo.

    The operation set is the union of the repo's own local and project keys,
    minus `*-launch-mode`. `effective` is ground truth from
    `resolve_agent_string`; `provenance` is derived from the raw layers and
    becomes `conflict` when the two disagree.

    Raises DestConfigUnreadable when a layer exists but cannot be trusted —
    callers rendering a multi-repo view should catch it per repo rather than let
    one broken repo empty the whole matrix.
    """
    project = _layer_defaults(root, PROJECT_CONFIG_NAME)
    local = _layer_defaults(root, LOCAL_CONFIG_NAME)

    operations = sorted(
        {k for k in project if _is_agent_operation(k)}
        | {k for k in local if _is_agent_operation(k)}
    )
    return _collect(root, operations, project, local)


def _collect(root: str | Path, operations: list[str], project: dict,
             local: dict) -> dict[str, OperationValue]:
    """Resolve `operations` for one root and assemble the answers.

    Each `resolve_agent_string` is a subprocess, so N operations means N spawns.
    The workers are pure and read-only and share no mutable state; results are
    keyed by operation and assembled only after every future has completed, so
    the output does not depend on completion order.
    """
    if not operations:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, len(operations))) as pool:
        effectives = list(
            pool.map(lambda op: _resolve_effective(root, op), operations)
        )
    return {
        op: _classify(op, project, local, eff)
        for op, eff in zip(operations, effectives)
    }


def diff_across_repos(
    roots: list[str | Path],
) -> dict[str, dict[str, OperationValue]]:
    """{operation: {repo_key: OperationValue}} across several repos.

    Operations are unioned across roots, so a repo that does not configure an
    operation another repo does still gets an entry for it (resolved for that
    repo, normally `builtin`) — which is what makes divergence visible.
    """
    layers: dict[str, tuple[str | Path, dict, dict]] = {}
    operations: set[str] = set()
    for root in roots:
        project = _layer_defaults(root, PROJECT_CONFIG_NAME)
        local = _layer_defaults(root, LOCAL_CONFIG_NAME)
        layers[repo_key(root)] = (root, project, local)
        operations |= {k for k in project if _is_agent_operation(k)}
        operations |= {k for k in local if _is_agent_operation(k)}

    ordered = sorted(operations)
    result: dict[str, dict[str, OperationValue]] = {op: {} for op in ordered}
    for key, (root, project, local) in layers.items():
        for op, value in _collect(root, ordered, project, local).items():
            result[op][key] = value
    return result


def _catalog_model_names(root: str | Path, agent: str) -> set[str]:
    """Model `name`s the destination's own catalog offers for `agent`.

    Read through the same strict probe and the same metadata dir as the config
    layers, so a corrupt catalog is a typed outcome and the catalog can never be
    read from a different tree than the values it is validating.
    """
    data = _read_layer(dest_metadata_dir(root) / f"models_{agent}.json")
    if data is None:
        return set()
    models = data.get("models", [])
    if not isinstance(models, list):
        raise DestConfigUnreadable(
            f"models_{agent}.json in {root}: 'models' holds "
            f"{type(models).__name__}, expected a list"
        )
    return {
        m["name"] for m in models
        if isinstance(m, dict) and isinstance(m.get("name"), str)
    }


def plan_push(value: str, dest_root: str | Path, operation: str,
              layer: str) -> PushOutcome:
    """Decide what pushing `value` into `dest_root` would do. Writes nothing.

    `layer` is 'project' or 'local'. Rejection reasons are distinct and each
    fires only for its own cause.
    """
    if layer not in ("project", "local"):
        raise ValueError(f"layer must be 'project' or 'local', got {layer!r}")

    # Syntax first: no I/O, so a malformed value is never misreported as an
    # unreadable destination.
    match = _AGENT_STRING_RE.match(value or "")
    if not match or match.group(1) not in MODEL_FILES:
        return PushOutcome(kind="rejected", reason=REASON_MALFORMED_AGENT_STRING)
    agent, model = match.group(1), match.group(2)

    try:
        # The project layer is read for its side effect only: it is the strict
        # probe that catches a corrupt destination. The shell resolver silently
        # falls through to the builtin default for a malformed config, so
        # without this read a broken repo would look healthy and be written to.
        _layer_defaults(dest_root, PROJECT_CONFIG_NAME)
        local = _layer_defaults(dest_root, LOCAL_CONFIG_NAME)
        catalog = _catalog_model_names(dest_root, agent)
    except DestConfigUnreadable:
        return PushOutcome(kind="rejected", reason=REASON_DEST_CONFIG_UNREADABLE)

    effective = _resolve_effective(dest_root, operation)
    if effective is None:
        # The resolver could not run at all (not an aitasks repo, missing
        # wrapper). Note it cannot report a *corrupt* config — the shell
        # resolver swallows malformed JSON and falls through to the builtin
        # default — which is why the strict layer reads above exist.
        return PushOutcome(kind="rejected", reason=REASON_DEST_CONFIG_UNREADABLE)

    if model not in catalog:
        return PushOutcome(
            kind="rejected", reason=REASON_MODEL_NOT_IN_DEST_CATALOG
        )

    if effective == value:
        return PushOutcome(kind="noop")

    masking_value = local.get(operation)
    if layer == "project" and masking_value is not None:
        return PushOutcome(kind="masked", masking_value=masking_value)

    return PushOutcome(kind="ok")


def apply_push(value: str, dest_root: str | Path, operation: str, layer: str,
               clear_mask: bool = False) -> None:
    """Write `value` into `dest_root`'s `layer` for `operation`.

    With `clear_mask=True` the local override for `operation` is also removed,
    dropping an emptied `defaults` and then an emptied local file — mirroring
    settings_app._handle_agent_pick / save_codeagent.

    The two writes are not atomic together, so the order is part of the
    contract: **project first, then clear local**. If the clear fails, the mask
    is still in place and the destination's effective value is unchanged; the
    repo behaves exactly as before and a retry converges. The reverse order
    would drop the user's override and swing the effective value to something
    they never chose.
    """
    if layer not in ("project", "local"):
        raise ValueError(f"layer must be 'project' or 'local', got {layer!r}")

    name = PROJECT_CONFIG_NAME if layer == "project" else LOCAL_CONFIG_NAME
    import_all_configs(
        bundle={"files": {name: {"defaults": {operation: value}}}},
        metadata_dir=dest_metadata_dir(dest_root),
        overwrite=True,
        merge=True,
    )

    if not clear_mask or layer != "project":
        return

    masking_value = None
    try:
        local_path = dest_metadata_dir(dest_root) / LOCAL_CONFIG_NAME
        local_data = _read_layer(local_path)
        if local_data is None:
            return
        defaults = local_data.get("defaults")
        if not isinstance(defaults, dict) or operation not in defaults:
            return
        masking_value = defaults[operation]
        del defaults[operation]
        if not defaults:
            del local_data["defaults"]
        if local_data:
            save_local_config(local_path, local_data)
        elif local_path.is_file():
            local_path.unlink()
    except BaseException as exc:
        raise PushPartialError(operation, masking_value, exc) from exc
