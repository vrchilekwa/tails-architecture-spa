from uuid import UUID

from app.models import DogProfile, Order, Subscription


class InMemoryStore:
    def __init__(self) -> None:
        self.dogs: dict[UUID, DogProfile] = {}
        self.subscriptions: dict[UUID, Subscription] = {}
        self.orders: dict[UUID, Order] = {}


store = InMemoryStore()
