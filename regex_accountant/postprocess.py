from __future__ import annotations

from dataclasses import dataclass, field
import re
from uuid import UUID

from regex_accountant.fetcher_api import Transaction
from regex_accountant.utils import nudge_date


@dataclass
class ExtTransaction(Transaction):
    index: int = -1
    account: str = ""
    custom_fields: dict[str, str] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        s = self.description or self.description_short or self.description_details
        if part := (self.client or self.client_short):
            if self.amount > 0:
                s += f" to {part}"
            else:
                s += f" from {part}"
        if part := (
            self.payment_method or self.payment_method_short or self.payment_method_long
        ):
            s += f" via {part}"
        return s

    @property
    def sort_date_posted(self):
        return nudge_date(super().sort_date_posted, self.index)

    @property
    def sort_date_cleared(self):
        return nudge_date(super().sort_date_cleared, self.index)


@dataclass
class Rule:

    id: UUID
    query: Query

    @staticmethod
    def fromjson(j: dict) -> Rule:
        return Rule(id=UUID(j["id"]), query=Query(j["query"]))


@dataclass
class RulesConfig:

    redaction_patterns: list[str]
    redaction_regex: re.Pattern

    custom_fields: set[str]
    field_lookup: dict[str, str]

    rules: list[Rule]

    @staticmethod
    def fromjson(j: dict) -> RulesConfig:
        patterns = j.get("redaction", {}).get("patterns", [])
        field_lookup = {
            item: key
            for key, val in j.get("fields", {}).items()
            for item in [key, *val["aliases"]]
        }
        c = RulesConfig(
            redaction_patterns=patterns,
            redaction_regex=re.compile("|".join(f"({pat})" for pat in patterns))
            if patterns
            else re.compile(r"\A(?!x)x"),
            custom_fields=set(field_lookup.values()),
            field_lookup=field_lookup,
            rules=[Rule.fromjson(r) for r in j.get("rules", [])],
        )
        return c


from regex_accountant.query import Query
