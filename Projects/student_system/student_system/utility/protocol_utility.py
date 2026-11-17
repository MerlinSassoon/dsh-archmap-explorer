"""Stateless JSON wire-protocol helpers."""

from __future__ import annotations

import json
from typing import Any

from ..model.protocol_model import ProtocolMessage


def encode_message(model: int, *args: Any, **kwargs: Any) -> bytes:
    """Encode one command envelope as UTF-8 JSON bytes."""

    return json.dumps(ProtocolMessage(model=model, args=args, kwargs=kwargs).as_dict()).encode(
        "utf-8"
    )


def decode_message(received: bytes) -> tuple[int, tuple[Any, ...], dict[str, Any]]:
    """Decode one UTF-8 JSON command envelope."""

    if not received:
        raise ConnectionError("接收到空包，连接已断开")
    payload = json.loads(received)
    return int(payload["model"]), tuple(payload.get("args", [])), dict(payload.get("kwargs", {}))
