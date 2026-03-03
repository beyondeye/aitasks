---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [ait_settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-03 00:41
updated_at: 2026-03-03 10:00
---

we want to document the new ait settings tui (see task t291) but that there some ait settings features that has not been yet properly reviewed, like that export/import feature (export does not ask where to store data, nor which subset of data to export, import does not have a file selector for choosing file to import, also settings are not currently identified by any file extension or any other characteristics that will make the import file browser being ablt to select those specific files. also i don't know if the import feature is enough hardened, protected against mismatch in the read json and what is required. Finally in Agent defaults tab I don't know that is the raw opration actually for, need to clarifiy this and if this should gbe removed from settings? or it still make sense?
