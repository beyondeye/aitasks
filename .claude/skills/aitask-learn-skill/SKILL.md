---
name: aitask-learn-skill
description: Learn a new skill from sources — a local file, a URL, a repo file/dir, or a tmux pane (capturing the workflow an agent just ran) — and generate a complete static SKILL.md.
user-invocable: true
---

A `/learn`-style command: gather a source, understand the procedure it describes,
and author a complete **static** skill from it. Modeled on the Hermes agent
`/learn` — a standards-guided prompt (no custom tool) that emits a `SKILL.md`.

This skill is two halves: **source acquisition** (this file — different per source
type) and **generation** (the shared `generate.md` core — the same for every
source). Source acquisition is read-only; the only writes happen in `generate.md`
when the new skill is created and committed.

## Workflow

### Step 1: Resolve the source

If invoked with an argument (e.g. `/aitask-learn-skill %5`,
`/aitask-learn-skill https://github.com/org/repo/blob/main/docs/howto.md`,
`/aitask-learn-skill ./notes/deploy.md`), use the argument as the source.

If invoked with no argument, ask with `AskUserQuestion`:
- Question: "What should I learn the skill from?"
- Header: "Source"
- Options:
  - "tmux pane" (description: "A pane id like %5 — capture the workflow an agent just ran in it")
  - "Local file" (description: "A path, e.g. ./notes/deploy.md")
  - "URL or repo file/dir" (description: "A doc page, or a GitHub/GitLab/Bitbucket file or directory")

The user supplies the actual value via the "Other" free-text input.

### Step 1b: Classify the source

- **tmux pane id** — matches `^%[0-9]+$` (e.g. `%5`). *(See Step 2A.)*
- **Local file** — starts with `/`, `~`, or `./`, OR contains no `://` and exists
  as a local file.
- **Repository single file** — contains `github.com` and `/blob/`, OR `gitlab.com`
  and `/-/blob/`, OR `bitbucket.org` and `/src/` where the last path segment has a
  file extension.
- **Repository directory** — contains `github.com` and `/tree/`, OR `gitlab.com`
  and `/-/tree/`, OR `bitbucket.org` and `/src/` where the last path segment has no
  file extension.
- **Generic URL** — contains `://` but matches none of the repository patterns.

### Step 2: Acquire the content (read-only)

Produce `content` (the source text) and a short `source_label` for the commit
message, then go to **Step 3**.

#### Step 2A: tmux pane — capture with incremental deepening

A pane shows only recent scrollback, and a workflow worth learning may be longer
than the default window. Capture in a **deepening loop** — do **not** assume a fixed
depth:

1. Capture an initial chunk (1000 lines of scrollback):
   ```bash
   SHADOW_CAPTURE_LINES=1000 ./.aitask-scripts/aitask_shadow_capture.sh <pane_id>
   ```
   This is read-only — `aitask_shadow_capture.sh` never sends input to the pane.
2. Judge whether the **start** of the workflow to be learned is present, or the
   earliest captured lines begin mid-action (truncated at the top).
3. If it looks truncated, tell the user and confirm before pulling more
   (`AskUserQuestion`: "The capture may not include the start of this workflow —
   retrieve more history?"). On confirmation, re-capture with `SHADOW_CAPTURE_LINES`
   increased by **+1000** (1000 → 2000 → 3000 …).
4. Stop when: the workflow's beginning is captured; **or** scrollback is exhausted
   (a larger `SHADOW_CAPTURE_LINES` returns no additional lines — you have hit the
   top of history; say so); **or** the user says it is enough.

Set `content` to the final capture and `source_label` to `pane <pane_id>`.

> Dry-run / test: pipe a pre-captured buffer through
> `./.aitask-scripts/aitask_shadow_capture.sh -` (reads stdin, cleans it) instead of
> a live pane. A fixture whose first chunk looks truncated exercises the deepening
> loop.

#### Step 2B: Local file

Read the file directly. Set `content` to its text and `source_label` to the path.

#### Step 2C: Repository single file

```bash
source .aitask-scripts/lib/repo_fetch.sh && repo_fetch_file "URL"
```
Handles GitHub/GitLab/Bitbucket via `gh`/`glab`/`curl` with raw-URL fallback. If it
fails, fall back to `WebFetch` on the platform raw URL (GitHub:
`raw.githubusercontent.com`, no `/blob`; GitLab: `/blob/`→`/-/raw/`; Bitbucket:
`/src/`→`/raw/`). Set `source_label` to the URL.

#### Step 2D: Repository directory

```bash
source .aitask-scripts/lib/repo_fetch.sh && repo_list_md_files "URL"
```
List the markdown files and ask the user (`AskUserQuestion`) which one(s) describe
the procedure to learn; fetch each chosen file as in Step 2C and concatenate into
`content`. Only `github.com`, `gitlab.com`, `bitbucket.org` are supported.

#### Step 2E: Generic URL

Fetch with `WebFetch` (prompt: "Extract the complete text content of this page,
preserving markdown formatting, headings, and code blocks. Return the full content
without summarizing."). Set `source_label` to the URL.

### Step 3: Generate the skill

**Read and follow `generate.md`** with `content` and `source_label`. It analyzes the
material, handles multi-part selection and generalization, asks for the new skill's
name + description, writes and commits `.claude/skills/<name>/SKILL.md`, and reports
the invocation path.

## Notes

- The argument is a **source location**: a tmux pane id (`%N`), a local file path, a
  URL, or a GitHub/GitLab/Bitbucket file/directory URL.
- Source acquisition (Step 2) is strictly read-only. The pane path uses
  `aitask_shadow_capture.sh`, which is read-only by contract — it never drives the
  captured pane.
- Repository fetching uses `.aitask-scripts/lib/repo_fetch.sh` (`gh`/`glab`/`curl`
  with `WebFetch` fallback); only the three hosted platforms are supported (no
  self-hosted instances).
- Default to **static** generated skills. A profile-aware `.j2` skill drags in
  goldens + the `aitask_skill_verify.sh` template surface and is out of scope.
- Generated skills are source code: commit them with plain `git`, never `./ait git`.
