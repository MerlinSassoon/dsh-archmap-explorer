from __future__ import annotations

import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass


def _provider_role(value):
    """Test marker used to annotate a Provider role."""
    def decorate(cls):
        return cls
    return decorate


@dataclass
class AppConfig:
    host: str = "localhost"
    port: int = 8080
    debug: bool = False

    def as_dict(self):
        return {"host": self.host, "port": self.port}


@dataclass
class Order:
    order_id: str
    total: float = 0.0

    def as_dict(self):
        return {"order_id": self.order_id, "total": self.total}


class OrderManager:
    def __init__(self, repository):
        self.repository = repository

    def create(self, order):
        """Create an order through the repository."""
        return self.repository.save(order)

    def _normalize(self, value):
        return str(value)


class OrderRepository:
    def __init__(self):
        self.sock = socket.socket()

    def save(self, order):
        """Persist an order over the external socket."""
        return bool(self.sock)


class Worker(ABC):
    @abstractmethod
    def run(self):
        """Execute the contract."""


class Spinner:
    def __init__(self, message: str = "loading"):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def wait(self):
        """Wait until work completes."""
        return self.message


@_provider_role("component")
class DecoratedWidget:
    def ping(self):
        """Ping the component."""
        return "pong"


class ConfigOverrideThing:
    def dump(self):
        """Serialization helper that must not become a module API."""
        return {}


def helper(value: int) -> int:
    """Pure helper."""
    return value + 1


def main():
    """Program entry."""
    return helper(1)
