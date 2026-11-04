#!/usr/bin/env python3
"""Decode a synthetic order lifecycle or a length-prefixed payload file."""
import argparse
import io
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.itch import decode_message, read_length_prefixed

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, help="2-byte length-prefixed ITCH payload file")
    args = parser.parse_args()
    if args.file:
        stream = args.file.open("rb")
    else:
        header = "1234abcd010203040506"
        ref = "0102030405060708"
        frames = [
            bytes.fromhex("41" + header + ref + "42 00000064 5445535420202020 000f4240"),
            bytes.fromhex("45" + header + ref + "00000019 0000000000000009"),
            bytes.fromhex("44" + header + ref),
        ]
        stream = io.BytesIO(b"".join(len(frame).to_bytes(2, "big") + frame for frame in frames))
    with stream:
        for frame in read_length_prefixed(stream):
            print(json.dumps(decode_message(frame).readable(), sort_keys=True))

if __name__ == "__main__": main()
