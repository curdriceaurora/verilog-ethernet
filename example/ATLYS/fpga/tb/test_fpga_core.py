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

import eth_ep
import arp_ep
import udp_ep
import gmii_ep

module = 'fpga_core'

srcs = []

srcs.append("../rtl/%s.v" % module)
srcs.append("../lib/eth/rtl/gmii_phy_if.v")
srcs.append("../lib/eth/rtl/eth_mac_1g_fifo.v")
srcs.append("../lib/eth/rtl/eth_mac_1g.v")
srcs.append("../lib/eth/rtl/eth_mac_1g_rx.v")
srcs.append("../lib/eth/rtl/eth_mac_1g_tx.v")
srcs.append("../lib/eth/rtl/eth_crc_8.v")
srcs.append("../lib/eth/rtl/eth_axis_rx.v")
srcs.append("../lib/eth/rtl/eth_axis_tx.v")
srcs.append("../lib/eth/rtl/udp_complete.v")
srcs.append("../lib/eth/rtl/udp.v")
srcs.append("../lib/eth/rtl/udp_ip_rx.v")
srcs.append("../lib/eth/rtl/udp_ip_tx.v")
srcs.append("../lib/eth/rtl/ip_complete.v")
srcs.append("../lib/eth/rtl/ip.v")
srcs.append("../lib/eth/rtl/ip_eth_rx.v")
srcs.append("../lib/eth/rtl/ip_eth_tx.v")
srcs.append("../lib/eth/rtl/ip_arb_mux_2.v")
srcs.append("../lib/eth/rtl/ip_mux_2.v")
srcs.append("../lib/eth/rtl/arp.v")
srcs.append("../lib/eth/rtl/arp_cache.v")
srcs.append("../lib/eth/rtl/arp_eth_rx.v")
srcs.append("../lib/eth/rtl/arp_eth_tx.v")
srcs.append("../lib/eth/rtl/eth_arb_mux_2.v")
srcs.append("../lib/eth/rtl/eth_mux_2.v")
srcs.append("../lib/eth/lib/axis/rtl/arbiter.v")
srcs.append("../lib/eth/lib/axis/rtl/priority_encoder.v")
srcs.append("../lib/eth/lib/axis/rtl/axis_fifo.v")
srcs.append("../lib/eth/lib/axis/rtl/axis_async_frame_fifo.v")
srcs.append("test_%s.v" % module)

src = ' '.join(srcs)

build_cmd = "iverilog -o test_%s.vvp %s" % (module, src)

def dut_fpga_core(clk,
                  rst,

                  current_test,
                  btnu,
                  btnl,
                  btnd,
                  btnr,
                  btnc,
                  sw,
                  led,

                  phy_rx_clk,
                  phy_rxd,
                  phy_rx_dv,
                  phy_rx_er,
                  phy_gtx_clk,
                  phy_txd,
                  phy_tx_en,
                  phy_tx_er,
                  phy_reset_n,

                  uart_rxd,
                  uart_txd):

    if os.system(build_cmd):
        raise Exception("Error running build command")
    return Cosimulation("vvp -m myhdl test_%s.vvp -lxt2" % module,
                clk=clk,
                rst=rst,
                current_test=current_test,

                btnu=btnu,
                btnl=btnl,
                btnd=btnd,
                btnr=btnr,
                btnc=btnc,
                sw=sw,
                led=led,

                phy_rx_clk=phy_rx_clk,
                phy_rxd=phy_rxd,
                phy_rx_dv=phy_rx_dv,
                phy_rx_er=phy_rx_er,
                phy_gtx_clk=phy_gtx_clk,
                phy_txd=phy_txd,
                phy_tx_en=phy_tx_en,
                phy_tx_er=phy_tx_er,
                phy_reset_n=phy_reset_n,

                uart_rxd=uart_rxd,
                uart_txd=uart_txd)

