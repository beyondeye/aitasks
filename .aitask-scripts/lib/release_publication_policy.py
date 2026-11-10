#!/usr/bin/env python3
"""Read the release-notification keys of a project_config.yaml (t2261_2).

Usage: release_publication_policy.py <project_config.yaml>

Parses the WHOLE document with a real YAML parser, so a key is found however it
is spelled: plain, single- or double-quoted, or inside a flow mapping. A
line-start grep would miss the last three and silently degrade a configured
publication policy to the generic one.

stdout protocol, read by lib/release_publication.sh:
    VAL<TAB><key><TAB><value>   one line per value (a list gives one per item)
    OK                          the LAST line, and only on success
or a single
    ERR<TAB><reason>            exit 3

A reader that dies half-way prints no OK line, so the caller never trusts a
truncated answer. Reasons: read_error, yaml_unavailable, yaml_error,
duplicate_key, document, or the name of the key whose value has the wrong type
or holds a tab / newline / carriage return.

Only the top-level keys below are judged. Every other key, of any shape, is
ignored: this reader answers "what does the release policy say", not "is the
whole config valid".
"""

from __future__ import annotations

import sys

SCALAR_KEYS = ("release_publication_workflow", "release_notify_host")
LIST_KEYS = ("release_publication_assets", "release_publication_checksum_manifests")


class _Refused(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _fail(reason: str) -> None:
    sys.stdout.write(f"ERR\t{reason}\n")
    sys.exit(3)


def _clean(key: str, value: object) -> str:
    # bool is a subclass of int, and a YAML `yes` must not pass as a string.
    if not isinstance(value, str):
        raise _Refused(key)
    if any(c in value for c in ("\t", "\n", "\r")) or value != value.strip():
        raise _Refused(key)
    if value == "":
        raise _Refused(key)
    return value


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        _fail("usage")
    try:
        with open(argv[1], "rb") as fh:
            raw = fh.read()
    except OSError:
        _fail("read_error")

    try:
        import yaml
    except Exception:  # noqa: BLE001 - any import failure means "cannot parse"
        _fail("yaml_unavailable")

    class _UniqueKeyLoader(yaml.SafeLoader):
        """SafeLoader that refuses a mapping with the same key twice.

        PyYAML keeps the LAST duplicate silently; another reader could keep the
        first, so a duplicated policy key has no single meaning and is refused.
        """

    def _construct_mapping(loader, node, deep=False):
        loader.flatten_mapping(node)
        seen = set()
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError:
                continue
            if key in seen:
                raise _Refused("duplicate_key")
            seen.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

    _UniqueKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
    )

    try:
        doc = yaml.load(raw, Loader=_UniqueKeyLoader)  # noqa: S506 - SafeLoader subclass
    except _Refused as exc:
        _fail(exc.reason)
    except Exception:  # noqa: BLE001 - every parse failure is one answer
        _fail("yaml_error")

    if doc is None:
        doc = {}
    if not isinstance(doc, dict):
        _fail("document")

    lines: list[str] = []
    try:
        for key in SCALAR_KEYS:
            if key in doc and doc[key] is not None:
                lines.append(f"VAL\t{key}\t{_clean(key, doc[key])}")
        for key in LIST_KEYS:
            if key not in doc or doc[key] is None:
                continue
            value = doc[key]
            items = value if isinstance(value, list) else [value]
            if not items:
                raise _Refused(key)
            for item in items:
                lines.append(f"VAL\t{key}\t{_clean(key, item)}")
    except _Refused as exc:
        _fail(exc.reason)

    for line in lines:
        sys.stdout.write(line + "\n")
    sys.stdout.write("OK\n")


if __name__ == "__main__":
    main(sys.argv)
