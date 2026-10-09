"""model_supersession - which code-agent models supersede which (t1910).

A framework promotion (``aitask_add_model.sh promote-config``) replaces the
default model of some operations. ``ait upgrade`` merges seed config with the
destination winning, so a project keeps the old default forever unless something
records what the promotion replaced. This module owns that record and the logic
built on it:

* the **table** (``lib/model_supersessions.json``): per agent, ``old -> {"by":
  new, "source": ...}``. Framework-owned: it ships in ``.aitask-scripts/`` and is
  replaced on every upgrade, like ``DEFAULT_AGENT_STRING``.
* **offers**: for a config layer's ``.defaults``, which ops use a model the table
  supersedes, and which model to offer instead.
* **recording**: the guarded edge-adder ``promote-config`` and
  ``record-supersession`` share, so the two can never disagree about what may be
  recorded.

Semantics, in one place:

* An edge ``A -> B`` is a GLOBAL declaration: every op using A, in every layer,
  is offered B. Same agent only — cross-agent moves are not lineage.
* SEED INVARIANT: no default in ``seed/codeagent_config.json`` names a model that
  has a successor. The framework must never ship a default it declares obsolete,
  and a fresh config must yield no offers.
* A chain is followed to its end; the offered target is the FURTHEST node that
  is registered (and not ``status: unavailable``) in the project's model
  registry. A revisited node is a cycle: that model gets no offer.
* ``_1m`` siblings: recording base edge ``A -> B`` also records
  ``A_1m -> B_1m`` when :func:`sibling_eligibility` says so. A derived edge never
  blocks a promotion.

Stdlib only, Python >= 3.7: ``install.sh`` runs the CLI on top of this module
before ``ait setup`` may have built the framework venv.
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
from collections import namedtuple

TABLE_VERSION = 1
SIBLING_SUFFIX = "_1m"
LAYERS = ("project", "local")

#: The framework-owned table shipped next to this module.
DEFAULT_TABLE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "model_supersessions.json")
#: Per-clone keep memory, in the git common dir (never committed).
KEPT_FILENAME = "ait-codeagent-supersession-kept.json"

# Whole-value validators: always fullmatch(), never match(). Python's `$` also
# matches just before a trailing newline, so match() would accept
# "claudecode/opus5\n" and produce an offer _apply_offers can never apply.
_AGENT_RE = re.compile(r"^[a-z]+$")
_MODEL_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_AGENT_STRING_RE = re.compile(r"^([a-z]+)/([a-z][a-z0-9_]*)$")
_FAMILY_RE = re.compile(r"[a-z]+")

#: One question: in ``layer``, ``ops`` use ``agent/old``; offer ``agent/new``.
Offer = namedtuple("Offer", "layer agent old new ops")


class SupersessionError(ValueError):
    """The table or a registry is malformed."""


class SupersessionCycle(SupersessionError):
    """Following ``by`` links revisited a model."""


# --- table -------------------------------------------------------------------

def empty_table() -> dict:
    return {"version": TABLE_VERSION, "agents": {}}


def validate_table(table) -> dict:
    """Return ``table`` if it has the expected shape, else raise."""
    if not isinstance(table, dict):
        raise SupersessionError("table must be a JSON object")
    if table.get("version") != TABLE_VERSION:
        raise SupersessionError(
            f"unsupported table version {table.get('version')!r} "
            f"(expected {TABLE_VERSION})")
    agents = table.get("agents")
    if not isinstance(agents, dict):
        raise SupersessionError("table 'agents' must be an object")
    for agent, edges in agents.items():
        if not _AGENT_RE.fullmatch(agent) or not isinstance(edges, dict):
            raise SupersessionError(f"bad agent entry {agent!r}")
        for old, entry in edges.items():
            if (not _MODEL_RE.fullmatch(old) or not isinstance(entry, dict)
                    or not isinstance(entry.get("by"), str)
                    or not _MODEL_RE.fullmatch(entry["by"])):
                raise SupersessionError(f"bad edge {agent}/{old}: {entry!r}")
    return table


def load_table(path) -> dict:
    """Load and validate the table. A missing file is an empty table."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return empty_table()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SupersessionError(f"{path}: invalid JSON: {exc}") from None
    return validate_table(data)


def render_table(table) -> str:
    """The canonical on-disk form (hand-written and generated must match)."""
    return json.dumps(table, indent=2, ensure_ascii=False) + "\n"


