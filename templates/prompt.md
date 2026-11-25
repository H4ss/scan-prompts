---
id: YYYY-MM-DD-NN
date: YYYY-MM-DD
version: 1
contract: "0.2"
target: factory-dev     # factory-dev | factory-review | opencode-plan | human
tickets: []
status: draft           # draft | ready | applied | superseded | withdrawn
supersedes: null
---

# <Title: what this prompt makes the agent do>

## Goal
One paragraph. What must be true when the agent is done.

## Inputs
Files and tickets the agent reads. Nothing else.

## Steps
Numbered, each checkable.

## Constraints
Scope, forbidden actions, anything beyond AGENTS.md for this prompt.

## Stop conditions
When the agent stops and hands back.

## Report
Exact format the agent returns.
