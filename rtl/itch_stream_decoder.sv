`timescale 1ns/1ps
`default_nettype none
// Nasdaq ITCH 5.0 payload subset A/F/E/C/X/D/U/P, one byte per transfer.
// SOP/EOP/ABORT are adapter sidebands, not an Ethernet or Nasdaq transport.
module itch_stream_decoder #(
    parameter integer FIFO_DEPTH = 4
) (
    input wire clk,
    input wire rst_n,
    input wire [7:0] s_data,
    input wire s_valid,
    output wire s_ready,
    input wire s_sop,
    input wire s_eop,
    input wire s_abort,
    output wire [455:0] m_event,
    output wire m_valid,
    input wire m_ready,
    output reg error_valid,
    output reg [3:0] error_code,
    output reg [31:0] stat_bytes,
    output reg [31:0] stat_decoded,
    output reg [31:0] stat_errors,
    output reg [31:0] stat_unsupported,
    output reg [31:0] stat_aborts,
    output reg [31:0] stat_resync
);
    reg active;
    reg [6:0] byte_count;
    reg [7:0] message_type;
    reg [343:0] packet;
    wire fifo_ready;
    assign s_ready = rst_n && !s_abort && fifo_ready;
    wire accepted = s_valid && s_ready;
    wire [7:0] kind = s_sop ? s_data : message_type;
    wire [6:0] next_count = s_sop ? 7'd1 :
                                    (byte_count == 127 ? 7'd127 : byte_count + 1'b1);
    wire [351:0] shifted = s_sop ? {344'b0, s_data} : {packet, s_data};
    function automatic [6:0] message_length(input [7:0] t);
        begin
            case (t)
                "A": message_length = 36;
                "F": message_length = 40;
                "E": message_length = 31;
                "C": message_length = 36;
                "X": message_length = 23;
                "D": message_length = 19;
                "U": message_length = 35;
                "P": message_length = 44;
                default: message_length = 0;
            endcase
        end
    endfunction
    wire [6:0] expected_length = message_length(kind);
    reg [351:0] normalized;
    // Type is already retained in message_type. Explicitly mark its duplicate.
    wire [7:0] unused_aligned_type = normalized[351:344];
    reg [63:0] order_ref, new_order_ref, stock, match_number;
    reg [31:0] shares, price, attribution;
    reg [7:0] side, printable;
    reg invalid_enum;
    always @* begin
        // Align a complete message to byte zero at the MSB. All shifts constant.
        case (kind)
            "A", "C": normalized = {shifted[287:0], 64'b0};
            "F": normalized = {shifted[319:0], 32'b0};
            "E": normalized = {shifted[247:0], 104'b0};
            "X": normalized = {shifted[183:0], 168'b0};
            "D": normalized = {shifted[151:0], 200'b0};
            "U": normalized = {shifted[279:0], 72'b0};
            "P": normalized = shifted;
            default: normalized = 0;
        endcase
        order_ref = normalized[263:200];
        new_order_ref = 0;
        side = 0;
        shares = 0;
        stock = 0;
        price = 0;
        match_number = 0;
        attribution = 0;
        printable = 0;
        invalid_enum = 0;
        case (kind)
            "A", "F", "P": begin
                side = normalized[199:192];
                shares = normalized[191:160];
                stock = normalized[159:96];
                price = normalized[95:64];
                invalid_enum = (side != "B") && (side != "S");
                if (kind == "F") attribution = normalized[63:32];
                if (kind == "P") match_number = normalized[63:0];
            end
            "E", "C": begin
                shares = normalized[199:168];
                match_number = normalized[167:104];
                if (kind == "C") begin
                    printable = normalized[103:96];
                    price = normalized[95:64];
                    invalid_enum = (printable != "Y") && (printable != "N");
                end
            end
            "X": shares = normalized[199:168];
            "U": begin
                new_order_ref = normalized[199:136];
                shares = normalized[135:104];
                price = normalized[103:72];
            end
            default: begin end
        endcase
    end
    wire [455:0] decoded = {
        kind, normalized[343:328], normalized[327:312], normalized[311:264],
        order_ref, new_order_ref, side, shares, stock, price, match_number,
        attribution, printable
    };
    wire emit_event = accepted && (active || s_sop) && s_eop &&
                      (expected_length != 0) && (next_count == expected_length) &&
                      !invalid_enum;
    event_fifo #(.WIDTH(456), .DEPTH(FIFO_DEPTH)) output_fifo (
        .clk(clk), .rst_n(rst_n), .in_valid(emit_event), .in_ready(fifo_ready),
        .in_data(decoded), .out_valid(m_valid), .out_ready(m_ready), .out_data(m_event)
    );

    // Single diagnostic per cycle; explicit abort preempts a transfer.
    // On SOP+EOP resync, the new frame's length error takes precedence.
    reg [3:0] diagnostic;
    always @* begin
        diagnostic = 0;
        if (s_abort && active) diagnostic = 5;
        else if (accepted) begin
            if (!active && !s_sop) diagnostic = 1;
            else begin
                if (active && s_sop) diagnostic = 4;
                if (s_eop && expected_length != 0) begin
                    if (next_count != expected_length) diagnostic = 2;
                    else if (invalid_enum) diagnostic = 3;
                end
            end
        end
    end
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active <= 0;
            byte_count <= 0;
            message_type <= 0;
            packet <= 0;
            error_valid <= 0;
            error_code <= 0;
            stat_bytes <= 0;
            stat_decoded <= 0;
            stat_errors <= 0;
            stat_unsupported <= 0;
            stat_aborts <= 0;
            stat_resync <= 0;
        end else begin
            error_valid <= (diagnostic != 0);
            error_code <= diagnostic;
            if (diagnostic != 0) stat_errors <= stat_errors + 1'b1;
            if (s_abort) begin
                if (active) stat_aborts <= stat_aborts + 1'b1;
                active <= 0;
                byte_count <= 0;
                packet <= 0;
            end else if (accepted) begin
                stat_bytes <= stat_bytes + 1'b1;
                if (s_sop || active) begin
                    if (s_sop) begin
                        message_type <= s_data;
                        if (active) stat_resync <= stat_resync + 1'b1;
                    end
                    active <= !s_eop;
                    byte_count <= s_eop ? 0 : next_count;
                    packet <= shifted[343:0];
                    if (s_eop && expected_length == 0)
                        stat_unsupported <= stat_unsupported + 1'b1;
                    if (emit_event) stat_decoded <= stat_decoded + 1'b1;
                end
            end
        end
    end
endmodule
`default_nettype wire
