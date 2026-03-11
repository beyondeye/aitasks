---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [opencode, verifiedstats]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-11 08:49
updated_at: 2026-03-11 15:37
boardidx: 40
---

currently in opencode there are two issues with verified state when the same llm models is available from different providers.

the first problem is a problem with model identifications: currently when using gpt5_4 (or other openai models) the codeagent+model identification procedure in task-workflow identify the model always as zen_gpt_5_4, even if this is openai.

2) verified stats are currently PER MODEL PROVIDER and PER MODEL. I am not sure that this is the correct way to accumulate stats. but again even though we are mostly interested about performance of llm model, independent of provider, yet the per-provider information CAN be useful (info on less reliable providers) so we should accumulate stats for both separately. currently the code created in task 303 does not support this.

another issue is that I don't see where verified stats data is stored the models_openscode.json is still empty even though we have already information of several runs for opencode+gpt5_4 task pick

another issue is a UX issue: in ait settings the models verified score are not easily discoverable: to improve this we could add verified information for models in the Models tab (average on all verified skills, number of verified skills), but also in the Agent Defauls tab we should more discoverability, for example showing there top 3 ranked models for each skill (if enough verified score information is available), and when selecting a skll there to change the default model in addition to showing the provider/model two stage selection allow to select from list of top ranked model for the skill)

another issue is that the performance with verified score is accumulated ALL TIMES, we don't have statistics for RECENT performace we should have additional stats for MONTH (current calendar month) and WEEK (current calendar week).

another issue is that this feature of verified score is not documented anywhere in web site, there should some more expanded documentation in ait settings, at least a reference in the skills page for the skills that support this feature (the additional step at the end where the user can vote, with a link to what a general page (that currently does not exists, to be a subpage of main skills page) that explain what verified scores are how they are accumulated the execution profile field to enable/disable them,

also currently ait stats does not print stats of verified scores, this could be useful: for each each skill the top 3 ranking all time/ last month/ last week. and also add support in plots of the same information, perhaps grouping multiple skills in a single screen (need to verifiy how to use plotext to show multiple grapsh in one page)

this is actually a collection of tasks, that should analyzed verified and decompose in multiple child tasks
