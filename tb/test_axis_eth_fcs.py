#!/usr/bin/env python
"""

Copyright (c) 2015-2016 Alex Forencich

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

"""

from myhdl import *
import os

try:
    from queue import Queue
except ImportError:
    from Queue import Queue

import axis_ep
import eth_ep

module = 'axis_eth_fcs'

srcs = []

srcs.append("../rtl/%s.v" % module)
srcs.append("../rtl/eth_crc_8.v")
srcs.append("test_%s.v" % module)

src = ' '.join(srcs)

build_cmd = "iverilog -o test_%s.vvp %s" % (module, src)

def dut_axis_eth_fcs(clk,
                     rst,
                     current_test,

                     input_axis_tdata,
                     input_axis_tvalid,
                     input_axis_tready,
                     input_axis_tlast,
                     input_axis_tuser,

                     output_fcs,
                     output_fcs_valid):

    if os.system(build_cmd):
        raise Exception("Error running build command")
    return Cosimulation("vvp -m myhdl test_%s.vvp -lxt2" % module,
                clk=clk,
                rst=rst,
                current_test=current_test,

                input_axis_tdata=input_axis_tdata,
                input_axis_tvalid=input_axis_tvalid,
                input_axis_tready=input_axis_tready,
                input_axis_tlast=input_axis_tlast,
                input_axis_tuser=input_axis_tuser,

                output_fcs=output_fcs,
                output_fcs_valid=output_fcs_valid)

def bench():

    # Parameters


    # Inputs
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    current_test = Signal(intbv(0)[8:])

    input_axis_tdata = Signal(intbv(0)[8:])
    input_axis_tvalid = Signal(bool(0))
    input_axis_tlast = Signal(bool(0))
    input_axis_tuser = Signal(bool(0))

    # Outputs
    input_axis_tready = Signal(bool(1))
    output_fcs = Signal(intbv(0)[32:])
    output_fcs_valid = Signal(bool(0))

    # sources and sinks
    source_queue = Queue()
    source_pause = Signal(bool(0))

    source = axis_ep.AXIStreamSource(clk,
                                     rst,
                                     tdata=input_axis_tdata,
                                     tvalid=input_axis_tvalid,
                                     tready=input_axis_tready,
                                     tlast=input_axis_tlast,
                                     tuser=input_axis_tuser,
                                     fifo=source_queue,
                                     pause=source_pause,
                                     name='source')

    # DUT
    dut = dut_axis_eth_fcs(clk,
                           rst,
                           current_test,

                           input_axis_tdata,
                           input_axis_tvalid,
                           input_axis_tready,
                           input_axis_tlast,
                           input_axis_tuser,

                           output_fcs,
                           output_fcs_valid)

    @always(delay(4))
    def clkgen():
        clk.next = not clk

    @instance
    def check():
        yield delay(100)
        yield clk.posedge
        rst.next = 1
        yield clk.posedge
        rst.next = 0
        yield clk.posedge
        yield delay(100)
        yield clk.posedge

        # testbench stimulus

        for payload_len in list(range(1,18))+list(range(64,82)):
            yield clk.posedge
            print("test 1: test packet, length %d" % payload_len)
            current_test.next = 1

            test_frame = eth_ep.EthFrame()
            test_frame.eth_dest_mac = 0xDAD1D2D3D4D5
            test_frame.eth_src_mac = 0x5A5152535455
            test_frame.eth_type = 0x8000
            test_frame.payload = bytearray(range(payload_len))
            test_frame.update_fcs()

            axis_frame = test_frame.build_axis()

            source_queue.put(axis_frame)
            yield clk.posedge
            yield clk.posedge

            yield output_fcs_valid.posedge

            print(hex(int(output_fcs)))
            print(hex(test_frame.eth_fcs))

            assert output_fcs == test_frame.eth_fcs

            yield delay(100)

        raise StopSimulation

    return dut, source, clkgen, check

def test_bench():
    sim = Simulation(bench())
    sim.run()

if __name__ == '__main__':
    print("Running test...")
    test_bench()
