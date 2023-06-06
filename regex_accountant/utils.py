import dataclasses
import typing


def dataclass_to_dict(o: object) -> dict:
    d = {field.name: getattr(o, field.name) for field in dataclasses.fields(o)}
    for k, v in d.items():
        if dataclasses.is_dataclass(v):
            d[k] = dataclass_to_dict(v)
        elif isinstance(v, list):
            v2 = []
            for e in v:
                if dataclasses.is_dataclass(e):
                    e = dataclass_to_dict(e)
                v2.append(e)
            d[k] = v2
    return d


T = typing.TypeVar("T")


def dict_to_dataclass(d: dict, cls: typing.Type[T]) -> T:
    return cls(**d)
