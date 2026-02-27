---
priority: medium
effort: medium
depends: [268]
issue_type: feature
status: Ready
labels: [aitask_pick, aitask_board, model_selection]
created_at: 2026-02-26 18:13
updated_at: 2026-02-26 18:13
---

we are going to add support for model selection for task pick in ait board. this work is related to work in task t265. the model selection will be a global settings in tui board for the default llm model to run if not explicitly specified in task definition. then when running pick command in ait board run claude with model configuration as defined in settings. this model configuration will be stored in board settings, in the format <provider>/<model> for example claude/sonnet4.6. the list of all available models for each privider will be stored aitasks/metadata/models_claude.txt one model per line. also in the models_claude.txt the model names will be stored in the format <provider>/<model>
