`timescale 1ns/1ps
`default_nettype none
module tb_decoder;
    parameter integer FIFO_DEPTH = 4;
    reg clk = 0;
    always #5 clk = !clk;
    reg rst_n = 0;
    reg [7:0] s_data = 0;
    reg s_valid = 0, s_sop = 0, s_eop = 0, s_abort = 0;
    wire s_ready, m_valid, error_valid;
    reg m_ready = 0;
    wire [455:0] m_event;
    wire [3:0] error_code;
    wire [31:0] stat_bytes, stat_decoded, stat_errors, stat_unsupported, stat_aborts, stat_resync;
    itch_stream_decoder #(.FIFO_DEPTH(FIFO_DEPTH)) dut (.*);
    integer cycle = 0, source, trace, code, sop, eop, data, gap, rc;
    integer seed = 1, ready_percent = 65, stall_start = -1, stall_end = -1;
    reg [31:0] random_state;
    reg [2047:0] stim_path, trace_path;
    always @(negedge clk) begin
        random_state = random_state ^ (random_state << 13);
        random_state = random_state ^ (random_state >> 17);
        random_state = random_state ^ (random_state << 5);
        if (cycle >= stall_start && cycle < stall_end) m_ready = 0;
        else m_ready = ((random_state % 100) < ready_percent);
    end
    // Observe pre-edge signals: transfers happen on this edge; registered
    // diagnostics/statistics are the results of the preceding edge.
    always @(posedge clk) begin
        if (trace != 0 && cycle > 0)
            $fdisplay(trace, "%0d %0d %0d %0d %0d %0d %0d %02h %0d %0d %0114h %0d %0d %0d %0d %0d %0d %0d %0d",
                cycle, rst_n, s_valid, s_ready, s_sop, s_eop, s_abort, s_data,
                m_valid, m_ready, m_event, error_valid, error_code, stat_bytes,
                stat_decoded, stat_errors, stat_unsupported, stat_aborts, stat_resync);
        cycle = cycle + 1;
        if (cycle > 3000000) $fatal(1, "timeout / possible deadlock");
    end
    initial begin
        if (!$value$plusargs("STIM=%s", stim_path)) $fatal(1, "missing STIM");
        if (!$value$plusargs("TRACE=%s", trace_path)) $fatal(1, "missing TRACE");
        rc = $value$plusargs("SEED=%d", seed);
        rc = $value$plusargs("READY=%d", ready_percent);
        rc = $value$plusargs("STALL_START=%d", stall_start);
        rc = $value$plusargs("STALL_END=%d", stall_end);
        random_state = seed == 0 ? 1 : seed;
        source = $fopen(stim_path, "r");
        trace = $fopen(trace_path, "w");
        if (source == 0 || trace == 0) $fatal(1, "cannot open test files");
        repeat (3) @(negedge clk);
        rst_n = 1;
        while (!$feof(source)) begin
            rc = $fscanf(source, "%d %d %d %h %d\n", code, sop, eop, data, gap);
            if (rc == 5) begin
                case (code)
                    1: begin
                        s_data = data[7:0]; s_sop = sop[0]; s_eop = eop[0]; s_valid = 1;
                        @(posedge clk);
                        while (!s_ready) @(posedge clk);
                        @(negedge clk);
                        s_valid = 0;
                        repeat (gap) @(negedge clk);
                    end
                    2: begin
                        s_valid = 0; s_abort = 1;
                        @(negedge clk); s_abort = 0;
                        repeat (gap) @(negedge clk);
                    end
                    3: begin
                        s_valid = 0; rst_n = 0;
                        repeat (gap < 1 ? 1 : gap) @(negedge clk);
                        rst_n = 1;
                    end
                    4: begin
                        s_data = data[7:0]; s_sop = sop[0]; s_eop = eop[0];
                        s_valid = 1; s_abort = 1;
                        @(negedge clk); s_valid = 0; s_abort = 0;
                    end
                    5: begin
                        ready_percent = gap;
                        m_ready = (ready_percent == 100);
                    end
                    0: begin s_valid = 0; repeat (gap) @(negedge clk); end
                    default: $fatal(1, "invalid stimulus command");
                endcase
            end else if (rc != -1) $fatal(1, "malformed stimulus");
        end
        s_valid = 0; s_abort = 0;
        while (m_valid) @(negedge clk);
        repeat (8) @(negedge clk);
        $fclose(source); $fclose(trace);
        $display("PASS driver completed %0d cycles", cycle);
        $finish;
    end
endmodule
`default_nettype wire
