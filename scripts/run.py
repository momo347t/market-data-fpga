#!/usr/bin/env python3
"""Portable simulation, reference checking, synthesis and demo entry point."""
import argparse
from collections import Counter, deque
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.itch import DecodeError, LENGTHS, UnsupportedMessage, decode_message
from tests.vectors import GOLDEN_ADD, message

def environment():
    env = os.environ.copy()
    suite = env.get("OSS_CAD_SUITE")
    candidate = Path(suite) if suite else ROOT.parent / ".tools" / "oss-cad-suite"
    if candidate.is_dir():
        env["PATH"] = os.pathsep.join([str(candidate / "bin"), str(candidate / "lib"), env.get("PATH", "")])
        env["VERILATOR_ROOT"] = str(candidate / "share" / "verilator")
    return env

def run(command, **kwargs):
    print("+", " ".join(map(str, command)), flush=True)
    return subprocess.run(list(map(str, command)), cwd=ROOT, env=environment(), check=True, **kwargs)

def tool(name):
    path = shutil.which(name, path=environment()["PATH"])
    if not path: raise SystemExit(f"Missing {name}. Install OSS CAD Suite or set OSS_CAD_SUITE; see README.")
    return path

def design_hash():
    digest = hashlib.sha256()
    for path in sorted((ROOT / "rtl").glob("*.sv")):
        digest.update(path.name.encode()); digest.update(path.read_bytes())
    return digest.hexdigest()

def stimulus(path, seed, frames, benchmark=False, depth=4):
    rng = random.Random(seed)
    rows = []
    def frame(raw, gaps=True, final=True):
        for i, byte in enumerate(raw):
            rows.append(f"1 {int(i == 0)} {int(final and i == len(raw)-1)} {byte:02x} {rng.randrange(3) if gaps else 0}")
    if benchmark:
        for _ in range(frames): frame(GOLDEN_ADD, False)
    else:
        # Directed golden, every message kind, extreme integers, gaps.
        frame(GOLDEN_ADD, False)
        for kind in LENGTHS:
            for edge in (0, 1, None): frame(message(kind, rng, edge))
        # Every possible short length; one byte beyond each legal length.
        for kind in LENGTHS:
            raw = message(kind, rng)
            for n in range(1, len(raw)): frame(raw[:n])
            frame(raw + b"\x00")
        # Orphan input, unsupported types, oversized frames with count saturation.
        rows += ["1 0 1 41 0", "1 0 0 ff 0"]
        for size in (1, 11, 44, 200): frame(b"Z" + rng.randbytes(size-1))
        for byte in range(256):
            if chr(byte) not in LENGTHS: frame(bytes([byte]), False)
        frame(b"A" + rng.randbytes(299))
        for kind, pos in (("A", 19), ("F", 19), ("P", 19), ("C", 31)):
            raw = bytearray(message(kind, rng)); raw[pos] = 0xff; frame(raw)
        # Restart in a frame and both diagnostic priorities on a 1-byte restart.
        frame(message("A", rng)[:7], final=False); frame(message("D", rng))
        frame(b"A\x01", final=False); frame(b"A")
        frame(b"A\x01", final=False); frame(b"Z")
        # Abort an active frame and abort while idle; reset inside a frame.
        frame(message("F", rng)[:15], final=False)
        rows.append("2 0 0 00 1"); rows.append("2 0 0 00 0")
        frame(b"A\x01", final=False); rows.append("4 1 1 41 0")
        frame(message("U", rng)[:22], final=False); rows.append("3 0 0 00 2")
        # Full output FIFO followed by a reset is exercised with forced sink stall.
        rows.append("0 0 0 00 80")  # drain older events before stopping the sink
        rows.append("5 0 0 00 0")
        for _ in range(depth): frame(message("D", rng), False)
        rows.append("3 0 0 00 2")
        rows.append("5 0 0 00 45")
        for _ in range(frames):
            raw = message(rng.choice(list(LENGTHS)), rng)
            choice = rng.randrange(20)
            if choice == 0:
                frame(raw[:rng.randrange(1, len(raw))])
            elif choice == 1:
                frame(raw + rng.randbytes(rng.randrange(1, 6)))
            elif choice == 2:
                frame(raw[:rng.randrange(1, len(raw))], final=False)
                rows.append("2 0 0 00 0")
            elif choice == 3:
                frame(raw[:5], final=False); rows.append("3 0 0 00 2")
            else: frame(raw, bool(rng.randrange(2)))
        frame(GOLDEN_ADD, False)  # recovery marker
    path.write_text("\n".join(rows) + "\n", encoding="ascii")

