---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [framework, python, gates]
assigned_to: dario-e@beyond-eye.com
anchor: 1657
created_at: 2026-09-01 16:42
updated_at: 2026-09-01 17:05
---

# Validate the ledger-block namespace before interpolating it into a regex

Surfaced in review of **t1657_1**, which introduced
`.aitask-scripts/lib/ledger_block.py`. Deferred there as a follow-up: current
usage is safe, so this is latent rather than live.

## The defect

`build_marker_re()` and `build_marker_search_re()` interpolate the caller's
`namespace` straight into a regex:

```python
def build_marker_re(namespace: str) -> re.Pattern:
    return re.compile(rf"^>\s*\*\*(\S+)\s+{namespace}:({_NAME_CHARS})\*\*(.*)$")
```

The module **declares** the intended charset and then never applies it —
`_NAMESPACE_CHARS = r"[A-Za-z0-9_]+"` at `ledger_block.py:48` has exactly one
occurrence in the file, its own definition. A constant that reads as a
validation rule but is dead is worse than no constant: it tells the next author
the input is already constrained.

Measured on the shipped module:

| namespace | result |
|---|---|
| `....` | **matches a `gate:` marker** — a wildcard namespace silently cross-parses another ledger's blocks |
| `note(` | `re.PatternError: missing ), unterminated subpattern` — a crash at compile time |

The silent case is the dangerous one: a consumer that parses another ledger's
blocks as its own would union, dedup and order records under the wrong spec.

## Why it is not live today

The only namespaces in the tree are `gate` (`gate_ledger.NAMESPACE`) and the
`note` literal t1657_2 introduces; both are plain identifiers. This is a
latent-defect fix on a new public API, not a bug report against current
behaviour.

## Suggested fix

Validate once, at the top of both builders, against the constant that already
exists:

```python
_NAMESPACE_RE = re.compile(rf"\A{_NAMESPACE_CHARS}\Z")

def _checked_namespace(namespace: str) -> str:
    if not _NAMESPACE_RE.match(namespace):
        raise ValueError(
            f"ledger namespace must match {_NAMESPACE_CHARS}, got {namespace!r}")
    return namespace
```

Prefer this over `re.escape()`: escaping would make a nonsense namespace *work*
rather than be rejected, and the charset is a real contract — a namespace is a
marker identifier, not arbitrary text. Fail closed.

Apply the same treatment to `_NAME_CHARS` if a record name ever becomes
caller-supplied; today it is a fixed pattern, not an input.

## Verification

- A new test asserting both builders reject `....`, `note(`, `""` and
  `note|gate` with `ValueError`, and still accept `gate` and `note`.
- Every existing gate and merge suite stays green — `gate` and `note` are valid,
  so no call site changes.
