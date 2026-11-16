"""Recipes: the recorded route to one screenshot (``scenes/<id>.yaml``).

A recipe is written by the tool from the journal of a capture that worked. It
is a cache of a route, not a specification: when it fails, or no longer shows
what its page describes, the agent finds a route again and replaces it.

```yaml
id: board_child_tasks
output: aitasks_board_child_tasks.svg
title: aitasks board
size: [126, 40]
dataset: base                 # sample_project.DATASETS
setup: []                     # commands run in the project before the launch
launch: ./ait board
steps:
  - wait: Backlog (2)
  - keys: [x]
  - wait: {text: Report ready, timeout: 120}   # a wait that needed longer
expect:                       # texts that must be on screen at capture time
  - t12_1 cart summary widget
illustrates: >-               # what the image is meant to show (for the agent)
  An expanded parent task with its child cards.
```

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

REQUIRED = ("id", "output", "size", "dataset", "launch", "expect", "illustrates")
OPTIONAL = ("title", "setup", "steps", "crop", "overlays")
STEP_KINDS = ("keys", "wait", "wait_gone")
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
    #: ``(kind, value, timeout)``; ``timeout`` is None for keys and for a wait
    #: that used the default budget.
    steps: tuple[tuple[str, object, float | None], ...] = ()
    crop: object = None
    overlays: object = None
    path: str = field(default="", compare=False)

    @property
    def window_title(self) -> str:
        return self.title or "aitasks"


def _is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value.strip("\n")


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

    steps = []
    raw_steps = data.get("steps") or []
    if not isinstance(raw_steps, list):
        fail("steps: must be a list")
    for number, step in enumerate(raw_steps, start=1):
        if not isinstance(step, dict) or len(step) != 1:
            fail(f"step {number}: must be a mapping with exactly one of {', '.join(STEP_KINDS)}")
        (kind, value), = step.items()
        if kind not in STEP_KINDS:
            fail(f"step {number}: unknown kind {kind!r}")
        timeout = None
        if kind == "keys":
            if (not isinstance(value, list) or not value
                    or not all(isinstance(k, str) and k for k in value)):
                fail(f"step {number}: keys must be a non-empty list of key names")
            value = tuple(value)
        else:
            if isinstance(value, dict):
                # The long form: a wait that was given more than the default.
                if set(value) != {"text", "timeout"}:
                    fail(f"step {number}: {kind} mapping must have exactly text and timeout")
                timeout = value["timeout"]
                if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                        or not 0 < timeout <= MAX_WAIT_TIMEOUT):
                    fail(f"step {number}: timeout must be a number of seconds in "
                         f"(0, {MAX_WAIT_TIMEOUT}]")
                timeout = float(timeout)
                value = value["text"]
            if not _is_text(value):
                fail(f"step {number}: {kind} must be a non-empty text")
        steps.append((kind, value, timeout))

    expect = data["expect"]
    if not isinstance(expect, list) or not expect or not all(_is_text(t) for t in expect):
        fail("expect: must be a non-empty list of texts")
    if not isinstance(data["illustrates"], str) or not data["illustrates"].strip():
        fail("illustrates: must say what the image is meant to show")
    title = data.get("title", "")
    if title and not _is_text(title):
        fail("title: must be one line")

    return Recipe(id=data["id"], output=data["output"], size=(size[0], size[1]),
                  dataset=data["dataset"], launch=data["launch"].strip(),
                  expect=tuple(expect), illustrates=" ".join(data["illustrates"].split()),
                  title=title or "", setup=tuple(setup), steps=tuple(steps),
                  crop=data.get("crop"), overlays=data.get("overlays"))


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


def dump(recipe: Recipe) -> str:
    body: dict = {}
    if recipe.title:
        body["title"] = recipe.title
    body["size"] = list(recipe.size)
    body["dataset"] = recipe.dataset
    body["setup"] = list(recipe.setup)
    body["launch"] = recipe.launch
    body["steps"] = [
        {kind: list(value) if kind == "keys"
         else value if timeout is None else {"text": value, "timeout": _number(timeout)}}
        for kind, value, timeout in recipe.steps]
    body["expect"] = list(recipe.expect)
    body["illustrates"] = recipe.illustrates
    if recipe.crop is not None:
        body["crop"] = recipe.crop
    if recipe.overlays is not None:
        body["overlays"] = recipe.overlays
    head = ("# Recorded by `website/screenshots.sh recipe save` from a capture that worked.\n"
            "# Do not edit a failing recipe by hand: re-discover the route and save with --replace.\n")
    return (head + _owner_line("id", recipe.id) + "\n" + _owner_line("output", recipe.output)
            + "\n" + yaml.safe_dump(body, sort_keys=False, allow_unicode=True, width=10 ** 6))


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
        if entry["kind"] == "keys":
            steps.append({"keys": list(entry["keys"])})
        elif entry["kind"] in ("wait", "wait_gone"):
            # A wait that was allowed longer than the default keeps its budget,
            # or a slow but reachable state would fail on replay.
            timeout = entry.get("timeout")
            if timeout is not None and timeout > DEFAULT_WAIT_TIMEOUT:
                steps.append({entry["kind"]: {"text": entry["text"],
                                              "timeout": _number(timeout)}})
            else:
                steps.append({entry["kind"]: entry["text"]})
    data = {"id": scene, "output": output, "size": list(session.size),
            "dataset": session.dataset, "setup": setup, "launch": launches[0]["command"],
            "steps": steps, "expect": list(expect), "illustrates": illustrates}
    if title:
        data["title"] = title
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
