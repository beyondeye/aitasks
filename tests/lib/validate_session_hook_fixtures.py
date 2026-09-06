#!/usr/bin/env python3
"""Validate the SessionStart hook fixtures against their committed schema.

Usage:  validate_session_hook_fixtures.py <tests/data/session_hooks dir>

Driven by ``schema.json`` in that directory rather than by rules hard-coded
here, so the contract has exactly one source and a child task that changes it
changes one file. Exits 0 when every fixture is valid, 1 otherwise, printing one
line per problem.

WHY THREE STATUSES. A single "required keys" rule cannot be right for every
outcome the t1705_1 spike can legitimately reach: a proven-unsupported agent has
no payload to carry, and an inconclusive probe must not masquerade as a settled
contract. ``_fixture_status`` therefore selects which fields are required and
which are forbidden -- notably, an ``unsupported`` fixture may carry NO payload
key at all, so nothing downstream can read a half-payload as real.

Reusable by child t1705_3, whose unit tests consume these same fixtures and must
branch on ``_fixture_status`` rather than assume a payload.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FIXTURE_GLOB = "*_sessionstart.json"


def _iter_strings(value):
    """Yield every string anywhere in a JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _iter_strings(v)


def validate_one(path: Path, schema: dict, problems: list[str]) -> None:
    name = path.name
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        problems.append(f"{name}: unreadable or not valid JSON ({exc})")
        return
    if not isinstance(data, dict):
        problems.append(f"{name}: top level is not a JSON object")
        return

    status_field = schema.get("status_field", "_fixture_status")
    status = data.get(status_field)
    statuses = schema["statuses"]
    if status not in statuses:
        problems.append(
            f"{name}: {status_field} is {status!r}, expected one of "
            f"{sorted(statuses)}"
        )
        return

    rules = statuses[status]

    for key in rules.get("required", []):
        if key not in data:
            problems.append(f"{name}: status {status!r} requires field {key!r}")

    for key in rules.get("required_non_empty", []):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(
                f"{name}: field {key!r} must be a non-empty string for status "
                f"{status!r} (got {value!r})"
            )

    for key, expected in rules.get("required_values", {}).items():
        if data.get(key) != expected:
            problems.append(
                f"{name}: field {key!r} must be {expected!r} for status "
                f"{status!r} (got {data.get(key)!r})"
            )

    for key, banned in rules.get("forbidden_values", {}).items():
        if data.get(key) == banned:
            problems.append(
                f"{name}: field {key!r} must not be {banned!r} for status "
                f"{status!r}"
            )

    for key in rules.get("forbidden", []):
        if key in data:
            problems.append(
                f"{name}: status {status!r} forbids field {key!r} -- a "
                f"half-payload must never be readable as a real one"
            )

    enum = rules.get("reason_enum")
    if enum and data.get("_reason") not in enum:
        problems.append(
            f"{name}: _reason must be one of {enum} for status {status!r} "
            f"(got {data.get('_reason')!r})"
        )

    evidence_keys = rules.get("required_evidence_keys")
    if evidence_keys:
        evidence = data.get("_evidence")
        if not isinstance(evidence, dict):
            problems.append(f"{name}: _evidence must be an object")
        else:
            for key in evidence_keys:
                if key not in evidence:
                    problems.append(
                        f"{name}: _evidence must record {key!r} (the positive "
                        f"control that licenses an {status!r} verdict)"
                    )

    # --- redaction: asserted on EVERY run, not only on a refresh -----------
    red = schema.get("redaction", {})
    expected_cwd = red.get("cwd_when_present_must_equal")
    if "cwd" in data and expected_cwd is not None and data["cwd"] != expected_cwd:
        problems.append(
            f"{name}: cwd must be redacted to {expected_cwd!r} (got "
            f"{data['cwd']!r})"
        )
    patterns = [re.compile(p) for p in red.get("forbidden_value_patterns", [])]
    for text in _iter_strings(data):
        for pattern in patterns:
            if pattern.search(text):
                problems.append(
                    f"{name}: value {text!r} leaks a real path "
                    f"(matches /{pattern.pattern}/)"
                )
                break


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    directory = Path(argv[1])
    schema_path = directory / "schema.json"
    if not schema_path.is_file():
        print(f"FAIL: no schema at {schema_path}")
        return 1
    try:
        schema = json.loads(schema_path.read_text())
    except ValueError as exc:
        print(f"FAIL: schema.json is not valid JSON ({exc})")
        return 1

    fixtures = sorted(directory.glob(FIXTURE_GLOB))
    if not fixtures:
        print(f"FAIL: no fixtures matching {FIXTURE_GLOB} in {directory}")
        return 1

    problems: list[str] = []
    for path in fixtures:
        validate_one(path, schema, problems)

    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        return 1

    for path in fixtures:
        data = json.loads(path.read_text())
        status = data.get("_fixture_status")
        reason = data.get("_reason", "")
        suffix = f" ({reason})" if reason and status != "unsupported" else ""
        print(f"  ok: {path.name} -> {status}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
