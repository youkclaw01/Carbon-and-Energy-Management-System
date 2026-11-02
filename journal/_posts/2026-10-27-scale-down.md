---
layout: post
title: "Day 4: Twelve Became Eight, Distributed Dev Got Dropped, Diagrams Redone"
date: 2026-10-27 22:00:00 +0900
tags: [design, simplify, architecture, decisions]
summary: "I cut back a structure I'd made too big: small units, one at a time, and diagrams redrawn by the book."
---
## The short diary
The loops kept slipping, so today I changed course. I discarded the plan to spread development across sub-agents. The lead agent now works in small units, one at a time. It was a day of tearing down what I'd piled up, and weirdly it felt great.

It started with paperwork. I compared the case requirements against the background document and adopted default decisions D-01 to D-06. Boring, and necessary.

Then a design review suggested folding the 12 services into 8 consolidated units. That made sense, so I rewrote the documents as 8 unit docs. I also fixed a 10-stage design definition: requirements, overall structure, business functions, data/DB/calculation, API/events, screens/UX, security/permissions, Korea infrastructure and cost, operations/recovery, and handoff/verification/consistency. Progress gets reported against those 10 stages from now on. No more vague "going well".

For the emission calculations I acquired Korean and Japanese legal texts and the official factors. The originals stay local and never get uploaded.

I also read a loop-engineering reference repo, and then I removed the old loop content, because it didn't work. That one stung a little after yesterday, but keeping something broken around out of pride is worse.

The afternoon went to diagrams. I'd drawn my own architecture by hand: external touch points (firewall, application gateway, network management) at the top, web and WAS next in a 3-tier flow, and data and databases at the bottom, all in traffic order. I ordered a redo from scratch. The prompts have to follow the drawing-procedure Markdown, the image generation receives the sample image bytes, and versions start at v6. The diagram also has to show Container Registry, AI Foundry (model calls must use Foundry models) and "Container Apps" labelling.

## What changed
- Compared the case requirements with the background document and adopted default decisions D-01 to D-06.
- Folded 12 services into 8 consolidated units after a design review, and rewrote the docs as 8 unit docs.
- Fixed a 10-stage design definition and asked for progress to be reported against those stages.
- Acquired Korean and Japanese legal texts and official factors as the basis for emission calculations. Originals stay local.
- Dropped the distributed sub-agent development plan. The lead agent now works in small units, one at a time.
- Read a loop-engineering reference repo and removed the old loop content because it didn't work.
- Ordered a diagram redo from scratch, based on my own hand-drawn architecture, with versions from v6 onward.
- Required Container Registry, AI Foundry and "Container Apps" labelling in the diagram.
- Set placement rules: Application Gateway only in Korea and only for the web portal, and all resources only in the Korea region.

## What got better
- Slicing work into "one small result, independent check, next" shows right away where it's stuck.
- Eight units are easier to hold in my head than twelve.
- Reporting against 10 fixed stages gives me a real sense of where we are.
- The diagram now follows the way I actually think about traffic, top to bottom.

## Issues
- The image model sometimes redrew the fixed facts, like counts and placement. It's creative when I need it to be accurate.
- What I did about it: the facts stay fixed, and the model only draws. The prompts follow the drawing procedure, and the sample image bytes go to the generator.
- The old loop content was dead weight. I removed it instead of patching it again.
- Dropping the distributed plan means throwing away effort I'd already invested. That's a sunk cost, and I chose to eat it.

## What I learned
> Cutting is design too. Deleting takes guts and evidence, both.

- If a structure doesn't work, shrink it before you add to it.
- Make the picture generator draw, not decide.
- Fixed stages make progress honest.
