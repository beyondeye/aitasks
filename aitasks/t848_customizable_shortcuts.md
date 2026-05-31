---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [custom_shortcuts]
children_to_implement: [t848_6, t848_7, t848_8]
created_at: 2026-05-27 15:00
updated_at: 2026-05-31 16:20
boardidx: 70
---

does make it sense to add suport for customizable shortcuts to the aitasks framework? users want to customize their working environemnt. but the operations in aitasks framework do not actually have a parallel in normal development environemnt. but customization can help attract users. need to seriously explore this. an additional prolem implementing this is that in many dialogs and tui eleements the shortcut are shown with the (P)lay, e(X)plore, etc convention. if we make the shortcut customizable, we need to remove this text, or perhapcs, create a custom string render that show a text and take a shortcut as argument and render the string with appropriate paraenthesis in the appropraite place if the defined shortcut character is inside the string. also need to make a sweep of which shortcuts are used where in order to define coherent shortcuts when a shortcut with the same of almost the same meaning is used in multiple places: the customization should change it ni all places. need to surface this shortcut definition as a custom dialog that can be opened directly from any tui, not ONLY in Settings TUI, because the user will probably want to change the shortcut from the tui where the shortcut are used, so the dialog should filter the shortcut relevant to that tui and allow to edit only them, this is a very complex task that need to split in child tasks
