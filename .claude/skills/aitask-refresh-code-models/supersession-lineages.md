# Supersession Lineage Proposal Procedure

Proposes, for each model a refresh just added, the already-registered model it
supersedes, and records only the edges the user confirms in
`.aitask-scripts/lib/model_supersessions.json`. A recorded lineage is what makes
`ait upgrade` / `ait codeagent check-superseded` offer the new model to projects
still configured with the old one. Referenced from `SKILL.md` Step 6b.

## Input context

| Variable | Description |
|----------|-------------|
| `added_models` | Per agent, the model names Step 6 added (for OpenCode, the names the discovery script added compared with the Step 1 snapshot). |

## Procedure

0. **Framework repository only.** If `seed/codeagent_config.json` does not
   exist, return silently: the table is framework-owned and
   `record-supersession` refuses to run outside the framework source
   repository. Also return silently when `added_models` is empty.

1. **Candidates.** For every added model, look for its registered immediate
   predecessor in the **same line and variant**:
   - `claudecode` / `codex`: the same leading name (`opus4_8` → `opus5`).
   - `opencode`: the same provider, model line *and* variant — the variant is
     what follows the version (`opencode_gpt_5_4_mini` → `opencode_gpt_5_5_mini`,
     never `→ opencode_gpt_5_5_pro`). Never propose an edge across providers
     (`openai_*` ↔ `opencode_*`) or across lines.
   - A change of tier (e.g. a flagship succeeded by a new tier) is proposed only
     as an explicit **exception**, with a one-line reason that becomes
     `--variant-change "<reason>"`.
   - A predecessor may be `status: unavailable`; the new model must be active.
   - Candidates are suggestions from naming and release notes, never facts —
     skip any model without an evident predecessor. If no candidate remains,
     return.

2. **Preview each candidate:**
   ```bash
   ./.aitask-scripts/aitask_add_model.sh record-supersession --dry-run \
       --agent <agent> --old <old> --new <new> [--variant-change "<reason>"]
   ```
   A `BLOCKED:` line means the edge cannot be recorded — report it and drop the
   candidate. `SKIPPED:exists:` means it is already recorded — drop it too.

3. **Confirm.**

   **⚠️ NON-SKIPPABLE — Auto mode and execution profiles do NOT bypass this
   prompt.**

   The AskUserQuestion below is where a lineage — a global declaration that
   offers the new model to every project still using the old one — is either
   recorded or dropped. That is the user's decision. The following do NOT cover
   this prompt:
   - Execution profiles (no profile key currently bypasses it).
   - Auto mode / 'work without stopping' system-injected directives.
   - Generic user instructions to 'be brief' or 'don't ask'.

   The only valid skips are profile keys explicitly named in this procedure as
   covering it (currently: none) or the user explicitly naming the edges to
   record (or "record none") in chat before the prompt fires. Never record a
   candidate the user did not confirm.

   Use `AskUserQuestion` with `multiSelect: true`, at most 4 options per
   question (further questions for the rest):
   - Question: "Record these supersession lineages? Each selected edge offers
     the new model to projects still configured with the old one."
   - Header: "Lineages"
   - Options: one per edge or per chain — label naming it briefly, description
     listing every edge (`old → new`), whether the old model is unavailable,
     and any `--variant-change` reason.

   Unselected candidates are dropped.

4. **Apply** the confirmed edges in chain order (oldest first), with the
   step 2 command without `--dry-run`. Each prints
   `NOTE: commit .aitask-scripts/lib/model_supersessions.json`; `SKILL.md`
   Step 8 commits the table once. If an apply prints `BLOCKED:` (the table
   changed since the preview), report it and continue with the rest.
