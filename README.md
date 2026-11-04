# FPGA ITCH Market-Data Decoder

[![RTL verification and synthesis](https://github.com/momo347t/market-data-fpga/actions/workflows/ci.yml/badge.svg)](https://github.com/momo347t/market-data-fpga/actions/workflows/ci.yml)

A synthesizable SystemVerilog decoder for eight Nasdaq TotalView-ITCH 5.0
payload types, with bounded buffering, ready/valid backpressure and an
independent Python reference model.

The project implements the complete declared payload-decoder boundary:
`A`, `F`, `E`, `C`, `X`, `D`, `U`, `P`. It accepts framed bytes and emits
456-bit normalized events. It does not implement the remaining ITCH types,
a network transport, session recovery, trading strategy or live exchange
connection. See the [interface contract](docs/protocol.md).

## Architecture

```text
framed bytes -> buffer -> alignment / field extraction -> event FIFO -> consumer
                               |
                       diagnostics / counters

synthetic fixtures -> SystemVerilog simulation trace -> Python scoreboard
```

- One byte accepted per clock while capacity is available.
- Strict supported-message lengths and checked side/printable enums.
- Output stability during stalls; full simultaneous FIFO dequeue/enqueue.
- Explicit reset, abort, malformed-frame and SOP-resynchronization behavior.
- Directed/random RTL verification at FIFO depths 1, 3 and 4.
- Verilator lint, Icarus simulation, Yosys mapping and nextpnr timing experiment.

The separate uninterrupted benchmark measures one cycle from the final
input-byte handshake to output handshake, and one input byte per active
cycle. The [recorded results](results/README.md) include seeds, counts,
resources, tool versions, hashes and the limits of the timing experiment.

## Try the software demo

Python 3.12+; no Python packages required:

```sh
python scripts/demo.py
python -m unittest discover -s tests -v
```

The demo prints an add, execution and deletion using synthetic payloads.
For a file of two-byte big-endian length-prefixed payloads:

```sh
python scripts/demo.py --file path/to/messages.bin
```

This file framing is a documented adapter convention, not an implementation
of MoldUDP64 or SoupBinTCP. Input files must already contain individual ITCH
payloads. No licensed or live market data is included.

## Run the hardware checks

Install the pinned official OSS CAD Suite (approximately 600-750 MB compressed):

```sh
python scripts/install_tools.py
python scripts/lint.py
python scripts/run.py test --frames 2000 --seeds 7 123 2026 65537
python scripts/synthesize.py --frequency 50
python scripts/report.py
```

The installer verifies release asset SHA-256 before extraction and does not
change system PATH. It supports Linux/Windows x86-64 and installs alongside
the repository in `../.tools`. For an existing suite, set `OSS_CAD_SUITE` to
its root. Other platforms can install the vendor's matching distribution
manually and put its executables on PATH.

Windows PowerShell example for an existing suite:

```powershell
$env:OSS_CAD_SUITE = 'C:\tools\oss-cad-suite'
python scripts/run.py test --frames 500 --seeds 7
```

The CI runs the same scripts with a shorter random campaign and uploads raw
evidence. Reports committed in `results/` describe the recorded local run;
CI artifacts describe their own host/run, and may differ in mapped placement.

## Review the implementation

| Path | Contents |
|---|---|
| `rtl/itch_stream_decoder.sv` | Payload parser, validation and diagnostics |
| `rtl/event_fifo.sv` | Parameterized synchronous event FIFO |
| `model/itch.py` | Independent byte-slice reference and container reader |
| `tb/tb_decoder.sv` | Handshake-respecting source and randomized sink |
| `tests/` | Golden, boundary, malformed and synthetic fixtures |
| `scripts/run.py` | Trace scoreboard, random campaigns and cycle benchmark |
| `bench/synthesis_top.sv` | Narrow-pin observable synthesis harness |
| `docs/` | Protocol, design trade-offs and review guide |

The design is intentionally single-clock and byte-wide. It has no CDC block
and no claim of multi-gigabit line rate. The implementation experiment uses
automatic pins, without a board-specific I/O timing model. No FPGA board has
been programmed for these results.

## Background and provenance

This portfolio project connects digital design, binary protocol handling,
verification and measurement. The
[design notes](docs/design.md) explain the architecture and verification
methods. It contains no employer firmware or copied course solution.

Protocol source: [Nasdaq TotalView-ITCH 5.0 specification](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHspecification.pdf),
consulted 4 November 2026. Tools: [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build).
MIT license covers this repository's original code, not third-party protocol
documents or tool distributions.
