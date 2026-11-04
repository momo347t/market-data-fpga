`timescale 1ns/1ps
`default_nettype none
// Narrow-pin implementation harness. Every event bit and statistics word
// contributes to a registered digest, keeping the decoder observable.
// The digest is a test sink, not a collision-resistant integrity check.
module synthesis_top (
    input wire clk, rst_n,
    input wire [7:0] s_data,
    input wire s_valid, s_sop, s_eop, s_abort, m_ready,
    output wire s_ready, m_valid, error_valid,
    output wire [3:0] error_code,
    output reg [31:0] digest
);
    wire [455:0] m_event;
    wire [31:0] stat_bytes, stat_decoded, stat_errors, stat_unsupported, stat_aborts, stat_resync;
    itch_stream_decoder #(.FIFO_DEPTH(4)) core (.*);
    wire [479:0] padded = {24'b0, m_event};
    reg [31:0] folded;
    integer index;
    always @* begin
        folded = stat_bytes ^ stat_decoded ^ stat_errors ^ stat_unsupported ^ stat_aborts ^ stat_resync;
        for (index = 0; index < 15; index = index + 1)
            folded = folded ^ padded[index*32 +: 32];
    end
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) digest <= 0;
        else if (m_valid && m_ready) digest <= {digest[30:0], digest[31]} ^ folded;
    end
endmodule
`default_nettype wire
