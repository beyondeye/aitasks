---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [ait_settings, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-02 09:08
updated_at: 2026-03-02 09:10
---

in the new ait settings tui, there are several bug, and issues. first it is not possible to navigate options and move between tabs with arrow keys. only with tab and only partially. in the Agent defaults when selecting a type of operation and pressing enter it is possible to edit the name selected (like text edit). this is not good UX. instead i suggest a separate editbox for the codeagent name with fuzzy find that while editing show the list of possible options and the possiblity to browse with up and down arrow between currently fuzzy finded options, and a similar code agent context aware for the modle name. also instead save to layer toggle in the dialog, in the main screen we should show the separate settings for project level and user level preferences (if present) for each operation. ask me questions if you need clarifications
