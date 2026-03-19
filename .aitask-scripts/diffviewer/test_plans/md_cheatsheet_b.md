---
Task: t000_markdown_cheatsheet_visual_test.md
Worktree: (none)
Branch: main
Base branch: main
---

# Markdown Syntax Reference

This plan demonstrates all common markdown syntax for visual testing of the diff viewer's markdown highlighting.

## Headings

### Third-Level Section

#### Fourth-Level Section

##### Fifth-Level Section

###### Sixth-Level Section

## Inline Formatting

This paragraph contains **strong text** and *italic text* and ***bold italic*** together. Here is `inline code` mixed with regular text. More **emphasis** at the end.

Another paragraph with *stress on several words* and **heavily emphasized words** and `settings.json` file references.

A new paragraph only in the B version with `special code` and **unique bold** content.

## Unordered Lists

- First item in the list
- Second item with **strong** content
- Third item with `code` inside
  - Nested item one
  - Nested item two
  - Nested item three (added)
- Fifth item added in version B

## Ordered Lists

1. Step one: initialize the project
2. Step two: configure the **server**

3. Step three: run `pip install`
4. Step four: verify the setup
   1. Sub-step: check logs

   2. Sub-step: run health check
   3. Sub-step: validate output (added)
5. Step five: deploy to staging

## Alternative List Markers

* Star-style list item
* Modified star item
* Third star item

## Code Blocks

Here is a fenced code block:

```python
def greet(name: str) -> str:
    """A personalized greeting function."""
    message = f"Hello, {name}!"
    print(message)
    return message
```

And another one:

```bash
#!/bin/bash
echo "Running deployment to staging..."
git pull origin main
npm run build
npm run test
```

## Blockquotes

> This is a blockquote with some critical information.

> It spans multiple lines and contains **strong** text.

> A different blockquote:
>
> > Nested blockquote for clarity.
> > With *italic* content inside.

## Horizontal Rules

---

Different content between horizontal rules.

---

## Links and References

Visit [the project wiki](https://wiki.example.com) for documentation.

See the [API reference](https://docs.example.com/api) for details.

Check the [changelog](https://example.com/changelog) for recent updates.

## Tables

| Column A  | Column B  | Column C  |
|-----------|-----------|-----------|
| Value 1   | Value 2   | Value 3   |
| Alpha     | Bravo     | Charlie   |
| **Bold**  | *Italic*  | `Code`    |
| Delta     | Echo      | Foxtrot   |

## Task Lists

- [x] Completed task
- [ ] Revised pending task
- [ ] Pending task
- [x] Newly completed task

## Mixed Content

This section combines **strong**, *italic*, `code`, and [links](https://wiki.example.com) in a single paragraph to test overlapping style rendering.

1. Ordered item with **strong** and `code`
2. Another with *italic* text
   - Nested unordered with **heavy emphasis**
   - And `inline code snippet`
3. Additional ordered item in version B

## Summary

This file serves as a markdown syntax reference variant for diff testing. Compare with `md_cheatsheet_a.md` to verify diff rendering across all change types including insert, delete, and replace hunks.
