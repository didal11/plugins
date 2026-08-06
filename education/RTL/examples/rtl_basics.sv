// RTL education examples for chapters 1-10.

module mux2 #(
    parameter int DATA_W = 8
) (
    input  logic [DATA_W-1:0] a,
    input  logic [DATA_W-1:0] b,
    input  logic              sel,
    output logic [DATA_W-1:0] y
);
    always_comb begin
        if (sel)
            y = b;
        else
            y = a;
    end
endmodule


module simple_alu #(
    parameter int DATA_W = 8
) (
    input  logic [DATA_W-1:0] a,
    input  logic [DATA_W-1:0] b,
    input  logic [2:0]        opcode,
    output logic [DATA_W-1:0] result,
    output logic              zero,
    output logic              error
);
    localparam logic [2:0] OP_ADD = 3'd0;
    localparam logic [2:0] OP_SUB = 3'd1;
    localparam logic [2:0] OP_AND = 3'd2;
    localparam logic [2:0] OP_OR  = 3'd3;
    localparam logic [2:0] OP_XOR = 3'd4;

    always_comb begin
        result = '0;
        error  = 1'b0;

        case (opcode)
            OP_ADD: result = a + b;
            OP_SUB: result = a - b;
            OP_AND: result = a & b;
            OP_OR:  result = a | b;
            OP_XOR: result = a ^ b;

            default: begin
                result = '0;
                error  = 1'b1;
            end
        endcase
    end

    assign zero = (result == '0);
endmodule


module register_with_enable #(
    parameter int DATA_W = 8
) (
    input  logic              clk,
    input  logic              reset_n,
    input  logic              enable,
    input  logic [DATA_W-1:0] d,
    output logic [DATA_W-1:0] q
);
    always_ff @(posedge clk or negedge reset_n) begin
        if (!reset_n)
            q <= '0;
        else if (enable)
            q <= d;
    end
endmodule


module pipeline2 #(
    parameter int DATA_W = 8
) (
    input  logic              clk,
    input  logic              reset_n,
    input  logic [DATA_W-1:0] data_in,
    input  logic              valid_in,
    output logic [DATA_W-1:0] data_out,
    output logic              valid_out
);
    logic [DATA_W-1:0] stage1_data;
    logic              stage1_valid;

    always_ff @(posedge clk or negedge reset_n) begin
        if (!reset_n) begin
            stage1_data  <= '0;
            stage1_valid <= 1'b0;
            data_out     <= '0;
            valid_out    <= 1'b0;
        end
        else begin
            stage1_data  <= data_in;
            stage1_valid <= valid_in;
            data_out     <= stage1_data;
            valid_out    <= stage1_valid;
        end
    end
endmodule


module vector_last_detector #(
    parameter int CNT_W = 3
) (
    input  logic [CNT_W-1:0] sample_cnt,
    input  logic [CNT_W:0]   vector_len,
    output logic             vector_last
);
    assign vector_last =
        ({1'b0, sample_cnt} == (vector_len - 1'b1));
endmodule


module gpio_example (
    input  logic out_enable,
    input  logic out_data,
    output logic in_data,
    inout  wire  pad
);
    assign pad     = out_enable ? out_data : 1'bz;
    assign in_data = pad;
endmodule
