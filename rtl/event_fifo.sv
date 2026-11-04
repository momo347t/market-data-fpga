`timescale 1ns/1ps
`default_nettype none
// Synchronous bounded FIFO. A full FIFO accepts a simultaneous pop/push.
module event_fifo #(
    parameter integer WIDTH = 456,
    parameter integer DEPTH = 4
) (
    input wire clk,
    input wire rst_n,
    input wire in_valid,
    output wire in_ready,
    input wire [WIDTH-1:0] in_data,
    output wire out_valid,
    input wire out_ready,
    output wire [WIDTH-1:0] out_data
);
    localparam integer AW = DEPTH <= 1 ? 1 : $clog2(DEPTH);
    localparam integer CW = $clog2(DEPTH + 1);
    localparam [CW-1:0] CAPACITY = CW'(DEPTH);
    localparam [AW-1:0] LAST_ADDRESS = AW'(DEPTH-1);
    reg [WIDTH-1:0] memory [0:DEPTH-1];
    reg [AW-1:0] rd_ptr, wr_ptr;
    reg [CW-1:0] count;
    wire pop = out_valid && out_ready;
    wire push = in_valid && in_ready;
    assign out_valid = rst_n && (count != 0);
    assign in_ready = rst_n && ((count < CAPACITY) || pop);
    assign out_data = memory[rd_ptr];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_ptr <= 0;
            wr_ptr <= 0;
            count <= 0;
        end else begin
            if (push) begin
                memory[wr_ptr] <= in_data;
                wr_ptr <= (wr_ptr == LAST_ADDRESS) ? '0 : wr_ptr + 1'b1;
            end
            if (pop)
                rd_ptr <= (rd_ptr == LAST_ADDRESS) ? '0 : rd_ptr + 1'b1;
            case ({push, pop})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: count <= count;
            endcase
        end
    end
`ifndef SYNTHESIS
    initial if (DEPTH < 1) $fatal(1, "FIFO DEPTH must be >= 1");
`endif
endmodule
`default_nettype wire
