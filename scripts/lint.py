#!/usr/bin/env python3
"""Run independent Verilator static checks on the synthesizable decoder."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import run, tool
run([tool("verilator_bin"), "--lint-only", "-Wall", "--top-module", "itch_stream_decoder",
     "rtl/event_fifo.sv", "rtl/itch_stream_decoder.sv"], timeout=45)
