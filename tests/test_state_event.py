from dataclasses import FrozenInstanceError, dataclass
from typing import Optional, override

from pytest import raises

from aggregate_root import Event
from aggregate_root.events import DomainEvent, SourceEventMeta


@dataclass(frozen=True)
class SimpleEvent(Event):
    a: int
    b: str
    c: Optional[str] = None
    d: int = 100


@dataclass(frozen=True)
class AnotherEvent(Event):
    @override
    @classmethod
    def event_type(cls) -> str:
        return "SimpleEvent2"

    a: int


@dataclass(frozen=True)
class SimpleDomainEvent(DomainEvent):
    a: int


def test_event_is_registered():
    assert SimpleEvent.event_type() == "SimpleEvent"
    assert SimpleEvent in SourceEventMeta._registry.values()
    assert AnotherEvent.event_type() == "SimpleEvent2"
    assert AnotherEvent in SourceEventMeta._registry.values()
    assert SourceEventMeta.get_event_type("SimpleEvent") == SimpleEvent
    assert SourceEventMeta.get_event_type("SimpleEvent2") == AnotherEvent


def test_required_fields():
    with raises(TypeError):
        SimpleEvent()  # type: ignore


def test_source_event_creation():
    event = SimpleEvent(5, "test")
    assert event.a == 5
    assert event.b == "test"
    assert event.c is None
    assert event.d == 100
    assert event.event_type() == "SimpleEvent"
    assert event.to_dict() == {"a": 5, "b": "test", "c": None, "d": 100}


def test_source_event_from_dict():
    event = SimpleEvent.from_dict({"a": 5, "b": "test", "d": 200, "x": "extra"})
    assert isinstance(event, SimpleEvent)
    assert event.a == 5
    assert event.b == "test"
    assert event.c is None
    assert event.d == 200


def test_event_immutablility():
    event = SimpleEvent(5, "test")
    with raises(FrozenInstanceError):
        event.a = 10  # type: ignore


def test_unique_event_types():
    class DuplicateEvent(Event):  # type: ignore
        pass

    with raises(ValueError):

        class DuplicateEvent(Event):  # type: ignore
            pass


def test_event_kind_differentiation():
    a = SimpleEvent(5, "test")
    b = SimpleDomainEvent(5)
    assert not isinstance(a, DomainEvent)
    assert isinstance(b, DomainEvent)
