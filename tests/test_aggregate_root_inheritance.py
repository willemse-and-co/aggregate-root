from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from aggregate_root import AggregateRoot, Event


@dataclass(frozen=True)
class AccountCreated(Event):
    name: str


@dataclass(frozen=True)
class AccountDebited(Event):
    value: Decimal


@dataclass(frozen=True)
class AccountCredited(Event):
    value: Decimal


class Account(AggregateRoot):
    def __init__(self, id: str):
        super().__init__(id)
        self._name: Optional[str] = None
        self._balance = Decimal(0)

    @classmethod
    def create(cls, name: str) -> "Account":
        id = str(uuid4())
        instance = cls(id)
        instance.produce_events(AccountCreated(name))
        return instance

    @property
    def name(self):
        return self._name

    @property
    def balance(self):
        return self._balance

    @AggregateRoot.produces_events
    def debit(self, value: Decimal) -> AccountDebited:
        return AccountDebited(value)

    @AggregateRoot.produces_events
    def credit(self, value: Decimal) -> AccountCredited:
        return AccountCredited(value)

    @AggregateRoot.handles_events(AccountCreated)
    def _on_account_created(self, event: AccountCreated):
        self._name = event.name

    @AggregateRoot.handles_events(AccountDebited)
    def _on_account_debited(self, event: AccountDebited):
        pass

    @AggregateRoot.handles_events(AccountCredited)
    def _on_account_credited(self, event: AccountCredited):
        pass


class AssetAccount(Account):
    @classmethod
    def create(cls, name: str) -> "AssetAccount":
        id = str(uuid4())
        instance = cls(id)
        instance.produce_events(AccountCreated(name))
        return instance

    @AggregateRoot.handles_events(AccountDebited)
    def _on_account_debited(self, event: AccountDebited):
        self._balance += event.value

    @AggregateRoot.handles_events(AccountCredited)
    def _on_account_credited(self, event: AccountCredited):
        self._balance -= event.value


class LiabilityAccount(Account):
    @classmethod
    def create(cls, name: str) -> "LiabilityAccount":
        id = str(uuid4())
        instance = cls(id)
        instance.produce_events(AccountCreated(name))
        return instance

    @AggregateRoot.handles_events(AccountDebited)
    def _on_account_debited(self, event: AccountDebited):
        self._balance -= event.value

    @AggregateRoot.handles_events(AccountCredited)
    def _on_account_credited(self, event: AccountCredited):
        self._balance += event.value


class DoubleLiabilityAccount(LiabilityAccount):
    @classmethod
    def create(cls, name: str) -> "LiabilityAccount":
        id = str(uuid4())
        instance = cls(id)
        instance.produce_events(AccountCreated(name))
        return instance

    @AggregateRoot.handles_events(AccountDebited)
    def _on_account_debited(self, event: AccountDebited):
        self._balance -= 2 * event.value

    @AggregateRoot.handles_events(AccountCreated)
    def _on_account_created(self, event: AccountCreated):
        self._name = event.name + " " + event.name


def test_event_handler_heirarchy():
    base_account = Account.create("Base")
    asset_account = AssetAccount.create("Asset")
    liability_account = LiabilityAccount.create("Liability")
    double_liability_account = DoubleLiabilityAccount.create("Double")
    assert base_account.name == "Base"
    assert asset_account.name == "Asset"
    assert liability_account.name == "Liability"
    assert double_liability_account.name == "Double Double"

    base_account.debit(Decimal(100))
    asset_account.debit(Decimal(100))
    liability_account.debit(Decimal(100))
    double_liability_account.debit(Decimal(100))

    assert base_account.balance == Decimal(0)
    assert asset_account.balance == Decimal(100)
    assert liability_account.balance == Decimal(-100)
    assert double_liability_account.balance == Decimal(-200)
