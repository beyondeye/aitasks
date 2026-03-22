---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ait_settings, execution_profiles]
created_at: 2026-03-22 09:23
updated_at: 2026-03-22 09:23
---

add in ait settings option to set default execution profiles foe each skill that support execution profiles, define a common procedure to be used by skill to determine execution profile (if such procedure does not exist yet) that also check if default exeution profile is defined for the skill, also add additional optional parameter for all skill that allow to override exeution profile by passing the name of the profile to use, (only the name without prefix). this is  complex task that should be split into child tasks. also need to update all skill documentation about option for default execution profile and update ait settings docs on how default execution profiles are set, and how default execution profile can be overriden
