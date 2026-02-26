---
priority: medium
effort: high
depends: ['191']
issue_type: feature
status: Ready
labels: [aitask_explain, codebrowser]
children_to_implement: [t195_10, t195_11]
created_at: 2026-02-22 11:19
updated_at: 2026-02-26 11:52
boardcol: now
boardidx: 20
---

currently with have single TUI, the ait board tui to view and organize tasks. it would be nice to have an additional TUI, to review the code in the project, possibly with code syntax lighting support, that in parallel show the source of changes as they can be extracted with the aitask_explain_extract_raw_data.sh and aitask_explain_process_raw_data.py (see also aitask_explain skill). the ide is to heve on the left the file tree for the project, that can collapsed/expanded and single files can be selected. when selected in the right side we open the source with line numbering on the left and on the right highlight of code ranges the tasks that originated this changes. the python script should autogenerate explain data as the user browse the project source tree. the generated explain data should be stored in separate aiexplain/codebrowser directory and organized in a way that replicate the project file structure. create an explain run for each directory in the source repo (not including the files in the subdirectory) name the run directory with the explain data with the directory path from source route with path slashes substituted with "__". also add at the end of the run the datetime when the run was generated. so that we can show this is information in the codebrowser and ask for refresh it. in the code browser should integrate with the claude code skill aitask_explain skill: the user in the board can click in the source code or select a line run with shift + arrows (show a cursor in the code window that the user can move with up/down arrows). then the user can use a shortcut to start claude code with a call to the claude code explain skill, with proper parameter according to selected file and range, and with the explain run data already created by the codebrowser for the code directory where the file is in . this is a very complex task and must be subdivided in child tasks before any implementaiton
