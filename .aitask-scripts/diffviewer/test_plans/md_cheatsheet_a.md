---
Task: t000_markdown_cheatsheet_visual_test.md
Worktree: (none)
Branch: main
Base branch: main
---

# Markdown Syntax Cheatsheet

This plan demonstrates all common markdown syntax for visual testing of the diff viewer's markdown highlighting.

## Headings

### Third-Level Heading

#### Fourth-Level Heading

##### Fifth-Level Heading

###### Sixth-Level Heading

## Inline Formatting

This paragraph contains **bold text** and *italic text* and ***bold italic*** together. Here is `inline code` mixed with regular text. More **bold** at the end.

Another paragraph with *emphasis on multiple words* and **strongly emphasized words** and `config.yaml` file references.

## Unordered Lists

- First item in the list
- Second item with **bold** content
- Third item with `code` inside
  - Nested item one
  - Nested item two
- Fourth item back at top level

## Ordered Lists

1. Step one: initialize the project
2. Step two: configure the **database**
3. Step three: run `npm install`
4. Step four: verify the setup
   1. Sub-step: check logs
   2. Sub-step: run health check

## Alternative List Markers

* Star-style list item
* Another star item
* Third star item

## Code Blocks

Here is a fenced code block:

```python
def hello_world():
    """A simple greeting function."""
    message = "Hello, World!"
    print(message)
    return message
```

And another one:

```bash
#!/bin/bash
echo "Running deployment..."
git pull origin main
npm run build
```

## Blockquotes

> This is a blockquote with some important information.
> It spans multiple lines and contains **bold** text.

> Another blockquote:
>
> > Nested blockquote for emphasis.
> > With *italic* content inside.

## Horizontal Rules

---

Content between horizontal rules.

---

## Links and References

Visit [the project homepage](https://example.com) for documentation.

See the [API reference](https://docs.example.com/api) for details.

## Tables

| Column A | Column B | Column C |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
| Alpha    | Beta     | Gamma    |
| **Bold** | *Italic* | `Code`   |

## Task Lists

- [x] Completed task
- [x] Another completed task
- [ ] Pending task
- [ ] Another pending task

## Mixed Content

This section combines **bold**, *italic*, `code`, and [links](https://example.com) in a single paragraph to test overlapping style rendering.

1. Ordered item with **bold** and `code`
2. Another with *italic* text
   - Nested unordered with **strong emphasis**
   - And `inline code reference`

## Final Notes

This file serves as a comprehensive markdown syntax reference for visual testing of the diff viewer's markdown highlighting feature. Compare with `md_cheatsheet_b.md` to verify diff rendering across all change types.
