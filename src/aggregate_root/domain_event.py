from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Union

PrimitiveDict = dict[str, "PrimitiveType"]
PrimitiveList = list["PrimitiveType"]
PrimitiveType = Union[str, int, float, bool, None, PrimitiveDict, PrimitiveList]


class DomainEventMeta(type):
    _registry: dict[str, type] = {}

    def __new__(cls, name: str, bases: tuple, namespace: dict[str, Any]) -> "DomainEventMeta":
        new_class = super().__new__(cls, name, bases, namespace)
        event_type = getattr(new_class, "event_type", None)
        key = name if event_type is None else event_type()
        cls._registry[key] = new_class
        return new_class

    @classmethod
    def get_event_type(cls, event_type: str) -> type["DomainEvent"]:
        return cls._registry[event_type]


@dataclass(frozen=True)
class DomainEvent(metaclass=DomainEventMeta):
    @classmethod
    def event_type(cls) -> str:
        """Ensure domain event classes are uniquely named as the registry is shared across all subclasses."""
        return cls.__name__

    @classmethod
    def from_primitive_dict(cls, data: PrimitiveDict) -> DomainEvent:
        field_names = {f.name for f in fields(cls)}
        filtered_data = {key: value for key, value in data.items() if key in field_names}
        return cls(**filtered_data)

    def to_primitive_dict(self) -> PrimitiveDict:
        return self.__dict__
