---
name: Skill Authoring Best Practices
description: Check Claude Code skill files for conciseness, structure, naming, descriptions, progressive disclosure, workflows, and common anti-patterns.
reviewtype: conventions
reviewlabels: [naming, organization, comments, complexity, dry, idioms]
environment: [aiagents]
source_url: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
similar_to: python/python_style_guide.md
---

## Review Instructions

### Conciseness and Token Efficiency
- Check that the SKILL.md body is under 500 lines; flag files exceeding this limit
- Flag explanations of concepts Claude already knows (e.g., what a PDF is, how libraries work)
- Look for narrative paragraphs that could be replaced with concise code examples or bullet points
- Verify that each paragraph justifies its token cost — remove motivational or historical context that doesn't aid execution

### Naming Conventions
- Check that the `name` frontmatter field uses only lowercase letters, numbers, and hyphens
- Check that `name` is at most 64 characters
- Flag names that are vague or overly generic (e.g., "helper", "utils", "tools", "documents")
- Flag names containing reserved words "anthropic" or "claude"
- Look for inconsistent naming patterns across a skill collection (prefer gerund form: "processing-pdfs", "analyzing-spreadsheets")

### Description Quality
- Verify the `description` field is non-empty and at most 1024 characters
- Check that the description is written in third person ("Processes Excel files…"), not first or second person
- Flag vague descriptions that lack specifics (e.g., "Helps with documents", "Processes data")
- Verify the description includes both what the skill does AND when to use it (trigger conditions)
- Check that the description contains key terms users would mention when needing this skill

### Degrees of Freedom
- Check that the level of specificity matches task fragility: fragile operations (database migrations, destructive changes) should have exact, low-freedom instructions
- Flag high-freedom instructions for operations where consistency is critical or errors are hard to reverse
- Flag overly prescriptive instructions for tasks where multiple valid approaches exist and context should guide the choice

### Progressive Disclosure and File Organization
- Verify that large skills split content into separate reference files rather than putting everything in SKILL.md
- Check that file references from SKILL.md are at most one level deep — flag chains where file A references file B which references file C
- Verify that reference files longer than 100 lines include a table of contents at the top
- Check that files are named descriptively (e.g., "form_validation_rules.md" not "doc2.md")
- Verify directories are organized by domain or feature, not generically ("reference/finance.md" not "docs/file1.md")
- Flag use of Windows-style backslash paths; all paths should use forward slashes

### Workflows and Feedback Loops
- Check that complex multi-step tasks include clear sequential workflow steps
- Look for workflows missing a validation/verification step before destructive or batch operations
- Verify that quality-critical operations include a feedback loop pattern (run validator, fix errors, repeat)
- Flag workflows that lack a checklist for Claude to track progress on multi-step tasks

### Content Quality
- Flag time-sensitive information (dates, version-specific instructions) not placed in a clearly marked "old patterns" or deprecated section
- Check for inconsistent terminology — flag when the same concept is referred to by multiple terms (e.g., mixing "API endpoint", "URL", "API route")
- Verify that examples are concrete input/output pairs, not abstract descriptions
- Flag skills that present multiple tool/library options without providing a clear default recommendation

### Executable Scripts
- Check that scripts handle error conditions explicitly rather than letting exceptions propagate to Claude
- Flag magic numbers or unexplained configuration constants — all values should have justifying comments
- Verify that required packages and dependencies are listed in the instructions
- Check that the skill makes execution intent clear: "Run script.py" (execute) vs "See script.py" (read as reference)
- Flag scripts that assume packages are installed without verifying or instructing installation
