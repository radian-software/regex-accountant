import codecs
from datetime import datetime, timedelta
import re
from typing import TypeVar

import mashumaro.codecs.basic as basic_codec
from mashumaro.dialect import Dialect
from mashumaro.types import SerializationStrategy

T = TypeVar("T")


class DateTimeSerializationStrategy(SerializationStrategy):
    def serialize(self, value: datetime) -> str:
        return value.isoformat()

    def deserialize(self, value: str) -> datetime:
        return datetime.fromisoformat(value.removesuffix("Z"))


class CustomDialect(Dialect):
    def __init__(self, prune: bool = False):
        if prune:
            self.omit_default = True
        self.serialization_strategy = {
            datetime: DateTimeSerializationStrategy(),
        }


def obj_to_dict(obj, prune=False, _encoder_cache={}):
    if not (encoder := _encoder_cache.get((obj.__class__, prune))):
        encoder = basic_codec.BasicEncoder(
            obj.__class__, default_dialect=CustomDialect(prune)  # type: ignore
        )
        _encoder_cache[obj.__class__, prune] = encoder
    return encoder.encode(obj)


def dict_to_obj(cls, d, _decoder_cache={}):
    if not (decoder := _decoder_cache.get(cls)):
        decoder = basic_codec.BasicDecoder(cls, default_dialect=CustomDialect())  # type: ignore
        _decoder_cache[cls] = decoder
    return decoder.decode(d)


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


def asdate(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def normalize_date(dt: datetime) -> datetime:
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        return dt
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        dt = dt.replace(hour=12)
    return dt.astimezone()


# https://stackoverflow.com/a/24519338
ESCAPE_SEQUENCE_RE = re.compile(
    r"""
    ( \\U........      # 8-digit hex escapes
    | \\u....          # 4-digit hex escapes
    | \\x..            # 2-digit hex escapes
    | \\[0-7]{1,3}     # Octal escapes
    | \\N\{[^}]+\}     # Unicode characters by name
    | \\[\\'"abfnrtv]  # Single-character escapes
    )""",
    re.UNICODE | re.VERBOSE,
)


def decode_escapes(s):
    def decode_match(match):
        try:
            return codecs.decode(match.group(0), "unicode-escape")
        except UnicodeDecodeError:
            # In case we matched the wrong thing after a double-backslash
            return match.group(0)

    return ESCAPE_SEQUENCE_RE.sub(decode_match, s)
