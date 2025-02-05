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

module = 'eth_mac_10g_tx'

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

def dut_eth_mac_10g_tx(clk,
                       rst,
                       current_test,

                       input_axis_tdata,
                       input_axis_tkeep,
                       input_axis_tvalid,
                       input_axis_tready,
                       input_axis_tlast,
                       input_axis_tuser,

                       xgmii_txd,
                       xgmii_txc,

                       ifg_delay):

    if os.system(build_cmd):
        raise Exception("Error running build command")
    return Cosimulation("vvp -m myhdl test_%s.vvp -lxt2" % module,
                clk=clk,
                rst=rst,
                current_test=current_test,

                input_axis_tdata=input_axis_tdata,
                input_axis_tkeep=input_axis_tkeep,
                input_axis_tvalid=input_axis_tvalid,
                input_axis_tready=input_axis_tready,
                input_axis_tlast=input_axis_tlast,
                input_axis_tuser=input_axis_tuser,

                xgmii_txd=xgmii_txd,
                xgmii_txc=xgmii_txc,
                
                ifg_delay=ifg_delay)

def bench():

    # Parameters
    ENABLE_PADDING = 1
    MIN_FRAME_LENGTH = 64

    # Inputs
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    current_test = Signal(intbv(0)[8:])

    input_axis_tdata = Signal(intbv(0)[64:])
    input_axis_tkeep = Signal(intbv(0)[8:])
    input_axis_tvalid = Signal(bool(0))
    input_axis_tlast = Signal(bool(0))
    input_axis_tuser = Signal(bool(0))
    ifg_delay = Signal(intbv(0)[8:])

    # Outputs
    input_axis_tready = Signal(bool(0))
    xgmii_txd = Signal(intbv(0x0707070707070707)[64:])
    xgmii_txc = Signal(intbv(0xff)[8:])
    
    # sources and sinks
    source_queue = Queue()
    source_pause = Signal(bool(0))
    sink_queue = Queue()

    source = axis_ep.AXIStreamSource(clk,
                                     rst,
                                     tdata=input_axis_tdata,
                                     tkeep=input_axis_tkeep,
                                     tvalid=input_axis_tvalid,
                                     tready=input_axis_tready,
                                     tlast=input_axis_tlast,
                                     tuser=input_axis_tuser,
                                     fifo=source_queue,
                                     pause=source_pause,
                                     name='source')

    sink = xgmii_ep.XGMIISink(clk,
                              rst,
                              rxd=xgmii_txd,
                              rxc=xgmii_txc,
                              fifo=sink_queue,
                              name='sink')

    # DUT
    dut = dut_eth_mac_10g_tx(clk,
                             rst,
                             current_test,

                             input_axis_tdata,
                             input_axis_tkeep,
                             input_axis_tvalid,
                             input_axis_tready,
                             input_axis_tlast,
                             input_axis_tuser,

                             xgmii_txd,
                             xgmii_txc,
                             
                             ifg_delay)

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

        ifg_delay.next = 12

        # testbench stimulus

        for payload_len in list(range(1,18))+list(range(40,58)):
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

            while xgmii_txc != 0xff or input_axis_tvalid:
                yield clk.posedge

            yield clk.posedge
            yield clk.posedge
            yield clk.posedge

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            assert rx_frame.data[0:8] == bytearray(b'\x55\x55\x55\x55\x55\x55\x55\xD5')

            eth_frame = eth_ep.EthFrame()
            eth_frame.parse_axis_fcs(rx_frame.data[8:])

            print(hex(eth_frame.eth_fcs))
            print(hex(eth_frame.calc_fcs()))

            assert len(eth_frame.payload.data) == max(payload_len, 46)
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

            source_queue.put(axis_frame1)
            source_queue.put(axis_frame2)
            yield clk.posedge
            yield clk.posedge

            while xgmii_txc != 0xff or input_axis_tvalid:
                yield clk.posedge

            yield clk.posedge
            yield clk.posedge
            yield clk.posedge

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            assert rx_frame.data[0:8] == bytearray(b'\x55\x55\x55\x55\x55\x55\x55\xD5')

            eth_frame = eth_ep.EthFrame()
            eth_frame.parse_axis_fcs(rx_frame.data[8:])

            print(hex(eth_frame.eth_fcs))
            print(hex(eth_frame.calc_fcs()))

            assert len(eth_frame.payload.data) == max(payload_len, 46)
            assert eth_frame.eth_fcs == eth_frame.calc_fcs()
            assert eth_frame.eth_dest_mac == test_frame1.eth_dest_mac
            assert eth_frame.eth_src_mac == test_frame1.eth_src_mac
            assert eth_frame.eth_type == test_frame1.eth_type
            assert eth_frame.payload.data.index(test_frame1.payload.data) == 0

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            assert rx_frame.data[0:8] == bytearray(b'\x55\x55\x55\x55\x55\x55\x55\xD5')

            eth_frame = eth_ep.EthFrame()
            eth_frame.parse_axis_fcs(rx_frame.data[8:])

            print(hex(eth_frame.eth_fcs))
            print(hex(eth_frame.calc_fcs()))

            assert len(eth_frame.payload.data) == max(payload_len, 46)
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

            source_queue.put(axis_frame1)
            source_queue.put(axis_frame2)
            yield clk.posedge
            yield clk.posedge

            while xgmii_txc != 0xff or input_axis_tvalid:
                yield clk.posedge

            yield clk.posedge
            yield clk.posedge
            yield clk.posedge

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            assert rx_frame.data[0:8] == bytearray(b'\x55\x55\x55\x55\x55\x55\x55\xD5')
            assert rx_frame.error[-1]

            # bad packet

            rx_frame = None
            if not sink_queue.empty():
                rx_frame = sink_queue.get()

            assert rx_frame.data[0:8] == bytearray(b'\x55\x55\x55\x55\x55\x55\x55\xD5')

            eth_frame = eth_ep.EthFrame()
            eth_frame.parse_axis_fcs(rx_frame.data[8:])

            print(hex(eth_frame.eth_fcs))
            print(hex(eth_frame.calc_fcs()))

            assert len(eth_frame.payload.data) == max(payload_len, 46)
            assert eth_frame.eth_fcs == eth_frame.calc_fcs()
            assert eth_frame.eth_dest_mac == test_frame2.eth_dest_mac
            assert eth_frame.eth_src_mac == test_frame2.eth_src_mac
            assert eth_frame.eth_type == test_frame2.eth_type
            assert eth_frame.payload.data.index(test_frame2.payload.data) == 0

            assert sink_queue.empty()

            yield delay(100)

        for payload_len in list(range(46,54)):
            yield clk.posedge
            print("test 4: test stream, length %d" % payload_len)
            current_test.next = 4

            for i in range(10):
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

            while xgmii_txc != 0xff or input_axis_tvalid:
                yield clk.posedge

            yield clk.posedge
            yield clk.posedge
            yield clk.posedge

            yield delay(100)

        raise StopSimulation

    return dut, source, sink, clkgen, check

def test_bench():
    sim = Simulation(bench())
    sim.run()

if __name__ == '__main__':
    print("Running test...")
    test_bench()
