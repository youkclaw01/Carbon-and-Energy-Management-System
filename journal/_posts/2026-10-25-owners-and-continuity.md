---
layout: post
title: "Day 2: Twelve Owners and an Agent That Picks Up Where It Left Off"
date: 2026-10-25 22:00:00 +0900
tags: [design, agents, continuity]
summary: "Split the system into 12 services with fixed owners, then checked whether an owner can resume after a break."
---
## The short diary
Day two was about people. Well, agents. Close enough.

I cut the design into 12 logical services. Each one got a fixed owner agent, and on top of that there's a separate review agent. What I wanted was simple: the same owner sees a service through design and development, and somebody else reviews it. Same identity the whole way, no handoff amnesia.

That sounds neat, but it raised an obvious worry. If an owner is supposed to stay the same, what happens when its process stops and starts again? Does it remember anything? So I gave each owner its own profile and memory space, then ran a continuity test: restart a process and ask whether the owner still remembers. It passed for the first owner and for the reviewer, including using the native memory tool in a fresh process. I'll admit I grinned at that one.

Somewhere in the middle of the day I also got a working UI draft going: a seven-screen English "Carbon & Energy" dashboard concept. Nothing fancy yet, but it gives the design something to point at.

Then I asked the uncomfortable question: can we actually deploy everything this design needs in the target subscription? I asked for a feasibility checklist. Better to find out now than after twelve services of beautiful drawings.

I also made a call about workload. I wanted the sub-agents doing the detailed design and uploading it to GitHub, with every agent writing design docs using harness-based loop engineering. I did not want the main assistant grinding through all the detail alone. And I wanted every agent to log progress, failures and execution details in a management ledger, with a project manager re-checking it.

## What changed
- Split the design into 12 logical services, each with a fixed owner agent, plus an independent review agent.
- Gave every owner its own profile and memory space, so each keeps the same identity through design and development.
- Ran the restart test. It passed for the first owner and for the reviewer, including native memory tool use in a fresh process.
- Picked the seven-screen English "Carbon & Energy" dashboard concept as the working UI draft.
- Set one rule in stone: passing development checks is not deployment authorization.
- Asked for a feasibility checklist covering whether all needed resources can be deployed in the target subscription.
- Asked sub-agents to produce the detailed design and upload it to GitHub, and asked every agent to write design docs using harness-based loop engineering.
- Asked every agent to log progress, failures and execution details in a management ledger, with a project manager re-checking it.
- Authorised the assistant to pick the recommended option on development decisions that would otherwise wait on my judgement.

## What got better
- Keeping authors and reviewers apart killed the "I checked it myself, so it's fine" feeling.
- Owners now survive a restart with their memory intact, so I'm not re-explaining the same context every session.
- The "checks passed" versus "approved to deploy" line is explicit. Green checks are good news, not permission.
- Letting the assistant take the recommended option on routine decisions means I'm not the bottleneck for every small fork.

## Issues
- More owners meant more missing progress notes. Twelve services, twelve chances for someone to quietly forget to write down what they did.
- What I did about it: every owner now has to log its own work in the ledger, and a project manager re-checks the entries. I'm not trusting memory when a ledger exists.
- The continuity test only covered the first owner and the reviewer so far. That's a good sign, not a full proof, and I'm not going to pretend otherwise.
- The deployment feasibility question is still a question. I asked for the checklist, and the answer comes later.

## What I learned
> More people doesn't make things faster. The paperwork falls apart first.

- Test continuity on purpose. Restart something and see what survives.
- Separate the person who writes from the person who checks.
- If a rule matters, like "checks passing is not a deploy approval", say it out loud and write it down.
