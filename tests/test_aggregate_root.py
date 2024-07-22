from dataclasses import dataclass
from typing import Union
from uuid import UUID, uuid4

from pytest import raises

from aggregate_root import AggregateRoot, Event


@dataclass(frozen=True)
class ExampleCreated(Event):
    pass


@dataclass(frozen=True)
class ExampleValueUpdated(Event):
    value: int


@dataclass(frozen=True)
class ExampleLocked(Event):
    pass


@dataclass(frozen=True)
class ExampleUnlocked(Event):
    pass


class ExampleAggregateRoot(AggregateRoot):
    def __init__(self, id: str):
        super().__init__(id)
        self._value = 0
        self._locked = False

    @classmethod
    def create(cls) -> "ExampleAggregateRoot":
        id = str(uuid4())
        instance = cls(id)
        instance.produce_events(ExampleCreated())
        return instance

    @property
    def value(self):
        return self._value

    @AggregateRoot.produces_events
    def add(self, value: int) -> ExampleValueUpdated:
        if self._locked:
            raise ValueError("Aggregate is locked")
        if isinstance(value, int):
            return ExampleValueUpdated(self._value + value)
        raise ValueError("Value must be an integer")

    @AggregateRoot.produces_events
    def toggle_lock(self) -> Union[ExampleLocked, ExampleUnlocked]:
        if self._locked:
            return ExampleUnlocked()
        return ExampleLocked()

    @AggregateRoot.handles_events(ExampleValueUpdated)
    def _handle_value_updated(self, event: ExampleValueUpdated):
        self._value = event.value

    def handle_event(self, event: Event) -> None:
        if isinstance(event, ExampleLocked):
            self._locked = True
        elif isinstance(event, ExampleUnlocked):
            self._locked = False


def test_example_aggregate_root_create():
    aggregate = ExampleAggregateRoot.create()
    assert aggregate.pending_events == [ExampleCreated()]
    assert isinstance(aggregate.aggregate_id, str)
    assert isinstance(UUID(aggregate.aggregate_id), UUID)
    assert aggregate.value == 0


def test_example_aggregate_root_add():
    aggregate = ExampleAggregateRoot.create()
    assert aggregate.pending_events == [ExampleCreated()]
    aggregate.add(5)
    assert aggregate.value == 5
    assert aggregate.pending_events == [ExampleCreated(), ExampleValueUpdated(5)]
    aggregate.add(3)
    assert aggregate.value == 8
    assert aggregate.pending_events == [
        ExampleCreated(),
        ExampleValueUpdated(5),
        ExampleValueUpdated(8),
    ]
    with raises(ValueError):
        aggregate.add("test")  # type: ignore
    aggregate.clear_events()
    assert aggregate.pending_events == []


def test_apply_event():
    id = "94ce0dd9-a4aa-4f2c-8513-b59ca2527806"
    aggregate = ExampleAggregateRoot(id)
    aggregate.apply_event(
        ExampleCreated(), ExampleValueUpdated(5), ExampleValueUpdated(10)
    )
    assert aggregate.pending_events == []
    assert aggregate.value == 10
    assert aggregate._locked is False
    aggregate.apply_event(ExampleLocked())
    assert aggregate._locked is True
    with raises(ValueError):
        aggregate.add(1)


def test_flush():
    aggregate = ExampleAggregateRoot.create()
    aggregate.add(5)
    aggregate.toggle_lock()
    assert aggregate.pending_events == [
        ExampleCreated(),
        ExampleValueUpdated(5),
        ExampleLocked(),
    ]
    with aggregate.flush() as events:
        assert events == [ExampleCreated(), ExampleValueUpdated(5), ExampleLocked()]
    assert aggregate.pending_events == []
    with raises(ValueError):
        aggregate.add(3)
    aggregate.toggle_lock()
    assert aggregate.pending_events == [ExampleUnlocked()]
    with raises(ValueError):
        with aggregate.flush() as events:
            raise ValueError("Prevent clearing events")
    assert aggregate.pending_events == [ExampleUnlocked()]
