import io
import random
import unittest
from model.itch import DecodeError, Event, LENGTHS, UnsupportedMessage, decode_message, read_length_prefixed
from tests.vectors import GOLDEN_ADD, message

class ModelTests(unittest.TestCase):
    def test_golden_add_offsets_and_endian(self):
        self.assertEqual(decode_message(GOLDEN_ADD), Event(
            message_type=ord("A"), stock_locate=0x1234, tracking_number=0xabcd,
            timestamp=0x010203040506, order_ref=0x0102030405060708,
            side=ord("B"), shares=100, stock=int.from_bytes(b"TEST    ", "big"), price=1000000))

    def test_all_types_and_numeric_boundaries(self):
        rng = random.Random(7)
        for kind in LENGTHS:
            for edge in (0, 1, None):
                with self.subTest(kind=kind, edge=edge):
                    data = message(kind, rng, edge)
                    self.assertEqual(len(data), LENGTHS[kind])
                    event = decode_message(data)
                    self.assertEqual(event.message_type, ord(kind))
                    self.assertLess(event.packed(), 1 << 456)
                    if edge is not None:
                        self.assertEqual(event.order_ref, (1 << 64) - 1 if edge else 0)
                        self.assertEqual(event.timestamp, (1 << 48) - 1 if edge else 0)

    def test_every_truncation_and_excess_length(self):
        rng = random.Random(1)
        for kind in LENGTHS:
            data = message(kind, rng)
            for length in range(len(data)):
                with self.assertRaises(DecodeError): decode_message(data[:length])
            with self.assertRaises(DecodeError): decode_message(data + b"\x00")

    def test_invalid_enums(self):
        rng = random.Random(2)
        for kind, index in (("A", 19), ("F", 19), ("P", 19), ("C", 31)):
            for invalid in (0, 0xff, ord("?")):
                data = bytearray(message(kind, rng)); data[index] = invalid
                with self.assertRaises(DecodeError): decode_message(bytes(data))

    def test_unsupported(self):
        for kind in (0, ord("S"), ord("R"), 255):
            with self.assertRaises(UnsupportedMessage): decode_message(bytes([kind]))

    def test_container_boundaries(self):
        data = GOLDEN_ADD
        self.assertEqual(list(read_length_prefixed(io.BytesIO(len(data).to_bytes(2, "big") + data))), [data])
        self.assertEqual(list(read_length_prefixed(io.BytesIO(b""))), [])
        for invalid in (b"\x00", b"\x00\x00", b"\x00\x04A"):
            with self.assertRaises(DecodeError): list(read_length_prefixed(io.BytesIO(invalid)))

    def test_random_payloads_do_not_crash_with_index_errors(self):
        rng = random.Random(123)
        for _ in range(5000):
            raw = rng.randbytes(rng.randrange(0, 80))
            try: decode_message(raw)
            except (DecodeError, UnsupportedMessage): pass

if __name__ == "__main__": unittest.main()
