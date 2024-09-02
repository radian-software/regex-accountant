from pathlib import Path

from lark import Lark


THIS_DIR = Path(__file__).resolve().parent


with open(THIS_DIR / "query.lark") as f:
    parser = Lark(f)


class Query:
    def __init__(self, q: str):
        self.ast = parser.parse(q)
