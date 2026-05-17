---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [claudeskills]
created_at: 2026-05-17 10:48
updated_at: 2026-05-17 10:48
boardidx: 60
---

Claude Code recently changed billing so `claude -p "<prompt>"` (headless/print mode) is charged at a higher rate than interactive invocations. Audit confirmed the aitasks framework already has a small footprint here — only two active call sites — but we should eliminate both and add a guard convention to prevent regressions.

## Confirmed call sites (verified by grep)

1. **`.aitask-scripts/aitask_codeagent.sh:547`** — the `batch-review` operation appends `--print` when `PARSED_AGENT=claudecode`:
   ```bash
   batch-review)
       CMD+=("--print" "${args[@]}")
       ;;
   ```
   Other operations in the same case (`pick`, `explain`, `qa`, `explore`, `raw`) all invoke `claude` interactively — no `--print`. The Gemini / Codex / OpenCode branches also do not use `--print`. So this is the only runtime headless call across the entire framework.

   **Proposed change:** Drop `--print` so `batch-review` runs in normal interactive mode like the other operations. If a non-interactive variant is genuinely needed (e.g., for CI), expose it as an explicit opt-in flag (`--headless`) rather than the default.

2. **`aidocs/extract_claudecode_tools.sh:23`** — manual one-shot script that regenerates `aidocs/claudecode_tools.md` using `claude -p` with a static heredoc prompt. Not part of any automation, hot path, or test.

   **Proposed change:** Convert to interactive invocation (paste-and-go), or replace with a documented "run this prompt interactively then save the output" recipe. Either way, the file should no longer shell out to `claude -p`.

## Guard convention

3. Add a short note under **Shell Conventions** in `CLAUDE.md` discouraging new `claude -p` (and `claude --print`) usage in scripts and skills, with rationale (Claude Code billing surcharge on headless print mode) and pointing to interactive mode as the default. Mention that this applies to skill `.md` files too (no current offenders, but worth pre-empting).

## Out of scope

- No skill files (`.claude/skills/`, `.opencode/`, `.gemini/`, `.agents/`, `seed/`) instruct any agent to call `claude -p` today — verified by grep. No changes needed there.
- No wrapper helpers (`claude_oneshot`, `claudecode_run_oneshot`, etc.) exist.
- Indirect `--print` usage is limited to dpkg flags in `aitask_setup.sh` (`dpkg --print-architecture`) — unrelated, ignore.
- Cost optimization of *interactive* claude calls (e.g., picking a cheaper model by default for read-only operations) is a separate concern — out of scope for this task.

## Acceptance

- `grep -rn 'claude -p\|claude --print' . --include='*.sh' --include='*.py' --include='*.md'` (excluding `archived/` and `.aitask-crews/`) returns zero matches.
- `aitask_codeagent.sh batch-review claudecode/<model> <args>` continues to work; if a non-interactive variant is preserved, it is gated behind an explicit flag.
- `CLAUDE.md` Shell Conventions section has a one-paragraph guard against new `claude -p` usage.