def successor(table, agent, name):
    entry = table["agents"].get(agent, {}).get(name)
    return entry["by"] if entry else None


def resolve_chain(table, agent, name) -> list:
    """``[name, successor, successor's successor, ...]``; raises on a cycle."""
    chain = [name]
    seen = {name}
    while True:
        nxt = successor(table, agent, chain[-1])
        if nxt is None:
            return chain
        if nxt in seen:
            raise SupersessionCycle(
                f"{agent}: cycle " + " -> ".join(chain + [nxt]))
        chain.append(nxt)
        seen.add(nxt)


def offer_target(table, agent, name, available):
    """The furthest registered successor of ``agent/name``, or None."""
    for candidate in reversed(resolve_chain(table, agent, name)[1:]):
        if candidate in available:
            return candidate
    return None


def family(name) -> str:
    """Leading letters of a model name: ``opus5_5`` -> ``opus``."""
    match = _FAMILY_RE.match(name)
    return match.group(0) if match else name


# --- configs and registries --------------------------------------------------

def valid_agent(name) -> bool:
    return isinstance(name, str) and bool(_AGENT_RE.fullmatch(name))


def valid_model(name) -> bool:
    return isinstance(name, str) and bool(_MODEL_RE.fullmatch(name))


def parse_agent_string(value):
    """``"claudecode/opus5"`` -> ``("claudecode", "opus5")``; malformed -> None."""
    if not isinstance(value, str):
        return None
    match = _AGENT_STRING_RE.fullmatch(value)
    return (match.group(1), match.group(2)) if match else None


def load_registry(path):
    """Offerable model names in a ``models_<agent>.json``; None when missing."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SupersessionError(f"{path}: invalid JSON: {exc}") from None
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        raise SupersessionError(f"{path}: 'models' must be a list")
    names = set()
    for entry in models:
        if (isinstance(entry, dict) and isinstance(entry.get("name"), str)
                and entry.get("status", "active") != "unavailable"):
            names.add(entry["name"])
    return names


def load_registries(metadata_dir):
    """``(registries, warnings)`` for every ``models_<agent>.json`` in a dir.

    ``models_<agent>.local.json`` holds user overrides, not the registry, and is
    skipped. An unreadable registry is a warning, never an exception: that
    agent simply gets no offers.
    """
    registries = {}
    warnings = []
    try:
        names = sorted(os.listdir(metadata_dir))
    except OSError:
        names = []
    for filename in names:
        if not (filename.startswith("models_") and filename.endswith(".json")):
            continue
        agent = filename[len("models_"):-len(".json")]
        if "." in agent:  # models_<agent>.local.json — user overrides, not the registry
            continue
        path = os.path.join(metadata_dir, filename)
        try:
            found = load_registry(path)
        except (OSError, SupersessionError) as exc:
            warnings.append(f"cannot read {filename}: {exc} — no offers for '{agent}'")
            continue
        if found is not None:
            registries[agent] = found
    return registries, warnings


def _seed_ops_using(seed_defaults, agent, name) -> list:
    return [op for op, value in seed_defaults.items()
            if parse_agent_string(value) == (agent, name)]


# --- offers ------------------------------------------------------------------

def find_offers(layer, defaults, table, registries):
    """Group the superseded ops of one layer into offers.

    ``registries`` maps agent -> set of offerable names. Returns
    ``(offers, warnings)``; offers are sorted by ``(agent, old)`` and list their
    ops in config order. A non-superseded value — including any custom choice —
    never produces an offer.
    """
    warnings = []
    groups = {}
    for op, value in defaults.items():
        parsed = parse_agent_string(value)
        if parsed is None:
            warnings.append(f"{layer}: ignoring malformed value for '{op}': {value!r}")
            continue
        agent, name = parsed
        if successor(table, agent, name) is None:
            continue
        available = registries.get(agent)
        if available is None:
            msg = (f"{layer}: no model registry for '{agent}' — cannot offer a "
                   f"successor for {agent}/{name}")
            if msg not in warnings:
                warnings.append(msg)
            continue
        try:
            target = offer_target(table, agent, name, available)
        except SupersessionCycle as exc:
            msg = f"{layer}: skipping {agent}/{name}: {exc}"
            if msg not in warnings:
                warnings.append(msg)
            continue
        if target is None:
            continue
        groups.setdefault((agent, name), (target, []))[1].append(op)
    offers = [Offer(layer, agent, old, target, tuple(ops))
              for (agent, old), (target, ops) in sorted(groups.items())]
    return offers, warnings


def seed_violations(table, seed_defaults) -> list:
    """``(op, agent, name)`` for every seed default the table supersedes."""
    out = []
    for op, value in seed_defaults.items():
        parsed = parse_agent_string(value)
        if parsed and successor(table, *parsed) is not None:
            out.append((op, parsed[0], parsed[1]))
    return out


# --- keep memory -------------------------------------------------------------

def _git(root, *args):
    try:
        proc = subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_common_dir(root):
    """The git common dir of ``root`` as a path string, or None outside git."""
    if _git(root, "rev-parse", "--is-inside-work-tree") != "true":
        return None
    out = _git(root, "rev-parse", "--git-common-dir")
    if not out:
        return None
    return out if os.path.isabs(out) else os.path.join(str(root), out)


def kept_path(root):
    """Where the keep memory of ``root``'s clone lives, or None outside git."""
    common = git_common_dir(root)
    return os.path.join(common, KEPT_FILENAME) if common is not None else None


