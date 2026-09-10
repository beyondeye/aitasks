# Documentation

The documentation lives in `website/content/docs/` — the Hugo/Docsy website is the single source of truth.
Make all updates there.

**Live site:** https://aitasks.io/

## Documentation Sections

This index lists the top-level pages and sections only; each section's landing page lists the pages inside it.

| Guide | Description |
|-------|-------------|
| [Overview](../website/content/docs/overview.md) | The challenge aitasks addresses, its core philosophy, and key features |
| [Getting Started](../website/content/docs/getting-started.md) | First-time setup and your first task workflow |
| [Installation](../website/content/docs/installation/_index.md) | Install aitasks and configure your development environment |
| [Concepts](../website/content/docs/concepts/_index.md) | Conceptual reference for the aitasks framework — what each building block is and why it exists |
| [TUI Applications](../website/content/docs/tuis/_index.md) | Terminal-based user interfaces for task management and code understanding |
| [Workflow Guides](../website/content/docs/workflows/_index.md) | End-to-end workflow guides for common aitasks operations |
| [Code Agent Skills](../website/content/docs/skills/_index.md) | Reference for aitasks skills across supported code agents |
| [Command Reference](../website/content/docs/commands/_index.md) | Complete CLI reference for all ait subcommands |
| [Development Guide](../website/content/docs/development/_index.md) | Architecture, internals, and release process |

This file is outside the Hugo build, so `website/check_links.py` never sees it;
`tests/test_docs_readme_links.sh` checks its inline links.
