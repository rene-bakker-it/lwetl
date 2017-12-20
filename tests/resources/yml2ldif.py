import base64
import os
import sys

from yaml import load as yaml_load

def print_values(string_dict, ofile=sys.stdout):
    def print_value(value):
        r = ['value:']
        try:
            value.encode().decode('ascii')
        except UnicodeDecodeError:
            r.append(':')
            value = base64.standard_b64encode(value.encode()).decode('ascii')
        while len(value) > 0:
            r += [' ', value[:64]]
            if len(value) > 64:
                value = value[64:]
                r.append("\n")
            else:
                value = []
        print(''.join(r), file=ofile)

    indx = 0
    for k in sorted(string_dict.keys()):
        indx += 1
        v = string_dict[k]
        if isinstance(v,str):
            print("dn: sn=" + k, file=ofile)
            print("sn: " + k, file=ofile)
            print("indx: %d" % (1000*indx), file=ofile)
            print_value(v)
            print("", file=ofile)
        else:
            indx2 = 0
            for kk in sorted(v.keys()):
                indx2 += 1
                vv = v[kk]
                print("dn: sn=%s, cn=%s" % (k,kk), file=ofile)
                print("sn: " + k, file=ofile)
                print("cn: " + kk, file=ofile)
                print("indx: %d" % ((1000*indx)+indx2), file=ofile)
                print_value(vv)
                print("", file=ofile)


f_in = os.path.join(os.path.dirname(__file__),'utf8.yml')
f_out = os.path.join(os.path.dirname(__file__),'utf8.ldif')

with open(f_out,'w') as g:
    with open(f_in,'r') as f:
        print_values(yaml_load(f),g)


