from datetime import datetime, timedelta
from typing import TypeVar

import dataclass_wizard as dw


T = TypeVar("T")


def prune_empty(obj: T) -> T:
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if not v:
                obj.pop(k)
                continue
            obj[k] = prune_empty(obj[k])
        return obj
    if isinstance(obj, list):
        return [prune_empty(elt) for elt in obj]  # type: ignore
    return obj


# https://github.com/rnag/dataclass-wizard/issues/92
def asdict(obj, prune=False) -> dict:
    dw.DumpMeta(key_transform="SNAKE").bind_to(obj.__class__)
    d = dw.asdict(obj)
    if prune:
        d = prune_empty(d)
    return d


def asdate(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def normalize_date(dt: datetime) -> datetime:
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        return dt
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        dt = dt.replace(hour=12)
    return dt.astimezone()
