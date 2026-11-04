#!/usr/bin/env python3
"""Reproduce mapped resources and an explicitly scoped iCE40 timing experiment."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import ROOT, design_hash, run, tool

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frequency", type=float, default=50.0, help="MHz clock target")
    args = parser.parse_args()
    if args.frequency <= 0: parser.error("frequency must be positive")
    build = ROOT / "build" / "synth"; build.mkdir(parents=True, exist_ok=True)
    yosys_script = "\n".join([
        "read_verilog -sv rtl/event_fifo.sv rtl/itch_stream_decoder.sv bench/synthesis_top.sv",
        "hierarchy -check -top synthesis_top",
        "synth_ice40 -top synthesis_top -json build/synth/design.json",
        "check -assert",
        "tee -o build/synth/statistics.json stat -json",
    ])
    script = build / "synth.ys"; script.write_text(yosys_script+"\n", encoding="ascii")
    run([tool("yosys"), "-Q", "-q", "-l", build / "yosys.log", "-s", script])
    run([tool("nextpnr-ice40"), "--hx8k", "--package", "ct256", "--freq", str(args.frequency),
         "--seed", "1", "--json", build / "design.json", "--asc", build / "implementation.asc",
         "--pcf-allow-unconstrained", "--report", build / "timing.json"],
        stdout=(build / "nextpnr.log").open("w"), stderr=-2)
    statistics = json.loads((build / "statistics.json").read_text())
    timing = json.loads((build / "timing.json").read_text())
    versions = {}
    for name, option in (("yosys", "-V"), ("nextpnr-ice40", "--version")):
        result = run([tool(name), option], capture_output=True, text=True)
        versions[name] = (result.stdout + result.stderr).strip()
    report = dict(design_sha256=design_hash(),
                  harness_sha256=hashlib.sha256((ROOT / "bench/synthesis_top.sv").read_bytes()).hexdigest(),
                  target="iCE40HX8K-CT256", clock_target_mhz=args.frequency, seed=1,
                  platform=platform.system(), tool_versions=versions,
                  scope="Narrow-pin observable harness; automatic pin placement; internal clock timing only. No board pinout, external I/O delay model, or on-board validation.",
                  mapped_statistics=statistics, implementation=timing)
    out = ROOT / "results"; out.mkdir(exist_ok=True)
    (out / "synthesis.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print("PASS synthesis + implementation; results/synthesis.json")

if __name__ == "__main__": main()