def load_kept(path):
    """``(kept, warnings)`` from a keep-memory file; None or missing -> ``{}``.

    Malformed content is ignored with a warning, never raised: the memory only
    suppresses re-asking, so losing it is the safe direction.
    """
    if path is None or not os.path.isfile(path):
        return {}, []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return {}, [f"ignoring unreadable {path}: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"ignoring malformed {path}: not a JSON object"]
    kept = {}
    warnings = []
    for layer in LAYERS:
        if layer not in data:
            continue
        entries = data[layer]
        if not isinstance(entries, dict):
            warnings.append(f"ignoring malformed '{layer}' entry in {path}")
            continue
        clean = {k: v for k, v in entries.items()
                 if isinstance(k, str) and isinstance(v, str)}
        if len(clean) != len(entries):
            warnings.append(f"ignoring malformed '{layer}' records in {path}")
        kept[layer] = clean
    return kept, warnings


def _kept_key(offer) -> str:
    return f"{offer.agent}/{offer.old}"


def is_kept(kept, offer) -> bool:
    """True while the user declined exactly this offered target."""
    entries = kept.get(offer.layer)
    if not isinstance(entries, dict):
        return False
    return entries.get(_kept_key(offer)) == f"{offer.agent}/{offer.new}"


def with_kept(kept, offer) -> dict:
    out = copy.deepcopy(kept)
    out.setdefault(offer.layer, {})[_kept_key(offer)] = f"{offer.agent}/{offer.new}"
    return out


def without_kept(kept, offer) -> dict:
    out = copy.deepcopy(kept)
    out.get(offer.layer, {}).pop(_kept_key(offer), None)
    return out


# --- recording ---------------------------------------------------------------

def _closes_cycle(table, agent, old, new) -> bool:
    if old == new:
        return True
    try:
        return old in resolve_chain(table, agent, new)
    except SupersessionCycle:
        return True


def sibling_eligibility(table, agent, base_old, base_new, seed_defaults, available):
    """Whether ``base_old_1m -> base_new_1m`` should accompany ``base_old -> base_new``.

    Returns ``(eligible, reason)``. The single decision shared by the recorder
    and the completeness contract (:func:`missing_sibling_edges`), so an
    intentional skip is never reported as a missing edge. Reasons:
    ``not_base`` / ``no_siblings`` (nothing to say), ``sibling_unregistered``,
    ``sibling_in_seed``, ``sibling_exists``, ``sibling_conflict``,
    ``sibling_cycle``, ``eligible``.
    """
    if base_old.endswith(SIBLING_SUFFIX) or base_new.endswith(SIBLING_SUFFIX):
        return False, "not_base"
    s_old, s_new = base_old + SIBLING_SUFFIX, base_new + SIBLING_SUFFIX
    have_old, have_new = s_old in available, s_new in available
    if not have_old and not have_new:
        return False, "no_siblings"
    if not (have_old and have_new):
        return False, "sibling_unregistered"
    if _seed_ops_using(seed_defaults, agent, s_old):
        return False, "sibling_in_seed"
    existing = successor(table, agent, s_old)
    if existing == s_new:
        return False, "sibling_exists"
    if existing is not None:
        return False, "sibling_conflict"
    if _closes_cycle(table, agent, s_old, s_new):
        return False, "sibling_cycle"
    return True, "eligible"


_SILENT_SIBLING_REASONS = ("not_base", "no_siblings", "eligible")


def missing_sibling_edges(table, seed_defaults, registries) -> list:
    """``(agent, old_1m, new_1m)`` for every eligible sibling edge not recorded."""
    missing = []
    for agent, edges in table["agents"].items():
        available = registries.get(agent, set())
        for old, entry in edges.items():
            eligible, _ = sibling_eligibility(
                table, agent, old, entry["by"], seed_defaults, available)
            if eligible:
                missing.append((agent, old + SIBLING_SUFFIX, entry["by"] + SIBLING_SUFFIX))
    return missing


def _declare(table, agent, old, new, seed, available, source, events, in_seed_label):
    """Add ``old -> new`` (+ eligible sibling) to ``table`` in place.

    The one guarded edge-adder. Appends events; returns True when blocked.
    """
    edge = f"{agent}/{old}->{agent}/{new}"
    if old == new:
        events.append(f"SKIPPED:self:{agent}/{old}")
        return False
    remaining = _seed_ops_using(seed, agent, old)
    if remaining:
        events.append(f"BLOCKED:{in_seed_label}:{agent}/{old}|{','.join(remaining)}")
        return True
    existing = successor(table, agent, old)
    if existing == new:
        events.append(f"SKIPPED:exists:{edge}")
    elif existing is not None:
        events.append(f"BLOCKED:conflict:{agent}/{old}->{agent}/{existing}")
        return True
    else:
        if new not in available:
            events.append(f"BLOCKED:unregistered:{agent}/{new}")
            return True
        if _closes_cycle(table, agent, old, new):
            events.append(f"BLOCKED:cycle:{edge}")
            return True
        table["agents"].setdefault(agent, {})[old] = {"by": new, "source": source}
        events.append(f"RECORDED:{edge}")
        if family(old) != family(new):
            events.append(f"WARN:family:{edge}")

    eligible, reason = sibling_eligibility(table, agent, old, new, seed, available)
    s_edge = f"{agent}/{old}{SIBLING_SUFFIX}->{agent}/{new}{SIBLING_SUFFIX}"
    if eligible:
        table["agents"][agent][old + SIBLING_SUFFIX] = {
            "by": new + SIBLING_SUFFIX, "source": f"{source} ({SIBLING_SUFFIX} sibling)"}
        events.append(f"RECORDED_SIBLING:{s_edge}")
    elif reason not in _SILENT_SIBLING_REASONS:
        events.append(f"SKIPPED:{reason}:{s_edge}")
    return False


def _invariant_events(table, seed, already_blocked) -> list:
    return [f"BLOCKED:seed_invariant:{op}|{agent}/{name}"
            for op, agent, name in seed_violations(table, seed)
            if (agent, name) not in already_blocked]


def plan_promotion(table, agent, new, seed_before, seed_after, available, source):
    """Supersession implied by a promotion that patched ``seed_before`` into ``seed_after``.

    Predecessors are the old values of the seed ops that now hold ``agent/new``.
    Returns ``(table, events, blocked)``; ``table`` is a modified copy.
    """
    table = copy.deepcopy(table)
    events = []
    predecessors = []
    for op, before in seed_before.items():
        after = seed_after.get(op)
        if after == before or parse_agent_string(after) != (agent, new):
            continue
        parsed = parse_agent_string(before)
        if parsed is None:
            continue
        if parsed[0] != agent:
            events.append(f"SKIPPED:cross_agent:{before}")
            continue
        if parsed[1] not in predecessors:
            predecessors.append(parsed[1])
    blocked = False
    blocked_names = set()
    for old in predecessors:
        if _declare(table, agent, old, new, seed_after, available, source, events,
                    "partial"):
            blocked = True
            blocked_names.add((agent, old))
    invariant = _invariant_events(table, seed_after, blocked_names)
    events.extend(invariant)
    return table, events, blocked or bool(invariant)


def plan_explicit(table, agent, old, new, seed, available, source):
    """An explicitly requested ``agent/old -> agent/new`` (``record-supersession``)."""
    table = copy.deepcopy(table)
    events = []
    blocked = _declare(table, agent, old, new, seed, available, source, events, "in_seed")
    invariant = _invariant_events(table, seed, {(agent, old)} if blocked else set())
    events.extend(invariant)
    return table, events, blocked or bool(invariant)
