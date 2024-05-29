from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .aggregate_root import AggregateRoot

AR = TypeVar("AR", bound=AggregateRoot)


class Repository(ABC, Generic[AR]):
    """
    Abstract base class for repositories that handle the persistence of aggregate roots.

    Methods:
        save: Saves the given aggregate root to the repository.
        load: Loads an aggregate root from the repository based on the given ID.
        remove: Removes the given aggregate root from the repository.
    """

    @abstractmethod
    def save(self, aggregate: AR) -> None:
        """
        Saves the given aggregate root to the repository.

        Parameters:
            aggregate (AR): The aggregate root to be saved.

        Returns:
            None
        """
        pass

    @abstractmethod
    def load(self, id: str) -> AR | None:
        """
        Loads an aggregate root from the repository based on the given ID.

        Parameters:
            id (str): The ID of the aggregate root to be loaded.

        Returns:
            AR | None: The loaded aggregate root, or None if not found.
        """
        pass

    @abstractmethod
    def remove(self, aggregate: AR) -> None:
        """
        Removes the given aggregate root from the repository.

        Parameters:
            aggregate (AR): The aggregate root to be removed.

        Returns:
            None
        """
        pass
