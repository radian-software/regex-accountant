from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import lark


THIS_DIR = Path(__file__).resolve().parent


with open(THIS_DIR / "query.lark") as f:
    parser = lark.Lark(f, ambiguity="resolve")


@dataclass
class Operation(ABC):
    pass


@dataclass
class BoolExpr(ABC):
    pass


@dataclass
class Expr(ABC):
    pass


@dataclass
class Comparator(ABC):
    pass


class EqualsIgnoringCase(Comparator):
    pass


class GreaterThanOrEqual(Comparator):
    pass


comparator_table = {
    "=": EqualsIgnoringCase(),
    ">=": GreaterThanOrEqual(),
}


@dataclass
class Identifier:
    value: str


@dataclass
class Comparison:
    lhs: Expr
    comp: Comparator
    rhs: Expr


@dataclass
class Plus(Expr):
    args: list[Expr]


@dataclass
class Times(Expr):
    args: list[Expr]


@dataclass
class Divide(Expr):
    lhs: Expr
    rhs: Expr


@dataclass
class Negate(Expr):
    arg: Expr


@dataclass
class Funcall(Expr):
    funcname: Identifier
    args: list[Expr]


@dataclass
class FilterOr(BoolExpr):
    exprs: list[BoolExpr]


@dataclass
class FilterAnd(BoolExpr):
    exprs: list[BoolExpr]


@dataclass
class Filter(Operation):
    expr: BoolExpr


@dataclass
class Pipeline:
    ops: list[Operation]


class Transformer(lark.Transformer):
    pipeline = Pipeline
    op_filter = lambda self, args: Filter(args[0])

    def filter(self, conjs):
        if len(conjs) == 1:
            return conjs[0]
        return FilterOr(conjs)

    def filter_conj(self, atoms):
        if len(atoms) == 1:
            return atoms[0]
        return FilterAnd(atoms)

    def filt_comp(self, args):
        if len(args) == 1:
            return args[0]
        lhs, comp, rhs = args
        return Comparison(lhs, comparator_table[comp.value], rhs)

    def expr(self, args):
        args = list(reversed(args))
        parts = []
        parts.append(args.pop())
        while args:
            op = args.pop()
            val = args.pop()
            if op.value == "-":
                val = Negate(val)
            parts.append(val)
        if len(parts) == 1:
            return parts[0]
        return Plus(parts)

    signum = lambda self, args: Decimal(args[0])

    rawstr = lambda self, tok: tok[0].value
    propname = lambda self, tok: Identifier(tok[0].value)

    def date(self, args):
        s = args[0]
        if len(s.split("-")) == 2:
            return datetime.strptime(s, "%Y-%m").date()
        return datetime.strptime(s, "%Y-%m-%d").date()


class Query:
    def __init__(self, q: str):
        self.ast = Transformer().transform(parser.parse(q))


q = Query("acct=venmo date>=2024-02")
