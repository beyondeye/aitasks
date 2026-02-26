---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [codebrowser]
created_at: 2026-02-26 18:00
updated_at: 2026-02-26 18:00
---

we want to add a settings screen for the codebroswer tui. look at how settings screen is implemented in the ait board. use the same patterns and shortcut for opening the settings. the initial settings I want to add is the -model parameter for claude when running explain with claude, default model should be sonnet4.6 avaiable models should be sonnet4.6, and claude4.6 i need to add aitasks/metadata/models_claude.txt for the list of models to show in settings and that are available for example for the to the codebrowser tui. in the codebrowser tui settings we should store the selected model name with the following pattern: claude/sonnet4.6: currently we support only claude this will change in the future. chte model_claude.txt metadata should gbe also present in the seed directory and make sure that it is added to the tarball at release and also make sure that it is properly installed by ait setup when initializing aitasks framework for a repo
