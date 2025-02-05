#!/usr/bin/env python
"""
Generates an AXI Stream crosspoint switch with the specified number of ports
"""

from __future__ import print_function

import argparse
import math
from jinja2 import Template

def main():
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument('-p', '--ports',  type=int, default=4, help="number of ports")
    parser.add_argument('-n', '--name',   type=str, help="module name")
    parser.add_argument('-o', '--output', type=str, help="output file name")

    args = parser.parse_args()

    try:
        generate(**args.__dict__)
    except IOError as ex:
        print(ex)
        exit(1)

def generate(ports=4, name=None, output=None):
    if name is None:
        name = "axis_crosspoint_{0}x{0}".format(ports)

    if output is None:
        output = name + ".v"

    print("Opening file '{0}'...".format(output))

    output_file = open(output, 'w')

    print("Generating {0} port AXI Stream crosspoint {1}...".format(ports, name))

    select_width = int(math.ceil(math.log(ports, 2)))

    t = Template(u"""/*

Copyright (c) 2014-2016 Alex Forencich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

*/

// Language: Verilog 2001

`timescale 1ns / 1ps

/*
 * AXI4-Stream {{n}}x{{n}} crosspoint
 */
module {{name}} #
(
    parameter DATA_WIDTH = 8
)
(
    input  wire        clk,
    input  wire        rst,

    /*
     * AXI Stream inputs
     */
{%- for p in ports %}
    input  wire [DATA_WIDTH-1:0]  input_{{p}}_axis_tdata,
    input  wire                   input_{{p}}_axis_tvalid,
    input  wire                   input_{{p}}_axis_tlast,
    input  wire                   input_{{p}}_axis_tuser,
{% endfor %}
    /*
     * AXI Stream outputs
     */
{%- for p in ports %}
    output wire [DATA_WIDTH-1:0]  output_{{p}}_axis_tdata,
    output wire                   output_{{p}}_axis_tvalid,
    output wire                   output_{{p}}_axis_tlast,
    output wire                   output_{{p}}_axis_tuser,
{% endfor %}
    /*
     * Control
     */
{%- for p in ports %}
    input  wire [{{w-1}}:0]             output_{{p}}_select{% if not loop.last %},{% endif %}
{%- endfor %}
);
{% for p in ports %}
reg [DATA_WIDTH-1:0]  input_{{p}}_axis_tdata_reg = {DATA_WIDTH{1'b0}};
reg                   input_{{p}}_axis_tvalid_reg = 1'b0;
reg                   input_{{p}}_axis_tlast_reg = 1'b0;
reg                   input_{{p}}_axis_tuser_reg = 1'b0;
{% endfor %}

{%- for p in ports %}
reg [DATA_WIDTH-1:0]  output_{{p}}_axis_tdata_reg = {DATA_WIDTH{1'b0}};
reg                   output_{{p}}_axis_tvalid_reg = 1'b0;
reg                   output_{{p}}_axis_tlast_reg = 1'b0;
reg                   output_{{p}}_axis_tuser_reg = 1'b0;
{% endfor %}

{%- for p in ports %}
reg [{{w-1}}:0]             output_{{p}}_select_reg = {{w}}'d0;
{%- endfor %}
{% for p in ports %}
assign output_{{p}}_axis_tdata = output_{{p}}_axis_tdata_reg;
assign output_{{p}}_axis_tvalid = output_{{p}}_axis_tvalid_reg;
assign output_{{p}}_axis_tlast = output_{{p}}_axis_tlast_reg;
assign output_{{p}}_axis_tuser = output_{{p}}_axis_tuser_reg;
{% endfor %}

always @(posedge clk) begin
    if (rst) begin
{%- for p in ports %}
        output_{{p}}_select_reg <= {{w}}'d0;
{%- endfor %}
{% for p in ports %}
        input_{{p}}_axis_tvalid_reg <= 1'b0;
{%- endfor %}
{% for p in ports %}
        output_{{p}}_axis_tvalid_reg <= 1'b0;
{%- endfor %}
    end else begin
{%- for p in ports %}
        input_{{p}}_axis_tvalid_reg <= input_{{p}}_axis_tvalid;
{%- endfor %}
{% for p in ports %}
        output_{{p}}_select_reg <= output_{{p}}_select;
{%- endfor %}
{%- for p in ports %}

        case (output_{{p}}_select_reg)
{%- for q in ports %}
            {{w}}'d{{q}}: output_{{p}}_axis_tvalid_reg <= input_{{q}}_axis_tvalid_reg;
{%- endfor %}
        endcase
{%- endfor %}
    end
{%- for p in ports %}

    input_{{p}}_axis_tdata_reg <= input_{{p}}_axis_tdata;
    input_{{p}}_axis_tlast_reg <= input_{{p}}_axis_tlast;
    input_{{p}}_axis_tuser_reg <= input_{{p}}_axis_tuser;
{%- endfor %}
{%- for p in ports %}

    case (output_{{p}}_select_reg)
{%- for q in ports %}
        {{w}}'d{{q}}: begin
            output_{{p}}_axis_tdata_reg <= input_{{q}}_axis_tdata_reg;
            output_{{p}}_axis_tlast_reg <= input_{{q}}_axis_tlast_reg;
            output_{{p}}_axis_tuser_reg <= input_{{q}}_axis_tuser_reg;
        end
{%- endfor %}
    endcase
{%- endfor %}
end

endmodule

""")
    
    output_file.write(t.render(
        n=ports,
        w=select_width,
        name=name,
        ports=range(ports)
    ))
    
    print("Done")

if __name__ == "__main__":
    main()

