#!/usr/bin/env python

"""
    Generates N random strings of length X
    in ascii, latin-1, and latin-2
    and writes them to the output directory
"""
import os
import random

ascii = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!#$&()*+,-.;<=>@[]^_{|}~'
char_sets = {
    'word': '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
    'ascii': ascii,
    'latin-1': ascii + 'ßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ',
    'latin-2': ascii + 'ßáâäçéëíîóôöúüý€‰ŠŒŽšœžŸÁÂÄÇÉËÍÎÓÔÖÚÜÝĂăĄąĆćČčĎďĐđĘęĚěĹĺĽľŁłŃńŇňŐőŔŕŘřŚśŞşŠšŢţŤťŮůŰűŹźŻŽž'
}

base_dir = os.path.join(os.path.dirname(__file__),'output')

X = 15
N = 500000
for lbl, chars in char_sets.items():
    fn = os.path.join(base_dir,lbl + '.txt')
    with open(fn,'w') as f:
        for n in range(N):
            print(''.join(random.choice(chars) for _ in range(X)),file=f)
    print('Writing of %s done' % fn)


