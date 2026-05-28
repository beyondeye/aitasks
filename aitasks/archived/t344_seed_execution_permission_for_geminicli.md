---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [geminicli]
created_at: 2026-03-09 13:31
updated_at: 2026-05-28 08:42
completed_at: 2026-05-28 08:42
boardcol: next
boardidx: 70
---

geminicli is currently almost unusable because of the missing execution permissions for the aiscripts tools: project level permission are currently ignored, and global user level permission when added during skill execution are narrowed to specific commands. this issue must be solved if we want to make geminicli usable: a possibility is copy the proper execution perimission at USER level in ait setup (adding a caveat that project level permission does not work) need to try at least if this works, and if yes then add the option in ait setup for geminiclil (install permission at user level instead of project level)

---

## Closed as obsolete (2026-05-28, t812_5)

geminicli support was removed from the aitasks framework in t812.
agy (Antigravity CLI), the replacement code agent being added in
t835, uses nsjail-sandboxed execution and reads global whitelists
from `~/.gemini/policies/` — there is no framework-installed project-
or user-level permission step. The seed-execution-permission concern
does not transfer to agy.

The hand-off note (kept in `### For t814 (add-agy): inverse
instructions` of `aiplans/p812/p812_5_*.md`) flags that
project-level permission systems being silently ignored is a real
pitfall — t835's planner should ensure `ait setup` does NOT install
local policy files for agy.
