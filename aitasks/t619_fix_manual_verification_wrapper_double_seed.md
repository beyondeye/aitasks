---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [task_workflow, aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-21 13:46
updated_at: 2026-04-21 13:48
---

`./.aitask-scripts/aitask_create_manual_verification.sh` always fails at the seed step, leaving a half-initialized task behind (task file created + committed but with an empty `## Verification Checklist` section). Observed in the wild during `/aitask-pick 617` on 2026-04-21 — the wrapper created `aitasks/t618_manual_verification_merge_pause_prompt_into_verify_question_.md` and then printed `ERROR:aitask_verification_parse.sh seed failed for <path>` with exit 1. Manual recovery: delete the empty `## Verification Checklist` header and re-run `aitask_verification_parse.sh seed`.

## Root cause

`aitask_create_manual_verification.sh:106` pre-writes the literal `## Verification Checklist` header into the description body passed via `--desc-file` to `aitask_create.sh`:

```bash
# line ~94–107
{
    printf '## Manual Verification Task\n\n'
    ...
    if [[ -n "$RELATED" ]]; then
        ...
        printf '**Related to:** t%s\n\n' "$bare_related"
    fi
    printf '## Verification Checklist\n'     # ← bug
} > "$tmp_desc"
```

The new task file is therefore created with an empty `## Verification Checklist` section already present. The subsequent call at line 154:

```bash
"$SCRIPT_DIR/aitask_verification_parse.sh" seed "$new_path" --items "$ITEMS"
```

invokes `cmd_seed` in `.aitask-scripts/aitask_verification_parse.py:254–258`, which refuses to proceed when a section is already present:

```python
if _locate_section(body) is not None:
    _die("verification checklist section already exists")
```

`seed` itself appends the header and its own surrounding blank line (python lines 272–276), so the wrapper's pre-staged header is redundant *and* fatal.

## Fix

Remove the single `printf '## Verification Checklist\n'` line from `aitask_create_manual_verification.sh:106`. The trailing blank line before it may also be dropped if it produces trailing whitespace.

After the fix:
1. The task body written by `aitask_create.sh` contains only the preamble and (optionally) the `**Related to:** t<id>` line.
2. `aitask_verification_parse.sh seed` finds no existing section, appends `## Verification Checklist` + items.
3. The wrapper's follow-up `./ait git commit -m "ait: Seed verification checklist for t<id>"` includes the items.

End state is identical to what the wrapper *intended* to produce; no callers need to change.

## Scope

- Fix: 1 line removed in `.aitask-scripts/aitask_create_manual_verification.sh`.
- Add regression test at `tests/test_create_manual_verification.sh` covering:
  - Wrapper exits 0 and prints `MANUAL_VERIFICATION_CREATED:<id>:<path>`.
  - The created task file contains one `## Verification Checklist` section followed by one `- [ ] ...` line per input bullet.
  - Running the wrapper with an empty items file still errors cleanly (the python `seed` command already handles this via `items file is empty`).
- No skill documentation changes needed — the skill instructions call the wrapper correctly; the bug is internal.

## History

Introduced in commit `aae0a65d feature: Add plan-time manual-verification task generation (t583_7)`. No tests exist in `tests/` referencing this wrapper (`grep -l aitask_create_manual_verification tests/` returns nothing), which is why the bug has been latent.

## Files to touch

- `.aitask-scripts/aitask_create_manual_verification.sh` — remove line 106.
- `tests/test_create_manual_verification.sh` — new regression test.

## Origin

Observed during `/aitask-pick 617` on 2026-04-21; the wrapper created t618 with an empty checklist and required manual recovery.
