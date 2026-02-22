---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [macos, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-22 18:41
updated_at: 2026-02-22 18:43
---

in several places in the aitasks framework claude skills or bash script we use sed. the version of sed installed by default on macos is not gnu sed (currently 4.9) that is expected by the aitasks framework. need to decide if to add another dependecy in ait setup to install gsed, or check all current usage of sed and make sure they are compatible with macos (extract all usage and check them on this pc). if we opt to use gnu sed, in addition to installing the dep via brew like we do for bash and python we need to check how to avoid the need to adapt the script to call gsed instead of sed
