"""Recipes: the recorded route to one screenshot (``scenes/<id>.yaml``).

A recipe is written by the tool from the journal of a capture that worked. It
is a cache of a route, not a specification: when it fails, or no longer shows
what its page describes, the agent finds a route again and replaces it.

```yaml
id: board_child_tasks
output: aitasks_board_child_tasks.svg
title: aitasks board
size: [126, 40]
window: board                 # optional: name of the first window
dataset: base                 # sample_project.DATASETS
setup: []                     # commands run in the project before the launch
launch: ./ait board
steps:
  - wait: Backlog (2)
  - keys: [x]
  - wait: {text: Report ready, timeout: 120}   # a wait that needed longer
  # Several panes (pane = a role, `main` by default, or <window>.<index> for a
  # pane the TUI created itself; never a tmux id):
  - pane_split: {name: mini, command: ./ait minimonitor, direction: h, size: '40'}
  - window_new: {name: agent-pick-14, command: claude /aitask-pick 14, role: agent}
  - keys: {keys: [j], pane: agent-pick-14.1}
  - wait: {text: TUI switcher, pane: mini}
capture: {window: agent-pick-14}   # optional: a whole window, or {pane: P};
                                   # absent = the main pane
expect:                       # texts that must be on screen at capture time
  - t12_1 cart summary widget
illustrates: >-               # what the image is meant to show (for the agent)
  An expanded parent task with its child cards.
crop:                         # optional: show only this cell rectangle
  cells: [1, 5, 40, 7]        # [column, row, width, height], borders included
  gutter: 30                  # optional: empty cells added on the right (labels)
  holds: t12 add checkout page   # optional: text that must lie inside it
overlays:                     # optional: drawn on top, in cell coordinates of the
                              # captured pane or window
  - type: box                 # box | tint | anchor (anchor draws only its marks)
    target: {cells: [0, 0, 126, 1], holds: aitasks board}
    callout: 1                # optional: numbered circle, unique per scene
  - type: anchor
    target: {cells: [2, 7, 36, 1]}
    label: Info line          # optional: leader line and text to the right
```

Every rectangle lies inside the window (``size``), and with a ``crop`` every
overlay target lies inside the crop. A pane is smaller than the window once it
is split, so the exact bounds are checked on the captured frame. A ``holds`` text is checked on the captured frame: if it
is not inside its rectangle the capture fails, so a layout that moved makes a
replay fail instead of annotating the wrong place.

``id:`` and ``output:`` own the image file. ``website/check_screenshots.py``
reads those two lines without a YAML parser (``markers.read_spec_owner``), so
this loader first asks that same reader and refuses whatever it refuses: the
checker and the loader cannot accept different sets.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import markers, sample_project
from .session import DEFAULT_TIMEOUT as DEFAULT_WAIT_TIMEOUT
from .session import LOCATOR_RE, MAIN, ROLE_RE, SIZE_RE, WINDOW_NAME_RE

REQUIRED = ("id", "output", "size", "dataset", "launch", "expect", "illustrates")
OPTIONAL = ("title", "setup", "steps", "crop", "overlays", "window", "capture")
STEP_KINDS = ("keys", "wait", "wait_gone", "pane_split", "window_new")
#: A recorded wait keeps its own budget only above the replay default
#: (``session.DEFAULT_TIMEOUT``).
MAX_WAIT_TIMEOUT = 3600.0


class RecipeError(Exception):
    pass


@dataclass(frozen=True)
class Recipe:
    id: str
    output: str
    size: tuple[int, int]
    dataset: str
    launch: str
    expect: tuple[str, ...]
    illustrates: str
    title: str = ""
    setup: tuple[str, ...] = ()
    #: ``(kind, value, timeout, pane)``. ``timeout`` is None for keys and for a
    #: wait that used the default budget; ``pane`` is None for the main pane.
    #: For ``pane_split`` / ``window_new`` the value is the step's mapping.
    steps: tuple[tuple[str, object, float | None, str | None], ...] = ()
    crop: object = None
    overlays: object = None
    #: Name of the first window ("" = tmux's automatic name).
    window: str = ""
    #: ``{"window": NAME}`` or ``{"pane": P}``; None = the main pane.
    capture: object = None
    path: str = field(default="", compare=False)

    @property
    def window_title(self) -> str:
        return self.title or "aitasks"


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


OVERLAY_TYPES = ("box", "tint", "anchor")
MAX_GUTTER = 200
MAX_CALLOUT = 99


def _cells(value, size, where: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 4 or not all(_is_int(v) for v in value):
        raise RecipeError(f"{where}: cells must be [column, row, width, height], four integers")
    c, r, w, h = value
    if c < 0 or r < 0 or w < 1 or h < 1:
        raise RecipeError(f"{where}: cells {value} must have column, row >= 0 and "
                          "width, height >= 1")
    if c + w > size[0] or r + h > size[1]:
        raise RecipeError(f"{where}: cells {value} reach outside the {size[0]}x{size[1]} pane")
    return [c, r, w, h]


def _target(value, size, where: str, extra=()) -> dict:
    """A rectangle mapping: ``cells`` plus an optional ``holds`` text."""
    if not isinstance(value, dict):
        raise RecipeError(f"{where}: must be a mapping with cells")
    unknown = sorted(set(map(str, value)) - {"cells", "holds", *extra})
    if unknown:
        raise RecipeError(f"{where}: unknown key(s): {', '.join(unknown)}")
    if "cells" not in value:
        raise RecipeError(f"{where}: missing cells")
    out = {"cells": _cells(value["cells"], size, where)}
    if "holds" in value:
        if not _is_text(value["holds"]):
            raise RecipeError(f"{where}: holds must be a one-line text")
        out["holds"] = value["holds"]
    return out


def validate_crop(value, size):
    """A normalised crop mapping, or None. Raises :class:`RecipeError`."""
    if value is None:
        return None
    crop = _target(value, size, "crop", extra=("gutter",))
    if "gutter" in value:
        gutter = value["gutter"]
        if not _is_int(gutter) or not 0 <= gutter <= MAX_GUTTER:
            raise RecipeError(f"crop: gutter must be an integer in [0, {MAX_GUTTER}]")
        if gutter:
            crop = {"cells": crop["cells"], "gutter": gutter,
                    **({"holds": crop["holds"]} if "holds" in crop else {})}
    return crop


def validate_overlays(value, size, crop=None):
    """A normalised overlay list, or None. Raises :class:`RecipeError`."""
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise RecipeError("overlays: must be a non-empty list")
    out, callouts = [], {}
    for number, item in enumerate(value, start=1):
        where = f"overlay {number}"
        if not isinstance(item, dict):
            raise RecipeError(f"{where}: must be a mapping")
        unknown = sorted(set(map(str, item)) - {"type", "target", "callout", "label"})
        if unknown:
            raise RecipeError(f"{where}: unknown key(s): {', '.join(unknown)}")
        kind = item.get("type")
        if kind not in OVERLAY_TYPES:
            raise RecipeError(f"{where}: type {kind!r} is not one of {', '.join(OVERLAY_TYPES)}")
        if "target" not in item:
            raise RecipeError(f"{where}: missing target")
        entry = {"type": kind, "target": _target(item["target"], size, f"{where} target")}
        if "callout" in item:
            callout = item["callout"]
            if not _is_int(callout) or not 1 <= callout <= MAX_CALLOUT:
                raise RecipeError(f"{where}: callout must be an integer in [1, {MAX_CALLOUT}]")
            if callout in callouts:
                raise RecipeError(f"{where}: callout {callout} is already used by "
                                  f"overlay {callouts[callout]}")
            callouts[callout] = number
            entry["callout"] = callout
        if "label" in item:
            if not _is_text(item["label"]):
                raise RecipeError(f"{where}: label must be a one-line text")
            entry["label"] = item["label"]
        if kind == "anchor" and "callout" not in entry and "label" not in entry:
            raise RecipeError(f"{where}: an anchor draws nothing without a callout or a label")
        if crop is not None:
            c, r, w, h = crop["cells"]
            tc, tr, tw, th = entry["target"]["cells"]
            if tc < c or tr < r or tc + tw > c + w or tr + th > r + h:
                raise RecipeError(f"{where}: target {entry['target']['cells']} lies outside "
                                  f"the crop {crop['cells']}; it would annotate cropped-away "
                                  "content")
        out.append(entry)
    return out


def _is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value.strip("\n")


def _pane_ref(value, roles, where: str) -> str:
    """A pane reference: a role created by an earlier step (or ``main``), or a
    ``<window>.<index>`` locator for a pane the TUI created itself."""
    if not isinstance(value, str) or not value:
        raise RecipeError(f"{where}: pane must be a role or <window>.<index>")
    if value in roles or LOCATOR_RE.fullmatch(value) and not ROLE_RE.fullmatch(value):
        return value
    if ROLE_RE.fullmatch(value):
        raise RecipeError(f"{where}: pane {value!r} is not created by an earlier step "
                          f"(roles so far: {', '.join(sorted(roles))})")
    raise RecipeError(f"{where}: pane {value!r} is neither a role nor <window>.<index>")


def _wait_value(value, kind: str, roles, where: str):
    """``(text, timeout, pane)`` from a wait step's value."""
    timeout = pane = None
    if isinstance(value, dict):
        unknown = sorted(set(map(str, value)) - {"text", "timeout", "pane"})
        if unknown or "text" not in value or len(value) < 2:
            raise RecipeError(f"{where}: {kind} mapping must have text plus timeout "
                              "and/or pane")
        if "timeout" in value:
            timeout = value["timeout"]
            if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                    or not 0 < timeout <= MAX_WAIT_TIMEOUT):
                raise RecipeError(f"{where}: timeout must be a number of seconds in "
                                  f"(0, {MAX_WAIT_TIMEOUT}]")
            timeout = float(timeout)
        if "pane" in value:
            pane = _pane_ref(value["pane"], roles, where)
        value = value["text"]
    if not _is_text(value):
        raise RecipeError(f"{where}: {kind} must be a non-empty text")
    return value, timeout, pane


