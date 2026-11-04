"""Synthetic fixtures built with struct, independently of RTL byte alignment."""
import random
import struct

def message(kind: str, rng: random.Random, edge: int | None = None) -> bytes:
    def number(bits):
        return rng.getrandbits(bits) if edge is None else ((1 << bits) - 1 if edge else 0)
    header = struct.pack(">cHH", kind.encode(), number(16), number(16)) + number(48).to_bytes(6, "big")
    ref, shares, price = number(64), number(32), number(32)
    side = rng.choice([b"B", b"S"])
    stock = rng.choice([b"TEST    ", b"ABCDEFGH", b"A       "])
    if kind in "AFP":
        body = struct.pack(">QcI8sI", ref, side, shares, stock, price)
        if kind == "F": body += b"ABCD"
        if kind == "P": body += struct.pack(">Q", number(64))
    elif kind in "EC":
        body = struct.pack(">QIQ", ref, shares, number(64))
        if kind == "C": body += struct.pack(">cI", rng.choice([b"Y", b"N"]), price)
    elif kind == "X": body = struct.pack(">QI", ref, shares)
    elif kind == "D": body = struct.pack(">Q", ref)
    elif kind == "U": body = struct.pack(">QQII", ref, number(64), shares, price)
    else: raise ValueError(kind)
    return header + body

GOLDEN_ADD = bytes.fromhex(
    "41 1234 abcd 010203040506 0102030405060708 42 00000064"
    " 5445535420202020 000f4240"
)
