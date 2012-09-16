# This file is part of dsoc.

# dsoc is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# dsoc is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with dsoc.  If not, see <http://www.gnu.org/licenses/>.

from sys import stderr
import usb
import struct
ba=bytearray
from time import sleep
from numpy import array, int8, int16

def str2hex(s):
    return "".join("%02x " % i for i in ba(s))

# Y scale seems to be a bit off between samples and screen
# this value gives the approximate number of y divisions in the sample data.
yscale_div=10.3

# full X scale, when menu is disabled
xscale_div=19.2

def io_check(cond, s):
    if not cond:
        raise IOError, s
    
class HTDSO(object):
    def __init__(self, verbose=False):
        self.verbose=verbose
        self.max_retries=5
        self.rbuf=bytearray()
        c=usb.core.find(idVendor=0x049f, idProduct=0x505a)
        self.c=c
        if not c:
            raise IOError, "DSO not found."
        if c.is_kernel_driver_active(0):
            c.detach_kernel_driver(0)
        self.sync()

    def transmit(self, vals, head):
        vals=ba(vals)
        l=len(vals)+1
        io_check(l<0x10000, "TX packet too long.")
        s=ba([head])+struct.pack("<H", l)
        s+=ba(vals)
        s.append(sum(s)&0xff)
        if self.verbose:
            print>>stderr, "-> DSO", str2hex(s)
        self.c.write(1, s)

    def recv_decode(self, r, vals, head):
        io_check(r[0]==head, "Response header does not match (0x%02x, 0x%02x)." %
                 (r[0], head))
        p_end=r[1]+256*r[2]+2
        io_check(p_end<len(r), "Partial packet.")
        io_check(r[3]==vals[0]|0x80, "Response command type does not match.")
        io_check(r[p_end]==sum(r[:p_end])&0xff, "Response checksum does not match.")
        return r[4:p_end], p_end+1

    def receive(self, vals, head):
        vals=ba(vals)
        if len(self.rbuf)<4:
            rvals=ba(self.c.read(0x82, 0x10000))
            self.rbuf+=rvals
            if self.verbose:
                print>>stderr, "<- DSO", str2hex(rvals)
                print>>stderr, " - BUF:", str2hex(self.rbuf)
        else:
            if self.verbose:
                print>>stderr, " - BUF:", str2hex(self.rbuf)
        try:
            r, i=self.recv_decode(self.rbuf, vals, head)
            self.rbuf=self.rbuf[i:]
            return r
        except IOError, e:
            if self.verbose:
                print>>stderr, "Receive decode error:", e
            self.rbuf=bytearray(0)
            try:
                self.c.read(0x82, 0x10000)
            except IOError:
                pass
            raise
    
    def echo(self, s):
        s="\x00"+s
        self.transmit(s, 0x53)
        r=self.receive(s, 0x53)
        io_check(r==s[1:], "ECHO reply does not match.")
        return r

    def sync(self):
        self.rbuf=bytearray()
        for i in range(100):
            try:
                self.echo("sync")
                self.echo("sync")
            except IOError:
                continue
            break

    def retry(f):
        def w(self, *args, **kwargs):
            for i in range(self.max_retries):
                try:
                    return f(self, *args, **kwargs)
                except IOError, e:
                    if self.verbose:
                        print>>stderr, (
                            "Communication failed (%s), "
                            "retry no. %d" % (e, i))

            raise IOError, "Maximum number of retries exceeded."
        return w

    @retry
    def lock_panel(self, lock=True):
        s=ba([0x12, 0x01, bool(lock)])
        self.transmit(s, 0x53)
        r=self.receive(s, 0x53)

    @retry
    def stop_acq(self, stop=True):
        s=ba([0x12, 0x00, bool(stop)])
        self.transmit(s, 0x53)
        r=self.receive(s, 0x53)
        
    def dsosafe(stop=True, lock=True):
        def wrapper(f):
            def wlock(self, *args, **kwargs):
                self.stop_acq(stop)
                self.lock_panel(lock)
                try:
                    return f(self, *args, **kwargs)
                except:
                    self.sync()
                    raise
                finally:
                    self.lock_panel(False)
                    self.stop_acq(False)
            return wlock
        return wrapper

    
    def bulk_input(self, s, head, samplemode=False, samplechan=0x00):
        f=ba()
        chk=0
        while True:
            r=self.receive(s, head)
            if r[0]==0x01:
                if samplemode:
                    io_check(r[1]==samplechan, "Sample channel "
                             "does not match received data.")
                f+=r[1+samplemode:]
                chk+=sum(r[1:])
            elif r[0]==0x02:
                if not samplemode:
                    io_check(chk&0xff==r[1], "Bulk checksum does not match.")
                else:
                    io_check(r[1]==samplechan, "Sample channel "
                             "does not match received data.")
                return f
            else:
                io_check(0, "Invalid bulk transfer id %d." % r[0])

    @retry
    @dsosafe()
    def get_file(self, fn):
        s=ba([0x10, 0x00])+fn
        self.transmit(s, 0x53)
        return self.bulk_input(s, 0x53)

    @retry
    @dsosafe()
    def command(self, cmd):
        s=ba([0x11])+cmd
        self.transmit(s, 0x43)
        return self.receive(s, 0x43)

    @retry
    @dsosafe()
    def screenshot(self, outfn=None):
        import Image
        s=ba([0x20])
        self.transmit(s, 0x53)
        r=self.bulk_input(s, 0x53)
        io_check(len(r)==800*480, "Image size does not match.")
        img=Image.new("P", (800, 480))
        import palette
        pal=reduce(lambda x,y:list(x)+list(y), palette.pal)
        img.putpalette(pal)
        for y in range(480):
            for x in range(800):
                img.putpixel((x, y), r[x+800*y])
        if outfn:
            img.save(outfn)
        return img

    @retry
    @dsosafe()
    def beep(self, ms):
        io_check( ms<25500, "Beep length too long.")
        s=ba([0x44, ms/100])
        self.transmit(s, 0x43)
        io_check(not len(self.receive(s, 0x43)), "Beep command returned data.")

    @retry
    @dsosafe(stop=False)
    def samples(self, ch):
        io_check(ch in [0,1], "Invalid channel for sample data.")
        s=ba([0x02, 0x01, ch])
        self.transmit(s, 0x53)
        r=self.receive(s, 0x53)
        slen=struct.unpack("<L", str(r[1:])+"\x00")[0]
        sdata=self.bulk_input(s, 0x53, True, ch)
        io_check(len(sdata)==slen, 
            ("Length of sample data received (%d) "+
            "does not match advertised length %d.") % (len(sdata), slen))
        return array(sdata, int8)

    @retry
    @dsosafe()
    def settings(self):
        import StringIO
        fmt=StringIO.StringIO(self.get_file("/protocol.inf"))
        scopetype=self.get_file("/logotype.dis")[:-1]
        
        from operator import iadd

        self.transmit("\x01", 0x53)
        s=self.receive("\x01", 0x53)

        coupling=["DC", "AC", "GND"]

        divy=reduce(iadd, ([.002*10**i,.005*10**i, .010*10**i] for i in
                           range(4)))
        
        tstates=["stop", "ready",
                 "auto", "trig'd",
                 "scan", "astop",
                 "armed"]

        tsource=["CH1", "CH2",
                 "EXT", "EXT/5",
                 "AC50"]

        ttypes=["Edge", "Video", "Pulse",
                "Slope", "O.T.", "Alt"]

        tmode=["auto", "normal"]

        tcoupling=["DC", "AC", "NoiseRej",
                   "HFRej", "LFRej"]
        
        tedges=["rising", "falling"]

        verti=["non-inverted", "inverted"]

        # horizontal settings do not seem to match (anymore?)
        # the horiz_scale setting is for a Hantek DSO5102B with
        # FW 120808.0, if comparing to the SysDATA v1.0 document.
        #tscales=reduce(iadd, ([4e-9*10**i,8e-9*10**i, 20e-9*10**i] for i in range(10)))+[40]
        tscales=reduce(iadd, ([2e-9*10**i, 4e-9*10**i,8e-9*10**i] for i in range(11)))

        unpack={1 : "<B", 2 : "<h", 8 : "<Q"}
        
        translations=[
            ("^VERT-CH.-COUP$",     lambda x : (coupling[x], "")),
            ("^VERT-CH.-VB$",       lambda x : (divy[x], "V")),
            ("^VERT-CH.-PROBE$",    lambda x : (10**x, "x")),
            ("^VERT-CH.-RPHASE$",   lambda x : (verti[x], "")),
            ("^TRIG-STATE$",        lambda x : (tstates[x], "")),
            ("^TRIG-TYPE$",         lambda x : (ttypes[x],  "")),
            ("^TRIG-MODE$",         lambda x : (tmode[x],   "")),
            ("^TRIG-COUP$",         lambda x : (tcoupling[x], "")),
            ("^TRIG-FREQUENCY$",    lambda x : (x*1e-3, "Hz")),
            ("^TRIG-HOLDTIME-MIN$", lambda x : (x*1e-12, "s")),
            ("^TRIG-HOLDTIME-MAX$", lambda x : (x*1e-12, "s")),
            ("^TRIG-HOLDTIME$",     lambda x : (x*1e-12, "s")),
            ("^TRIG-EDGE-SLOPE$",   lambda x : (tedges[x], "")),
            ("^HORIZ-TB$",          lambda x : (tscales[x], "s"))
            ]

        res={"UNIT" : (scopetype, "")}
        
        for i, l in enumerate(fmt):
            ls=l.split()
            name=ls[0].translate(None, "[]")
            if name=="TOTAL":
                assert(i==0)
                continue
            elif name=="START":
                assert(i==1)
                continue
            elif name=="END":
                assert(len(s)==0)
                continue
            
            n=int(ls[1])

            v=struct.unpack(unpack[n], str(s[:n]))[0]

            for r, c in translations:
                import re
                if re.match(r, name):
                    value, comment=c(v)
                    res[name]=value, comment
                    break
            else:
                res[name]=v, ""
            s=s[n:]

        return res, s

    @retry
    def reset(self):
        """ Reset scope to initial state. """
        self.transmit("\x7f", "\x43")
    
if __name__=="__main__":
    h=HTDSO()