def _keys_value(value, roles, where: str):
    pane = None
    if isinstance(value, dict):
        if set(map(str, value)) != {"keys", "pane"}:
            raise RecipeError(f"{where}: keys mapping must have exactly keys and pane")
        pane = _pane_ref(value["pane"], roles, where)
        value = value["keys"]
    if (not isinstance(value, list) or not value
            or not all(isinstance(k, str) and k for k in value)):
        raise RecipeError(f"{where}: keys must be a non-empty list of key names")
    return tuple(value), pane


def _new_pane_value(kind: str, value, roles, where: str) -> tuple[dict, str]:
    """The normalised mapping of a ``pane_split`` / ``window_new`` step and
    the role it creates."""
    allowed = ({"name", "command", "target", "direction", "size", "full"}
               if kind == "pane_split" else {"name", "command", "role"})
    if not isinstance(value, dict):
        raise RecipeError(f"{where}: {kind} must be a mapping")
    unknown = sorted(set(map(str, value)) - allowed)
    if unknown:
        raise RecipeError(f"{where}: {kind}: unknown key(s): {', '.join(unknown)}")
    for key in ("name", "command"):
        if not _is_text(value.get(key)):
            raise RecipeError(f"{where}: {kind} needs a one-line {key}")
    out = {"name": value["name"], "command": value["command"]}
    if kind == "window_new":
        if not WINDOW_NAME_RE.fullmatch(value["name"]):
            raise RecipeError(f"{where}: window name {value['name']!r} must match "
                              f"{WINDOW_NAME_RE.pattern}")
        role = value.get("role") or value["name"]
        if value.get("role"):
            out["role"] = value["role"]
    else:
        role = value["name"]
        if value.get("target") is not None:
            out["target"] = _pane_ref(value["target"], roles, where)
        direction = value.get("direction", "h")
        if direction not in ("h", "v"):
            raise RecipeError(f"{where}: direction must be h or v")
        out["direction"] = direction
        if value.get("size") is not None:
            size = str(value["size"])
            if isinstance(value["size"], bool) or not SIZE_RE.fullmatch(size):
                raise RecipeError(f"{where}: size {value['size']!r} must be cells (40) "
                                  "or a percentage (40%)")
            out["size"] = size
        if value.get("full"):
            if value["full"] is not True:
                raise RecipeError(f"{where}: full must be true or absent")
            out["full"] = True
    if not ROLE_RE.fullmatch(role):
        raise RecipeError(f"{where}: role {role!r} must match {ROLE_RE.pattern}")
    if role in roles:
        raise RecipeError(f"{where}: role {role!r} is already used")
    return out, role


