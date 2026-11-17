from dataclasses import dataclass


@dataclass
class Config:
    host: str = "localhost"
    port: int = 8080


@dataclass
class Order:
    order_id: str
    total: float = 0.0


@dataclass
class Receipt:
    order_id: str
    accepted: bool
