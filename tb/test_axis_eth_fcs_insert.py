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
import struct
import zlib

try:
    from queue import Queue
except ImportError:
    from Queue import Queue

import axis_ep
import eth_ep

module = 'axis_eth_fcs_insert'

srcs = []

srcs.append("../rtl/%s.v" % module)
srcs.append("../rtl/eth_crc_8.v")
srcs.append("test_%s.v" % module)

src = ' '.join(srcs)

build_cmd = "iverilog -o test_%s.vvp %s" % (module, src)

def dut_axis_eth_fcs_insert(clk,
                            rst,
                            current_test,
                            
                            input_axis_tdata,
                            input_axis_tvalid,
                            input_axis_tready,
                            input_axis_tlast,
                            input_axis_tuser,
                            
                            output_axis_tdata,
                            output_axis_tvalid,
                            output_axis_tready,
                            output_axis_tlast,
                            output_axis_tuser,

                            busy):

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

                output_axis_tdata=output_axis_tdata,
                output_axis_tvalid=output_axis_tvalid,
                output_axis_tready=output_axis_tready,
                output_axis_tlast=output_axis_tlast,
                output_axis_tuser=output_axis_tuser,

                busy=busy)

def bench():

    # Parameters
    ENABLE_PADDING = 1
    MIN_FRAME_LENGTH = 64

    # Inputs
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    current_test = Signal(intbv(0)[8:])

    input_axis_tdata = Signal(intbv(0)[8:])
    input_axis_tvalid = Signal(bool(0))
    input_axis_tlast = Signal(bool(0))
    input_axis_tuser = Signal(bool(0))
    output_axis_tready = Signal(bool(0))

    # Outputs
    input_axis_tready = Signal(bool(0))
    output_axis_tdata = Signal(intbv(0)[8:])
    output_axis_tvalid = Signal(bool(0))
    output_axis_tlast = Signal(bool(0))
    output_axis_tuser = Signal(bool(0))
    busy = Signal(bool(0))

    # sources and sinks
    source_queue = Queue()
    source_pause = Signal(bool(0))
    sink_queue = Queue()
    sink_pause = Signal(bool(0))

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

    sink = axis_ep.AXIStreamSink(clk,
                                rst,
                                tdata=output_axis_tdata,
                                tvalid=output_axis_tvalid,
                                tready=output_axis_tready,
                                tlast=output_axis_tlast,
                                tuser=output_axis_tuser,
                                fifo=sink_queue,
                                pause=sink_pause,
                                name='sink')

    # DUT
    dut = dut_axis_eth_fcs_insert(clk,
                                  rst,
                                  current_test,

                                  input_axis_tdata,
                                  input_axis_tvalid,
                                  input_axis_tready,
                                  input_axis_tlast,
                                  input_axis_tuser,

                                  output_axis_tdata,
                                  output_axis_tvalid,
                                  output_axis_tready,
                                  output_axis_tlast,
                                  output_axis_tuser,

                                  busy)

    @always(delay(4))
    def clkgen():
        clk.next = not clk

    def wait_normal():
        while input_axis_tvalid or output_axis_tvalid:
            yield clk.posedge

    def wait_pause_source():
        while input_axis_tvalid or output_axis_tvalid:
            source_pause.next = True
            yield clk.posedge
            yield clk.posedge
            yield clk.posedge
            source_pause.next = False
            yield clk.posedge

    def wait_pause_sink():
        while input_axis_tvalid or output_axis_tvalid:
            sink_pause.next = True
            yield clk.posedge
            yield clk.posedge
            yield clk.posedge
            sink_pause.next = False
            yield clk.posedge

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

            for wait in wait_normal, wait_pause_source, wait_pause_sink:
                source_queue.put(axis_frame)
                yield clk.posedge
                yield clk.posedge

                yield wait()

                yield clk.posedge
                yield clk.posedge
                yield clk.posedge

                rx_frame = None
                if not sink_queue.empty():
                    rx_frame = sink_queue.get()

                eth_frame = eth_ep.EthFrame()
                eth_frame.parse_axis_fcs(rx_frame)

                print(hex(eth_frame.eth_fcs))
                print(hex(eth_frame.calc_fcs()))

                assert eth_frame.payload.data == test_frame.payload.data
                assert eth_frame.eth_fcs == eth_frame.calc_fcs()
                assert eth_frame.eth_dest_mac == test_frame.eth_dest_mac
                assert eth_frame.eth_src_mac == test_frame.eth_src_mac
                assert eth_frame.eth_type == test_frame.eth_type
                assert eth_frame.payload.data.index(test_frame.payload.data) == 0

                assert sink_queue.empty()

                yield delay(100)

            yield clk.posedge
            print("test 2: back-to-back packets, length %d" % payload_len)
            current_test.next = 2

            test_frame1 = eth_ep.EthFrame()
            test_frame1.eth_dest_mac = 0xDAD1D2D3D4D5
            test_frame1.eth_src_mac = 0x5A5152535455
            test_frame1.eth_type = 0x8000
            test_frame1.payload = bytearray(range(payload_len))
            test_frame1.update_fcs()
            test_frame2 = eth_ep.EthFrame()
            test_frame2.eth_dest_mac = 0xDAD1D2D3D4D5
            test_frame2.eth_src_mac = 0x5A5152535455
            test_frame2.eth_type = 0x8000
            test_frame2.payload = bytearray(range(payload_len))
            test_frame2.update_fcs()

            axis_frame1 = test_frame1.build_axis()
            axis_frame2 = test_frame2.build_axis()

            for wait in wait_normal, wait_pause_source, wait_pause_sink:
                source_queue.put(axis_frame1)
                source_queue.put(axis_frame2)
                yield clk.posedge
                yield clk.posedge

                yield wait()

                yield clk.posedge
                yield clk.posedge
                yield clk.posedge

                rx_frame = None
                if not sink_queue.empty():
                    rx_frame = sink_queue.get()

                eth_frame = eth_ep.EthFrame()
                eth_frame.parse_axis_fcs(rx_frame)

                print(hex(eth_frame.eth_fcs))
                print(hex(eth_frame.calc_fcs()))

                assert eth_frame.payload.data == test_frame1.payload.data
                assert eth_frame.eth_fcs == eth_frame.calc_fcs()
                assert eth_frame.eth_dest_mac == test_frame1.eth_dest_mac
                assert eth_frame.eth_src_mac == test_frame1.eth_src_mac
                assert eth_frame.eth_type == test_frame1.eth_type
                assert eth_frame.payload.data.index(test_frame1.payload.data) == 0

                rx_frame = None
                if not sink_queue.empty():
                    rx_frame = sink_queue.get()

                eth_frame = eth_ep.EthFrame()
                eth_frame.parse_axis_fcs(rx_frame)

                print(hex(eth_frame.eth_fcs))
                print(hex(eth_frame.calc_fcs()))

                assert eth_frame.payload.data == test_frame2.payload.data
                assert eth_frame.eth_fcs == eth_frame.calc_fcs()
                assert eth_frame.eth_dest_mac == test_frame2.eth_dest_mac
                assert eth_frame.eth_src_mac == test_frame2.eth_src_mac
                assert eth_frame.eth_type == test_frame2.eth_type
                assert eth_frame.payload.data.index(test_frame2.payload.data) == 0

                assert sink_queue.empty()

                yield delay(100)

            yield clk.posedge
            print("test 3: tuser assert, length %d" % payload_len)
            current_test.next = 3

            test_frame1 = eth_ep.EthFrame()
            test_frame1.eth_dest_mac = 0xDAD1D2D3D4D5
            test_frame1.eth_src_mac = 0x5A5152535455
            test_frame1.eth_type = 0x8000
            test_frame1.payload = bytearray(range(payload_len))
            test_frame1.update_fcs()
            test_frame2 = eth_ep.EthFrame()
            test_frame2.eth_dest_mac = 0xDAD1D2D3D4D5
            test_frame2.eth_src_mac = 0x5A5152535455
            test_frame2.eth_type = 0x8000
            test_frame2.payload = bytearray(range(payload_len))
            test_frame2.update_fcs()

            axis_frame1 = test_frame1.build_axis()
            axis_frame2 = test_frame2.build_axis()

            axis_frame1.user = 1

            for wait in wait_normal, wait_pause_source, wait_pause_sink:
                source_queue.put(axis_frame1)
                source_queue.put(axis_frame2)
                yield clk.posedge
                yield clk.posedge

                yield wait()

                yield clk.posedge
                yield clk.posedge
                yield clk.posedge

                rx_frame = None
                if not sink_queue.empty():
                    rx_frame = sink_queue.get()

                assert rx_frame.user[-1]

                rx_frame = None
                if not sink_queue.empty():
                    rx_frame = sink_queue.get()

                eth_frame = eth_ep.EthFrame()
                eth_frame.parse_axis_fcs(rx_frame)

                print(hex(eth_frame.eth_fcs))
                print(hex(eth_frame.calc_fcs()))

                assert eth_frame.payload.data == test_frame2.payload.data
                assert eth_frame.eth_fcs == eth_frame.calc_fcs()
                assert eth_frame.eth_dest_mac == test_frame2.eth_dest_mac
                assert eth_frame.eth_src_mac == test_frame2.eth_src_mac
                assert eth_frame.eth_type == test_frame2.eth_type
                assert eth_frame.payload.data.index(test_frame2.payload.data) == 0

                assert sink_queue.empty()

                yield delay(100)

        for payload_len in list(range(1,18)):
            yield clk.posedge
            print("test 4: test short packet, length %d" % payload_len)
            current_test.next = 4

            test_frame = bytearray(range(payload_len))

            for wait in wait_normal, wait_pause_source, wait_pause_sink:
                source_queue.put(test_frame)
                yield clk.posedge
                yield clk.posedge

                yield wait()

                yield clk.posedge
                yield clk.posedge
                yield clk.posedge

                rx_frame = None
                if not sink_queue.empty():
                    rx_frame = sink_queue.get()

                payload = rx_frame.data[:-4]
                fcs = struct.unpack('<L', rx_frame.data[-4:])[0]
                check_fcs = zlib.crc32(bytes(payload)) & 0xffffffff

                print(hex(fcs))
                print(hex(check_fcs))

                assert test_frame == payload
                assert check_fcs == fcs

                assert sink_queue.empty()

                yield delay(100)

        raise StopSimulation

    return dut, source, sink, clkgen, check

def test_bench():
    sim = Simulation(bench())
    sim.run()

if __name__ == '__main__':
    print("Running test...")
    test_bench()
