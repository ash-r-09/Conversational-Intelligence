"""BANT scoring + conversation intelligence. Rule-based, no API calls.

Evidence comes from two places, merged: the regex rules in config/bant.yaml (money amounts,
deadline + date) and the plain-phrase word directory in config/lexicon.yaml.
"""
import re
from pathlib import Path

import yaml

from .lexicon import compile_phrases, first_hits, hit, load_lexicon
from .parser import Turn, parse

DIMS = ("budget", "authority", "need", "timeline")
POINTS_PER_DIM = 25
DEFAULT_LEXICON = Path(__file__).resolve().parent.parent / "config" / "lexicon.yaml"


def load_config(path, lexicon_path=None) -> dict:
    cfg = yaml.safe_load(Path(path).read_text())
    lp = Path(lexicon_path) if lexicon_path else (Path(path).parent / "lexicon.yaml")
    if not lp.exists():
        lp = DEFAULT_LEXICON
    cfg["lexicon"] = load_lexicon(lp)
    return cfg


def _compile(cfg: dict) -> dict:
    lex_dims = (cfg.get("lexicon") or {}).get("dimensions", {})
    out = {}
    for d in DIMS:
        spec = cfg["dimensions"][d]
        lx = lex_dims.get(d, {})
        out[d] = {
            "cue": re.compile(spec["cue"], re.I),
            "lex_cue": compile_phrases(lx.get("cue", [])),
            "levels": {int(k): [re.compile(p, re.I) for p in v] for k, v in spec["levels"].items()},
            "lex_levels": {lv: compile_phrases(lx.get(f"level_{lv}", [])) for lv in (3, 2, 1)},
            "disq": [re.compile(p, re.I) for p in spec.get("disqualifiers", [])],
            "lex_disq": compile_phrases(lx.get("disqualifiers", [])),
            "question": spec["question"],
        }
    return out


def _quote(text: str, n: int = 200) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _turn_level(t: Turn, r: dict) -> tuple[int, str | None]:
    """Strongest level (0-3) this turn supports, and the phrase that triggered it."""
    for lv in (3, 2, 1):
        for p in r["levels"].get(lv, []):
            m = p.search(t.text)
            if m:
                return lv, (m.group(0) or "deadline + date pattern")
        got = first_hits(r["lex_levels"][lv], t.text)
        if got:
            return lv, got[0]
    return 0, None


def score_turns(turns: list[Turn], cfg: dict) -> dict:
    rules = _compile(cfg)
    w = cfg["weights"]
    result = {"dimensions": {}, "warnings": []}

    unknown = sorted({t.speaker for t in turns if t.role == "unknown"})
    if unknown:
        result["warnings"].append(
            f"Unlabelled speakers ignored as evidence: {', '.join(unknown)}. "
            "Label them (Seller)/(Customer) or pass --seller / --customer.")
    if not any(t.role == "customer" for t in turns):
        result["warnings"].append("No customer turns found, so every dimension scores 0.")

    for d in DIMS:
        r = rules[d]
        best = {"level": 0, "weight": 0.0, "points": 0.0, "turn": None, "prompted": None,
                "quote": None, "matched": None}
        flags = []
        hits = 0
        for t in turns:
            if t.role != "customer":
                continue
            if any(p.search(t.text) for p in r["disq"]) or hit(r["lex_disq"], t.text, guard=False):
                flags.append({"turn": t.idx, "quote": _quote(t.text)})
                continue  # a turn that disqualifies this dimension is never positive evidence for it
            level, matched = _turn_level(t, r)
            if not level:
                continue
            hits += 1
            prev = turns[t.idx - 1] if t.idx > 0 else None
            led = bool(prev and prev.role == "seller"
                       and (r["cue"].search(prev.text) or hit(r["lex_cue"], prev.text, guard=False)))
            weight = w["led"] if led else w["unprompted"]
            pts = POINTS_PER_DIM * level / 3 * weight
            if pts > best["points"]:
                best = {"level": level, "weight": weight, "points": pts, "turn": t.idx,
                        "prompted": "led" if led else "unprompted", "quote": _quote(t.text),
                        "matched": matched}
        if flags and best["level"] > 1:  # a stated disqualifier caps the dimension at level 1
            best["points"] = POINTS_PER_DIM * 1 / 3 * best["weight"]
            best["level"] = 1
        best["points"] = round(best["points"], 1)
        best["disqualifiers"] = flags
        best["evidence_turns"] = hits
        best["question"] = r["question"]
        result["dimensions"][d] = best

    total = round(sum(v["points"] for v in result["dimensions"].values()), 1)
    g = cfg["grades"]
    result["total"] = total
    result["grade"] = "Qualified" if total >= g["qualified"] else "Nurture" if total >= g["nurture"] else "Unqualified"
    result["gaps"] = [{"dimension": d, "ask": v["question"]}
                      for d, v in result["dimensions"].items() if v["level"] < 2]
    result["intelligence"] = _intelligence(turns, cfg)
    return result


def _intelligence(turns: list[Turn], cfg: dict) -> dict:
    ic = cfg["intelligence"]
    lex = cfg.get("lexicon") or {}
    words = {"seller": 0, "customer": 0}
    for t in turns:
        if t.role in words:
            words[t.role] += len(t.text.split())
    total_words = sum(words.values()) or 1

    comp_names = set(ic.get("competitors", []))
    for group in (lex.get("competitors") or {}).values():
        comp_names.update(group)
    comp = compile_phrases(sorted(comp_names))
    competitors = sorted({m.lower() for t in turns for m in first_hits(comp, t.text, guard=False)})

    nxt = re.compile(ic["next_steps"], re.I)
    customer = [t for t in turns if t.role == "customer"]

    objections: dict[str, list[str]] = {}
    for cat, phrases in (lex.get("objections") or {}).items():
        rx = compile_phrases(phrases)
        quotes = [_quote(t.text) for t in customer if hit(rx, t.text)]
        if quotes:
            objections[cat] = quotes[:3]
    legacy = re.compile(ic["objections"], re.I)  # catch-all from bant.yaml
    if not objections:
        other = [_quote(t.text) for t in customer if legacy.search(t.text)]
        if other:
            objections["other"] = other[:3]

    buy_rx = compile_phrases(lex.get("buying_signals", []))
    stall_rx = compile_phrases(lex.get("stall_signals", []))
    buying = [_quote(t.text) for t in customer if hit(buy_rx, t.text)]
    stalls = [_quote(t.text) for t in customer if hit(stall_rx, t.text)]
    if len(buying) > len(stalls) and buying:
        momentum = "positive"
    elif len(stalls) > len(buying):
        momentum = "stalling"
    else:
        momentum = "mixed" if buying else "unclear"

    title_rx = compile_phrases(lex.get("stakeholder_titles", []))
    stakeholders = sorted({m.lower() for t in customer for m in first_hits(title_rx, t.text, guard=False)})

    return {
        "talk_ratio_seller_pct": round(100 * words["seller"] / total_words),
        "seller_questions": sum(t.text.count("?") for t in turns if t.role == "seller"),
        "customer_questions": sum(t.text.count("?") for t in customer),
        "competitors_mentioned": competitors,
        "next_steps": [_quote(t.text) for t in turns if nxt.search(t.text)][:3],
        "objections": objections,
        "buying_signals": buying[:5],
        "stall_signals": stalls[:5],
        "momentum": momentum,
        "stakeholders_mentioned": stakeholders,
    }


def score_text(text: str, cfg: dict, seller_names=(), customer_names=()) -> dict:
    return score_turns(parse(text, seller_names, customer_names), cfg)