def _validate_steps(raw_steps) -> tuple[list, set]:
    if not isinstance(raw_steps, list):
        raise RecipeError("steps: must be a list")
    roles = {MAIN}
    steps = []
    for number, step in enumerate(raw_steps, start=1):
        where = f"step {number}"
        if not isinstance(step, dict) or len(step) != 1:
            raise RecipeError(f"{where}: must be a mapping with exactly one of "
                              f"{', '.join(STEP_KINDS)}")
        (kind, value), = step.items()
        if kind not in STEP_KINDS:
            raise RecipeError(f"{where}: unknown kind {kind!r}")
        if kind == "keys":
            value, pane = _keys_value(value, roles, where)
            steps.append((kind, value, None, pane))
        elif kind in ("wait", "wait_gone"):
            steps.append((kind, *_wait_value(value, kind, roles, where)))
        else:
            value, role = _new_pane_value(kind, value, roles, where)
            roles.add(role)
            steps.append((kind, value, None, None))
    return steps, roles


def validate_capture(value, roles=None):
    """``{"window": NAME}`` / ``{"pane": P}`` normalised, or None (main pane)."""
    if value is None:
        return None
    if not isinstance(value, dict) or len(value) != 1 \
            or next(iter(value)) not in ("window", "pane"):
        raise RecipeError("capture: must be {window: NAME} or {pane: P}")
    (key, name), = value.items()
    if key == "window":
        if not isinstance(name, str) or not WINDOW_NAME_RE.fullmatch(name):
            raise RecipeError(f"capture: window {name!r} must match {WINDOW_NAME_RE.pattern}")
        return {"window": name}
    return {"pane": _pane_ref(name, roles if roles is not None else {MAIN}, "capture")}


