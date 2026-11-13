"""Pure paginated multi-selection protocol shared by native and text forms.

Page submissions are immutable. A candidate-set revision is a new question
occurrence. Navigation never enters the selected set. Explicit empty selection
is valid when the caller's cardinality allows it; missing input is not empty.
"""
from __future__ import annotations

import json

from .errors import QuestionError


def validate_shape(question):
    count = len(question["options"])
    for key, default, low, high in [("page_size", 3, 1, 20),
                                    ("min_selected", 0, 0, count),
                                    ("max_selected", count, 0, count)]:
        value = question.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise QuestionError(f"invalid multi-select {key}")
    if question.get("min_selected", 0) > question.get("max_selected", count):
        raise QuestionError("invalid multi-select cardinality")
    if type(question.get("allow_early_finish", True)) is not bool:
        raise QuestionError("invalid allow_early_finish")


def page_view(question, occurrence, selection):
    index = selection["page"]
    size = question.get("page_size", 3)
    start = index * size
    options = question["options"][start:start + size]
    has_more = start + size < len(question["options"])
    actions = (["next"] if has_more else [])
    if not has_more or question.get("allow_early_finish", True):
        actions.append("finish")
    actions.extend(["all", "none"])
    return {"page_id": f"{occurrence}/{question['id']}/{index}", "index": index,
            "page_count": (len(question["options"]) + size - 1) // size,
            "options": options, "selected_so_far": selection["selected"],
            "actions": actions,
            "prompt_answer_format": '{"selected":["exact option ID"],"action":"next or finish"}'}


def parse_submission(value):
    if isinstance(value, str):
        if len(value) > 20000:
            raise QuestionError("selection payload too large")
        def unique_fields(pairs):
            result = {}
            for key, val in pairs:
                if key in result:
                    raise QuestionError("duplicate selection payload field")
                result[key] = val
            return result
        try:
            value = json.loads(value, object_pairs_hook=unique_fields)
        except (ValueError, TypeError) as exc:
            raise QuestionError("selection requires explicit JSON selected/action fields") from exc
    if not isinstance(value, dict) or set(value) != {"selected", "action"}:
        raise QuestionError("selection requires exactly selected and action")
    selected = value["selected"]
    if (not isinstance(selected, list) or not all(isinstance(x, str) for x in selected)
            or len(set(selected)) != len(selected)):
        raise QuestionError("selection must contain distinct exact option IDs")
    if not isinstance(value["action"], str) or value["action"] not in {"next", "finish", "all", "none"}:
        raise QuestionError("invalid selection action")
    if value["action"] in {"all", "none"} and selected:
        raise QuestionError("all/none cannot be combined with selected items")
    return {"selected": sorted(selected), "action": value["action"]}


def advance(question, occurrence, selection, page_id, submission):
    page = page_view(question, occurrence, selection)
    if page_id != page["page_id"]:
        raise QuestionError("stale or missing page_id; inspect the pending page")
    if submission["action"] not in page["actions"]:
        raise QuestionError("this page does not allow that action")
    page_ids = {o["id"] for o in page["options"]}
    if not set(submission["selected"]).issubset(page_ids):
        raise QuestionError("selection contains IDs outside the displayed page")
    action = submission["action"]
    selected = set(selection["selected"]) | set(submission["selected"])
    if action == "all":
        selected = {o["id"] for o in question["options"]}
    elif action == "none":
        selected = set()
    ordered = [o["id"] for o in question["options"] if o["id"] in selected]
    done = action != "next"
    if len(ordered) > question.get("max_selected", len(question["options"])):
        raise QuestionError("selection exceeds maximum cardinality")
    if done and len(ordered) < question.get("min_selected", 0):
        raise QuestionError("selection is below minimum cardinality")
    return ordered, done
