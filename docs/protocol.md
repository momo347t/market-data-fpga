# Interfaces and supported format

The design decodes a subset of Nasdaq TotalView-ITCH 5.0 **payloads**. Its
framing sidebands are an adapter interface, not MoldUDP64, SoupBinTCP,
Ethernet, IP or UDP. A transport adapter must first delimit individual ITCH
messages and present their payload bytes in order.

The authoritative format is the [Nasdaq specification](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHspecification.pdf),
consulted 4 November 2026, sections 1.3-1.5.1. Integers are big-endian; prices
remain unsigned integers with four implied decimal places. Symbols are eight
ASCII bytes with right-side spaces, preserved verbatim.

| Type | Payload bytes | Event |
|---|---:|---|
| A | 36 | Add without attribution |
| F | 40 | Add with attribution |
| E | 31 | Execution |
| C | 36 | Execution with price |
| X | 23 | Partial cancellation |
| D | 19 | Deletion |
| U | 35 | Replacement |
| P | 44 | Non-cross trade |

All other types, including directory, system events and cross trades, are
outside this subset. This is a decoder, not a complete feed handler or order
book. An E/C/X/D/U event does not repeat the original symbol/side/price when
the protocol omits them; a downstream stateful book must retain that state.
U does not change side/symbol. P is a trade report and does not mutate the
displayed order book; its legacy side/reference fields are preserved, not
interpreted as an add order.

## Input: byte stream

All inputs are synchronous to `clk`. Reset `rst_n` is active low and
asynchronously asserted; its deassertion must be synchronized by the
integrator. The core has one clock domain.

- A byte is accepted on a rising edge with `s_valid && s_ready`.
- `s_sop` marks its first byte (the type); `s_eop` marks its last byte.
- A source holds valid, byte, SOP and EOP unchanged while ready is low.
- Pauses in valid are legal and have no timeout meaning.
- `s_abort` is out-of-band and takes precedence over a byte transfer, even
  with valid asserted. It discards the active partial frame, not queued events.
- SOP in an unfinished frame discards that partial frame and starts anew.
- A missing EOP does not generate a timeout: recover with SOP, abort or reset.
- Input ready conservatively follows output FIFO capacity for every byte,
  including unsupported and malformed frames. This keeps bounded storage and
  a simple ready path; it can stall before the next frame starts.

Supported messages require exactly the declared type length. Buy/sell must
be B/S on A/F/P; printable must be Y/N on C. Other domain rules (valid symbol,
timestamp within a day, price limits, quantity, order existence) are left to
downstream validation. Numeric extreme tests intentionally check bit fidelity
rather than business validity.

The shift buffer is fixed at 44 bytes. The byte count saturates at 127;
therefore excessively long supported frames cannot accidentally wrap into a
valid length. An oversized supported frame is rejected when EOP arrives.
An unsupported frame increments its counter when EOP arrives, regardless of
its length. A zero-byte payload has no representation on this byte interface.

## Output: normalized events

`m_event[455:0]` is meaningful when `m_valid` is high, stable while blocked,
and consumed on `m_valid && m_ready`. FIFO depth is parameterized (>=1);
full simultaneous dequeue/enqueue is supported, including depth one and
non-power-of-two depths. Reset discards partial frames and queued events.
The event bus is unspecified when valid is low.

Packed order, **most significant field first**:

| Field | Bits | Meaning |
|---|---:|---|
| message_type | 8 | Original type byte |
| stock_locate | 16 | Instrument locate |
| tracking_number | 16 | Tracking field |
| timestamp | 48 | Raw nanosecond timestamp |
| order_ref | 64 | Original reference |
| new_order_ref | 64 | U replacement reference |
| side | 8 | A/F/P side byte |
| shares | 32 | Message quantity |
| stock | 64 | A/F/P symbol bytes |
| price | 32 | Price field on A/F/C/U/P |
| match_number | 64 | E/C/P execution reference |
| attribution | 32 | F attribution bytes |
| printable | 8 | C printable byte |

Absent fields are zero. The field widths sum to 456. `Event.packed()` defines
the identical external layout for software consumers; its payload decoding
uses byte slices independently of the RTL alignment logic.

## Diagnostics and counters

Diagnostics are registered one-cycle pulses, not a ready/valid output queue.
They describe the preceding edge. Counter registers wrap modulo 2^32 and
clear on reset. Their six outputs count accepted bytes, decoded events
enqueued, error indications, unsupported EOPs, active-frame aborts and SOP
resynchronizations. A decoded event later discarded by reset remains counted
until that same reset clears all counters.

| error_code | Condition |
|---:|---|
| 0 | No error |
| 1 | Accepted byte without an active frame or SOP |
| 2 | Supported frame ended with wrong length |
| 3 | Checked enum invalid |
| 4 | SOP replaced a partial frame |
| 5 | Explicit abort discarded a partial frame |

At most one diagnostic is emitted per edge. If a new SOP also ends a
malformed one-byte supported frame, its length error takes precedence over
the resync diagnostic; `stat_resync` still records the replaced old frame.
Unsupported messages are counted separately, not reported as format errors.
Abort while idle is a no-op.

## Software file container

The demo accepts two-byte big-endian payload length followed by payload,
repeated. This is an explicitly chosen file container. Reading such a file
does not implement either Nasdaq network transport. Truncated prefixes,
zero lengths and truncated payloads are rejected.
