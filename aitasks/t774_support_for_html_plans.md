---
priority: high
effort: high
depends: [1076]
issue_type: feature
status: Ready
labels: [aitask_pick, html_plans]
created_at: 2026-05-14 15:46
updated_at: 2026-06-25 11:05
boardidx: 180
---

currently the aitasks framework only support markdown plan files, associated to tasks. there is a growing trend to better integrate html as a format for implementation plans or exploration of the implementation space. see https://x.com/trq212/status/2052809885763747935 I want to gradually add full support for html plans files in the aitasks framework. the first step would be that a 3rd file associated to aitasks tasks. that is curently we have a task file and a markdown file associated to the task. I would like to also add an option html "plan" file. with full support for archiving/querying/ zipping old files like we currently have for markdonw plan files associated to tasks. Once this is supported we can start thinking how to integrate html plan files in exisitng workflows supported by aitasks. I think we are not going to "substitute" markdown plans with html plans. I think we are going to have them in parallel, with different and varying roles as described in the linked page on x. like the html plan containing prototypes and the markdown the authorative actual implementation plan, that translate all the information in the the html "plan" file (like multiple mockups, etc) into a single actionable plan, or referencing info contained in the html plan (again like mockups, or configurations selected by the user). One issue for all this to work, is that in "planning" mode claude and other code agent cannot write files they can only update the internal markdown plan file, so unless this changes we need to find a way to allow writing the html plan during "planning" I think that the upcoming implementation of the gates franework (task 635) that will allow multi-stage processing will be perfect to integrate this kind of workflow, with plan -> html plan with mocks/ multiple choices -> user choices and refinemeent of impl plan, etc. naturally able to integrate html plans in the task implementation workflow. this a very complex tasks, and that need be first probably explored in brainstorming mode before implementation
see also https://thariqs.github.io/html-effectiveness/
Recently claude code shipped a new feature that encapsulate working with html plan in a feature called "artifacts"
https://code.claude.com/docs/en/artifacts
This is obviously a way to take advantage of html ouput from the codeagent in more structured and use-case oriented way.
when brainstorming about the integrating of html in aitasks framework we should take a look also as how artifacts are designed in claude code.

## Coordination — t1065 unified artifact model

t1065 (`aidocs/unified_artifact_design.md`) brainstormed this integration and
**revises the planned approach** for HTML plans:

- **HTML plans become an "artifact", not a 3rd inline-committed file.** Instead of
  committing/archiving/zipping the HTML alongside the markdown plan, it flows
  through the unified artifact storage layer (pluggable backend + universal local
  cache). Archive/query/zip parity is delivered *through the storage layer*.
- **Storage policy:** the **configured remote backend is the preferred home** for
  shareable HTML plans; the **local cache is always active/mandatory** for
  open/edit/preview/offline; the zero-config `local` backend is bootstrap/dev/
  offline-only (resolves only on machines with the `aitask-data` branch; bloats it
  for large HTML). The markdown plan stays inline and authoritative.
- **Handle-only references:** the task/plan stores only a stable `art:<id>`
  handle; mutable pointer/version/backend state lives in a manifest, so backend
  migration / cache refresh never rewrite task files.
- **Planning-mode write blocker:** addressed by a proposed **artifact-producing
  gate archetype** (t635's unbuilt third gate family). The handle is preallocated
  (derivable) during planning; content is materialized post-approval; the approved
  plan body is never patched.

See `aidocs/unified_artifact_design.md` §7 (HTML-plan policy) and §8
(planning-mode-write seam).

**Implementation:** the artifact substrate is built under **t1076**
(`unified_artifact_implementation`) and its children t1076_1..t1076_4. This task
(t774) `depends: [1076]` and is the **HTML-plan consumer** that routes plans
through that substrate once it lands.
