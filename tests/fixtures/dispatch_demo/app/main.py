def handler_a():
    """Handle mode A."""
    return "a"


def handler_b():
    """Handle mode B."""
    return "b"


def main(mode):
    """Dispatch to a mode handler."""
    handlers = {
        "a": handler_a,
        "b": handler_b,
    }
    return handlers[mode]()
