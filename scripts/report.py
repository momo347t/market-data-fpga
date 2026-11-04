#!/usr/bin/env python3
"""Generate a readable summary only when reports match the current RTL."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import ROOT, design_hash

def main():
    simulation = json.loads((ROOT / "results/simulation.json").read_text())
    synthesis = json.loads((ROOT / "results/synthesis.json").read_text())
    digest = design_hash()
    assert simulation["design_sha256"] == synthesis["design_sha256"] == digest, "stale RTL reports; rerun tests/synthesis"
    assert synthesis["harness_sha256"] == hashlib.sha256((ROOT / "bench/synthesis_top.sv").read_bytes()).hexdigest(), "stale harness report"
    cells = synthesis["mapped_statistics"]["design"]["num_cells_by_type"]
    use = synthesis["implementation"]["utilization"]
    clocks = synthesis["implementation"]["fmax"]
    runs = simulation["runs"]
    outputs = sum(sum(v for k,v in row["coverage"].items() if k.startswith("output_") and len(k)==8) for row in runs)
    lines = ["# Reproduced measurements", "", f"RTL SHA-256: `{digest}`.", "",
             "## Functional verification", "", "| Check | Recorded result |", "|---|---|",
             f"| RTL campaigns | {len(runs)} |",
             f"| FIFO depths | {', '.join(map(str, sorted(set(row['fifo_depth'] for row in runs))))} |",
             f"| Random seeds | {', '.join(map(str, sorted(set(row['seed'] for row in runs))))} |",
             f"| Generated random frames per campaign | {simulation['frames_per_random_run']} plus directed cases |",
             f"| Simulated cycles in mixed campaigns | {sum(row['cycles'] for row in runs):,} |",
             f"| Events checked at output handshake | {outputs:,} |",
             "| Golden payload and software tests | 7 unittest cases, including 5,000 random raw buffers |",
             "| No-stall A-message benchmark | 512 messages, 18,432 consecutive input bytes |",
             "| Post-frame output handshake latency | 1 cycle, all 512 benchmark messages |",
             "| Input acceptance during benchmark active window | 1 byte/cycle |", "",
             "Mixed campaigns check all supported message types and all five diagnostic codes, input/output stalls, FIFO-full reset flushing, malformed lengths, unknown types, abort and resynchronization. Static checks use Verilator with warnings treated as errors.", "",
             "## iCE40 implementation harness", "", "| Measure | Recorded result |", "|---|---|",
             f"| Target | {synthesis['target']} |",
             f"| Requested clock | {synthesis['clock_target_mhz']} MHz |",
             f"| Mapped LUT4 | {cells.get('SB_LUT4', 0):,} |",
             f"| Mapped flip-flops | {sum(v for k,v in cells.items() if k.startswith('SB_DFF')):,} |",
             f"| Routed logic cells | {use['ICESTORM_LC']['used']:,} / {use['ICESTORM_LC']['available']:,} |",
             f"| Block RAM | {use['ICESTORM_RAM']['used']} |",
             f"| P&R seed | {synthesis['seed']} |",
             f"| Host | {synthesis['platform']} |"]
    for name, clock in clocks.items():
        assert clock["achieved"] >= clock["constraint"], "timing target not met"
        lines.append(f"| Internal clock estimate | {clock['achieved']:.2f} MHz |")
    lines += ["", "The routed measurement is for `bench/synthesis_top.sv`, including its observable digest sink and counters. Pins are assigned automatically. There is no board pinout, external I/O delay model or physical-board measurement. The internal-clock estimate is not full board timing closure or a measured exchange/network latency.", "",
              "At 50 MHz, cycle scaling gives a 20 ns post-frame handshake delay and 720 ns from the first byte of a 36-byte A message to its handshake, without stalls. These are derived values, not physical measurements. With stalls, latency is not bounded by this experiment.", "",
              "## Reproduce", "", "```sh", "python scripts/lint.py",
              "python scripts/run.py test --frames 2000 --seeds 7 123 2026 65537",
              "python scripts/synthesize.py --frequency 50", "python scripts/report.py", "```", "",
              "Raw evidence: [simulation.json](simulation.json), [synthesis.json](synthesis.json). Tool versions and the harness hash are included. Different tools, platform, seed, wrapper or FIFO depth can change implementation results.", ""]
    (ROOT / "results/README.md").write_text("\n".join(lines), encoding="utf-8")
    print("Generated results/README.md from matching reports")

if __name__ == "__main__": main()