def bench():

    # Parameters
    TARGET = "SIM"

    # Inputs
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    current_test = Signal(intbv(0)[8:])

    btnu = Signal(bool(0))
    btnl = Signal(bool(0))
    btnd = Signal(bool(0))
    btnr = Signal(bool(0))
    btnc = Signal(bool(0))
    sw = Signal(intbv(0)[8:])
    phy_rx_clk = Signal(bool(0))
    phy_rxd = Signal(intbv(0)[8:])
    phy_rx_dv = Signal(bool(0))
    phy_rx_er = Signal(bool(0))
    uart_rxd = Signal(bool(0))

    # Outputs
    led = Signal(intbv(0)[8:])
    phy_gtx_clk = Signal(bool(0))
    phy_txd = Signal(intbv(0)[8:])
    phy_tx_en = Signal(bool(0))
    phy_tx_er = Signal(bool(0))
    phy_reset_n = Signal(bool(0))
    uart_txd = Signal(bool(0))

    # sources and sinks
    gmii_source_queue = Queue()
    gmii_sink_queue = Queue()

    gmii_source = gmii_ep.GMIISource(phy_rx_clk,
                                     rst,
                                     txd=phy_rxd,
                                     tx_en=phy_rx_dv,
                                     tx_er=phy_rx_er,
                                     fifo=gmii_source_queue,
                                     name='gmii_source')

    gmii_sink = gmii_ep.GMIISink(phy_gtx_clk,
                                 rst,
                                 rxd=phy_txd,
                                 rx_dv=phy_tx_en,
                                 rx_er=phy_tx_er,
                                 fifo=gmii_sink_queue,
                                 name='gmii_sink')

    # DUT
    dut = dut_fpga_core(clk,
                        rst,
                        current_test,

                        btnu,
                        btnl,
                        btnd,
                        btnr,
                        btnc,
                        sw,
                        led,

                        phy_rx_clk,
                        phy_rxd,
                        phy_rx_dv,
                        phy_rx_er,
                        phy_gtx_clk,
                        phy_txd,
                        phy_tx_en,
                        phy_tx_er,
                        phy_reset_n,

                        uart_rxd,
                        uart_txd)

    @always(delay(4))
    def clkgen():
        clk.next = not clk
        phy_rx_clk.next = not phy_rx_clk

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

        yield clk.posedge
        print("test 1: test UDP RX packet")
        current_test.next = 1

        test_frame = udp_ep.UDPFrame()
        test_frame.eth_dest_mac = 0x020000000000
        test_frame.eth_src_mac = 0xDAD1D2D3D4D5
        test_frame.eth_type = 0x0800
        test_frame.ip_version = 4
        test_frame.ip_ihl = 5
        test_frame.ip_dscp = 0
        test_frame.ip_ecn = 0
        test_frame.ip_length = None
        test_frame.ip_identification = 0
        test_frame.ip_flags = 2
        test_frame.ip_fragment_offset = 0
        test_frame.ip_ttl = 64
        test_frame.ip_protocol = 0x11
        test_frame.ip_header_checksum = None
        test_frame.ip_source_ip = 0xc0a80181
        test_frame.ip_dest_ip = 0xc0a80180
        test_frame.udp_source_port = 5678
        test_frame.udp_dest_port = 1234
        test_frame.payload = bytearray(range(32))
        test_frame.build()

        gmii_source_queue.put(b'\x55\x55\x55\x55\x55\x55\x55\xD5'+test_frame.build_eth().build_axis_fcs().data)

        # wait for ARP request packet
        while gmii_sink_queue.empty():
            yield clk.posedge

        rx_frame = gmii_sink_queue.get(False)
        check_eth_frame = eth_ep.EthFrame()
        check_eth_frame.parse_axis_fcs(rx_frame.data[8:])
        check_frame = arp_ep.ARPFrame()
        check_frame.parse_eth(check_eth_frame)

        print(check_frame)

        assert check_frame.eth_dest_mac == 0xFFFFFFFFFFFF
        assert check_frame.eth_src_mac == 0x020000000000
        assert check_frame.eth_type == 0x0806
        assert check_frame.arp_htype == 0x0001
        assert check_frame.arp_ptype == 0x0800
        assert check_frame.arp_hlen == 6
        assert check_frame.arp_plen == 4
        assert check_frame.arp_oper == 1
        assert check_frame.arp_sha == 0x020000000000
        assert check_frame.arp_spa == 0xc0a80180
        assert check_frame.arp_tha == 0x000000000000
        assert check_frame.arp_tpa == 0xc0a80181

        # generate response
        arp_frame = arp_ep.ARPFrame()
        arp_frame.eth_dest_mac = 0x020000000000
        arp_frame.eth_src_mac = 0xDAD1D2D3D4D5
        arp_frame.eth_type = 0x0806
        arp_frame.arp_htype = 0x0001
        arp_frame.arp_ptype = 0x0800
        arp_frame.arp_hlen = 6
        arp_frame.arp_plen = 4
        arp_frame.arp_oper = 2
        arp_frame.arp_sha = 0xDAD1D2D3D4D5
        arp_frame.arp_spa = 0xc0a80181
        arp_frame.arp_tha = 0x020000000000
        arp_frame.arp_tpa = 0xc0a80180

        gmii_source_queue.put(b'\x55\x55\x55\x55\x55\x55\x55\xD5'+arp_frame.build_eth().build_axis_fcs().data)

        while gmii_sink_queue.empty():
            yield clk.posedge

        rx_frame = gmii_sink_queue.get(False)
        check_eth_frame = eth_ep.EthFrame()
        check_eth_frame.parse_axis_fcs(rx_frame.data[8:])
        check_frame = udp_ep.UDPFrame()
        check_frame.parse_eth(check_eth_frame)

        print(check_frame)

        assert check_frame.eth_dest_mac == 0xDAD1D2D3D4D5
        assert check_frame.eth_src_mac == 0x020000000000
        assert check_frame.eth_type == 0x0800
        assert check_frame.ip_version == 4
        assert check_frame.ip_ihl == 5
        assert check_frame.ip_dscp == 0
        assert check_frame.ip_ecn == 0
        assert check_frame.ip_identification == 0
        assert check_frame.ip_flags == 2
        assert check_frame.ip_fragment_offset == 0
        assert check_frame.ip_ttl == 64
        assert check_frame.ip_protocol == 0x11
        assert check_frame.ip_source_ip == 0xc0a80180
        assert check_frame.ip_dest_ip == 0xc0a80181
        assert check_frame.udp_source_port == 1234
        assert check_frame.udp_dest_port == 5678
        assert check_frame.payload.data == bytearray(range(32))

        assert gmii_source_queue.empty()
        assert gmii_sink_queue.empty()

        yield delay(100)

        raise StopSimulation

    return dut, gmii_source, gmii_sink, clkgen, check

def test_bench():
    sim = Simulation(bench())
    sim.run()

if __name__ == '__main__':
    print("Running test...")
    test_bench()
