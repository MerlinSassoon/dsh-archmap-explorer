from __future__ import annotations

from .cache import Cache
from .model import Config, Order, Receipt
from .repository import Repository


class OrderManager:
    """Owns order orchestration and its cache."""

    def __init__(self, config: Config, repository: Repository):
        self.config = config
        self.repository = repository
        self.cache = Cache()

    def place(self, order: Order) -> Receipt:
        accepted = self.repository.save(order)
        self.cache.put(order.order_id, accepted)
        return Receipt(order.order_id, accepted)
