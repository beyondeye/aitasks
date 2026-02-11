--- effort:med pri:hi

I would like to modify the task creation scripts to add more metadata attributes to the fornt matter of the task definition. also I would like to change the metadata format at beginning of the task to be a proper yml front matter. The attributes I want add are created_at:<date-and-time> and update_at<date-and-time> and labels:<list of labels> and issue_type. possible value for issue_type:bug/feature (for now) status:ready/done. Note that changing the front matter format require to change the code used for parsing it in aitask_ls.sh. ask me questions if you need more clarifications

---
COMPLETED: 2026-02-01 14:33
