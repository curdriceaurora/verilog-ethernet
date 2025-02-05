"""

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

"""

from myhdl import *

class GMIIFrame(object):
    def __init__(self, data=b'', error=None):
        self.data = b''
        self.error = None

        if type(data) is GMIIFrame:
            self.data = data.data
            self.error = data.error
        else:
            self.data = bytearray(data)

    def build(self):
        if self.data is None:
            return

        f = list(self.data)
        d = []
        er = []
        i = 0

        assert_er = False
        if (type(self.error) is int or type(self.error) is bool) and self.error:
            assert_er = True
            self.error = None

        while len(f) > 0:
            d.append(f.pop(0))
            if self.error is None:
                er.append(0)
            else:
                er.append(self.error[i])
            i += 1

        if assert_er:
            er[-1] = 1
            self.error = 1

        return d, er

    def parse(self, d, er):
        if d is None or er is None:
            return

        self.data = bytearray(d)
        self.error = er

    def __eq__(self, other):
        if type(other) is GMIIFrame:
            return self.data == other.data

    def __repr__(self):
        return 'GMIIFrame(data=%s, error=%s)' % (repr(self.data), repr(self.error))

    def __iter__(self):
        return self.data.__iter__()


def GMIISource(clk, rst,
               txd,
               tx_en,
               tx_er,
               fifo=None,
               name=None):

    @instance
    def logic():
        frame = None
        d = []
        er = []
        ifg_cnt = 0

        while True:
            yield clk.posedge, rst.posedge

            if rst:
                frame = None
                txd.next = 0
                tx_en.next = 0
                tx_er.next = 0
                d = []
                er = []
                ifg_cnt = 0
            else:
                if ifg_cnt > 0:
                    ifg_cnt -= 1
                    txd.next = 0
                    tx_er.next = 0
                    tx_en.next = 0
                elif len(d) > 0:
                    txd.next = d.pop(0)
                    tx_er.next = er.pop(0)
                    tx_en.next = 1
                    if len(d) == 0:
                        ifg_cnt = 12
                elif not fifo.empty():
                    frame = GMIIFrame(fifo.get())
                    d, er = frame.build()
                    if name is not None:
                        print("[%s] Sending frame %s" % (name, repr(frame)))
                    txd.next = d.pop(0)
                    tx_er.next = er.pop(0)
                    tx_en.next = 1
                else:
                    txd.next = 0
                    tx_er.next = 0
                    tx_en.next = 0

    return logic


def GMIISink(clk, rst,
             rxd,
             rx_dv,
             rx_er,
             fifo=None,
             name=None):

    @instance
    def logic():
        frame = None
        d = []
        er = []

        while True:
            yield clk.posedge, rst.posedge

            if rst:
                frame = None
                d = []
                er = []
            else:
                if rx_dv:
                    if frame is None:
                        frame = GMIIFrame()
                        d = []
                        er = []
                    d.append(int(rxd))
                    er.append(int(rx_er))
                elif frame is not None:
                    if len(d) > 0:
                        frame.parse(d, er)
                        if fifo is not None:
                            fifo.put(frame)
                        if name is not None:
                            print("[%s] Got frame %s" % (name, repr(frame)))
                    frame = None
                    d = []
                    er = []

    return logic