def _validate(data: dict, where: str) -> Recipe:
    def fail(message: str):
        raise RecipeError(f"{where}: {message}")

    if not isinstance(data, dict):
        fail("the recipe is not a mapping")
    unknown = sorted(set(data) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        fail(f"unknown key(s): {', '.join(map(str, unknown))}")
    missing = [key for key in REQUIRED if key not in data]
    if missing:
        fail(f"missing key(s): {', '.join(missing)}")

    for key in ("id", "output"):
        if not isinstance(data[key], str):
            fail(f"{key}: must be a string")
    if not markers.SCENE_RE.match(data["id"]):
        fail(f"id {data['id']!r} must match [a-z0-9_]+")
    problem = markers.path_problem(data["output"])
    if problem:
        fail(f"output {data['output']!r} {problem}")

    size = data["size"]
    if (not isinstance(size, list) or len(size) != 2
            or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in size)):
        fail("size: must be [columns, rows], two positive integers")
    if not isinstance(data["dataset"], str) or data["dataset"] not in sample_project.DATASETS:
        known = ", ".join(sorted(sample_project.DATASETS))
        fail(f"dataset {data['dataset']!r} is not one of: {known}")
    if not _is_text(data["launch"]):
        fail("launch: must be one non-empty line")

    setup = data.get("setup") or []
    if not isinstance(setup, list) or not all(_is_text(c) for c in setup):
        fail("setup: must be a list of one-line commands")

    window = data.get("window", "")
    if window and (not isinstance(window, str) or not WINDOW_NAME_RE.fullmatch(window)):
        fail(f"window: {window!r} must match {WINDOW_NAME_RE.pattern}")
    try:
        steps, roles = _validate_steps(data.get("steps") or [])
        capture = validate_capture(data.get("capture"), roles)
    except RecipeError as exc:
        fail(str(exc))

    expect = data["expect"]
    if not isinstance(expect, list) or not expect or not all(_is_text(t) for t in expect):
        fail("expect: must be a non-empty list of texts")
    if not isinstance(data["illustrates"], str) or not data["illustrates"].strip():
        fail("illustrates: must say what the image is meant to show")
    title = data.get("title", "")
    if title and not _is_text(title):
        fail("title: must be one line")
    try:
        crop = validate_crop(data.get("crop"), size)
        overlays = validate_overlays(data.get("overlays"), size, crop)
    except RecipeError as exc:
        fail(str(exc))

    return Recipe(id=data["id"], output=data["output"], size=(size[0], size[1]),
                  dataset=data["dataset"], launch=data["launch"].strip(),
                  expect=tuple(expect), illustrates=" ".join(data["illustrates"].split()),
                  title=title or "", setup=tuple(setup), steps=tuple(steps),
                  crop=crop, overlays=overlays, window=window or "", capture=capture)


def load(path: Path) -> Recipe:
    path = Path(path)
    owner = markers.read_spec_owner(path)
    if owner.problems:
        raise RecipeError(f"{path.name}: " + "; ".join(owner.problems))
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RecipeError(f"{path.name}: not valid YAML: {exc}") from exc
    recipe = _validate(data, path.name)
    if recipe.id != path.stem:
        raise RecipeError(f"{path.name}: id {recipe.id!r} differs from the file name")
    # The two readers must agree, or the checker and the tool would disagree
    # about which scene owns which image.
    if (recipe.id, recipe.output) != (owner.id, owner.output):
        raise RecipeError(
            f"{path.name}: the line reader read id/output as "
            f"{owner.id!r}/{owner.output!r}, YAML as {recipe.id!r}/{recipe.output!r}")
    return Recipe(**{**recipe.__dict__, "path": str(path)})


