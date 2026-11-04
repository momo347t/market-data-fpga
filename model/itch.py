"""Decode a documented eight-message subset of Nasdaq TotalView-ITCH 5.0.

Offsets refer to the official payload, not a transport header. Prices retain
their integer representation (four implied decimal places).
"""
from dataclasses import asdict, dataclass
from typing import BinaryIO, Iterator

LENGTHS = {"A": 36, "F": 40, "E": 31, "C": 36, "X": 23, "D": 19, "U": 35, "P": 44}
EVENT_FIELDS = (
    ("message_type", 8), ("stock_locate", 16), ("tracking_number", 16),
    ("timestamp", 48), ("order_ref", 64), ("new_order_ref", 64), ("side", 8),
    ("shares", 32), ("stock", 64), ("price", 32), ("match_number", 64),
    ("attribution", 32), ("printable", 8),
)

class DecodeError(ValueError):
    """A supported payload has invalid length or an invalid checked enum."""

class UnsupportedMessage(ValueError):
    """The message type is outside this project's declared subset."""

@dataclass(frozen=True)
class Event:
    message_type: int
    stock_locate: int
    tracking_number: int
    timestamp: int
    order_ref: int = 0
    new_order_ref: int = 0
    side: int = 0
    shares: int = 0
    stock: int = 0
    price: int = 0
    match_number: int = 0
    attribution: int = 0
    printable: int = 0

    def packed(self) -> int:
        result = 0
        for name, width in EVENT_FIELDS:
            value = getattr(self, name)
            if not 0 <= value < (1 << width):
                raise ValueError(f"{name} does not fit {width} bits")
            result = (result << width) | value
        return result

    def readable(self) -> dict:
        value = asdict(self)
        value["message_type"] = chr(self.message_type)
        value["side"] = chr(self.side) if self.side else None
        value["printable"] = chr(self.printable) if self.printable else None
        value["stock"] = self.stock.to_bytes(8, "big").decode("ascii", errors="backslashreplace").rstrip() if self.stock else None
        return value

def decode_message(payload: bytes) -> Event:
    if not payload:
        raise DecodeError("empty payload")
    kind = chr(payload[0])
    if kind not in LENGTHS:
        raise UnsupportedMessage(f"unsupported type 0x{payload[0]:02x}")
    if len(payload) != LENGTHS[kind]:
        raise DecodeError(f"{kind}: expected {LENGTHS[kind]} bytes, got {len(payload)}")
    def uint(start: int, size: int) -> int:
        return int.from_bytes(payload[start:start + size], "big")
    fields = dict(message_type=payload[0], stock_locate=uint(1, 2),
                  tracking_number=uint(3, 2), timestamp=uint(5, 6), order_ref=uint(11, 8))
    if kind in "AFP":
        if payload[19] not in (ord("B"), ord("S")):
            raise DecodeError("invalid buy/sell indicator")
        fields.update(side=payload[19], shares=uint(20, 4), stock=uint(24, 8), price=uint(32, 4))
        if kind == "F":
            fields["attribution"] = uint(36, 4)
        if kind == "P":
            fields["match_number"] = uint(36, 8)
    elif kind in "EC":
        fields.update(shares=uint(19, 4), match_number=uint(23, 8))
        if kind == "C":
            if payload[31] not in (ord("Y"), ord("N")):
                raise DecodeError("invalid printable indicator")
            fields.update(printable=payload[31], price=uint(32, 4))
    elif kind == "X":
        fields["shares"] = uint(19, 4)
    elif kind == "U":
        fields.update(new_order_ref=uint(19, 8), shares=uint(27, 4), price=uint(31, 4))
    return Event(**fields)

def read_length_prefixed(stream: BinaryIO) -> Iterator[bytes]:
    """Read this project's 2-byte big-endian length + ITCH payload container."""
    while True:
        header = stream.read(2)
        if not header:
            return
        if len(header) != 2:
            raise DecodeError("truncated length prefix")
        length = int.from_bytes(header, "big")
        if length == 0:
            raise DecodeError("zero-length frame")
        payload = stream.read(length)
        if len(payload) != length:
            raise DecodeError("truncated payload")
        yield payload
