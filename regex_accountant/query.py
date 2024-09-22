from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import re
from typing import Any

import lark

from regex_accountant.postprocess import ExtTransaction as Txn


THIS_DIR = Path(__file__).resolve().parent


with open(THIS_DIR / "query.lark") as f:
    parser = lark.Lark(f, ambiguity="resolve")


@dataclass
class Operation(ABC):
    @abstractmethod
    def apply(self, txns: list[Txn]) -> list[Txn]:
        raise NotImplementedError


@dataclass
class BoolExpr(ABC):
    @abstractmethod
    def matches(self, txn: Txn) -> bool:
        raise NotImplementedError


@dataclass
class Expr(ABC):
    def evaluate(self, txn: Txn) -> Any:
        pass


@dataclass
class Comparator(ABC):
    @abstractmethod
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr) -> bool:
        raise NotImplementedError


class Equals(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr) -> bool:
        return lhs.evaluate(txn) == rhs.evaluate(txn)


class EqualsIgnoringCase(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr) -> bool:
        lhs_val = lhs.evaluate(txn)
        rhs_val = rhs.evaluate(txn)
        if isinstance(lhs_val, str):
            lhs_val = lhs_val.casefold()
        if isinstance(rhs_val, str):
            rhs_val = rhs_val.casefold()
        return lhs_val == rhs_val


class Contains(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr) -> bool:
        return rhs.evaluate(txn) in lhs.evaluate(txn)


class ContainsIgnoringCase(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr) -> bool:
        lhs_val = lhs.evaluate(txn)
        rhs_val = rhs.evaluate(txn)
        if isinstance(lhs_val, str):
            lhs_val = lhs_val.casefold()
        if isinstance(rhs_val, str):
            rhs_val = rhs_val.casefold()
        return rhs_val in lhs_val


class LessThan(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr) -> bool:
        return lhs.evaluate(txn) < rhs.evaluate(txn)


class LessThanOrEqual(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr) -> bool:
        return lhs.evaluate(txn) <= rhs.evaluate(txn)


class GreaterThan(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr) -> bool:
        return lhs.evaluate(txn) > rhs.evaluate(txn)


class GreaterThanOrEqual(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr) -> bool:
        return lhs.evaluate(txn) >= rhs.evaluate(txn)


class MatchesRegex(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr) -> bool:
        return re.fullmatch(rhs.evaluate(txn), lhs.evaluate(txn))


comparator_table = {
    "==": Equals(),
    "=": EqualsIgnoringCase(),
    "::": Contains(),
    ":": ContainsIgnoringCase(),
    "<": LessThan(),
    ">": GreaterThan(),
    "<=": LessThanOrEqual(),
    ">=": GreaterThanOrEqual(),
    "~": MatchesRegex(),
}


@dataclass
class Identifier(Expr):
    value: str
    default_to_string: bool = False  # hack, remove

    def evaluate(self, txn: Txn) -> Any:
        if self.value in {"date", "date_posted", "posted"}:
            return txn.date_posted
        if self.value in {"date_cleared", "cleared"}:
            return txn.date_cleared
        if self.value in {"currency", "cur"}:
            return txn.currency
        if self.value in {"amount", "amt", "value", "val"}:
            return txn.amount
        if self.value in {"source_uid", "uid", "id"}:
            return txn.source_uid
        if self.value in {"description", "desc"}:
            return txn.description
        if self.value in {"description_short", "desc_short"}:
            return txn.description_short or txn.description
        if self.value in {
            "description_details",
            "desc_details",
            "description_detail",
            "desc_detail",
            "description_long",
            "desc_long",
        }:
            return txn.description_details or txn.description
        if self.value in {"client", "counterparty", "merchant"}:
            return txn.client
        if self.value in {"client_short", "counterparty_short", "merchant_short"}:
            return txn.client_short or txn.client
        if self.value in {
            "payment_method",
            "method",
            "payment_instrument",
            "instrument",
        }:
            return txn.payment_method
        if self.value in {
            "payment_method_short",
            "method_short",
            "payment_instrument_short",
            "payment_instrument_short",
        }:
            return txn.payment_method_short or txn.payment_method
        if self.value in {
            "payment_method_long",
            "method_long",
            "payment_instrument_long",
            "payment_instrument_long",
        }:
            return txn.payment_method_long or txn.payment_method
        if self.value in {"account_id", "account", "acct_id", "acct"}:
            return txn.account_id
        if self.default_to_string:
            return self.value
        raise RuntimeError(f"no such txn property {repr(self.value)}")


@dataclass
class Comparison(BoolExpr):
    lhs: Expr
    comp: Comparator
    rhs: Expr

    def matches(self, txn: Txn) -> bool:
        return self.comp.matches(txn, self.lhs, self.rhs)


@dataclass
class Plus(Expr):
    args: list[Expr]

    def evaluate(self, txn: Txn) -> Any:
        return sum(arg.evaluate(txn) for arg in self.args)


@dataclass
class Times(Expr):
    args: list[Expr]

    def evaluate(self, txn: Txn) -> Any:
        product = 1
        for arg in self.args:
            product *= arg.evaluate(txn)
        return product


@dataclass
class Divide(Expr):
    lhs: Expr
    rhs: Expr

    def evaluate(self, txn: Txn) -> Any:
        return self.lhs.evaluate(txn) / self.rhs.evaluate(txn)


@dataclass
class Negate(Expr):
    arg: Expr

    def evaluate(self, txn: Txn) -> Any:
        return -self.arg.evaluate(txn)


function_table = {
    "abs": abs,
}


@dataclass
class Funcall(Expr):
    funcname: Identifier
    args: list[Expr]

    def evaluate(self, txn: Txn) -> Any:
        return function_table[self.funcname.value](
            *(arg.evaluate(txn) for arg in self.args)
        )


@dataclass
class Value(Expr):
    value: Any

    def evaluate(self, txn: Txn) -> Any:
        return self.value


@dataclass
class FilterOr(BoolExpr):
    exprs: list[BoolExpr]

    def matches(self, txn: Txn):
        return any(expr.matches(txn) for expr in self.exprs)


@dataclass
class FilterAnd(BoolExpr):
    exprs: list[BoolExpr]

    def matches(self, txn: Txn):
        return all(expr.matches(txn) for expr in self.exprs)


@dataclass
class Filter(Operation):
    expr: BoolExpr

    def matches(self, txn: Txn) -> bool:
        return self.expr.matches(txn)

    def apply(self, txns: list[Txn]) -> list[Txn]:
        return [txn for txn in txns if self.matches(txn)]


@dataclass
class Pipeline:
    ops: list[Operation]

    def apply(self, txns: list[Txn]) -> list[Txn]:
        for op in self.ops:
            txns = op.apply(txns)
        return txns


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

    signum = lambda self, args: Value(Decimal(args[0]))

    escstr = lambda self, tok: Value(tok[0].value)
    rawstr = lambda self, tok: Identifier(tok[0].value, default_to_string=True)
    propname = lambda self, tok: Identifier(tok[0].value)

    def date(self, args):
        s = args[0]
        if len(s.split("-")) == 2:
            return datetime.strptime(s, "%Y-%m").date()
        return datetime.strptime(s, "%Y-%m-%d").date()


class Query:
    def __init__(self, q: str):
        self.ast: Pipeline = Transformer().transform(parser.parse(q))

    def apply(self, txns: list[Txn]) -> list[Txn]:
        return self.ast.apply(txns)


q = Query("acct=venmo date>=2024-02")
