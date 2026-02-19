---
name: Python Style Guide
description: Check Python code for Google style guide compliance including naming, formatting, docstrings, and language rules
reviewtype: style
reviewlabels: [naming, formatting, idioms, comments]
environment: [python]
source_url: https://github.com/gemini-cli-extensions/conductor/tree/main/templates/code_styleguides
---

## Review Instructions

### Language Rules
- Flag bare `except:` clauses (use specific exception types)
- Flag mutable objects (`[]`, `{}`) as default argument values
- Check that `if foo is None:` is used instead of `if foo == None:`
- Verify that implicit false is used for empty containers (e.g., `if not my_list:`)
- Check that comprehensions are used only for simple cases (flag complex logic in comprehensions)
- Flag mutable global state (module-level constants in `ALL_CAPS` are acceptable)
- Verify that type annotations are used for public APIs

### Formatting
- Check that line length does not exceed 80 characters
- Verify that indentation uses 4 spaces (no tabs)
- Check that two blank lines separate top-level definitions
- Check that one blank line separates method definitions
- Verify that binary operators are surrounded by single spaces
- Check that imports are on separate lines, grouped: standard library, third-party, application

### Naming
- Check that modules, functions, methods, and variables use `snake_case`
- Check that class names use `PascalCase`
- Check that constants use `ALL_CAPS_WITH_UNDERSCORES`
- Check that internal members use a single leading underscore (`_internal_variable`)

### Docstrings
- Verify that triple double quotes (`"""`) are used for docstrings
- Check that every public module, function, class, and method has a docstring
- Verify that docstrings start with a one-line summary
- Check that `Args:`, `Returns:`, and `Raises:` sections are included where applicable
- Verify that f-strings are used for string formatting

### Main Guard
- Verify that executable files have a `main()` function
- Check that executable files use `if __name__ == '__main__':` guard
