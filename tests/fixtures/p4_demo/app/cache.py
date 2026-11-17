class Cache:
    """In-memory cache owned by the manager."""

    def put(self, key: str, value: object) -> None:
        self.last = (key, value)
