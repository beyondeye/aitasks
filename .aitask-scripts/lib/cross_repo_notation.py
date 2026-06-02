"""Cross-repo ``<project>#<id>`` notation parser.

Minimal, dependency-free helper shared by TUIs and scripts that need to
find cross-repo task references inside free text (task bodies, plan bodies).
The canonical notation lives in ``aidocs/framework/cross_repo_references.md``:

    aitasks#835_3     # preferred
    aitasks#t835_3    # accepted; the leading ``t`` is tolerated

Keep the surface to a single ``parse(text)`` function so future consumers
(e.g. ``ait monitor`` cross-repo surfacing) reuse it instead of reinventing
the regex.
"""

import re

# Unanchored variant of the canonical regex from
# aidocs/framework/cross_repo_references.md (``^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$``)
# so it can scan references embedded in larger text. The leading ``t`` on the
# id is tolerated but stripped from the returned value (canonical form).
_NOTATION_RE = re.compile(r"([a-z0-9_-]+)#t?(\d+(?:_\d+)?)")


def parse(text):
    """Find all ``<project>#<id>`` / ``<project>#t<id>`` references in *text*.

    Returns a list of ``(project_name, task_id)`` tuples in order of
    appearance. ``task_id`` is returned without the optional ``t`` prefix
    (canonical form, e.g. ``835_3``). Returns an empty list when *text* is
    falsy or contains no matches.
    """
    if not text:
        return []
    return [(m.group(1), m.group(2)) for m in _NOTATION_RE.finditer(text)]
