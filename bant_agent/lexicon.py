"""Plain-phrase word directory -> regex, with a negation guard and a consistency checker."""
import re
from pathlib import Path

import yaml

NEGATORS = {"not", "no", "never", "without", "don't", "dont", "doesn't", "isn't", "aren't",
            "can't", "cannot", "won't", "wouldn't", "neither", "nor", "hardly"}
LEVEL_KEYS = {3: "level_3", 2: "level_2", 1: "level_1"}


def load_lexicon(path) -> dict:
    p = Path(path)
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def phrase_to_regex(phrase: str) -> str:
    """'don't have budget*' -> whole-word regex; * = any word ending; apostrophes optional."""
    tokens = phrase.strip().lower().replace("’", "'").split()
    parts = []
    for tok in tokens:
        star = tok.endswith("*")
        core = re.escape(tok.rstrip("*")).replace("'", "['’]?")
        parts.append(core + (r"\w*" if star else ""))
    return r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)"


def compile_phrases(phrases):
    phrases = sorted({p.strip() for p in phrases if p and p.strip()}, key=len, reverse=True)
    if not phrases:
        return None
    return re.compile("|".join(phrase_to_regex(p) for p in phrases), re.I)


def _negated(text: str, start: int) -> bool:
    words = text[max(0, start - 40):start].lower().replace("’", "'").split()[-3:]
    return any(w.strip(",.;:!?\"") in NEGATORS for w in words)


def hit(rx, text: str, guard: bool = True) -> bool:
    """True if rx matches text (and, when guard, at least one match is not negated)."""
    if rx is None:
        return False
    for m in rx.finditer(text):
        if not guard or not _negated(text, m.start()):
            return True
    return False


def first_hits(rx, text: str, guard: bool = True) -> list[str]:
    if rx is None:
        return []
    return [m.group(0) for m in rx.finditer(text) if not guard or not _negated(text, m.start())]


def check(lex: dict) -> list[str]:
    """Return human-readable problems: duplicates, cross-level conflicts, bad phrases."""
    problems = []
    for dim, spec in (lex.get("dimensions") or {}).items():
        seen: dict[str, str] = {}
        for key in ["cue", "level_3", "level_2", "level_1", "disqualifiers"]:
            for ph in spec.get(key, []) or []:
                norm = ph.strip().lower()
                try:
                    re.compile(phrase_to_regex(ph))
                except re.error as e:
                    problems.append(f"{dim}.{key}: cannot compile '{ph}' ({e})")
                if key == "cue":
                    continue
                if norm in seen:
                    kind = "duplicate" if seen[norm] == key else "CONFLICT"
                    problems.append(f"{dim}: {kind} '{ph}' in {seen[norm]} and {key}")
                else:
                    seen[norm] = key
    return problems


def counts(lex: dict) -> dict:
    out = {}
    for dim, spec in (lex.get("dimensions") or {}).items():
        out[dim] = {k: len(spec.get(k, []) or []) for k in
                    ["cue", "level_3", "level_2", "level_1", "disqualifiers"]}
    comp = lex.get("competitors") or {}
    out["competitors"] = sum(len(v) for v in comp.values())
    out["buying_signals"] = len(lex.get("buying_signals") or [])
    out["stall_signals"] = len(lex.get("stall_signals") or [])
    out["objections"] = {k: len(v) for k, v in (lex.get("objections") or {}).items()}
    out["stakeholder_titles"] = len(lex.get("stakeholder_titles") or [])
    return out


def search(lex: dict, word: str) -> list[str]:
    """Where does a word/phrase appear in the directory?"""
    w = word.lower()
    found = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + [str(k)])
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, str) and w in item.lower():
                    found.append(f"{'.'.join(path)}: {item}")

    walk(lex, [])
    return found
