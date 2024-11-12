from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import total_ordering
from pathlib import Path
import re
from typing import Any, Tuple

import lark

from regex_accountant.postprocess import ExtTransaction as Txn
from regex_accountant.utils import decode_escapes


THIS_DIR = Path(__file__).resolve().parent


with open(THIS_DIR / "query.lark") as f:
    parser = lark.Lark(f, ambiguity="resolve")


@total_ordering
@dataclass
class QueryDate:
    year: int
    month: int | None = None  # 1-12
    day: int | None = None  # 1-31

    @staticmethod
    def parse(s: str) -> QueryDate:
        return QueryDate(*map(int, s.split("-")))

    # Custom comparison methods. They work the way normal comparison
    # methods do when comparing against another QueryDate object. But
    # you can also compare against a datetime or date object and it
    # will do a looser comparison, like QueryDate.parse("2012-02")
    # will compare equal to date(year=2012, month=2, day=d) for any
    # value d.

    def __eq__(self, o: QueryDate | datetime | date) -> bool:
        if self.year != o.year:
            return False
        if self.month not in {None, o.month}:
            return False
        if self.day not in {None, o.day}:
            return False
        return True

    def __le__(self, o: QueryDate | datetime | date) -> bool:
        if self.year > o.year:
            return False
        if self.month and o.month and self.month > o.month:
            return False
        if self.day and o.day and self.day > o.day:
            return False
        return True


@dataclass
class Operation(ABC):
    @abstractmethod
    def apply(self, txns: list[Txn], cfg: RulesConfig) -> list[Txn]:
        raise NotImplementedError


@dataclass
class BoolExpr(ABC):
    @abstractmethod
    def matches(self, txn: Txn, cfg: RulesConfig) -> bool:
        raise NotImplementedError


@dataclass
class Expr(ABC):
    def evaluate(self, txn: Txn, cfg: RulesConfig) -> Any:
        pass


@dataclass
class Comparator(ABC):
    @abstractmethod
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr, cfg: RulesConfig) -> bool:
        raise NotImplementedError

    @staticmethod
    def preprocess(lhs: Any, rhs: Any, *ops: str) -> Tuple[Any, Any]:
        if "casefold" in ops:
            if isinstance(lhs, str) and isinstance(rhs, str):
                lhs = lhs.casefold()
                rhs = rhs.casefold()
        if "normdate" in ops:
            if isinstance(lhs, datetime) and isinstance(rhs, Decimal):
                rhs = QueryDate(int(rhs))
            if isinstance(rhs, datetime) and isinstance(lhs, Decimal):
                lhs = QueryDate(int(lhs))
        return lhs, rhs


class Equals(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr, cfg: RulesConfig) -> bool:
        l, r = Comparator.preprocess(
            lhs.evaluate(txn, cfg), rhs.evaluate(txn, cfg), "normdate"
        )
        return l == r


class EqualsIgnoringCase(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr, cfg: RulesConfig) -> bool:
        l, r = Comparator.preprocess(
            lhs.evaluate(txn, cfg), rhs.evaluate(txn, cfg), "casefold", "normdate"
        )
        return l == r


class Contains(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr, cfg: RulesConfig) -> bool:
        l, r = Comparator.preprocess(lhs.evaluate(txn, cfg), rhs.evaluate(txn, cfg))
        return r in l


class ContainsIgnoringCase(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr, cfg: RulesConfig) -> bool:
        l, r = Comparator.preprocess(
            lhs.evaluate(txn, cfg), rhs.evaluate(txn, cfg), "casefold"
        )
        return r in l


class LessThan(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr, cfg: RulesConfig) -> bool:
        l, r = Comparator.preprocess(
            lhs.evaluate(txn, cfg), rhs.evaluate(txn, cfg), "normdate"
        )
        return l < r


class LessThanOrEqual(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr, cfg: RulesConfig) -> bool:
        l, r = Comparator.preprocess(
            lhs.evaluate(txn, cfg), rhs.evaluate(txn, cfg), "normdate"
        )
        return l <= r


class GreaterThan(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr, cfg: RulesConfig) -> bool:
        l, r = Comparator.preprocess(
            lhs.evaluate(txn, cfg), rhs.evaluate(txn, cfg), "normdate"
        )
        return l > r


class GreaterThanOrEqual(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr, cfg: RulesConfig) -> bool:
        l, r = Comparator.preprocess(
            lhs.evaluate(txn, cfg), rhs.evaluate(txn, cfg), "normdate"
        )
        return l >= r


class MatchesRegex(Comparator):
    def matches(self, txn: Txn, lhs: Expr, rhs: Expr, cfg: RulesConfig) -> bool:
        l, r = Comparator.preprocess(lhs.evaluate(txn, cfg), rhs.evaluate(txn, cfg))
        return re.fullmatch(r, l)


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

    def evaluate_fallback(self) -> Any:
        return None

    def evaluate(self, txn: Txn, cfg: RulesConfig) -> Any:
        if self.value in {"date", "date_posted", "posted"}:
            return txn.sort_date_posted
        if self.value in {"date_cleared", "cleared"}:
            return txn.sort_date_cleared
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
        if self.value in {"source", "src", "fetcher"}:
            return txn.account
        if self.value in cfg.field_lookup:
            field_name = cfg.field_lookup[self.value]
            return txn.custom_fields.get(field_name, "")
        if res := self.evaluate_fallback():
            return res
        raise RuntimeError(f"no such txn property {repr(self.value)}")


