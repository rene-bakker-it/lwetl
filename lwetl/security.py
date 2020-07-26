"""
    Security functions for jdbc
"""

import base64
import getpass
import os
import random
import sys

from cryptography.fernet import Fernet
from .exceptions import DecryptionError

KEY = None


def init_key(key: str) -> bytes:
    """
    Generate a 32-byte key from the imput string
    @param key:
    @return: 32-byte key, b54 url-safe encoded
    """
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
    return base64.urlsafe_b64encode(k)


def get_key(k):
    """
    @return: bytearray with the key used for encryption
    """
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
    """
    Encrypt the input string with the specified key. Uses the default key of not specified.
    @param str s: the string to encrypt
    @param str key: the key/password to encrypt with
    @return a b64 url-safe encoded string:
    """

    if len(s) > 127:
        raise RuntimeError('String too long for encryption.')
    s2 = '{:02x}{}'.format(128 + len(s), s)
    while len(s2) < 132:
        s2 += chr(random.randint(33, 126))

    fernet = Fernet(get_key(key))
    return base64.urlsafe_b64encode(fernet.encrypt(bytes(s2.encode()))).decode()


def decrypt(s: str, key=None, raise_error=False):
    """
    Decrypt he input string wkth the specified key. Uses the defautl key of not specified.
    @param str s: b64 encoded input string
    @param str key: the encryption key/password
    @param bool raise_error: raise an error instead of terminating the program
    @return the decrypted string:
    @raise DecryptionError if the input string cannot be decrypted and raise_error is set to True
    """
    fernet = Fernet(get_key(key))
    try:
        s2 = fernet.decrypt(base64.urlsafe_b64decode(s.encode())).decode()
    except Exception as e:
        if raise_error:
            raise DecryptionError('Cannot decrypt.')
        else:
            print('Password decryption error. Wrong password? {}'.format(e), file=sys.stderr)
            sys.exit(1)
    return s2[2:2 + int(s2[0:2], 16) - 128]


if __name__ == '__main__':
    get_key('èç@£AB34adc')
    for t1 in ['çur@tor€=12B', 'abc']:
        print('Test phrase: {}'.format(t1))
        t2 = encrypt(t1)
        print('Encrypted:   {}'.format(t2))
        t3 = decrypt(t2)
        print('Decrypted:   {}'.format(t3))
        if t3 != t1:
            raise RuntimeError('Encryption test failed.')