class ReferenceStream:
    """Byte-list frame assembler; payload decoding uses the independent model."""
    def __init__(self): self.reset()
    def reset(self):
        self.frame = None
        self.stats = [0] * 6
        self.last_error = 0
    def edge(self, valid, ready, sop, eop, abort, data):
        error, event = 0, None
        if abort:
            if self.frame is not None:
                self.stats[4] += 1; error = 5
            self.frame = None
        elif valid and ready:
            self.stats[0] += 1
            if sop:
                if self.frame is not None:
                    self.stats[5] += 1; error = 4
                self.frame = bytearray()
            if self.frame is None:
                error = 1
            else:
                # Retain only up to 128 bytes; length saturates outside all valid lengths.
                if len(self.frame) < 128: self.frame.append(data)
                if eop:
                    try:
                        event = decode_message(bytes(self.frame))
                        self.stats[1] += 1
                    except UnsupportedMessage: self.stats[3] += 1
                    except DecodeError:
                        kind = chr(self.frame[0])
                        error = 2 if len(self.frame) != LENGTHS.get(kind) else 3
                    self.frame = None
        if error: self.stats[2] += 1
        self.last_error = error
        self.stats = [x & 0xffffffff for x in self.stats]
        return event

def check_trace(path, depth):
    ref = ReferenceStream(); pending = deque(); coverage = Counter()
    latencies = []; previous = None; last_cycle = -1
    for line in path.open(encoding="ascii"):
        fields = line.split()
        if len(fields) != 19: raise AssertionError(f"malformed trace: {line}")
        cycle, reset, valid, ready, sop, eop, abort = map(int, fields[:7])
        data = int(fields[7], 16); mv, mr = map(int, fields[8:10])
        packed = int(fields[10], 16) if mv else None
        ev, ec = map(int, fields[11:13]); stats = list(map(int, fields[13:]))
        try:
            if not reset:
                coverage["reset_discarded_events"] += len(pending)
                ref.reset(); pending.clear(); coverage["reset_cycles"] += 1
            assert ev == int(ref.last_error != 0) and ec == ref.last_error, ("diagnostic", ev, ec, ref.last_error)
            assert stats == ref.stats, ("statistics", stats, ref.stats)
            expected_ready = int(bool(reset and not abort and (len(pending) < depth or (pending and mr))))
            assert ready == expected_ready, ("input ready", ready, expected_ready)
            assert mv == int(bool(pending)), ("output valid", mv, len(pending))
            if mv:
                assert packed == pending[0][0].packed(), ("output payload", hex(packed), pending[0][0])
            if previous is not None and reset and previous["reset"]:
                if previous["mv"] and not previous["mr"]:
                    assert mv and packed == previous["packed"], "output changed while blocked"
                if previous["valid"] and not previous["ready"] and not abort and not previous["abort"]:
                    assert (valid, sop, eop, data) == previous["source"], "source driver violated hold contract"
            if mv and mr:
                event, end_cycle = pending.popleft()
                latencies.append(cycle-end_cycle)
                coverage[f"output_{chr(event.message_type)}"] += 1
            if mv and not mr: coverage["output_stall_cycles"] += 1
            if valid and not ready and not abort: coverage["input_stall_cycles"] += 1
            if reset:
                event = ref.edge(valid, ready, sop, eop, abort, data)
                if ref.last_error: coverage[f"error_{ref.last_error}"] += 1
                if event:
                    pending.append((event, cycle)); coverage["decoded"] += 1
                if valid and ready: coverage["accepted_bytes"] += 1
                if abort: coverage["abort_cycles"] += 1
                coverage["max_fifo_occupancy"] = max(coverage["max_fifo_occupancy"], len(pending))
            previous = dict(reset=reset, mv=mv, mr=mr, packed=packed, valid=valid,
                            ready=ready, abort=abort, source=(valid, sop, eop, data))
            last_cycle = cycle
        except AssertionError as exc:
            raise AssertionError(f"{path.name}, cycle {cycle}: {exc}") from exc
    assert not pending, "simulation ended with undrained events"
    assert ref.frame is None, "simulation ended inside a frame"
    return dict(cycles=last_cycle+1, coverage=dict(coverage),
                output_handshake_latency_cycles=dict(min=min(latencies), max=max(latencies), samples=len(latencies)))

