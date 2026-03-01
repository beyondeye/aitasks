---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [modelwrapper]
children_to_implement: [t268_5, t268_6, t268_7, t268_8]
created_at: 2026-02-27 08:06
updated_at: 2026-03-01 15:23
boardcol: now
boardidx: 10
---

we are currently in several TUIs open claude code by calling it directly. in some upcoming features we are also going to run claude in batch mode. calling it directly is a problem because we want in the near future integrate with opencode/geminicli/codexcli. there is also the issue of llm model selection: all llmclis support model selection as start option and there are use cases for thet for example in t259 batch reviews. we currenlty don't have infrastructure for model configuration for different operations and operations (task pick in ait board, or claude explain in codebrowser tui, or in the future configuration of which llmcli to run for batched reviews in t260. we have started thinking on how to address this issue in t265 and t266, but since this issue is common to many components in this task we want to define properly the architecture and the infrastructure for it

there are several required components required: one is a wrapper bash script aitask_codeagent.sh for wrapping calls to claude code gemini cli opencode and so on. and also a standard for passing to this a wrapper a parameter to will define the spefic tool and agent we want to use. my idea is to define a single string format for this, that for example "gemini/geminipro3" will use geminicli with gemini3pro, "claude/sonnet4.6" will use claude code with model sonnet4.6

also there should be a list of supported models for each tui tool and for each operation that the tui support in aitasks tui , codebrowsertui and so on. thess should be defined in aitasks/metadata directory like other existing confiugration file. there should be a list of all "available" models installed from seed that is used by aitask_codeagent.sh to actually route to different agentclis according to the model confiugration unified string as defined above. there should be also a confiugraiton file for project defaualt of whitch model/cli to use for each supported codeagent operation supported by the various tuis tools. and separately for each tui tool in the json settings file (like board_config.json) the actual user configuation user customize to use for each operation.

by the way there is an issue with board_config.json: it currently in aitasks/metadata so it is a "PER_PROJECT" configuation not a "PER-USER" configuration, with should add an addition board_config.json PER-USER (and similarly for other TUI) and the actual configuration for the specific user will the per project config as default config and additional per user config with overrides) the peruser  config must be store in some place taht is gitignored.

affter this refactoring we need also to add proper documentation of tui configurations: per project and per user, and aiagent configurations. ask me questons if you need clarifications

Now that I think about it is better to encapsulate about the information about available models, inside the bash script aitask_codeagent, with a command line parameter for returning the list of available agents/model combinations instead of storing this information in a different place.
in any case the agent need to be able to handle to full of possible agent/model combination and it needs to translate our local naming convention to the naming convention needed when calling in practive codexli, claude code, or gemini cli with a -model parameter
