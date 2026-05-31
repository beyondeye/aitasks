### Section Format
Wrap each major section of your output in structured section markers using HTML comments:
  Opening: `<!-- section: name [dimensions: dim1, dim2] -->`
  Closing: `<!-- /section: name -->`
Dimensions reference the dimension keys from the "Dimension Keys" block in your input (if present).
A dimension entry may be an exact key (`component_auth`) or a prefix glob (`component_*`, `assumption_*`, `tradeoff_*`) that links every key sharing that prefix. Use real keys from the Dimension Keys block (or a `prefix_*` glob) — do not invent keys that are absent from your input.
Section names must be lowercase_snake_case.
