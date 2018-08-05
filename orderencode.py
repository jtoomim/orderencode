#!/usr/bin/env python
import json, cStringIO, traceback, sys

def feerate(x):
    return x['fee'] / (len(x['data'])/2.)

def encode_order(txlist):
    txlist = txlist[:]
    byfee = sorted(txlist, key=feerate, reverse=True)
    newtxlist = []
    offsets = []
    indices = {byfee[i][u'hash']:i for i in range(len(byfee))} # can't use byfee.index(...) because it's O(n)
    for pos in range(len(byfee)):
        tx = txlist[pos]
        offset = indices[tx[u'hash']] - pos 
        offsets.append(offset)
    return offsets, compress(offsets)

def decode_order(byfee, compressed):
    offsets = decompress(compressed)
    txlist = []
    for pos in range(len(byfee)):
        txlist.append(byfee[offsets[pos]+pos])
    return txlist

def compress(offsets):
    compressedn = []
    compressedv = [0]
    n = 0
    v = offsets[0]
    for off in offsets:
        if v == off:
            n += 1
        else:
            compressedn.append(n)
            compressedv.append(v)
            n = 1
            v = off
    if n:
        compressedn.append(n)
        compressedv.append(v)
    del compressedv[0]
    bitmap, residuals = make_bitmap(compressedn)
    return ((bitmap, residuals), compressedv)

def decompress(compressed):
    n_vals = unmake_bitmap(compressed[0][0], compressed[0][1])
    offsets = []
    oldoff = 0
    for n, off in zip(n_vals, compressed[1]):
        offsets.extend([off + oldoff]*n)
        oldoff = 0
    return offsets


def make_bitmap(counts):
    """
    Generates a bitmap for which values in counts equal 1, plus a list of the residuals
    """
    residuals = [count for count in counts if count!=1]
    bits = [1<<(i%8) if counts[i] == 1 else 0 for i in range(len(counts))]
    byts = [chr(sum(bits[8*i:8*(i+1)])) for i in range((len(counts)+7)/8)]
    ''.join(byts)
    return ''.join(byts), residuals

def unmake_bitmap(bitmap, residuals):
    residuals = residuals[:]
    n_vals = []
    for byte in map(ord, bitmap):
        for n in range(8):
            if byte & 1<<n:
                n_vals.append(1)
            elif residuals:
                n_vals.append(residuals.pop(0))
            else:
                break
    return n_vals

if __name__ == '__main__':

    if len(sys.argv) < 2:
        print """Usage:
        bitcoin-cli getblocktemplate > somefilename
        python orderencode.py s[-v] omefilename

        If you don't have bitcoin-cli handy, feel free to try it on the four sample
        GBT files in samplegbts/:

        for i in `seq 1 4`; do python orderencode.py samplegbts/$i; done
        """
        sys.exit()

    filename = sys.argv[-1]

    with open(filename, 'r') as f:
        gbt = json.loads(f.read())
    txlist = gbt['transactions']
    off, comp =  encode_order(txlist)

    print "%i bitmap bytes, %i residual varints, %i offset varints" % (len(comp[0][0]), len(comp[0][1]), len(comp[1]))
    def varintsize(x):
        if -2**8  < x <  (2**8-4): return 1
        if -2**16 < x < (2**16-1): return 3
        if -2**32 < x < (2**32-1): return 5
        if -2**64 < x < (2**64-1): return 9
    print "%i bytes total" % (len(comp[0][0]) + sum(map(varintsize, comp[0][1])) + sum(map(varintsize, comp[1])))
    print len(txlist), "transactions total"


    byfee = sorted(txlist, key=feerate, reverse=True)
    decoded = decode_order(byfee, comp)

    if len(decoded) != len(txlist):
        print "Wrong list lengt! %i != %i" % (len(decoded), len(txlist))
    errors = sum([int(gb!=dc) for gb, dc in zip(decoded, txlist)])
    print "%i total errors" % errors
    print "\nCompressed data:"
    print "  Bitmap of non-repeating offsets:", map(ord, comp[0][0])
    print "  Repetition count of repeating offsets:", comp[0][1]
    print "  The offsets values:", comp[1]
    print ""
    if not decoded == gbt['transactions'] or '-v' in sys.argv:
        print "idx\tGBT\tDecoded\tSorted\tCorrect\tOffset"
        for idx, dc, gb, bf, o in zip(range(len(decoded)), decoded, txlist, byfee, off):
            print "%i\t%7.3f\t%7.3f\t%7.3f\t%s\t%i" % (idx, feerate(gb), feerate(dc), feerate(bf), '*' if gb == dc else "", o)
