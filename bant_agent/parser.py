"""Turn a plain-text transcript into speaker-tagged turns."""
import re
from dataclasses import dataclass

LINE = re.compile(r"^\s*(?:\[(?P<ts>[\d:]+)\]\s*)?(?P<speaker>[A-Za-z][^:\n]{0,40}?):\s*(?P<text>\S.*)$")
SELLER = re.compile(r"\b(seller|rep|ae|sdr|bdr|sales|host)\b", re.I)
CUSTOMER = re.compile(r"\b(customer|prospect|buyer|client)\b", re.I)


@dataclass
class Turn:
    idx: int
    speaker: str
    role: str  # seller | customer | unknown
    text: str


def _role(speaker: str, seller_names, customer_names) -> str:
    base = re.sub(r"\(.*?\)", "", speaker).strip().lower()
    if base in seller_names:
        return "seller"
    if base in customer_names:
        return "customer"
    if SELLER.search(speaker):
        return "seller"
    if CUSTOMER.search(speaker):
        return "customer"
    return "unknown"


def parse(text: str, seller_names=(), customer_names=()) -> list[Turn]:
    """Lines look like `Alex (Seller): hi` or `[00:12] Priya (Customer): hello`.
    Lines with no speaker label continue the previous turn."""
    seller_names = {n.strip().lower() for n in seller_names}
    customer_names = {n.strip().lower() for n in customer_names}
    text = text.replace("’", "'")
    turns: list[Turn] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        m = LINE.match(raw)
        if m:
            sp = m.group("speaker").strip()
            turns.append(Turn(len(turns), sp, _role(sp, seller_names, customer_names), m.group("text").strip()))
        elif turns:
            turns[-1].text += " " + raw.strip()
    return turns
