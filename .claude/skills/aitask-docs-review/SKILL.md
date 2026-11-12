---
name: aitask-docs-review
description: Review documentation pages or page drafts against the project's configured doc-update guide — reader-level check, prose check, and a fresh-reader test for beginner-level pages — and report what a reader would stumble on.
---

## Purpose

This skill holds the **procedure** for reviewing documentation pages. The
**rules** it applies live in the project's configured doc-update guide, and this
skill copies none of them: it reads the guide on every run and applies what it
finds there. A project changes its rules by editing its guide, never this file.

For each page the review answers three questions:

- **Level:** does the page fit the reader level it declares?
- **Prose:** does the page follow the guide's writing rules?
- **Fresh reader:** can a reader at the beginner level answer their own
  questions from the page alone? This test runs only on beginner-level pages.

Callers:

- the `docs_updated` gate (`.claude/skills/aitask-gate-docs-updated/SKILL.md`,
  step 3b), which passes the drafts it is about to apply;
- an audit of existing pages;
- a person, ad hoc, on any page.

## Invocation

```
/aitask-docs-review <path>... [--budget <n>] [--caller gate|adhoc|audit]
```

- `<path>` — one or more pages. From the gate these are `.draft` files under
  `.aitask-gates/<task-id>/docs_updated_<run-id>_drafts/`, each next to an
  optional `.base` (the page as it was when drafting began). Ad hoc or in an
  audit they are live page paths.
- `--budget <n>` — how many fresh-reader tests this call may run. The gate
  passes what is left of its run's budget. Default `3`.
- `--caller` — default `adhoc`. With `gate` the review may revise the `.draft`
  files it was given (see "Procedure invariants"). With `adhoc` or `audit` it
  reports only, and edits a live page only when the person asks for it.

The review never extends its own budget. Running more tests than the budget
allows is the caller's decision, made with the user.

## Procedure invariants

These belong to the procedure, not to the guide, so they hold in every project:

- **Rewrite prose only.** Never change code blocks, inline code, commands,
  paths, URLs, frontmatter or link targets. Removing a whole clause that
  contains one of them is a cut, not an edit of it: the next rule applies.
- **Add no facts, names or numbers.** If a sentence needs a fact the page does
  not state, ask, or write a simpler sentence that needs no new fact.
- **A fact cut from a page moves; it is never deleted.** Find the page that owns
  it (the guide says which page owns which kind of detail). With `--caller gate`,
  put the fact on that page in the same drafts directory:
  - **The owning page already has a `.draft` there:** add the fact to that
    `.draft`, and leave its `.base` exactly as it is. Never re-copy the live
    page over an existing `.base`, and never rebuild the draft from the live
    page: the first hides any edit another session made since drafting began
    (the gate's apply check would then pass and overwrite it); the second
    throws away the changes already proposed for that page.
  - **It has no draft yet:** if the page exists, **first** copy it to
    `<page path>.base`, then write `<page path>.draft` from that copy. If it
    does not exist, write only the `.draft`.

  Either way the owning page's draft has changed, so it is reviewed (Step 3 and,
  within the budget, Step 4) in this same call before the report; list it in the
  report as a changed or added page. Otherwise (`adhoc`, `audit`), report the cut
  and where the fact should go. If no owning page can be found, keep the fact and
  report it as unresolved.
- **A fact found to be wrong** is corrected, or dropped with the reason in the
  report.

## Workflow

### Step 1: Resolve and read the guide

From the repository root:

```bash
./.aitask-scripts/aitask_resolve_config_path.sh doc_update.guide \
  aitasks/metadata/doc_update_guide.md
```

The command prints one line: the guide's path, or an empty line when no guide is
configured or the helper could not run. Read the whole guide. An empty line means
there is no guide: take the no-level-model path (Step 6), and say in the report
that no guide was found.

### Step 2: Detect the level model

The guide has a level model when it has a `## Reader levels` heading whose list
declares all three of:

- `Level field:` — the frontmatter field that holds a page's level;
- `Beginner level:` — the level value for readers new to the project;
- `Personas:` — one sentence per level value, describing that reader.

That heading and those three labels are the only parts of the guide this skill
reads by name. Everything else in the guide is rule text, applied as written.

If any of the three is missing, there is no level model: go to Step 6.

### Step 3: Level and prose check, one page at a time

One pass per page, in this conversation, with no sub-agent.

1. Read the page's level from its frontmatter, under the declared level field.
   Accept both forms, `field: value` and `field: [value]`. When no sub-agent is
   available and the page is at the beginner level, write its Step 4 questions
   now, before reading the body (Step 4, item 6).
2. **No level set:** record a level finding saying the field is required, and set
   `reader=not-run(untagged)` for the page. Still run the prose check.
3. **Level check:** compare the page with the guide's contract for its level and
   with the guide's rules for its page type.
4. **Prose check:** compare the page with the guide's prose rules and writing
   conventions.
5. With `--caller gate`, fix each finding you can fix within the procedure
   invariants, in the `.draft` itself, and list every change. A finding you
   cannot fix that way is **unresolved**: it goes in the report for the user to
   decide on.

### Step 4: Fresh-reader test, beginner-level pages only

