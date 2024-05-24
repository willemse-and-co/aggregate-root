from __future__ import annotations

from abc import ABC
from collections.abc import Iterable as IterableCollection
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable
from typing import Iterable as IterableType
from typing import Iterator, Type, TypeVar, Union

from .domain_event import DomainEvent

T = TypeVar("T", bound="DomainEvent")
A = TypeVar("A", bound="AggregateRoot")


class AggregateRoot(ABC):
    """
    Base class for aggregate roots in a domain-driven design context.

    Attributes:
        _id (str): Uniqe identifier for the aggregate.
        _pending_events (list[DomainEvent]): List of domain events that have not yet been persisted.
        _version (int): Version of the aggregate, used for optimistic concurrency control.
        _event_handlers (dict[type, Callable[["AggregateRoot", DomainEvent], None]]): Mapping of event types to handler methods.
    """

    _event_handlers: dict[type, Callable[["AggregateRoot", DomainEvent], None]]

    def __init__(self, id: str) -> None:
        """
        Initialize a new aggregate root with an ID.

        It is recommended to create a factory method for creating new instances of the aggregate.

        Parameters:
            id (str): Unique identifier for the aggregate.

        Example:
            >>> class MyAggregate(AggregateRoot):
            ...     @classmethod
            ...     def create(cls) -> "MyAggregate":
            ...         id = str(uuid4())
            ...         instance = cls(id)  # invoke __init__ method
            ...         instance.produce_events(MyAggregateCreated())
            ...         return instance

        """
        self._id: str = id
        self._pending_events: list[DomainEvent] = []
        self._version: int = 0

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
    def pending_events(self) -> list[DomainEvent]:
        """
        Get the list of pending domain events that have not yet been persisted.

        Returns:
            list[DomainEvent]: The list of pending domain events.
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

    def produce_events(self, *events: DomainEvent) -> None:
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
            *events (DomainEvent): One or more domain events to apply to the aggregate.

        Example:
            >>> class MyAggregate(AggregateRoot):
            ...     @classmethod
            ...     def create(cls) -> "MyAggregate":
            ...         id = str(uuid4())
            ...         instance = cls(id)
            ...         instance.produce_events(MyAggregateCreated())  # produce an event
            ...         return instance

        """
        for event in events:
            self.apply_event(event)
            self._pending_events.append(event)

    def apply_event(self, *events: DomainEvent) -> None:
        """
        Apply one or more events to the aggregate.

        This method is called by produce_events to apply events to the aggregate. apply_event delegates
        to the appropriate event handler method, if one is defined. If no handler is defined, the event
        is passed to the handle_event method, which can be overridden in subclasses to handle events that
        are not otherwise handled by methods decorated with @handles_events.

        apply_event should also be used by event-sourced repositories to reconstitute the state of an
        aggregate from a sequence of persisted events.

        Parameters:
            *events (DomainEvent): One or more domain events to apply to the aggregate.

        Example:
            >>> # Example load() function that reconstitutes an aggregate from a sequence of events
            >>> def load(aggregate_id: str) -> MyAggregate:
            ...     events = load_events(aggregate_id)  # example function that loads events from a database
            ...     aggregate = MyAggregate(aggregate_id)
            ...     aggregate.apply_event(*events)  # apply all previous events to the aggregate
            ...     aggregate.version = len(events)  # set the version number
            ...     return aggregate

        """
        for event in events:
            event_type = type(event)
            if event_type in self._event_handlers:
                handler = self._event_handlers[event_type]
                handler(self, event)
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

        Example:
            >>> # Example save() function that persists the aggregate to a database
            >>> def save(aggregate: MyAggregate) -> None:
            ...     events = aggregate.pending_events
            ...     persist_events(aggregate.aggregate_id, events) # example function that persists events to a database
            ...     aggregate.clear_events()  # clear the pending events
        """
        self._pending_events.clear()

    @classmethod
    def produces_events(
        cls, method: Callable[..., Union[DomainEvent, IterableType[DomainEvent], None]]
    ) -> Callable[..., Union[DomainEvent, IterableType[DomainEvent], None]]:
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

        Example:
            >>> class Product(AggregateRoot):
            ...     @AggregateRoot.produces_events
            ...     def subtract_from_inventory(self, count: int) -> InventoryUpdated:
            ...         if count <= 0:
            ...             raise ValueError("Count must be greater than zero")
            ...         if self.inventory_count < count:
            ...             raise ValueError("Insufficient inventory")
            ...         return InventoryUpdated(self.inventory_count - count)
        """

        @wraps(method)
        def wrapper(
            self: AggregateRoot, *args: Any, **kwargs: Any
        ) -> Union[DomainEvent, IterableType[DomainEvent], None]:
            events = method(self, *args, **kwargs)
            if events is not None:
                if isinstance(events, IterableCollection):
                    self.produce_events(*events)
                else:
                    self.produce_events(events)
            return events

        return wrapper

    @classmethod
    def handles_events(
        cls: Any, event_type: Type[T]
    ) -> Callable[[Callable[[A, T], None]], Callable[[A, T], None]]:
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

        def decorator(handler: Callable[[A, T], None]) -> Callable[[A, T], None]:
            if not hasattr(cls, "_event_handlers") or cls._event_handlers is None:
                cls._event_handlers = {}
            cls._event_handlers[event_type] = handler
            return handler

        return decorator

    def handle_event(self, event: DomainEvent) -> None:
        """
        Handle events that do not have a specific event handler.

        This is a fallback method that can be overridden in subclasses to handle events that are not
        otherwise handled by methods decorated with @handles_events. By default, this method does
        nothing.

        Parameters:
            event (DomainEvent): The domain event to handle.

        Example:
            >>> class MyAggregate(AggregateRoot):
            ...     @AggregateRoot.handles_events(MyEvent)
            ...     def _handle_my_event(self, event: MyEvent):
            ...         # handle MyEvent
            ...
            ...     def handle_event(self, event: DomainEvent):
            ...         if isinstance(event, MyOtherEvent):
            ...             # handle MyOtherEvent
        """
        pass

    @contextmanager
    def flush(self) -> Iterator[list[DomainEvent]]:
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
