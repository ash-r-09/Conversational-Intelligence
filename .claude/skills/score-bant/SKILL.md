---
name: score-bant
description: Score sales call transcripts on BANT (Budget, Authority, Need, Timeline) with conversation intelligence. Use when the user says "score this call", "BANT this transcript", "is this deal qualified", or points at call transcripts (.txt/.md).
---

# Score calls on BANT

Repo: `~/Projects/Conversational-Intelligence` (override with `$BANT_AGENT_DIR`). Run from the repo dir with `.venv/bin/python`.

## Transcript format
One turn per line: `Name (Seller): text` or `Name (Customer): text`. Optional `[00:12]` timestamp prefix. If speakers are not labelled, pass `--seller "Alex,Sam"` and/or `--customer "Priya"`.

## Steps
1. Run `.venv/bin/python -m bant_agent score <file-or-folder> [--out out/]`. A folder gives a ranked table and, with `--out`, `report.csv` plus a `.md` and `.json` per call.
2. Show the user: total/100, grade, each BANT dimension with its evidence quote and whether it was `unprompted` or `led`, the disqualifiers, and the "Ask next" questions.
3. Spot-check: read the quoted evidence. If a quote clearly does not support its level (sarcasm, a past deal, a different company), say so in a separate "Reviewer notes" section. Never change the script's numbers; report disagreement alongside them.
4. Surface script warnings (unlabelled speakers, no customer turns) before the scores.

## Rules
- Only customer turns count as evidence. The seller's pitch never earns points.
- Add or change words in `config/lexicon.yaml` (plain phrases). Run `.venv/bin/python -m bant_agent lexicon` to check for conflicts, then `.venv/bin/pytest -q`. Weights and thresholds live in `config/bant.yaml`.
- The report shows `matched` (the phrase that triggered each level), momentum, objections by type and stakeholders mentioned; include them.
- Never invent evidence. If a dimension has none, say "none found".
