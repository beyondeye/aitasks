# Batch Task Creation Procedure

Creates a task using `aitask_create.sh` in batch mode.

## Input

| Parameter | Required | Description |
|-----------|----------|-------------|
| `mode` | yes | `parent` or `child` |
| `name` | yes | Short snake_case task name (will be sanitized by the script) |
| `description` | yes | Task description content (markdown, can be multi-line) |
| `priority` | yes | `high`, `medium`, or `low` |
| `effort` | yes | `low`, `medium`, or `high` |
| `issue_type` | yes | `bug`, `feature`, `enhancement`, `chore`, `documentation`, `performance`, `refactor`, `style`, or `test` |
| `labels` | yes | Comma-separated labels (e.g., `"ui,backend"`) |
| `parent_num` | if child | Parent task number (numeric, e.g., `10` not `t10`) |
| `no_sibling_dep` | optional | Set `true` to skip auto-dependency on previous sibling (for parallel child tasks). Default: `false` (sequential). |
| `anchor` | optional | Explicit topic-root task id (the board's group key). Accepts `N` / `N_M` (a leading `t` is stripped); validated to exist. Mutually exclusive with `followup_of`; rejected with `parent_num`. See **Topic anchoring** below. |
| `followup_of` | optional | Anchor this task to the **topic root** of source task `N` (provenance for a follow-up). Mutually exclusive with `anchor`; rejected with `parent_num`. See **Topic anchoring** below. |
| `issue_url` | optional | Issue tracker URL |
| `pull_request_url` | optional | Pull request URL |
| `contributor` | optional | Contributor name (for PR/issue imports) |
| `contributor_email` | optional | Contributor email (for PR/issue imports) |

> **Profile-driven gate declaration (auto-injected, t635_14):** When the active
> profile declares `default_gates`, the templates below auto-inject `--gates "<list>"`
> so every task created here declares those gates in its frontmatter — the single
> config point that also drives the risk producer. The registry
> (`aitasks/metadata/gates.yaml`) defines how each gate runs; the profile chooses
> which to declare. This is rendered into the command for you (no caller parameter);
> when the profile declares none, the flag is omitted.

## Output

The script prints `Created: <filepath>` on success. To extract the task ID after creation:

```bash
./ait git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
```

Parse the task number from the filename (e.g., `aitasks/t42_fix_login.md` → `42`).

## Procedure

### Passing the description

There are two ways to pass the task description:

**Mode 1 — Heredoc via stdin (recommended):** Use `--desc-file -` with a heredoc. This is a single command — no temporary file is created. The `-` means "read from stdin", and the heredoc pipes the text directly. This is the safest mode because the single-quoted delimiter (`<<'TASK_DESC'`) prevents all shell expansion — no need to escape quotes, `$`, backticks, or other special characters in the description.

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --name "task_name" \
  ... \
  --desc-file - <<'TASK_DESC'
Description content here. Can be multi-line.
Supports markdown, code blocks, special characters — no escaping needed.
TASK_DESC
```

The closing `TASK_DESC` must be on its own line with no leading whitespace.

**Mode 2 — Inline (`--desc`):** For short, single-line descriptions only. Requires careful shell quoting — any quotes, `$`, or backticks in the description must be escaped.

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --name "task_name" \
  ... \
  --desc "Short single-line description"
```

**`--desc` and `--desc-file` are mutually exclusive** — use one or the other, not both.

### Parent task creation

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --name "<name>" \
  --priority <priority> \
  --effort <effort> \
  --type <issue_type> \
  --labels "<labels>" \
{%- if profile.default_gates is defined and profile.default_gates %}
  --gates "{{ profile.default_gates | join(',') }}" \
{%- endif %}
  --desc-file - <<'TASK_DESC'
<description>
TASK_DESC
```

### Child task creation

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --parent <parent_num> \
  --name "<name>" \
  --priority <priority> \
  --effort <effort> \
  --type <issue_type> \
  --labels "<labels>" \
{%- if profile.default_gates is defined and profile.default_gates %}
  --gates "{{ profile.default_gates | join(',') }}" \
{%- endif %}
  --desc-file - <<'TASK_DESC'
<description>
TASK_DESC
```

Add `--no-sibling-dep` after `--parent <parent_num>` if `no_sibling_dep` is `true`.

### Optional flags

Append these flags before `--desc` or `--desc-file` when provided:

```bash
  --issue "<issue_url>" \
  --pull-request "<pull_request_url>" \
  --contributor "<contributor>" \
  --contributor-email "<contributor_email>" \
```

### Topic anchoring (grouping)

The optional `anchor` frontmatter field is a **topic group key**: it points at the
**root** task of a subject so loosely-related and follow-up tasks cluster together
on the board without a rigid parent-child tree. The group key is `anchor` when
set, else the task's own id — so a root and its followups share a key by simple
equality. **A root task emits no `anchor:` line.** Pass one of these (they are
**mutually exclusive**, and all three are **rejected alongside `--parent`** — a
child's anchor is always parent-derived, re-anchor afterward with
`aitask_update.sh --anchor`):

- `--anchor <id>` — set the anchor explicitly to an existing topic root.
- `--followup-of <source_id>` — derive the anchor from a source task: the
  script reads the source's anchor and sets `anchor = source.anchor` if present,
  else — for an anchorless **child** source `<p>_<c>` — its parent `<p>`, else
  the source id itself. **Anchor always points at the root and never chains:** a
  follow-up of a follow-up still resolves to the same root.

A **child created with `--parent P`** auto-inherits `anchor = P.anchor` if `P`
has one, else `P` — so a board topic-group spans the whole parent-child subtree
plus loose follow-ups as one cluster. All ids are normalized to **bare** form
(`42`, `42_1`; a leading `t` is stripped) and validated to exist (archived roots
are allowed).

## Important notes

- **Prefer `--desc-file -` with heredoc:** It avoids shell quoting issues with special characters. Use `--desc` only for short single-line descriptions. Do not use both — they are mutually exclusive.
- **`--commit` is required:** Without it, the task is created as a draft in `aitasks/new/` instead of being assigned a real ID and committed.
- **Parent number is numeric:** Use `--parent 10`, not `--parent t10`.
- **Auto sibling dependency:** When creating child tasks, the script automatically adds a dependency on the previous sibling (e.g., child 2 depends on child 1) unless `--no-sibling-dep` is passed.
- **Script path:** Always use `./.aitask-scripts/aitask_create.sh`, not just `aitask_create.sh`.
