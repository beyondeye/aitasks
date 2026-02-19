---
name: HTML CSS Style Guide
description: Check HTML and CSS code for Google style guide compliance including semantics, formatting, and selector usage
reviewtype: style
reviewlabels: [naming, formatting, organization]
environment: [html-css]
source_url: https://github.com/gemini-cli-extensions/conductor/tree/main/templates/code_styleguides
---

## Review Instructions

### HTML General
- Check that HTTPS is used for all embedded resources
- Verify that indentation uses 2 spaces (no tabs)
- Check that all HTML element names and attributes are lowercase
- Flag trailing whitespace
- Verify that UTF-8 encoding is specified with `<meta charset="utf-8">`
- Check that `<!doctype html>` is used

### HTML Semantics
- Verify that HTML elements are used according to their intended purpose (e.g., `<p>` for paragraphs, `<a>` for links)
- Check that images have `alt` attributes
- Check that audio/video elements have transcripts or captions
- Flag inline styles and scripts (separate concerns into external files)
- Flag `type` attributes on `<link>` and `<script>` elements (should be omitted)

### HTML Formatting
- Verify that block, list, and table elements start on new lines with indented children
- Check that double quotation marks are used for attribute values

### CSS Selectors and Naming
- Flag ID selectors used for styling (prefer class selectors)
- Check that class names are meaningful and descriptive, not presentational (e.g., `.video-player` not `.red-text`)
- Verify that class names use hyphen-separated words (`.site-navigation`)
- Flag use of `!important`

### CSS Values
- Check that shorthand properties are used where possible (`padding`, `font`, `margin`)
- Verify that units are omitted for `0` values (`margin: 0;` not `margin: 0px;`)
- Check that leading `0`s are included for decimal values (`0.8em` not `.8em`)
- Verify that 3-character hex notation is used where possible (`#fff` not `#ffffff`)

### CSS Formatting
- Check that declarations within a rule are alphabetically ordered
- Verify that a semicolon follows every declaration
- Check that a space follows property name colons (`font-weight: bold;`)
- Verify that each selector and declaration starts on its own line
- Check that single quotes are used for attribute selectors and property values
