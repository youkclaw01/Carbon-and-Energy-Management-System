---
layout: post
title: "Day 3: Endless Loops and 13 Deliveries That Were Sent but Not Accepted"
date: 2026-10-26 22:00:00 +0900
tags: [loops, rollout, network, failure]
summary: "Tried to run write-review-revise loops on autopilot. They stalled again and again. At least the design repo got born."
---
## The short diary
Monday was a fight with automation, and automation mostly won.

The good news first: the private design repository exists now. The first pushes went in, 12 service drafts plus the review comments. Something real finally lives somewhere.

Then I tried to run the write-review-revise loop on autopilot. I ran a bounded, sequential rollout of 13 owner submissions, and it kept going for more than an hour. Every single delivery came back the same way: "delivery verified, not accepted". That wasn't a bug. I'd set semantic acceptance to false on purpose, so every delivery needs a separate review. Still, seeing thirteen of them in a row was humbling. The call succeeded. The answer wasn't necessarily right. Those are two different things.

Several runs also just died with exit code 1. One was a file-not-found while writing a temp file for the controller. Another hit a guard that says "native delivery unverified; inspect only, no resubmission". The guard is annoying and correct. It stopped the loop from blindly resubmitting something it couldn't confirm.

The reviews that did come back were "conditional". I decided a conditional verdict is not a pass, full stop. I also drafted a second candidate (R2) of the common contract between services, and eight issues blocked freezing it. So the shared contract stays open.

Between all that, I made a bigger structural call on the network: out with many role-based networks, in with a hub and spoke per region, operating through the Korea hub. Spoke subnets, firewall and application gateway sit in the hub, and the global front door sits outside the network. I also approved a database provider registration, for one provider only, and had it verified with capabilities calls in four regions.

Late in the day I asked for two things: a "knowledge" resource documenting the control-loop implementation work, and a root-cause explanation of why the handoff from correction to review kept failing. I also wanted factory access to its own page through VPN.

## What changed
- Created the private design repository and pushed 12 service drafts plus review comments.
- Ran the automated write-review-revise loop, then a bounded sequential rollout of 13 owner submissions that ran for over an hour.
- Every delivery ended "delivery verified, not accepted", with semantic acceptance deliberately false, so a separate review is required.
- Drafted the R2 candidate of the common contract. Eight issues blocked the freeze.
- Changed the network baseline to hub and spoke per region, operating through the Korea hub, with spoke subnets, firewall and application gateway in the hub and the global front door outside the network.
- Approved a database provider registration for one provider only, verified with capabilities calls in four regions.
- Asked for a "knowledge" resource documenting the control-loop work, and for a root-cause explanation of the repeated correction-to-review handoff failures.
- Wanted factory access to its own page through VPN.

## What got better
- A "conditional" review is no longer counted as a pass. The verdicts are separate now.
- The repo gives the design a home, and the review comments sit next to the drafts they're about.
- Hub and spoke per region is simpler to reason about than a pile of role-based networks.
- Scoping the provider approval to one provider means I granted exactly what I meant to grant.

## Issues
- The loop kept dying. The causes I could see were a file-not-found while writing a controller temp file, and the "native delivery unverified; inspect only, no resubmission" guard. Several runs ended with exit code 1.
- What I did about it: I decided to report every stop exactly as it is, no polishing. And I asked for a root-cause explanation of the handoff failure, because retrying harder isn't a fix.
- Eight open issues blocked the common contract. It stays unfrozen until they're resolved.
- The task ledger kept drifting away from what was really done. I don't have a clean fix yet beyond not trusting it blindly.

## What I learned
> Automation needs a brake that stops failures before it needs a gas pedal for successes.

- "Delivered" and "accepted" are different states. Name them differently.
- A guard that refuses to resubmit is doing its job, even when I'm irritated.
- Report failures as they happened. A tidy lie costs more later.
