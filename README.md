# Aggregate Root

Aggregate Root is a Python library that provides a base implementation for aggregate roots and domain events in a Domain-Driven Design (DDD) context. This library simplifies the creation and management of aggregate roots and domain events, enabling developers to focus on business logic and domain rules.

## Installation
You can install the `aggregate-root` library from PyPI using pip:

```bash
pip install aggregate-root
```

## Usage

### `AggregateRoot` and `Event`

`AggregateRoot` is the base class for aggregate roots, and `Event` is the base class for state events produced by command methods on AggregateRoots. Together, they enable the creation and management of Domain-Driven Design (DDD) aggregates.

#### Example
```python
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from aggregate_root import AggregateRoot, Event

# Domain Events (should be idempotent, past-tense verbs)
# It's not necessary to include the aggregate ID in the event payload
# as an aggregate's ID is not permitted to change over the course of
# its life. When persisting state or publishing the events, the aggregate
# ID should be obtained from the aggregate instance itself.


# In this example, a design choice was made to exclude initial state from
# the BookCreated event, in favour of producing multiple events in the
# Book aggregate's factory method.

@dataclass(frozen=True)
class BookCreated(Event):
    pass


@dataclass(frozen=True)
class BookTitleUpdated(Event):
    title: str


@dataclass(frozen=True)
class BookAuthorUpdated(Event):
    author: str


@dataclass(frozen=True)
class BookYearPublishedUpdated(Event):
    year_published: int


@dataclass(frozen=True)
class CopyAdded(Event):
    barcode: str
    date: datetime


@dataclass(frozen=True)
class CopyRemoved(Event):
    barcode: str
    date: datetime


@dataclass(frozen=True)
class CopyBorrowed(Event):
    barcode: str
    date: datetime
    borrower_id: str
    due_at: datetime


@dataclass(frozen=True)
class CopyReturned(Event):
    barcode: str
    date: datetime


# The Book aggregate is defined by a Book AggregateRoot that holds reference
# to zero or more BookCopy instances. The idea being, the root entity describes
# the common publication information and the BookCopy holds information 
# pertaining to a specific physical instance. This makes sense within the
# inventory bounded context of a library's inventory management subdomain.

class Book(AggregateRoot):
    def __init__(self, isbn: str):
        super().__init__(id=isbn)
        self._copies: list[BookCopy] = []
        self._title: str = ""
        self._author: str = ""
        self._year_published: int = 0

    @property
    def title(self):
        return self._title

    @property
    def author(self):
        return self._author

    @property
    def year_published(self):
        return self._year_published

    @property
    def copies(self):
        return self._copies

    @classmethod
    def create(cls, isbn: str, title: str, author: str, year_published: int) -> "Book":
        """
        Factory method to create a new book.
        """
        if not re.match(r"^\d{13}$", isbn):
            raise ValueError("ISBN must be 13 digits")
        if not title:
            raise ValueError("Title cannot be empty")
        if not author:
            raise ValueError("Author cannot be empty")
        if year_published < 0 or year_published > datetime.now().year:
            raise ValueError("Invalid year published")

        instance = cls(isbn)

        # Produce multiple events on create.
        # By not including initial state in the BookCreated event, we allow for each piece of
        # data in the aggregate to be represented by a single event type only. This may be
        # helpful to external event consumers (like read model updaters, or other microservices).
        instance.produce_events(
            BookCreated(),
            BookTitleUpdated(title),
            BookAuthorUpdated(author),
            BookYearPublishedUpdated(year_published),
        )
        return instance

    # Methods decorated with @AggregateRoot.produces_events should not directly affect state.
    # This is where domain invariants and business rules should be validated before returning
    # one or more Event subclass instances.

    @AggregateRoot.produces_events
    def add_copy(self, barcode: str) -> CopyAdded:
        """
        Add a copy of the book
        """
        if not barcode:
            raise ValueError("Barcode cannot be empty")
        if any(copy.barcode == barcode for copy in self._copies):
            raise ValueError("Copy already exists")
        return CopyAdded(barcode, datetime.now())

    @AggregateRoot.produces_events
    def update_title(self, title: str) -> BookTitleUpdated:
        """
        Update the title of the book
        """
        if not title:
            raise ValueError("Title cannot be empty")
        return BookTitleUpdated(title)

    @AggregateRoot.produces_events
    def update_author(self, author: str) -> BookAuthorUpdated:
        """
        Update the author of the book
        """
        if not author:
            raise ValueError("Author cannot be empty")
        return BookAuthorUpdated(author)

    @AggregateRoot.produces_events
    def update_year_published(self, year_published: int) -> BookYearPublishedUpdated:
        """
        Update the year published of the book
        """
        if year_published < 0 or year_published > datetime.now().year:
            raise ValueError("Invalid year published")
        return BookYearPublishedUpdated(year_published)

    @AggregateRoot.produces_events
    def remove_copy(self, barcode: str) -> CopyRemoved:
        """
        Remove a copy of the book
        """
        for copy in self._copies:
            if copy.barcode == barcode:
                return CopyRemoved(barcode, datetime.now())
        raise ValueError("Copy not found")

    @AggregateRoot.produces_events
    def borrow_copy(self, barcode: str, borrower_id: str) -> CopyBorrowed:
        """
        Borrow a copy of the book
        """
        for copy in self._copies:
            if copy.barcode == barcode:
                if copy.borrowed:
                    raise ValueError("Copy is already borrowed")
                now = datetime.now()
                due_date = now + timedelta(days=14)
                return CopyBorrowed(barcode, now, borrower_id, due_date)
        raise ValueError("Copy not found")

    @AggregateRoot.produces_events
    def return_copy(self, barcode: str) -> CopyReturned:
        """
        Return a copy of the book
        """
        for copy in self._copies:
            if copy.barcode == barcode:
                if not copy.borrowed:
                    raise ValueError("Copy is not borrowed")
                return CopyReturned(barcode, datetime.now())
        raise ValueError("Copy not found")


    # Methods decorated with @AggregateRoot.handles_events are responsible for updating aggregate
    # state. They must not raise any exceptions. This allows for backwards compatibility in
    # event-sourced systems that rehydrate aggregates from an event store using 
    # AggregateRoot.apply_event() as opposed to setting state from a simple CRUD data model.
    # I.e., if business logic changes over time, we do not want historical events failing to be
    # applied when loading an aggregate that was previously updated using old business logic.

    @AggregateRoot.handles_events(BookTitleUpdated)
    def _handle_book_title_updated(self, event: BookTitleUpdated):
        self._title = event.title

    @AggregateRoot.handles_events(BookAuthorUpdated)
    def _handle_book_author_updated(self, event: BookAuthorUpdated):
        self._author = event.author

    @AggregateRoot.handles_events(BookYearPublishedUpdated)
    def _handle_book_year_published_updated(self, event: BookYearPublishedUpdated):
        self._year_published = event.year_published

    @AggregateRoot.handles_events(CopyAdded)
    def _handle_copy_added(self, event: CopyAdded):
        self._copies.append(BookCopy(event.barcode))

    @AggregateRoot.handles_events(CopyRemoved)
    def _handle_copy_removed(self, event: CopyRemoved):
        self._copies = [copy for copy in self._copies if copy.barcode != event.barcode]

    @AggregateRoot.handles_events(CopyBorrowed)
    def _handle_copy_borrowed(self, event: CopyBorrowed):
        for copy in self._copies:
            if copy.barcode == event.barcode:
                copy.check_out(event.borrower_id)

    @AggregateRoot.handles_events(CopyReturned)
    def _handle_copy_returned(self, event: CopyReturned):
        for copy in self._copies:
            if copy.barcode == event.barcode:
                copy.check_in()


# BookCopy is part of the Book aggregate, but is not a subclass of AggregateRoot.
# this is because in DDD, all interactions with a domain aggregate must come through the root.
# I.e., The Book AggregateRoot is responsible for managing it's BookCopy instances.
# A domain aggregate is a transactional boundary. Whenever an interface wishes to execute a
# command that impacts a book copy, it must load the entire Book aggregate and subsequently
# save the entire aggregate in a single transaction.
class BookCopy:
    def __init__(self, barcode: str):
        self._barcode: str = barcode
        self.borrower_id: Optional[str] = None

    def check_out(self, borrower_id: str):
        self.borrower_id = borrower_id

    def check_in(self):
        self.borrower_id = None

    @property
    def borrowed(self):
        return self.borrower_id is not None

    @property
    def barcode(self):
        return self._barcode


# example usage:
# In real-world applications, interactions with the domain would come through application
# services and persistence would be abstracted via repositories.

# Use the factory method to create a new book record
book = Book.create("9781617294549", "Microservices Patterns", "Chris Richardson", 2019)

# Add some physical copies
book.add_copy("BARCODE_1")
book.add_copy("BARCODE_2")

# Borrow a copy
book.borrow_copy("BARCODE_1", "USER_1")

# Return a copy
book.return_copy("BARCODE_1")

# Remove a copy from the shelves
book.remove_copy("BARCODE_1")

# In a repository, obtain the pending events for saving
events = book.pending_events
# ... save the events or use the events to update the data model
book.clear_events()

# Or, to automatically clear the pending events after saving.
with book.flush() as events:
    # ... save the events or use the events to update the data model
```