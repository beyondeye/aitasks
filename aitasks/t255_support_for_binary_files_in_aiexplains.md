---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts, aitask_explain]
created_at: 2026-02-26 09:19
updated_at: 2026-02-26 09:19
---

the script used to extract aiexplain data: aitask_explain_extract_raw_data.sh and aitask_explain_process_raw_data.py currently process also BINARY files as if they where code files. this is wrong: see for example extracted data here /home/ddt/Work/aitasks/aiexplains/codebrowser/imgs__20260226_091100 here.NOTE DON'T ACTUALLY FULLY READ THE DATA THIS ARE HUGE FILES. need to redesign how binary files are handled for the aiexplains feature, both the format of the reference.yaml that will be output, also how the preprocessing script detect binary data and process it and also how the aitask_explain skill handle this cases. this is a complex task that must be decomposed in child tasks
