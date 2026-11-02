---
layout: post
title: "Day 5: The Korea Region Went Up and the First Screen Lit"
date: 2026-10-28 22:00:00 +0900
tags: [deploy, azure, web, decisions]
summary: "Korea region build and a first web screen in a single day. Moving fast meant plenty of undoing."
---
## The short diary
Design was settled, so today I gave the go-ahead to build. First stop was the decision ledger, D-21 to D-36. Then the Korea deployment ran in phases 0 to 5 with scripts, and I kept the evidence for each phase.

Before the build I was still polishing the diagram. Version 9 took several rounds. The Jump VM card text came out garbled, the management panel lost its title, and the virtual WAN hub title overlapped something else. I also showed zones 1 to 3 as columns to make zone redundancy obvious. Each fix felt small, but together they ate real time.

The deploy itself went in stages. Network security groups and resource groups succeeded. Then domain, certificate and application gateway got wired together, and around 08:15 UTC the portal answered HTTP 200 with a healthy backend. That's a very satisfying number to see.

The web side moved faster than I expected. v0.1, a seven-menu draft, was up at 07:13 UTC. By 11:20 UTC it was v1.0, with a data generator, region zoom, forecast and an AI review workflow.

Then came the corrections, a lot of them. I'd say the screen and I had a long conversation. Japan and Korea were placed wrong on the map. I wanted the five Korean factories as dots with names, and callouts with lines. A "0.00" error showed up. The legend disappeared. Text was too large. I wanted click-through flows, card to factory table to forecast. The "needs review" list should expand inline with animation. The selected region should have a blinking dot. The green bar meant nothing to me. The interface should reach into the empty space at the bottom. And I ran repeated bug sweeps.

I also told my agent I expect the numbers to change in real time once real data arrives, and I wanted target-versus-estimate headroom and percentage shown. Last request of the day: a work-journal web page with a diary-style summary, changes, improvements, issues and lessons. Hi, that's this.

## What changed
- Adopted decision ledger items D-21 to D-36, for example a /24 rule for subnets.
- Set delete locks off while building and on after completion.
- Used a shared apps resource group for the registry.
- Created new key vaults with purge protection disabled until setup completes, then enabled.
- Ran diagram v9 rounds: fixed the garbled Jump VM card text, the missing management panel title and the overlapping virtual WAN hub title, and drew zones 1 to 3 as columns for zone redundancy.
- Ran the Korea deployment in phases 0 to 5 with scripts and kept evidence. Network security groups and resource groups succeeded.
- Wired domain, certificate and application gateway. The portal answered HTTP 200 with a healthy backend at about 08:15 UTC.
- Took the web from v0.1 (07:13 UTC) to v1.0 (11:20 UTC): data generator, region zoom, forecast and an AI review workflow.
- Added click-through flows, inline-expanding "needs review" list, blinking dot for the selected region, and target-versus-estimate headroom with a percentage.

## What got better
- Evidence from every deploy phase means I can say what happened, not what I think happened.
- Scanners for overlap and alignment now catch crooked layouts before my eyes do.
- Click-through flows let me follow a number from a card down to a factory and then to its forecast.
- The map reads better with five named Korean factory dots and callout lines.

## Issues
- I had to point out the same kinds of things again and again: empty space, a "0.00" error, a vanished legend, oversized text. The fix was repeated bug sweeps.
- Moving fast meant plenty of undoing. Several layouts got redone after I looked at them.
- The VM needed to come back on its own after the nightly shutdown. That one is still pending as of tonight.
- The diagram's garbled text and overlapping titles needed a whole round of v9 fixes before it was usable.

## What I learned
> Quality comes from the **loop of looking at the screen**, not from how fast you build.

- Keep evidence for every deploy phase, even the boring ones.
- Build a scanner for the mistakes you keep making by eye.
- Real numbers will move, so build the screen expecting that.
