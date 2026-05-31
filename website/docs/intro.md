---
title: Introduction
description: What Conversion Coach is, the one idea it is built on, and the three personas it coaches.
sidebar_position: 1
---

# Conversion Coach

**Track:** Insurance AI (UNIQA) — AI-Guided Conversion Flow
**Built for:** [Zero One Hack_01](https://docs.zero-one.lumos-consulting.at/) at AI Factory Austria, Vienna.

Conversion Coach replaces a static, form-based insurance calculator with an
**AI-guided conversion flow**: a coach that watches a user move through the
signup funnel, detects when they are about to drop off, and intervenes with the
right nudge — phrased for *that* user — at the right moment.

## The one idea this whole project is built on

> **Decision logic lives in inspectable code. The LLM produces behavior
> (persona bots) and words (intervention wording) — never decisions.**

This track is explicitly *not* an "LLM-wrapper" case. The jury grades
**traceable decision rules**, **trigger precision/recall**, and **annoyance
rate**. A coach whose when/how policy is fused into model weights has nothing
inspectable to show and scores poorly.

So the split is deliberate:

- The **state machine**, the **detection layer**, and the **decision/policy
  layer** are all readable code.
- The **model** only drives the synthetic users and phrases an intervention
  *after* the policy has already decided to fire it.

A second principle drives the build order:

> **Build the measurement substrate first; upgrade components into it.**

The eval harness is not the finale — it is the scaffold built in Phase 1 and
filled in every phase after. Every later phase is "swap a stub for a real
component and re-run the same harness." See [Build phases](./phases.md).

## What it coaches: three personas

A single unified strategy fails — the central technical challenge is that each
persona drops off for a different reason, at a different step, and "conversion"
means something different for each.

| Persona | Primary drop | Conversion counts as | Never do |
|---|---|---|---|
| **Judith** — Rising Hybrid | initial price (S4) | online purchase **or** advisor handoff | aggressive online-only push |
| **Franz** — Online Affine | final price (S7) | online purchase **only** (handoff = failure) | suggest an advisor / add friction |
| **Peter** — Service Affine | early, pre-price (S1–S3) | qualified service contact (online is **not** the target) | push self-service / add options |

The full decision table — interventions per persona and the discriminative
signal signatures that distinguish them — lives in
[Build phases → Phase 2](./phases.md).

## The in-scope path

Only the **private-doctor / "myself" / Start & Optimal** path is coached.
Hospital, "other persons", and the advisory-only tariffs (Opt.Plus / Premium)
route to an advisor and are deliberately **not** coached. The funnel skips
Step 5 (an out-of-scope add-on step), so the in-scope journey is:

```
S0 → S1 → S2 → S3 → S4 → S6 → S7 → S12 → CONVERTED
```

See [Architecture](./architecture.md) for the state machine and the data path.

## Where to go next

- **[Architecture](./architecture.md)** — the frozen interfaces, the per-episode
  data path, and the service topology.
- **[Build phases](./phases.md)** — the staged build, one swappable component at
  a time, each gated by an acceptance test.
- **[Running locally](./running-locally.md)** — set up the environment and run a
  simulation.
- **[Reference](./reference.md)** — the repository module map.
