from .manager import OrderManager
from .model import Config, Order
from .repository import Repository


def run_cli() -> None:
    """Simple interactive entry surface."""
    raw = input("order id: ")
    print(OrderManager(Config(), Repository()).place(Order(raw)).accepted)


def main() -> None:
    run_cli()