class IdentifierOrString(Identifier):
    def evaluate_fallback(self) -> Any:
        return self.value


@dataclass
class Comparison(BoolExpr):
    lhs: Expr
    comp: Comparator
    rhs: Expr

    def matches(self, txn: Txn, cfg: RulesConfig) -> bool:
        return self.comp.matches(txn, self.lhs, self.rhs, cfg)


@dataclass
class Plus(Expr):
    args: list[Expr]

    def evaluate(self, txn: Txn, cfg: RulesConfig) -> Any:
        return sum(arg.evaluate(txn, cfg) for arg in self.args)


@dataclass
class Times(Expr):
    args: list[Expr]

    def evaluate(self, txn: Txn, cfg: RulesConfig) -> Any:
        product = 1
        for arg in self.args:
            product *= arg.evaluate(txn, cfg)
        return product


@dataclass
class Divide(Expr):
    lhs: Expr
    rhs: Expr

    def evaluate(self, txn: Txn, cfg: RulesConfig) -> Any:
        return self.lhs.evaluate(txn, cfg) / self.rhs.evaluate(txn, cfg)


@dataclass
class Negate(Expr):
    arg: Expr

    def evaluate(self, txn: Txn, cfg: RulesConfig) -> Any:
        return -self.arg.evaluate(txn, cfg)


function_table = {
    "abs": abs,
}


@dataclass
class Funcall(Expr):
    funcname: Identifier
    args: list[Expr]

    def evaluate(self, txn: Txn, cfg: RulesConfig) -> Any:
        return function_table[self.funcname.value](
            *(arg.evaluate(txn, cfg) for arg in self.args)
        )


@dataclass
class Value(Expr):
    value: Any

    def evaluate(self, txn: Txn, cfg: RulesConfig) -> Any:
        return self.value


@dataclass
class FilterOr(BoolExpr):
    exprs: list[BoolExpr]

    def matches(self, txn: Txn, cfg: RulesConfig):
        return any(expr.matches(txn, cfg) for expr in self.exprs)


@dataclass
class FilterAnd(BoolExpr):
    exprs: list[BoolExpr]

    def matches(self, txn: Txn, cfg: RulesConfig):
        return all(expr.matches(txn, cfg) for expr in self.exprs)


@dataclass
class FilterNot(BoolExpr):
    expr: BoolExpr

    def matches(self, txn: Txn, cfg: RulesConfig):
        return not self.expr.matches(txn, cfg)


@dataclass
class Filter(Operation):
    expr: BoolExpr

    def matches(self, txn: Txn, cfg: RulesConfig) -> bool:
        return self.expr.matches(txn, cfg)

    def apply(self, txns: list[Txn], cfg: RulesConfig) -> list[Txn]:
        return [txn for txn in txns if self.matches(txn, cfg)]


@dataclass
class Sort(Operation):
    expr: Expr
    reverse: bool

    def apply(self, txns: list[Txn], cfg: RulesConfig) -> list[Txn]:
        return list(
            sorted(
                txns, key=lambda obj: self.expr.evaluate(obj, cfg), reverse=self.reverse
            )
        )


@dataclass
class Setter:
    field: Identifier
    value: Expr


@dataclass
class Set(Operation):
    setters: list[Setter]

    def apply(self, txns: list[Txn], cfg: RulesConfig) -> list[Txn]:
        for setter in self.setters:
            assert setter.field.value in cfg.field_lookup, setter.field
        for txn in txns:
            for setter in self.setters:
                txn.custom_fields[
                    cfg.field_lookup[setter.field.value]
                ] = setter.value.evaluate(txn, cfg)
        return txns


@dataclass
class Pipeline:
    ops: list[Operation]

    def apply(self, txns: list[Txn], cfg: RulesConfig) -> list[Txn]:
        for op in self.ops:
            txns = op.apply(txns, cfg)
        return txns


class Transformer(lark.Transformer):
    pipeline = Pipeline
    op_filter = lambda self, args: Filter(args[0])
    op_sort = lambda self, args: Sort(
        args[0], args[1].value == "desc" if len(args) > 1 else False
    )
    op_set = lambda self, args: Set(args)

    def setter(self, args):
        return Setter(args[0], args[1])

    def filter(self, conjs):
        return FilterOr(conjs)

    def filter_conj(self, atoms):
        return FilterAnd(atoms)

    def filt_comp(self, args):
        if args[1] is None:
            return args[0]
        lhs, comp, rhs = args
        invert = False
        opstr = comp.value
        if opstr.startswith("!"):
            opstr = opstr[1:]
            invert = True
        expr = Comparison(lhs, comparator_table[opstr], rhs)
        if invert:
            expr = FilterNot(expr)
        return expr

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

    def expr_func(self, args):
        return Funcall(args[0], args[1:])

    signum = lambda self, args: Value(Decimal(args[0]))

    string = lambda self, tok: Value(tok[0].value)
    escstr = lambda self, tok: Value(decode_escapes(tok[0].value)[1:-1])
    string_or_ident = lambda self, tok: IdentifierOrString(tok[0].value)
    ident = lambda self, tok: Identifier(tok[0].value)

    def date(self, args):
        return Value(QueryDate.parse(args[0]))


class Query:
    def __init__(self, q: str):
        self.ast: Pipeline = Transformer().transform(parser.parse(q))

    def apply(self, txns: list[Txn], cfg: RulesConfig) -> list[Txn]:
        return self.ast.apply(txns, cfg)


from regex_accountant.postprocess import RulesConfig