def load_all(scenes_dir: Path) -> dict[str, Recipe]:
    recipes: dict[str, Recipe] = {}
    outputs: dict[str, str] = {}
    scenes_dir = Path(scenes_dir)
    if not scenes_dir.is_dir():
        return recipes
    for path in sorted(scenes_dir.glob("*.yaml")):
        recipe = load(path)
        if recipe.output in outputs:
            raise RecipeError(
                f"{path.name}: output {recipe.output!r} is already owned by "
                f"scene {outputs[recipe.output]!r}")
        outputs[recipe.output] = recipe.id
        recipes[recipe.id] = recipe
    return recipes


def _owner_line(key: str, value: str) -> str:
    """An ``id:`` / ``output:`` line both readers load as ``value``."""
    for line in (f"{key}: {value}", f'{key}: "{value}"'):
        _, read, problem = markers.read_spec_scalar(line)
        if problem is None and read == value:
            return line
    raise RecipeError(f"{key} {value!r} cannot be written as a single-line scalar")


def _number(value: float):
    return int(value) if float(value).is_integer() else value


class _Flow(list):
    """A list written on one line (``[2, 6, 38, 6]``): cell rectangles."""


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(
    _Flow, lambda dumper, data: dumper.represent_sequence(
        "tag:yaml.org,2002:seq", data, flow_style=True))


