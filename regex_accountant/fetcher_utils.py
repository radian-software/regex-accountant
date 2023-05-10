from datetime import datetime
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
