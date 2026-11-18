# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is a solo researcher working on their own Mac. They bring private documents and a question, run a simulated social scenario, and inspect what happened before deciding what deserves real-world follow-up.

## Product Purpose

MiroFish Local turns documents into a small simulated society. It builds a knowledge graph, creates agents, runs them on simulated Twitter and Reddit, stores their activity as labelled memory, and writes a report. Success means the researcher can start a scenario, watch it unfold, explore the graph and review the report without losing sight of what came from source material and what came from simulation.

## Positioning

A private scenario lab: a serious place to test ideas on your own machine, without sending documents to cloud services.

## Operating Context

Runs are long and local. The researcher may leave a run active for more than an hour, return to check progress, inspect recent activity, and later compare report claims with recorded posts and graph facts. Models, graph memory and simulation data stay on the Mac after setup.

## Capabilities and Constraints

- Keep the five-stage workflow: graph build, environment setup, simulation, report and interaction.
- Keep the knowledge graph available beside the work.
- Keep run details and logs available.
- Keep language switching, with English as the default.
- The first screen starts a scenario with documents and a question, with recent runs and privacy status nearby.
- Running, graph exploration and report review are all central jobs.
- Facts learned from simulation must remain distinguishable from source facts.
- The app is loopback-only and has no login system.
- The product must not present simulations as forecasts, opinion polls or evidence about real people.

## Brand Commitments

The product name is MiroFish Local. It is an unofficial fork of MiroFish. The repository has an original animated fish logo at `docs/assets/logo.svg`.

## Evidence on Hand

The sanitized fictional reference test is in `eval/results/`, with reports, posts, comments, profiles, graph data, audits and network watch logs. The final run used 19 agents and 24 simulated hours, took 81 minutes, recorded 0 outside connections in 957 checks, and had 24 of 41 report claims supported by an AI audit.

## Product Principles

1. Privacy is visible through real system status, never decorative claims.
2. Evidence stays close to every conclusion.
3. Simulated material is always labelled as simulated.
4. Long-running work remains understandable when the researcher returns.
5. Depth is available without getting in the way of the next action.

## Accessibility & Inclusion

The interface must keep multilingual support, with English as the default.
