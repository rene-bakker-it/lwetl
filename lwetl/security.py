"""
    Security functions for jdbc
"""
import base64
import getpass
import os
import random
import sys

from Crypto.Cipher import AES

KEY = None

def init_key(key: str)->bytes:
    global KEY
    k = key
    if len(k) != 32:
        k = bytearray(k.encode())
        if len(k) > 32:
            k = k[:32]
        while len(k) < 32:
            k.append(len(k))
        k = bytes(k)
    if KEY is None:
        KEY = k
    return k


def get_key(k):
    '''
    @return: bytearray with the key used for encryption
    '''
    global KEY

    if isinstance(k, str) and (len(k.strip()) > 0):
        key = k
    elif KEY is None:
        key = os.environ.get('LWETL')
    else:
        key = KEY
    if key is None:
        print('Enter lwetl master password: ')
        key = getpass.getpass()
    return init_key(key)

def encrypt(s: str, key=None):
    iv = bytearray()
    while len(iv) < AES.block_size:
        iv.append(random.randint(0, 255))
    iv = bytes(iv)
    cphr = AES.new(get_key(key), AES.MODE_CFB, iv)
    if len(s) > 127:
        raise RuntimeError('String too long for encryption.')
    s2 = '{:02x}{}'.format(128+len(s),s)
    while len(s2) < 132:
        s2 += chr(random.randint(33,126))
    mesg = iv + cphr.encrypt(s2.encode())
    return base64.urlsafe_b64encode(mesg).decode()

def decrypt(s: str, key=None):
    try:
        mesg = base64.urlsafe_b64decode(s)
        iv = mesg[0:AES.block_size]
        cphr = AES.new(get_key(key), AES.MODE_CFB, iv)
        s2 = cphr.decrypt(mesg[AES.block_size:]).decode()
    except Exception:
        print('Password decryption error. Wrong password?', file=sys.stderr)
        sys.exit(1)

    return s2[2:2+int(s2[0:2], 16)-128]


if __name__ == '__main__':
    key = get_key('èç@£AB34adc')
    for s1 in ['çur@tor€=12B', 'abc']:
        print('Test phrase: {}'.format(s1))
        s2 = encrypt(s1)
        print('Encrypted:   {}'.format(s2))
        s3 = decrypt(s2)
        print('Decrypted:   {}'.format(s3))
        if s3 != s1:
            raise RuntimeError('Encryption test failed.')