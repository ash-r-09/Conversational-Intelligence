"""CLI: python -m bant_agent score <file-or-folder> [--out DIR] [--json]"""
import argparse
import csv
import json
import sys
from pathlib import Path

from .lexicon import check, counts, load_lexicon, search
from .scoring import DEFAULT_LEXICON, DIMS, load_config, score_text

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "bant.yaml"


def render_markdown(name: str, r: dict) -> str:
    L = [f"# {name}: {r['total']}/100, {r['grade']}", ""]
    L += ["| BANT | Points | Level | Evidence |", "|---|---|---|---|"]
    for d in DIMS:
        v = r["dimensions"][d]
        ev = (f"\"{v['quote']}\" ({v['prompted']}, turn {v['turn']}, matched \"{v['matched']}\")"
              if v["quote"] else "none found")
        if v["disqualifiers"]:
            ev += f" ⚠ disqualifier: \"{v['disqualifiers'][0]['quote']}\""
        L.append(f"| {d.title()} | {v['points']}/25 | {v['level']}/3 | {ev} |")
    if r["gaps"]:
        L += ["", "**Ask next:**"] + [f"- {g['dimension'].title()}: {g['ask']}" for g in r["gaps"]]
    i = r["intelligence"]
    L += ["", "**Conversation intelligence**",
          f"- Seller talk share: {i['talk_ratio_seller_pct']}% · seller questions: {i['seller_questions']} · customer questions: {i['customer_questions']}",
          f"- Momentum: **{i['momentum']}** · buying signals: {len(i['buying_signals'])} · stall signals: {len(i['stall_signals'])}",
          f"- Stakeholders mentioned: {', '.join(i['stakeholders_mentioned']) or 'none'}",
          f"- Competitors: {', '.join(i['competitors_mentioned']) or 'none'}",
          f"- Next steps: {'; '.join(i['next_steps']) or 'none agreed'}"]
    if i["objections"]:
        L.append("- Objections: " + "; ".join(f"{cat}: \"{qs[0]}\"" for cat, qs in i["objections"].items()))
    else:
        L.append("- Objections: none")
    for w in r["warnings"]:
        L.append(f"- ⚠ {w}")
    return "\n".join(L)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="bant_agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("path", help="transcript .txt/.md file or a folder of them")
    s.add_argument("--config", default=str(DEFAULT_CONFIG))
    s.add_argument("--lexicon", default=None, help="word directory (default: config/lexicon.yaml)")
    s.add_argument("--seller", default="", help="comma-separated seller names")
    s.add_argument("--customer", default="", help="comma-separated customer names")
    s.add_argument("--out", help="write report.csv and per-call .json/.md here")
    s.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    lx = sub.add_parser("lexicon", help="inspect/validate the word directory")
    lx.add_argument("--lexicon", default=str(DEFAULT_LEXICON))
    lx.add_argument("--search", help="find where a word or phrase appears in the directory")
    a = p.parse_args(argv)

    if a.cmd == "lexicon":
        lex = load_lexicon(a.lexicon)
        if a.search:
            hits = search(lex, a.search)
            print("\n".join(hits) or f"'{a.search}' not found")
            return 0
        print(json.dumps(counts(lex), indent=2))
        problems = check(lex)
        print("\nProblems:" if problems else "\nNo problems found.")
        for pr in problems:
            print(f"- {pr}")
        return 1 if any("CONFLICT" in x or "cannot compile" in x for x in problems) else 0

    cfg = load_config(a.config, a.lexicon)
    path = Path(a.path)
    files = sorted(f for f in path.iterdir() if f.suffix in (".txt", ".md")) if path.is_dir() else [path]
    if not files:
        print("No transcript files found.", file=sys.stderr)
        return 1
    sellers = [x for x in a.seller.split(",") if x]
    customers = [x for x in a.customer.split(",") if x]

    results = []
    for f in files:
        results.append((f.stem, score_text(f.read_text(), cfg, sellers, customers)))
    results.sort(key=lambda kv: kv[1]["total"], reverse=True)

    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for name, r in results:
            (out / f"{name}.json").write_text(json.dumps(r, indent=2))
            (out / f"{name}.md").write_text(render_markdown(name, r))
        with open(out / "report.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["call", "total", "grade", "budget", "authority", "need", "timeline", "gaps"])
            for name, r in results:
                w.writerow([name, r["total"], r["grade"]] + [r["dimensions"][d]["points"] for d in DIMS]
                           + [", ".join(g["dimension"] for g in r["gaps"])])

    if a.json:
        print(json.dumps({n: r for n, r in results}, indent=2))
    elif len(results) == 1:
        print(render_markdown(*results[0]))
    else:
        print("| Call | Score | Grade | B | A | N | T | Gaps |\n|---|---|---|---|---|---|---|---|")
        for name, r in results:
            d = r["dimensions"]
            print(f"| {name} | {r['total']} | {r['grade']} | " + " | ".join(str(d[x]["points"]) for x in DIMS)
                  + f" | {', '.join(g['dimension'] for g in r['gaps']) or '-'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
