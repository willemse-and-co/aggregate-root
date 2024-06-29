import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from pytest import raises

from aggregate_root import AggregateRoot, Event


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
        instance.produce_events(
            BookCreated(),
            BookTitleUpdated(title),
            BookAuthorUpdated(author),
            BookYearPublishedUpdated(year_published),
        )
        return instance

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


def test_library():
    book = Book.create("9783161484100", "The Hobbit", "J.R.R. Tolkien", 1937)
    assert book.aggregate_id == "9783161484100"
    book.add_copy("123456")
    book.add_copy("234567")
    assert len(book.copies) == 2
    book.borrow_copy("123456", "user1")
    with raises(ValueError):
        book.borrow_copy("123456", "user2")
    book.borrow_copy("234567", "user3")
    book.return_copy("123456")
    book.borrow_copy("123456", "user2")
    book.remove_copy("123456")
    assert len(book.copies) == 1
