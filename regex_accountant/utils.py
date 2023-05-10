import dataclasses
import typing


def dataclass_to_dict(o: object) -> dict:
    return {field.name: getattr(o, field.name) for field in dataclasses.fields(o)}


T = typing.TypeVar("T")


def dict_to_dataclass(d: dict, cls: typing.Type[T]) -> T:
    return cls(**d)
