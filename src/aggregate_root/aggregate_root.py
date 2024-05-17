from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable as IterableCollection
from functools import wraps
from typing import Callable
from typing import Iterable as IterableType

from .domain_event import DomainEvent


class AggregateRoot(ABC):
    _event_handlers: dict[type, Callable[["AggregateRoot", DomainEvent], None]]

    def __init__(self, id: str) -> None:
        self._id: str = id
        self._pending_events: list[DomainEvent] = []
        self._version: int = 0

    @classmethod
    def aggregate_type(cls) -> str:
        return cls.__name__

    @property
    def aggregate_id(self) -> str:
        return self._id

    @property
    def pending_events(self) -> list[DomainEvent]:
        return self._pending_events

    @property
    def pending_event_count(self) -> int:
        return len(self._pending_events)

    @property
    def version(self) -> int:
        return self._version

    @version.setter
    def version(self, value: int) -> None:
        if value < self._version:
            raise ValueError("Version must be greater than or equal to current version")
        self._version = value

    def produce_event(self, *events: DomainEvent) -> None:
        """
        produce_event should be used to apply pending events to the
        aggregate after validating domain invariants.
        """
        for event in events:
            self.apply_event(event)
            self._pending_events.append(event)

    def apply_event(self, event: DomainEvent) -> None:
        """
        apply_event should be used to handle events that have previously been applied to the aggregate.
        Useful for replaying events when the aggregate is loaded from an event store.
        """
        event_type = type(event)
        if event_type in self._event_handlers:
            handler = self._event_handlers[event_type]
            handler(self, event)
        else:
            self.handle_event(event)

    def clear_events(self) -> None:
        self._pending_events.clear()

    @classmethod
    def produces_events(
        cls, method: Callable[..., DomainEvent | IterableType[DomainEvent] | None]
    ):
        @wraps(method)
        def wrapper(self: AggregateRoot, *args, **kwargs):
            events = method(self, *args, **kwargs)
            if events is not None:
                if isinstance(events, IterableCollection):
                    self.produce_event(*events)
                else:
                    self.produce_event(events)
            return events

        return wrapper

    @classmethod
    def handles_events(cls, event_type: type[DomainEvent]):
        def decorator(handler: Callable[["AggregateRoot", DomainEvent], None]):
            if not hasattr(cls, "_event_handlers") or cls._event_handlers is None:
                cls._event_handlers = {}
            cls._event_handlers[event_type] = handler
            return handler

        return decorator

    @abstractmethod
    def handle_event(self, event: DomainEvent) -> None:
        """
        override this method to handle events that are not otherwise
        handled by methods decorated with @handles_events
        """
        pass
