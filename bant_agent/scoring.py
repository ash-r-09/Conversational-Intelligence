"""BANT scoring + conversation intelligence. Rule-based, no API calls."""
import re
from pathlib import Path

import yaml

from .parser import Turn, parse

DIMS = ("budget", "authority", "need", "timeline")
POINTS_PER_DIM = 25


def load_config(path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def _compile(cfg: dict) -> dict:
    out = {}
    for d in DIMS:
        spec = cfg["dimensions"][d]
        out[d] = {
            "cue": re.compile(spec["cue"], re.I),
            "levels": {int(k): [re.compile(p, re.I) for p in v] for k, v in spec["levels"].items()},
            "disq": [re.compile(p, re.I) for p in spec.get("disqualifiers", [])],
            "question": spec["question"],
        }
    return out


def _quote(text: str, n: int = 200) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


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
        best = {"level": 0, "weight": 0.0, "points": 0.0, "turn": None, "prompted": None, "quote": None}
        flags = []
        hits = 0
        for t in turns:
            if t.role != "customer":
                continue
            if any(p.search(t.text) for p in r["disq"]):
                flags.append({"turn": t.idx, "quote": _quote(t.text)})
                continue  # a turn that disqualifies this dimension is never positive evidence for it
            level = 0
            for lv in sorted(r["levels"], reverse=True):
                if any(p.search(t.text) for p in r["levels"][lv]):
                    level = lv
                    break
            if not level:
                continue
            hits += 1
            prev = turns[t.idx - 1] if t.idx > 0 else None
            led = bool(prev and prev.role == "seller" and r["cue"].search(prev.text))
            weight = w["led"] if led else w["unprompted"]
            pts = POINTS_PER_DIM * level / 3 * weight
            if pts > best["points"]:
                best = {"level": level, "weight": weight, "points": pts, "turn": t.idx,
                        "prompted": "led" if led else "unprompted", "quote": _quote(t.text)}
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
    words = {"seller": 0, "customer": 0}
    for t in turns:
        if t.role in words:
            words[t.role] += len(t.text.split())
    total_words = sum(words.values()) or 1
    comp = re.compile(r"\b(" + "|".join(map(re.escape, ic["competitors"])) + r")\b", re.I)
    competitors = sorted({m.group(1).lower() for t in turns for m in comp.finditer(t.text)})
    nxt = re.compile(ic["next_steps"], re.I)
    obj = re.compile(ic["objections"], re.I)
    return {
        "talk_ratio_seller_pct": round(100 * words["seller"] / total_words),
        "seller_questions": sum(t.text.count("?") for t in turns if t.role == "seller"),
        "customer_questions": sum(t.text.count("?") for t in turns if t.role == "customer"),
        "competitors_mentioned": competitors,
        "next_steps": [_quote(t.text) for t in turns if nxt.search(t.text)][:3],
        "objections": [_quote(t.text) for t in turns if t.role == "customer" and obj.search(t.text)][:5],
    }


def score_text(text: str, cfg: dict, seller_names=(), customer_names=()) -> dict:
    return score_turns(parse(text, seller_names, customer_names), cfg)
