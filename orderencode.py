#!/usr/bin/env python
import json, cStringIO, traceback, sys

filename = sys.argv[1] if len(sys.argv) > 1 else 'gbt'

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
    with open(filename, 'r') as f:
        gbt = json.loads(f.read())
    txlist = gbt['transactions']
    off, comp =  encode_order(txlist)

    print "%i bitmap bytes, %i residual varints, %i offset varints" % (len(comp[0][0]), len(comp[0][1]), len(comp[1]))
    print len(txlist), "transactions total"


    byfee = sorted(txlist, key=feerate, reverse=True)
    decoded = decode_order(byfee, comp)

    if len(decoded) != len(txlist):
        print "Wrong list lengt! %i != %i" % (len(decoded), len(txlist))
    errors = sum([int(gb!=dc) for gb, dc in zip(decoded, txlist)])
    print "%i total errors" % errors
    if not decoded == gbt['transactions']:
        print "idx\tGBT\tDec\tSort\tCorrect\tOffset"
        for idx, dc, gb, bf, o in zip(range(len(decoded)), decoded, txlist, byfee, off):
            print "%i\t%7.3f\t%7.3f\t%7.3f\t%s\t%i" % (idx, feerate(gb), feerate(dc), feerate(bf), '*' if gb == dc else "", o)
