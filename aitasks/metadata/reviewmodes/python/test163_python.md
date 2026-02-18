---
name: Python Best Practices
description: Check type hints, modern idioms, context managers, and pythonic patterns
reviewtype: conventions
reviewlabels: [type-hints, idioms, context-managers, pythonic, resource-cleanup]
environment: [python]
---

## Review Instructions

### Type Hints
- Flag public functions missing type annotations on parameters and return types
- Look for use of `Any` where a more specific type is known — `Any` defeats the purpose of type checking
- Flag outdated typing imports: use `list`, `dict`, `tuple`, `set` directly instead of `typing.List`, `typing.Dict`, etc. (Python 3.9+)
- Check for missing `Optional[]` or `| None` on parameters that accept None
- Flag return type annotations that are too broad (e.g., `-> dict` when `-> UserConfig` would be more precise)
- Look for `# type: ignore` comments without explanation — these should document why the ignore is needed

### Modern Python Idioms
- Flag `.format()` or `%` string formatting — use f-strings instead (cleaner and faster)
- Look for `os.path.join()`, `os.path.exists()`, `os.path.dirname()` — use `pathlib.Path` instead
- Flag manual classes used purely as data containers — use `dataclasses.dataclass` or `typing.NamedTuple`
- Check for `dict.keys()` in containment checks — `key in dict` is sufficient (no need for `key in dict.keys()`)
- Flag `type()` comparisons — use `isinstance()` for type checking
- Look for manual JSON config parsing that could use `pydantic` or `dataclass` with validation

### Context Managers
- Flag file operations without `with` statement — always use `with open(...) as f:` to ensure cleanup
- Look for manual resource cleanup (explicit `.close()` calls) that should use context managers
- Check for classes that hold resources (connections, locks, temporary files) but don't implement `__enter__`/`__exit__`
- Flag `try/finally` blocks that could be replaced by existing context managers (e.g., `tempfile.NamedTemporaryFile`, `contextlib.suppress`)

### Pythonic Patterns
- Flag manual index tracking — use `enumerate()` instead of `for i in range(len(items))`
- Look for manual dict/list building in loops — use comprehensions where they improve readability
- Check for manual counter/grouping logic — use `collections.Counter` or `collections.defaultdict`
- Flag `if len(x) == 0` or `if len(x) > 0` — use `if not x` or `if x` (truthy/falsy checks)
- Look for manual flattening of nested lists — use `itertools.chain.from_iterable()`
- Flag `isinstance(x, (str, bytes))` checks scattered through code — centralize type dispatch
- Check for bare `assert` statements in production code — assertions are stripped with `-O` flag; use proper validation
