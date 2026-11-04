# Review and interview guide

Start with `scripts/demo.py`, then follow one A message through the core and
the packed output fields. Explain the following with a waveform or trace:

1. What ready/valid guarantees when either side pauses, and why source data
   cannot change while blocked.
2. Why a full FIFO can accept a new event on the same edge that its head is
   consumed, including depth one.
3. How the parser retains a message while receiving bytes and includes the
   final byte in the event enqueued on EOP.
4. Why unknown message types are distinct from malformed supported messages.
5. What happens on missing SOP, early EOP, overlong frames, a new SOP inside
   a frame, an explicit abort and a reset with queued outputs.
6. How big-endian fields and symbol padding are preserved; why prices use
   integers and absent event fields are zero.
7. Why E and U need downstream order state, and why P is not an add order.
8. The difference between last-byte latency, complete-message latency and
   sustained throughput; how backpressure changes each claim.
9. Why the model is independent, which checks are directed/random, and what
   these tests do not formally prove.
10. What the iCE40 harness measures, why its digest is needed, and why its
    internal timing result does not prove board I/O timing or exchange latency.

Useful small experiments: change FIFO depth to three; stall the sink for
hundreds of clocks; send an unsupported type; corrupt an enum; abort half an
order; compare the expected diagnostic and statistics with the trace. A useful
optimization proposal must preserve the documented interface and be checked
against the same reference and test campaigns.
