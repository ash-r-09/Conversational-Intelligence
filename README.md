<h1 align="center">Conversational-Intelligence</h1>
<p align="center">Sales conversation intelligence and BANT scoring from call transcripts.<br>Rule-based, explainable, no API key.</p>

---

## What it does

Give it call transcripts. For each call it returns:

- **BANT score (0-100):** Budget, Authority, Need and Timeline, 25 points each, with the exact customer quote behind every number.
- **Grade:** Qualified (70+), Nurture (40-69) or Unqualified (below 40).
- **Ask next:** a suggested follow-up question for every weak dimension.
- **Conversation intelligence:** seller talk share, questions asked, competitors mentioned, objections and agreed next steps.

## Two rules that keep the score honest

1. **Only the customer's words count.** The seller says "do you have a problem with call tracking?" on every call. Crediting that to the buyer is the classic failure of keyword scoring, so seller turns never earn points.
2. **Unprompted beats led.** If the customer raises budget on their own, it scores in full. If they answer a seller's budget question, it scores at 70%. Disqualifiers ("no budget this year", "not my call") cap a dimension at level 1 and are shown as warnings.

## Quick start

```bash
git clone https://github.com/ash-r-09/Conversational-Intelligence.git && cd Conversational-Intelligence
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m bant_agent score samples                # ranked table
.venv/bin/python -m bant_agent score samples/hot-deal.txt   # full report for one call
.venv/bin/python -m bant_agent score samples --out out      # + report.csv, .md, .json per call
.venv/bin/pytest
```

Sample output (synthetic transcripts):

| Call | Score | Grade | B | A | N | T | Gaps |
|---|---|---|---|---|---|---|---|
| indian-english | 79.2 | Qualified | 25 | 11.7 | 25 | 17.5 | - |
| hot-deal | 77.5 | Qualified | 17.5 | 17.5 | 25 | 17.5 | - |
| warm-deal | 50.9 | Nurture | 5.8 | 16.7 | 16.7 | 11.7 | budget |
| cold-deal | 0.0 | Unqualified | 0 | 0 | 0 | 0 | all four |

## Transcript format

One turn per line:

```
Alex (Seller): What prompted you to look at this?
[00:42] Priya (Customer): We're losing deals and can't see why.
```

Unlabelled speakers are ignored as evidence (with a warning). Label them with `--seller "Alex,Sam"` or `--customer "Priya"`.

## How each dimension is scored

Each dimension gets a level of 0-3 from the strongest matching pattern, then `points = 25 × level/3 × weight`.

| | Level 3 | Level 2 | Level 1 |
|---|---|---|---|
| **Budget** | approved / allocated | an amount stated with budget context | budget mentioned |
| **Authority** | "I make the final decision", C-level self-description | VP/director, will champion to the decision maker | needs approval from someone |
| **Need** | pain with a number ("6 hours a week", "30%") | specific pain | wants to improve |
| **Timeline** | deadline with a date or quarter | a timeframe ("next quarter") | "soon" / "ASAP" |

## The word directory

[`config/lexicon.yaml`](config/lexicon.yaml) is the file to edit. It holds about 700 plain phrases, no regex needed:

| Section | What it holds |
|---|---|
| `dimensions.<budget/authority/need/timeline>` | phrases per strength (`level_3`, `level_2`, `level_1`), `disqualifiers`, and seller `cue` phrases |
| `competitors` | about 43 tools in four groups (conversation intelligence, CRM, sales data, coaching) |
| `buying_signals` | "send me a proposal", "can we try it", "who else uses this"... |
| `stall_signals` | "just send me an email", "I'll get back to you", "comparing vendors"... |
| `objections` | seven groups: price, timing, trust and security, status quo, integration, value, adoption |
| `stakeholder_titles` | roles the customer mentions (a sign the deal is multi-threaded) |

Matching rules: whole words only, `budget*` means any ending, apostrophes are optional, and a phrase is ignored when negated within three words ("*not* looking to improve"). A few common Hinglish phrases are included.

```bash
.venv/bin/python -m bant_agent lexicon                     # counts per section and conflict check
.venv/bin/python -m bant_agent lexicon --search budget     # where does a word appear?
```

The checker fails on a phrase that sits at two strength levels of one dimension, and on phrases that won't compile. Two things stay in [`config/bant.yaml`](config/bant.yaml): the few regex rules that need patterns (money amounts, deadline plus date) and the weights and grade thresholds.

## Use it inside Claude Code

The repo ships a skill and a subagent in [`.claude/`](.claude):

- `/score-bant <file-or-folder>` runs the scorer, shows evidence and follow-up questions, and adds separate reviewer notes if a quote doesn't support its level.
- The `bant-scorer` subagent does the same on request: *"which of these calls are qualified?"*

To use them from any folder, copy `.claude/skills/score-bant` to `~/.claude/skills/` and `.claude/agents/bant-scorer.md` to `~/.claude/agents/`.

## Limits

- **Rules, not understanding.** Phrase lists miss paraphrase, sarcasm and other languages, and can credit a past deal or another company's budget. English only.
- **Not validated.** The samples are synthetic and the weights are hand-set. Nobody has checked the scores against human-labelled real calls, so don't read the grade as a forecast.
- **Plain text only.** Audio, Gong/Chorus JSON and PDFs are not parsed; convert them to the format above first.
- **Natural next step:** use an LLM only on the evidence quotes to review borderline levels, keeping the rule-based score as the audit trail.

MIT License. See [`LICENSE`](LICENSE).
