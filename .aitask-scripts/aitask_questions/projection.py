"""Explicit, versioned projections used by approval freshness.

Exact bytes are the default. These two rules are the only exceptions, and each
is named in the manifest or consumption record it applies to, so a later change
of rule is a new version rather than a silent reinterpretation. A record made
under an older version is not honoured: it is retired, never re-read under the
new rule.

  task-requirements/v2  what a plan approval binds of the TASK file: the
                        frontmatter fields in REQUIREMENT_FIELDS, and its body
                        without framework ledger blocks. Recording a gate,
                        receiving a note, or a status/assignment/board write
                        therefore does not void the approval; editing the
                        description, a dependency or the declared gates does.
  plan-bookkeeping/v2   what may change in an approved PLAN file after its
                        approval was claimed without voiding it: the state of
                        task-list checkboxes, nothing else. No text can be
                        added, so the tolerance cannot carry a requirement.

One more shape is recognised, and it is NOT a tolerance - the approval does not
stand under it, so nothing may be implemented on it:

  plan-closing-notes/v1 the approved plan, intact, followed only by the
                        sections the workflow writes when the work is done
                        (CLOSING_HEADINGS). Verdict NOTES: enough to archive a
                        finished task, never enough to resume implementing.

Spec: aidocs/codeagents/codex_questions.md, "Gate enforcement".
"""
from __future__ import annotations

import hashlib
import json
import re

from .errors import QuestionError

TASK_PROJECTION = "task-requirements/v2"
PLAN_PROJECTION = "plan-bookkeeping/v2"
CLOSING_PROJECTION = "plan-closing-notes/v1"
# The sections the workflow appends to a plan after implementation.
CLOSING_HEADINGS = ("## Post-Review Changes", "## Final Implementation Notes")

# Frontmatter that states what the task requires. Everything else is workflow
# state (status, assigned_to, updated_at, board position, active_gates* -
# derived from `gates` at claim - plan_approved_at, implemented_with, ...) and
# changes while an approved plan is being implemented.
REQUIREMENT_FIELDS = ("issue_type", "depends", "xdeps", "xdeprepo", "gates",
                      "verifies", "folded_tasks")

# The checkpoint whose approval is of a change set that is then committed. Its
# occurrences also bind where the change goes: the branch, and what each path
# holds there (see Store._capture, commit.py).
CHANGE_CHECKPOINT = "review_approved"

# The checkpoint whose approval is of merging one revision into one branch. Its
# occurrences bind both (Store._merge_target); it binds no files.
MERGE_CHECKPOINT = "merge_approved"

# The checkpoint whose approval is of a task's plan, and the workflow names
# that are tasks: t<N> or t<parent>_<child>.
PLAN_CHECKPOINT = "plan_approved"
TASK_WORKFLOW_RE = re.compile(r"t(\d+)(?:_(\d+))?")
TASK_DIR = "aitasks"

# Framework ledgers appended to a task file. A block is its marker line plus
# the quoted/blank lines after it, as the ledger parsers read it.
_MARKER_RE = re.compile(r"^>\s*\*\*\S+\s+[A-Za-z0-9_]+:[A-Za-z0-9_]+\*\*")
_LEDGER_HEADERS = ("## Gate Runs", "## Inbox")
_LEDGER_COMMENT_RE = re.compile(r"^<!-- Appended by the \w+ framework\. .* -->$")
_CHECKBOX_RE = re.compile(rb"^([ \t]*(?:[-*+]|\d+[.)])[ \t]+\[)[ xX](\])", re.M)
_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$")


def is_task_workflow(workflow):
    return TASK_WORKFLOW_RE.fullmatch(workflow) is not None


def task_file(project, workflow):
    """Project-relative path of the task file a task workflow names."""
    match = TASK_WORKFLOW_RE.fullmatch(workflow)
    parent, child = match.group(1), match.group(2)
    if child is None:
        found = sorted((project / TASK_DIR).glob(f"t{parent}_*.md"))
    else:
        found = sorted((project / TASK_DIR / f"t{parent}").glob(f"t{parent}_{child}_*.md"))
    if len(found) != 1:
        raise QuestionError(f"task file for {workflow} is missing or ambiguous; "
                            "its requirements cannot be bound")
    return str(found[0].relative_to(project))


def _field_value(first, more):
    """A frontmatter value in one comparable form: a list of items, or text.

    `depends: [1, 3]`, `depends: [1,3]` and the block form are one value. An
    empty value and an empty list are both "nothing", and so is an absent key.
    """
    first = first.strip()
    items = [line.strip()[1:].strip() for line in more if line.strip().startswith("-")]
    if not first and items:
        values = items
    elif first.startswith("[") and first.endswith("]"):
        values = [part.strip() for part in first[1:-1].split(",") if part.strip()]
    else:
        text = " ".join([first] + [line.strip() for line in more]).strip()
        return text.strip("'\"")
    return [value.strip("'\"") for value in values]


