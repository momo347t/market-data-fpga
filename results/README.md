# Reproduced measurements

RTL SHA-256: `07c60ff57e9e68790c9978d298c9d2614aa412772f6f496b3c1e670f46422790`.

## Functional verification

| Check | Recorded result |
|---|---|
| RTL campaigns | 12 |
| FIFO depths | 1, 3, 4 |
| Random seeds | 7, 123, 2026, 65537 |
| Generated random frames per campaign | 2000 plus directed cases |
| Simulated cycles in mixed campaigns | 1,292,076 |
| Events checked at output handshake | 19,640 |
| Golden payload and software tests | 7 unittest cases, including 5,000 random raw buffers |
| No-stall A-message benchmark | 512 messages, 18,432 consecutive input bytes |
| Post-frame output handshake latency | 1 cycle, all 512 benchmark messages |
| Input acceptance during benchmark active window | 1 byte/cycle |

Mixed campaigns check all supported message types and all five diagnostic codes, input/output stalls, FIFO-full reset flushing, malformed lengths, unknown types, abort and resynchronization. Static checks use Verilator with warnings treated as errors.

## iCE40 implementation harness

| Measure | Recorded result |
|---|---|
| Target | iCE40HX8K-CT256 |
| Requested clock | 50.0 MHz |
| Mapped LUT4 | 4,010 |
| Mapped flip-flops | 2,411 |
| Routed logic cells | 5,863 / 7,680 |
| Block RAM | 0 |
| P&R seed | 1 |
| Host | Windows |
| Internal clock estimate | 61.21 MHz |

The routed measurement is for `bench/synthesis_top.sv`, including its observable digest sink and counters. Pins are assigned automatically. There is no board pinout, external I/O delay model or physical-board measurement. The internal-clock estimate is not full board timing closure or a measured exchange/network latency.

At 50 MHz, cycle scaling gives a 20 ns post-frame handshake delay and 720 ns from the first byte of a 36-byte A message to its handshake, without stalls. These are derived values, not physical measurements. With stalls, latency is not bounded by this experiment.

## Reproduce

```sh
python scripts/lint.py
python scripts/run.py test --frames 2000 --seeds 7 123 2026 65537
python scripts/synthesize.py --frequency 50
python scripts/report.py
```

Raw evidence: [simulation.json](simulation.json), [synthesis.json](synthesis.json). Tool versions and the harness hash are included. Different tools, platform, seed, wrapper or FIFO depth can change implementation results.
