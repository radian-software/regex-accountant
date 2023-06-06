from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import total_ordering
import locale
import typing


def month_sequence(
    start_date: datetime, end_date: datetime
) -> typing.Generator[tuple[int, int], None, None]:
    year, month = start_date.year, end_date.month
    while datetime(year=year, month=month, day=1) < end_date:
        yield year, month
        month += 1
        if month > 12:
            month, year = 1, year + 1


def year_sequence(
    start_date: datetime, end_date: datetime
) -> typing.Generator[int, None, None]:
    year = start_date.year
    while datetime(year=year, month=1, day=1) < end_date:
        yield year
        year += 1


@dataclass
@total_ordering
class CurrencyInfo:

    currency: str
    amount: Decimal

    def __add__(self, other):
        if self.currency != other.currency:
            return NotImplemented
        return CurrencyInfo(currency=self.currency, amount=self.amount + other.amount)

    def __sub__(self, other):
        if self.currency != other.currency:
            return NotImplemented
        return CurrencyInfo(currency=self.currency, amount=self.amount - other.amount)

    def __mul__(self, other):
        if not (isinstance(other, int) or isinstance(other, Decimal)):
            return NotImplemented
        return CurrencyInfo(currency=self.currency, amount=self.amount * other)

    def __round__(self, *args):
        rounded: Decimal = round(self.amount, *args)  # type: ignore
        return CurrencyInfo(currency=self.currency, amount=rounded)

    def __truediv__(self, other):
        if self.currency != other.currency:
            return NotImplemented
        return self.amount / other.amount

    def __le__(self, other):
        if self.currency != other.currency:
            return NotImplemented
        return self.amount < other.amount

    def __abs__(self):
        return CurrencyInfo(currency=self.currency, amount=abs(self.amount))

    @staticmethod
    def sum(currencies):
        assert currencies, "can't sum list of zero currencies"
        gen = iter(currencies)
        total = next(gen)
        for currency in gen:
            total += currency
        return total


def parse_currency(currency: str) -> CurrencyInfo:
    # Todo: support other currencies than USD, this will be needed soon
    assert "$" in currency
    return CurrencyInfo(
        currency="USD",
        amount=Decimal(locale.delocalize(currency.strip().lstrip("$").strip())),
    )


def scale_prices(
    prices: list[CurrencyInfo],
    desired_sum: CurrencyInfo,
    places_to_round_to=2,
) -> list[CurrencyInfo]:
    old_sum = CurrencyInfo.sum(prices)
    ratio = desired_sum / old_sum
    new_prices = [p * ratio for p in prices]
    if places_to_round_to is not None:
        new_prices = [round(p, places_to_round_to) for p in new_prices]
    new_sum = CurrencyInfo.sum(new_prices)
    if new_sum != desired_sum:
        error = new_sum - desired_sum
        largest_price_idx, _ = max(enumerate(new_prices), key=lambda item: abs(item[1]))
        new_prices[largest_price_idx] -= error
    return new_prices
