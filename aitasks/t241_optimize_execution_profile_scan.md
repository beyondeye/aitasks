---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [aitask_pick, bash_scripts, skill_optiomizations, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 08:51
updated_at: 2026-02-25 09:20
---

we use execution profiles across multiple skill (for example aitask-pick) to reduce back-and-forth questions with the user and speed up development, I have just noticed that execution profiles handling itself is now slowing up skills. for identifying the available execution profiles, at the beginning of the skills that support there is useless overhead: see for example the log of operation at the beginning of aitask-pick:

the llm first list all avaiable execution profiles, then READ EACH OF THEM, this only for being able to present the user with the question Select an execution profile (pre-configured answers to reduce prompts):

I would like to optimize this with a helper bash script called aitask_pick_scan_execution_profiles, that directly return a list of avaiable profiles that we can skip all this llm operations and actually read in the llm context only the chosen execution profile. check for all skill that use execution profiles and rewrite the step for choosing the execution profile in this new way

skill that will probably benefit from this optimization: - .claude/skills/aitask-pick/SKILL.md (1 ref: --sync)                                                                                                                                                                                     
- .claude/skills/task-workflow/SKILL.md                                                                                                                                                              
- .claude/skills/aitask-pickrem/SKILL.md                                                                                                                                                                        
- .claude/skills/aitask-pickweb/SKILL.md                                                                                                                                                                   
- .claude/skills/aitask-explore/SKILL.md                                                                                                                                                                                  
- .claude/skills/aitask-fold/SKILL.md                                                                                                                                                                                   
- .claude/skills/aitask-review/SKILL.md 
probably more