def simulate(args):
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    build = ROOT / "build" / "sim"; build.mkdir(parents=True, exist_ok=True)
    results = []
    for depth in (1, 3, 4):
        executable = build / f"decoder_d{depth}.vvp"
        run([tool("iverilog"), "-g2012", "-Wall", "-s", "tb_decoder", f"-Ptb_decoder.FIFO_DEPTH={depth}",
             "-o", executable, "rtl/event_fifo.sv", "rtl/itch_stream_decoder.sv", "tb/tb_decoder.sv"])
        for seed in args.seeds:
            name = f"d{depth}_s{seed}"; stim = build / f"{name}.txt"; trace = build / f"{name}.trace"
            stimulus(stim, seed, args.frames, depth=depth)
            run([tool("vvp"), executable, f"+STIM={stim.as_posix()}", f"+TRACE={trace.as_posix()}",
                 f"+SEED={seed}", "+READY=45", "+STALL_START=80", "+STALL_END=480"])
            checked = check_trace(trace, depth)
            for kind in LENGTHS: assert checked["coverage"].get(f"output_{kind}", 0), (name, kind)
            for code in range(1,6): assert checked["coverage"].get(f"error_{code}", 0), (name, code)
            assert checked["coverage"].get("input_stall_cycles", 0)
            assert checked["coverage"].get("output_stall_cycles", 0)
            assert checked["coverage"].get("reset_discarded_events", 0) >= depth
            results.append(dict(name=name, fifo_depth=depth, seed=seed, **checked))
    # Dedicated no-stall, no-gap throughput/latency measurement.
    stim = build / "benchmark.txt"; trace = build / "benchmark.trace"
    stimulus(stim, 1, 512, benchmark=True)
    run([tool("vvp"), build / "decoder_d4.vvp", f"+STIM={stim.as_posix()}", f"+TRACE={trace.as_posix()}", "+READY=100"])
    benchmark = check_trace(trace, 4)
    assert benchmark["output_handshake_latency_cycles"] == dict(min=1, max=1, samples=512)
    accepted = [int(s.split()[0]) for s in trace.read_text().splitlines() if s.split()[2:4] == ["1", "1"]]
    assert len(accepted) == 512*36 and accepted[-1]-accepted[0]+1 == len(accepted)
    benchmark["accepted_bytes_per_cycle_active_window"] = 1.0
    benchmark["add_order_messages_per_cycle_active_window"] = 1/36
    report = dict(design_sha256=design_hash(), frames_per_random_run=args.frames, runs=results, benchmark=benchmark)
    out = ROOT / "results"; out.mkdir(exist_ok=True)
    (out / "simulation.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(f"PASS: {len(results)} directed/random RTL runs + throughput run; report results/simulation.json")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sim = sub.add_parser("test"); sim.add_argument("--frames", type=int, default=1500)
    sim.add_argument("--seeds", type=int, nargs="+", default=[7, 123, 2026])
    args = parser.parse_args()
    if args.frames < 1: parser.error("--frames must be positive")
    simulate(args)

if __name__ == "__main__": main()