def _flow_cells(value):
    """A copy of a crop / overlay value with every ``cells`` list in flow style."""
    if isinstance(value, dict):
        return {k: _Flow(v) if k == "cells" else _flow_cells(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_flow_cells(v) for v in value]
    return value


def _dump_step(kind, value, timeout, pane) -> dict:
    """The schema form of one step: the short form whenever it says it all."""
    if kind == "keys":
        return {kind: list(value) if pane is None else {"keys": list(value), "pane": pane}}
    if kind in ("wait", "wait_gone"):
        if timeout is None and pane is None:
            return {kind: value}
        out = {"text": value}
        if timeout is not None:
            out["timeout"] = _number(timeout)
        if pane is not None:
            out["pane"] = pane
        return {kind: out}
    return {kind: dict(value)}


def dump(recipe: Recipe) -> str:
    body: dict = {}
    if recipe.title:
        body["title"] = recipe.title
    body["size"] = list(recipe.size)
    if recipe.window:
        body["window"] = recipe.window
    body["dataset"] = recipe.dataset
    body["setup"] = list(recipe.setup)
    body["launch"] = recipe.launch
    body["steps"] = [_dump_step(*step) for step in recipe.steps]
    body["expect"] = list(recipe.expect)
    body["illustrates"] = recipe.illustrates
    if recipe.crop is not None:
        body["crop"] = _flow_cells(recipe.crop)
    if recipe.overlays is not None:
        body["overlays"] = _flow_cells(recipe.overlays)
    if recipe.capture is not None:
        body["capture"] = dict(recipe.capture)
    head = ("# Recorded by `website/screenshots.sh recipe save` from a capture that worked.\n"
            "# Do not edit a failing recipe by hand: re-discover the route and save with --replace.\n")
    return (head + _owner_line("id", recipe.id) + "\n" + _owner_line("output", recipe.output)
            + "\n" + yaml.dump(body, Dumper=_Dumper, sort_keys=False, allow_unicode=True,
                                width=10 ** 6))


def from_session(session, *, scene: str, output: str, expect: list[str], illustrates: str,
                 title: str = "") -> Recipe:
    """Build a recipe from a session's WHOLE journal.

    Only a clean discovery session qualifies: a replay session (also one kept
    open after a failure) is for inspection, and a journal with a failed step
    is exploration. Neither may become a recipe; the route has to be walked
    once, cleanly, in a fresh session.
    """
    again = "Start a fresh session, walk the route cleanly, then save."
    if session.origin != "discovery":
        raise RecipeError(f"session {session.id} is a replay session; it is for inspection "
                          f"only and cannot be saved. {again}")
    failed = [n for n, entry in enumerate(session.journal, start=1) if not entry.get("ok", True)]
    if failed:
        raise RecipeError(f"session {session.id} has a failed step (journal entry "
                          f"{failed[0]}: {session.journal[failed[0] - 1]['kind']}). {again}")
    launches = [e for e in session.journal if e["kind"] == "launch"]
    if len(launches) != 1:
        raise RecipeError(f"session {session.id} has no launch (`run`) to record")
    shots = [i for i, e in enumerate(session.journal)
             if e["kind"] == "shot" and e.get("scene") == scene]
    if not shots:
        raise RecipeError(f"session {session.id} took no shot for scene {scene!r}")
    upto = shots[-1]
    setup = [e["command"] for e in session.journal[:upto] if e["kind"] == "setup"]
    steps = []
    for entry in session.journal[:upto]:
        pane = entry.get("pane")
        if entry["kind"] == "keys":
            steps.append({"keys": list(entry["keys"]) if pane is None
                          else {"keys": list(entry["keys"]), "pane": pane}})
        elif entry["kind"] in ("wait", "wait_gone"):
            # A wait that was allowed longer than the default keeps its budget,
            # or a slow but reachable state would fail on replay.
            timeout = entry.get("timeout")
            long_wait = timeout is not None and timeout > DEFAULT_WAIT_TIMEOUT
            if not long_wait and pane is None:
                steps.append({entry["kind"]: entry["text"]})
                continue
            value = {"text": entry["text"]}
            if long_wait:
                value["timeout"] = _number(timeout)
            if pane is not None:
                value["pane"] = pane
            steps.append({entry["kind"]: value})
        elif entry["kind"] == "pane_split":
            value = {"name": entry["name"], "command": entry["command"],
                     "direction": entry.get("direction", "h")}
            for key in ("target", "size"):
                if entry.get(key) is not None:
                    value[key] = entry[key]
            if entry.get("full"):
                value["full"] = True
            steps.append({"pane_split": value})
        elif entry["kind"] == "window_new":
            value = {"name": entry["window"], "command": entry["command"]}
            if entry["name"] != entry["window"]:
                value["role"] = entry["name"]
            steps.append({"window_new": value})
    data = {"id": scene, "output": output, "size": list(session.size),
            "dataset": session.dataset, "setup": setup, "launch": launches[0]["command"],
            "steps": steps, "expect": list(expect), "illustrates": illustrates}
    if title:
        data["title"] = title
    # The crop and overlays the shot was taken with are part of the route.
    shot = session.journal[upto]
    if shot.get("crop") is not None:
        data["crop"] = shot["crop"]
    if shot.get("overlays") is not None:
        data["overlays"] = shot["overlays"]
    if shot.get("capture") is not None:
        data["capture"] = shot["capture"]
    if getattr(session, "window", ""):
        data["window"] = session.window
    return _validate(data, f"scene {scene}")


def write(recipe: Recipe, scenes_dir: Path, *, replace: bool = False) -> Path:
    """Write ``scenes/<id>.yaml`` atomically, after reading it back.

    Without ``replace`` an existing recipe is refused. With it, the existing
    ``id`` and ``output`` are kept: a repair never changes which file a scene
    owns.
    """
    scenes_dir = Path(scenes_dir)
    path = scenes_dir / f"{recipe.id}.yaml"
    if path.exists():
        if not replace:
            raise RecipeError(f"{path.name} exists; repair it with --replace")
        existing = markers.read_spec_owner(path)
        if existing.output is not None and existing.output != recipe.output:
            raise RecipeError(
                f"{path.name} owns output {existing.output!r}; a replacement must keep it "
                f"(got {recipe.output!r})")
    for other in sorted(scenes_dir.glob("*.yaml")) if scenes_dir.is_dir() else []:
        if other != path and markers.read_spec_owner(other).output == recipe.output:
            raise RecipeError(f"output {recipe.output!r} is already owned by {other.name}")
    scenes_dir.mkdir(parents=True, exist_ok=True)
    tmp = scenes_dir / f".{recipe.id}.yaml.tmp"
    text = dump(recipe)
    tmp.write_text(text, encoding="utf-8")
    try:
        # Read it back through BOTH readers before it takes the real name, so
        # a recipe that does not round-trip never replaces a working one.
        owner = markers.read_spec_owner(tmp)
        if owner.problems or (owner.id, owner.output) != (recipe.id, recipe.output):
            raise RecipeError(f"{path.name}: id/output do not read back: "
                              + "; ".join(owner.problems))
        if _validate(yaml.safe_load(text), path.name) != recipe:
            raise RecipeError(f"{path.name}: the recipe does not read back as written")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return path
