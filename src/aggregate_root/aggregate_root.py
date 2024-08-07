from __future__ import annotations

from abc import ABCMeta
from collections.abc import Iterable as IterableCollection
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable
from typing import Iterable as IterableType
from typing import Iterator, Type, TypeVar, Union

from .events import Event

T = TypeVar("T", bound="Event")
A = TypeVar("A", bound="AggregateRoot")


class AggregateMeta(ABCMeta):
    def __call__(cls, *args, **kwargs):
        instance = super().__call__(*args, **kwargs)
        instance._collect_handlers()
        return instance


class AggregateRoot(metaclass=AggregateMeta):
    """
    Base class for aggregate roots in a domain-driven design context.

    Attributes:
        _id (str): Unique identifier for the aggregate.
        _pending_events (list[Event]): List of domain events that have not yet been persisted.
        _version (int): Version of the aggregate, used for optimistic concurrency control.
        _event_handlers (dict[type, Callable[["AggregateRoot", Event], None]]): Mapping of event types to handler methods.
    """

    def __init__(self, id: str) -> None:
        """
        Initialize a new aggregate root with an ID.

        It is recommended to create a factory method for creating new instances of the aggregate.

        Parameters:
            id (str): Unique identifier for the aggregate.
        """
        self._id: str = id
        self._pending_events: list[Event] = []
        self._version: int = 0
        self._event_handlers: dict[
            Type[Event], Callable[["AggregateRoot", Event], None]
        ] = {}

    def _collect_handlers(self):
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, "__event_type__"):
                self._event_handlers[getattr(attr, "__event_type__")] = attr

    @classmethod
    def aggregate_type(cls) -> str:
        """
        Get the name of the aggregate type.

        Returns:
            str: The name of the aggregate type.
        """
        return cls.__name__

    @property
    def aggregate_id(self) -> str:
        """
        Get the unique identifier for the aggregate.

        Returns:
            str: The unique identifier for the aggregate.
        """
        return self._id

    @property
    def pending_events(self) -> list[Event]:
        """
        Get the list of pending domain events that have not yet been persisted.

        Returns:
            list[Event]: The list of pending domain events.
        """
        return self._pending_events

    @property
    def version(self) -> int:
        """
        Get the version number of the aggregate.

        Returns:
            int: The version number of the aggregate.
        """
        return self._version

    @version.setter
    def version(self, value: int) -> None:
        """
        Set the version number of the aggregate.

        Parameters:
            value (int): The new version number.

        Raises:
            ValueError: If the new version number is less than the current version.
        """
        if value < self._version:
            raise ValueError("Version must be greater than or equal to current version")
        self._version = value

    def produce_events(self, *events: Event) -> None:
        """
        Produce one or more events and apply them to the aggregate.

        After validating domain invariants, methods of AggregateRoot subclasses will
        typically produce domain events that represent changes to the state of the
        aggregate. These events are then applied to the aggregate. Note, methods that
        produce events should not have side effects beyond producing events. I.e., they
        should not modify the state of the aggregate directly – that should be done in
        the event handlers.

        The most common use case for this method is to apply *Created events in factory
        methods that create new instances of the aggregate. In most other cases, the
        produces_events decorator can be used instead.

        See also: produces_events decorator

        Parameters:
            *events (Event): One or more domain events to apply to the aggregate.
        """
        for event in events:
            self.apply_event(event)
            self._pending_events.append(event)

    def apply_event(self, *events: Event) -> None:
        """
        Apply one or more events to the aggregate.

        This method is called by produce_events to apply events to the aggregate. apply_event delegates
        to the appropriate event handler method, if one is defined. If no handler is defined, the event
        is passed to the handle_event method, which can be overridden in subclasses to handle events that
        are not otherwise handled by methods decorated with @handles_events.

        apply_event should also be used by event-sourced repositories to reconstitute the state of an
        aggregate from a sequence of persisted events.

        Parameters:
            *events (Event): One or more domain events to apply to the aggregate.
        """
        for event in events:
            event_type = type(event)
            handler = self._event_handlers.get(event_type, None)
            if handler:
                print("**************")
                handler(event)
            else:
                self.handle_event(event)

    def clear_events(self) -> None:
        """
        Clear the list of pending events.

        This method is typically called after persisting the aggregate to a database.
        It is only necessary to call this method if the instance is to be reused after
        persisting the events. If the instance is not reused, the pending events will
        be garbage collected when the instance is destroyed.

        See also: flush context manager
        """
        self._pending_events.clear()

    @staticmethod
    def produces_events(
        method: Callable[..., Union[Event, IterableType[Event], None]]
    ) -> Callable[..., Union[Event, IterableType[Event], None]]:
        """
        Decorator to mark a method as producing domain events.

        This decorator is used to mark methods that produce domain events. When the method is called,
        the events produced by the method are applied to the aggregate. The method should not have
        side effects beyond producing events. I.e., it should not modify the state of the aggregate
        directly – that should be done in the event handlers.

        Methods that produce events should validate domain invariants before producing events. If
        an invariant is violated, the method should raise an exception.

        Parameters:
            method (Callable): The method that produces domain events.

        Returns:
            Callable: The decorated method.
        """

        @wraps(method)
        def wrapper(
            self: "AggregateRoot", *args: Any, **kwargs: Any
        ) -> Union[Event, IterableType[Event], None]:
            events = method(self, *args, **kwargs)
            if events:
                if isinstance(events, IterableCollection):
                    self.produce_events(*events)
                else:
                    self.produce_events(events)
            return events

        return wrapper

    @staticmethod
    def handles_events(event_type: Type[T]):
        """
        Decorator to mark a method as handling specific domain events.

        This decorator is used to mark methods that handle specific domain events. When an event of the
        specified type is applied to the aggregate, the method is called with the event as an argument.
        The method should update the state of the aggregate based on the event.

        Event handlers should not be able to raise exceptions or otherwise fail as this would leave the
        aggregate in an inconsistent state. The responsibility for validating domain invariants and raising
        exceptions lies with the methods that produce events. This allows for backward compatibility when
        business rules change.

        Parameters:
            event_type (Type): The type of event to handle.

        Returns:
            Callable: The decorator.
        """

        def decorator(func: Callable[[A, T], None]):
            setattr(func, "__event_type__", event_type)
            return func

        return decorator

    def handle_event(self, event: Event) -> None:
        """
        Handle events that do not have a specific event handler.

        This is a fallback method that can be overridden in subclasses to handle events that are not
        otherwise handled by methods decorated with @handles_events. By default, this method does
        nothing.

        Parameters:
            event (Event): The domain event to handle.
        """
        pass

    @contextmanager
    def flush(self) -> Iterator[list[Event]]:
        """
        Context manager to flush (process and clear) pending events.

        This context manager can be used to clear the list of pending events after a block of code.
        If an exception is raised inside the block, the pending events will not be cleared. If no
        exception is raised, the pending events will be cleared after the block.

        The most likely use case for this context manager is in the save method of a repository class
        that persists the aggregate to a database. The pending events should be cleared after the
        aggregate is successfully persisted.

        Example:
            >>> class MyRepository:
            ...     def save(self, aggregate: MyAggregate) -> None:
            ...         with aggregate.flush() as events:
            ...             tx = self.db.begin()
            ...             try:
            ...                 self._save_events(tx, aggregate.aggregate_id, events) # example method that saves events to a database
            ...                 tx.commit()
            ...             except:
            ...                 tx.rollback()
            ...                 raise
        """
        yield self._pending_events
        self.clear_events()