The test checks whether a reader new to the project can use the page. A
reviewer who has seen only the page answers the questions such a reader would
ask, and then reports what it had to guess. (The method follows the reader
testing in anthropics/skills `doc-coauthoring`; the procedure here is our own.)

1. **Candidates** are the pages at the declared beginner level. Pages at another
   level get `reader=not-run(not-beginner)`.
2. **Order** the candidates by most changed body lines first: lines added plus
   lines removed between the `.base` and the `.draft`, counting only below the
   frontmatter. A page with no `.base` (a new page), or a live page, counts all
   of its body lines.
3. **Budget:** take candidates in that order while budget is left. Each test,
   sub-agent or self-review, uses 1. Every candidate left over gets
   `reader=not-run(cap)` and is listed in the report.
4. **Questions:** each tested page gets 5 to 10 questions that a reader at the
   beginner level would bring to it. They ask what a newcomer wants from the
   subject (what it is, why they would want it, how to start, what happens in
   the common situations), never what the page's own sections happen to cover.
   So they must come from a context that has **not seen the page body**: by this
   step Step 3 has read it, and a caller that drafted the page wrote it.
   Questions that mirror the body make whatever the body explains look needed,
   which hides the "details not needed" signal the test exists to measure. The
   reader sub-agent writes them (item 5). When the page is tested again after an
   edit, reuse the first test's questions, so the two reports can be compared.
5. **Sub-agent:** start a sub-agent. Its first prompt carries only:
   - the page's title and its `description`;
   - the beginner level's persona sentence from the guide, as "you are this
     reader";
   - a request for the 5 to 10 questions it would bring to such a page.

   On a re-test, give it the earlier questions instead of asking. Record the
   questions. Then, in the same conversation, give it:
   - the page text, inline;
   - the instruction to answer those questions from the page text alone, and
     not to open files, search or browse.

   Collect its answers. Then ask it, in the same conversation:
   - what was ambiguous;
   - what it assumed the reader already knew;
   - every term it had to guess the meaning of;
   - every detail it did not need to answer the questions, leaving out the
     page's frontmatter and its navigation (lists of links to related pages, a
     link to the next page), which are not content the reader is asked to use;
   - anything that contradicts something else on the page.

   Compare its answers with the page: a wrong answer, or an answer it had to
   guess, is a finding. Record `reader=subagent`.
6. **No sub-agents available:** write the questions yourself from the title,
   `description` and persona before Step 3 reads the page body (see Step 3,
   item 1). If you saw the body before this review began, for example because
   you drafted it, say so in the reader report: the questions may mirror the
   page. Then answer them yourself as that reader, from the page text alone, and
   go through the same five follow-up questions as a checklist. Record
   `reader=self-review`.
7. A reader finding is **reported, not fixed** by this step: it goes in the
   reader report and, unless a Step 3 fix already covers it, in the unresolved
   list.

### Step 5: Report

One block per page, then one footer for the call:

```
PAGE: <path>
level=<ok|findings:N|not-run(no-level-model)>  prose=<ok|findings:N>  reader=<value>
Level findings: <list, or none>
Prose findings: <list, or none>
Changes made: <list of edits to the draft, and pages added for moved facts, or none>
Reader report: guessed terms <…>; details not needed <…>; ambiguities <…>; contradictions <…>
Unresolved: <N> — <list, or none>

BUDGET_USED:<n> BUDGET_LEFT:<m> NOT_RUN_CAP:<paths, or none>
```

`reader=` takes exactly one of these six values per page:

| Value | Meaning |
|-------|---------|
| `subagent` | A sub-agent ran the fresh-reader test. |
| `self-review` | No sub-agent was available; the self-review checklist ran instead. |
| `not-run(not-beginner)` | The page is not at the beginner level. |
| `not-run(untagged)` | The page sets no level (also reported as a level finding). |
| `not-run(cap)` | A beginner-level page left over once the budget was spent. |
| `not-run(no-level-model)` | The guide has no level model (Step 6). |

### Step 6: No level model

When the guide has no level model, or no guide was found:

- run the prose check of Step 3 against whatever writing conventions the guide
  has (none, when no guide was found);
- skip the level check and the fresh-reader test for every page:
  `level=not-run(no-level-model)` and `reader=not-run(no-level-model)`;
- use no budget: `BUDGET_USED:0`;
- say at the top of the report that the project's guide has no level model, so
  pages were checked for prose only.

## MUST NOT

- Copy rule text from the guide into this skill, the report's headings, or any
  other procedure file. Quote a rule only when explaining a finding.
- Read any part of the guide by name other than the `## Reader levels` heading
  and its three labels.
- Give the fresh reader a path instead of the page text, or let it read files.
- Change anything outside prose, or add a fact, name or number.
- Delete a fact instead of moving it.
- Run more fresh-reader tests than the budget passed in.
- Edit a live page with `--caller adhoc` or `audit` unless the person asks.

## Notes

- The `docs_updated` gate runs this skill on its drafts before it asks the user
  to confirm, so the reader report is about the exact text that will be applied.
- Codex CLI and OpenCode wrappers for this skill do not exist yet.
