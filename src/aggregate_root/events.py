from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Dict


class SourceEventMeta(type):
    """
    Metaclass for domain events providing a registry of event types.

    This metaclass ensures that domain event classes are uniquely named and registered in the registry.
    The registry is used to look up domain event classes by their event type name.

    Attributes:
        _registry (Dict[str, type]): A dictionary of event type names to domain event classes.
    """

    _registry: Dict[str, type] = {}

    def __new__(
        cls, name: str, bases: tuple, namespace: dict[str, Any]
    ) -> SourceEventMeta:
        """
        Create a new domain event class and register it in the registry.

        Parameters:
            name (str): The name of the class.
            bases (tuple): The base classes of the class.
            namespace (dict): The class attributes.

        Returns:
            SourceEventMeta: The new domain event class.
        """
        new_class = super().__new__(cls, name, bases, namespace)
        event_type = getattr(new_class, "event_type", lambda: name)()
        if name not in ("Event", "DomainEvent"):
            if event_type in cls._registry:
                raise ValueError(
                    f"Event type '{event_type}' is already registered as {cls._registry[name]}"
                )
            cls._registry[event_type] = new_class
        return new_class

    @classmethod
    def get_event_type(cls, event_type: str) -> type[Event] | None:
        """
        Get the domain event class for the given event type name.

        Parameters:
            event_type (str): The event type name.

        Returns:
            type[Event] | None: The domain event class or None if not found.
        """
        return cls._registry.get(event_type)


@dataclass(frozen=True)
class Event(metaclass=SourceEventMeta):
    """
    Base class for aggregate state change events.

    State events are immutable data classes representing a change in state of an aggregate root.
    Each source event class is uniquely named and registered in the event registry.
    """

    @classmethod
    def event_type(cls) -> str:
        """
        Get the unique name of the domain event class.

        Override this method in a subclass to provide a custom event type name.

        Returns:
            str: The unique name of the domain event class.
        """
        return cls.__name__

    @classmethod
    def from_dict(cls, data: dict) -> Event:
        """
        Create a domain event instance from a dictionary of data.

        Parameters:
            data (dict): A dictionary of event data.

        Returns:
            Event: The domain event instance.
        """
        field_names = {f.name for f in fields(cls)}
        filtered_data = {
            key: value for key, value in data.items() if key in field_names
        }
        return cls(**filtered_data)  # type: ignore

    def to_dict(self) -> dict:
        """
        Convert the domain event instance to a dictionary of data.

        Returns:
            dict: A dictionary of event data.
        """
        return self.__dict__


@dataclass(frozen=True)
class DomainEvent(Event):
    """
    Base class for domain events.

    """

    pass
