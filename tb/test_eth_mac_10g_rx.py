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
import xgmii_ep

axis_ep.skip_assert = True

module = 'eth_mac_10g_rx'

srcs = []

srcs.append("../rtl/%s.v" % module)
srcs.append("../rtl/eth_crc_8.v")
srcs.append("../rtl/eth_crc_16.v")
srcs.append("../rtl/eth_crc_24.v")
srcs.append("../rtl/eth_crc_32.v")
srcs.append("../rtl/eth_crc_40.v")
srcs.append("../rtl/eth_crc_48.v")
srcs.append("../rtl/eth_crc_56.v")
srcs.append("../rtl/eth_crc_64.v")
srcs.append("test_%s.v" % module)

src = ' '.join(srcs)

build_cmd = "iverilog -o test_%s.vvp %s" % (module, src)

def dut_eth_mac_10g_rx(clk,
                       rst,
                       current_test,

                       xgmii_rxd,
                       xgmii_rxc,

                       output_axis_tdata,
                       output_axis_tkeep,
                       output_axis_tvalid,
                       output_axis_tlast,
                       output_axis_tuser,

                       error_bad_frame,
                       error_bad_fcs):

    if os.system(build_cmd):
        raise Exception("Error running build command")
    return Cosimulation("vvp -m myhdl test_%s.vvp -lxt2" % module,
                clk=clk,
                rst=rst,
                current_test=current_test,

                xgmii_rxd=xgmii_rxd,
                xgmii_rxc=xgmii_rxc,

                output_axis_tdata=output_axis_tdata,
                output_axis_tkeep=output_axis_tkeep,
                output_axis_tvalid=output_axis_tvalid,
                output_axis_tlast=output_axis_tlast,
                output_axis_tuser=output_axis_tuser,

                error_bad_frame=error_bad_frame,
                error_bad_fcs=error_bad_fcs)

