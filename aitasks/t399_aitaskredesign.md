---
priority: medium
effort: high
depends: ['398']
issue_type: feature
status: Implementing
labels: [aitask-redesign]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-16 09:20
updated_at: 2026-03-17 15:11
boardcol: now
boardidx: 100
---

It can happens that we start to implement some aitask and then we discover that the implementation direction was wrong, or perhaps we decide that the feature is not useful, and revert all or a part of its changes (see task t398). But we do not delete the task and eventually we want to reimplement it using different implementation techniques or techs, changing the design, and so on. but don't want to loose all the user "intention" that was incorporated in the original plan; althogh the actual task implementation was discarded, the user intentions, ideas, pain points that were conveid in the task description are still useful context to use when redesigning the feature. an example of this is task t259 batch reviews, that is not yet implemented, now that we have decided to create a more general infrastructure for running batch agents (see task t386), many of the specific details that were in the origianal plans in t259 must be changed. but many other higher level details not related to the infrastructure to run the batch reviews, are still relevant.

another use case for this aitask-redesign feature is brainstorming alternative designs. once an initial detailed design with child decomposition and embededded high level user intentions is created. we can use the redesign feature to brainstorm alternatives to the intial full design. the skill flow is similar.

in a classical user-driven redesign we have original aitask/aiplan design that must be adapted because explciit requirement/user input/ changed infrastructure/ changed use-case /changed tech to use etc.  in the "brainstorm mode" the exploration directions are more driven (at least initially by the code agent) but the flow is very similar.

so as possible documunted workflows for the aitask_redesign skill we should document both actual redesign and brainstorm and design the skill for both use cases. please help me design this new skill. this is a complex task that need to splitted in child task, with a child task also for documenting the new skill and its associated workflows. ask me questions if you need clarifications

note that the new redesign skill is complementary and can be coupled with the use of the aitask-revert skill (it should be documented in workflows), that is first we revert a task, partially or completely and then with run the aitask-redesign skill
