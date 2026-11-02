---
layout: post
title: "Day 1: I Built the Worker Before the Work"
date: 2026-10-24 22:00:00 +0900
tags: [start, setup, approvals]
summary: "No code today. I set up a design-only agent and sorted out memory and approval rules first."
---
## The short diary
I didn't write a single line of code today. Not one. And honestly? It was a good day.

The plan for this case study is simple on paper: a carbon and energy cost operations system for a steel and chemicals group in APAC, all on mock data. I'm doing it with an AI agent as my collaborator, design first. But before any design happens, I wanted to know who exactly I'm working with and what that someone is allowed to touch.

So the whole day went into building the worker before the work. I set up a dedicated agent with its own workspace, its own memory rules and its own approval boundaries. It's independent from everything else I do, so nothing gets mixed up. Rule number one, which I wrote down early so I couldn't talk myself out of it: design only. Building, deploying, or touching anything in the cloud needs my explicit go-ahead.

Then came the fun part, which was telling it what I actually wanted out of the design. I asked for a proposed infrastructure architecture diagram, all planning and design content as Markdown, slide documents that explain each area, and the whole design organised into numbered areas. That's a lot of paper for a day with zero code. Still, it felt like laying out tools on the bench before starting.

By the end of the day I had rules, boundaries and a clear picture of how the rest of the week should go. It looks like an empty day from the outside. It wasn't.

## What changed
- Set up an isolated workspace and a dedicated agent, hooked into VS Code, the platform I normally develop on.
- Wrote the main rule down: the agent designs only, and anything that builds, deploys or changes the cloud waits for my explicit yes.
- Defined what I want delivered: a proposed infrastructure architecture diagram, planning and design content as Markdown, slide documents for each area, and a design organised into numbered areas.
- Split the control logic three ways: approval, policy and limits; restricted execution; cross-border export control.
- Chose private endpoints as the broad default, so private networking is the starting point rather than an afterthought.
- Planned containerised microservices on Container Apps, coming after the infrastructure.
- Picked harness-based loop engineering as the default development method.
- Agreed on the medallion data architecture, with one clear decision: we do NOT copy all the Gold data centrally.
- Decided that services pass data to each other through APIs or events.
- Gave memory clear jobs: Git and files are the source of truth for the system and its sources, and a conversational memory service only handles chat memory.
- Approved an independent verifier that checks real operation and looks for errors and regressions, plus a development harness that keeps concrete evidence.
- Decided that the development agents are separate from the product's own business AI.

## What got better
- What my agent may and may not do is written down now. Nothing can sneak past what I allowed, including by accident.
- Memory has a clear split, so I won't wonder later whether the truth lives in a file or in a chat.
- Keeping the development agents apart from the product's business AI means I won't confuse the helper with the thing being built.
- Evidence will be kept as we go, because I approved the harness and the verifier before there was anything to verify. Much easier than bolting it on later.

## Issues
- I tried to wire up several memory services at the same time. Bad idea. The setup got heavy fast, and I spent time on plumbing instead of design.
- What I did about it: I parked the heavy memory-service integration and went chat channel first, with VS Code as the starting point. Everything else can wait until it earns a spot.
- A smaller one: a day with no code is hard to measure. There's nothing to run and no screen to look at. I had to accept that the output today is decisions, not features.

## What I learned
> Sorting out the setup first makes a day look empty, but it makes every day after it faster.

- Write the approval boundary before the agent has anything to approve.
- Give every kind of memory one job, and don't let two systems claim the same truth.
- Parking something isn't failing. It's just not today's problem.