def bench():

    # Parameters


    # Inputs
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    current_test = Signal(intbv(0)[8:])

    xgmii_rxd = Signal(intbv(0x0707070707070707)[64:])
    xgmii_rxc = Signal(intbv(0xff)[8:])

    # Outputs
    output_axis_tdata = Signal(intbv(0)[64:])
    output_axis_tkeep = Signal(intbv(0)[8:])
    output_axis_tvalid = Signal(bool(0))
    output_axis_tlast = Signal(bool(0))
    output_axis_tuser = Signal(bool(0))
    error_bad_frame = Signal(bool(0))
    error_bad_fcs = Signal(bool(0))

    # sources and sinks
    source_queue = Queue()
    sink_queue = Queue()

    source = xgmii_ep.XGMIISource(clk,
                                  rst,
                                  txd=xgmii_rxd,
                                  txc=xgmii_rxc,
                                  fifo=source_queue,
                                  name='source')

    sink = axis_ep.AXIStreamSink(clk,
                                 rst,
                                 tdata=output_axis_tdata,
                                 tkeep=output_axis_tkeep,
                                 tvalid=output_axis_tvalid,
                                 tlast=output_axis_tlast,
                                 tuser=output_axis_tuser,
                                 fifo=sink_queue,
                                 name='sink')

    # DUT
    dut = dut_eth_mac_10g_rx(clk,
                             rst,
                             current_test,

                             xgmii_rxd,
                             xgmii_rxc,

                             output_axis_tdata,
                             output_axis_tkeep,
                             output_axis_tvalid,
                             output_axis_tlast,
                             output_axis_tuser,

                             error_bad_frame,
                             error_bad_fcs)

    @always(delay(4))
    def clkgen():
        clk.next = not clk

    error_bad_frame_asserted = Signal(bool(0))
    error_bad_fcs_asserted = Signal(bool(0))

    @always(clk.posedge)
    def monitor():
        if (error_bad_frame):
            error_bad_frame_asserted.next = 1
        if (error_bad_fcs):
            error_bad_fcs_asserted.next = 1

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

            axis_frame = test_frame.build_axis_fcs()

            xgmii_frame = xgmii_ep.XGMIIFrame(b'\x55\x55\x55\x55\x55\x55\x55\xD5'+bytearray(axis_frame))

            source_queue.put(xgmii_frame)
            yield clk.posedge
            yield clk.posedge

            while xgmii_rxc != 0xff or output_axis_tvalid or not source_queue.empty():
                yield clk.posedge

            yield clk.posedge
            yield clk.posedge
            yield clk.posedge

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            eth_frame = eth_ep.EthFrame()
            eth_frame.parse_axis(rx_frame)
            eth_frame.update_fcs()

            assert eth_frame == test_frame

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

            axis_frame1 = test_frame1.build_axis_fcs()
            axis_frame2 = test_frame2.build_axis_fcs()

            xgmii_frame1 = xgmii_ep.XGMIIFrame(b'\x55\x55\x55\x55\x55\x55\x55\xD5'+bytearray(axis_frame1))
            xgmii_frame2 = xgmii_ep.XGMIIFrame(b'\x55\x55\x55\x55\x55\x55\x55\xD5'+bytearray(axis_frame2))

            source_queue.put(xgmii_frame1)
            source_queue.put(xgmii_frame2)
            yield clk.posedge
            yield clk.posedge

            while xgmii_rxc != 0xff or output_axis_tvalid or not source_queue.empty():
                yield clk.posedge

            yield clk.posedge

            while xgmii_rxc != 0xff or output_axis_tvalid or not source_queue.empty():
                yield clk.posedge

            yield clk.posedge
            yield clk.posedge
            yield clk.posedge

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            eth_frame = eth_ep.EthFrame()
            eth_frame.parse_axis(rx_frame)
            eth_frame.update_fcs()

            assert eth_frame == test_frame1

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            eth_frame = eth_ep.EthFrame()
            eth_frame.parse_axis(rx_frame)
            eth_frame.update_fcs()

            assert eth_frame == test_frame2

            assert sink_queue.empty()

            yield delay(100)

            yield clk.posedge
            print("test 3: truncated frame, length %d" % payload_len)
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

            axis_frame1 = test_frame1.build_axis_fcs()
            axis_frame2 = test_frame2.build_axis_fcs()

            axis_frame1.data = axis_frame1.data[:-1]

            error_bad_frame_asserted.next = 0
            error_bad_fcs_asserted.next = 0

            xgmii_frame1 = xgmii_ep.XGMIIFrame(b'\x55\x55\x55\x55\x55\x55\x55\xD5'+bytearray(axis_frame1))
            xgmii_frame2 = xgmii_ep.XGMIIFrame(b'\x55\x55\x55\x55\x55\x55\x55\xD5'+bytearray(axis_frame2))

            source_queue.put(xgmii_frame1)
            source_queue.put(xgmii_frame2)
            yield clk.posedge
            yield clk.posedge

            while xgmii_rxc != 0xff or output_axis_tvalid or not source_queue.empty():
                yield clk.posedge

            yield clk.posedge

            while xgmii_rxc != 0xff or output_axis_tvalid or not source_queue.empty():
                yield clk.posedge

            yield clk.posedge
            yield clk.posedge
            yield clk.posedge

            assert error_bad_frame_asserted
            assert error_bad_fcs_asserted

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            assert rx_frame.user[-1]

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            eth_frame = eth_ep.EthFrame()
            eth_frame.parse_axis(rx_frame)
            eth_frame.update_fcs()

            assert eth_frame == test_frame2

            assert sink_queue.empty()

            yield delay(100)

            yield clk.posedge
            print("test 4: errored frame, length %d" % payload_len)
            current_test.next = 4

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

            axis_frame1 = test_frame1.build_axis_fcs()
            axis_frame2 = test_frame2.build_axis_fcs()

            error_bad_frame_asserted.next = 0
            error_bad_fcs_asserted.next = 0

            xgmii_frame1 = xgmii_ep.XGMIIFrame(b'\x55\x55\x55\x55\x55\x55\x55\xD5'+bytearray(axis_frame1))
            xgmii_frame2 = xgmii_ep.XGMIIFrame(b'\x55\x55\x55\x55\x55\x55\x55\xD5'+bytearray(axis_frame2))

            xgmii_frame1.error = 1

            source_queue.put(xgmii_frame1)
            source_queue.put(xgmii_frame2)
            yield clk.posedge
            yield clk.posedge

            while xgmii_rxc != 0xff or output_axis_tvalid or not source_queue.empty():
                yield clk.posedge

            yield clk.posedge

            while xgmii_rxc != 0xff or output_axis_tvalid or not source_queue.empty():
                yield clk.posedge

            yield clk.posedge
            yield clk.posedge
            yield clk.posedge

            assert error_bad_frame_asserted
            assert not error_bad_fcs_asserted

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            assert rx_frame.user[-1]

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            eth_frame = eth_ep.EthFrame()
            eth_frame.parse_axis(rx_frame)
            eth_frame.update_fcs()

            assert eth_frame == test_frame2

            assert sink_queue.empty()

            yield delay(100)

        for payload_len in list(range(46,54)):
            yield clk.posedge
            print("test 5: test stream, length %d" % payload_len)
            current_test.next = 5

            for i in range(10):
                test_frame = eth_ep.EthFrame()
                test_frame.eth_dest_mac = 0xDAD1D2D3D4D5
                test_frame.eth_src_mac = 0x5A5152535455
                test_frame.eth_type = 0x8000
                test_frame.payload = bytearray(range(payload_len))
                test_frame.update_fcs()

                axis_frame = test_frame.build_axis_fcs()

                source_queue.put(b'\x55\x55\x55\x55\x55\x55\x55\xD5'+bytearray(axis_frame))

            yield clk.posedge
            yield clk.posedge

            while xgmii_rxc != 0xff or output_axis_tvalid or not source_queue.empty():
                yield clk.posedge

            yield clk.posedge
            yield clk.posedge
            yield clk.posedge

            yield delay(100)

        raise StopSimulation

    return dut, monitor, source, sink, clkgen, check

def test_bench():
    sim = Simulation(bench())
    sim.run()

if __name__ == '__main__':
    print("Running test...")
    test_bench()