def _requirement_fields(lines):
    """The REQUIREMENT_FIELDS of a frontmatter block, as canonical lines."""
    found, idx = {}, 0
    while idx < len(lines):
        match = _KEY_RE.match(lines[idx])
        idx += 1
        if not match:
            continue
        more = []
        while idx < len(lines) and (not lines[idx].strip() or lines[idx][:1] in " \t-"):
            more.append(lines[idx])
            idx += 1
        if match.group(1) in REQUIREMENT_FIELDS:
            value = _field_value(match.group(2), more)
            if value:
                found[match.group(1)] = value
    return [f"{key}: {json.dumps(found[key], ensure_ascii=False)}"
            for key in REQUIREMENT_FIELDS if key in found]


def task_requirements(data):
    """task-requirements/v2 of a task file's bytes."""
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise QuestionError("task file is not UTF-8") from exc
    fields = []
    if lines and lines[0].strip() == "---":
        try:
            close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        except StopIteration as exc:
            raise QuestionError("task file frontmatter is unterminated") from exc
        fields = _requirement_fields(lines[1:close])
        lines = lines[close + 1:]
    kept, idx = [], 0
    while idx < len(lines):
        line = lines[idx]
        if _MARKER_RE.match(line):
            idx += 1
            while idx < len(lines) and not _MARKER_RE.match(lines[idx]) and (
                    lines[idx].startswith(">") or not lines[idx].strip()):
                idx += 1
            kept.append("")
            continue
        if line.rstrip() not in _LEDGER_HEADERS and not _LEDGER_COMMENT_RE.match(line.rstrip()):
            kept.append(line.rstrip())
        idx += 1
    out = []
    for line in kept:  # removed blocks leave blank runs; they carry nothing
        if line or (out and out[-1]):
            out.append(line)
    body = "\n".join(out).strip("\n")
    return "\n".join(fields + ["---", body]).encode()


def unmet(workflow, checkpoint, manifest, target=None):
    """Why a manifest lacks what its checkpoint must bind today, or "".

    Asked of a saved claim as well as of a new one: a plan approval recorded
    before the task's requirements were bound, or under an older rule, cannot
    be shown to cover them; neither can a merge approval that names no
    revision.
    """
    if checkpoint == PLAN_CHECKPOINT and is_task_workflow(workflow):
        if not any(entry.get("projection") == TASK_PROJECTION for entry in manifest):
            return f"task requirements are not bound under {TASK_PROJECTION}"
    if checkpoint == MERGE_CHECKPOINT and (target or {}).get("kind") != "merge":
        return "the merged revision and its destination are not bound"
    return ""


def derived(project, workflow, checkpoint):
    """Manifest entries the server binds by itself: [(entry, bound bytes)]."""
    if checkpoint != PLAN_CHECKPOINT or not is_task_workflow(workflow):
        return []
    rel = task_file(project, workflow)
    try:
        bound = task_requirements((project / rel).read_bytes())
    except OSError as exc:
        raise QuestionError("task file is unreadable") from exc
    return [({"path": rel, "sha256": hashlib.sha256(bound).hexdigest(),
              "projection": TASK_PROJECTION}, bound)]


def plan_covers(approved, live):
    """plan-bookkeeping/v2: is `live` the approved plan with only boxes ticked?"""
    return _CHECKBOX_RE.sub(rb"\1 \2", approved) == _CHECKBOX_RE.sub(rb"\1 \2", live)


def plan_closed(approved, live):
    """plan-closing-notes/v1: is `live` the approved plan (boxes aside) with
    only the workflow's closing sections appended after it?

    The appended part must open with a closing heading and may hold no other
    first- or second-level heading (fenced code aside), so it cannot smuggle a
    new plan section in.
    """
    approved = _CHECKBOX_RE.sub(rb"\1 \2", approved).rstrip()
    live = _CHECKBOX_RE.sub(rb"\1 \2", live)
    if not live.startswith(approved):
        return False
    rest = live[len(approved):]
    if rest[:1] not in (b"\n", b"\r") or not rest.strip():
        return False  # nothing appended, or text glued onto the last approved line
    try:
        lines = rest.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return False
    fenced, opened = False, False
    for line in lines:
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            if not opened:
                return False
            continue
        if fenced or not line.strip():
            continue
        if line.rstrip() in CLOSING_HEADINGS:
            opened = True
        elif not opened or re.match(r"#{1,2}(\s|$)", line):
            return False
    return opened and not fenced
