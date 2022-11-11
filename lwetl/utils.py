"""
    Internal module with small utility functions
"""

import re
from datetime import datetime
from base64 import urlsafe_b64encode, urlsafe_b64decode

# regex filters
RE_IS_NUMBER = re.compile(r'^\d+(\.\d*)*$')
RE_IS_DATE_TIME_MS = re.compile(r'^\d{4}(-\d{2}){2} \d{2}(:\d{2}){2}(\.\d{3})$')
RE_IS_DATE_TIME = re.compile(r'^\d{4}(-\d{2}){2} \d{2}(:\d{2}){2}(\.\d+)?$')
RE_IS_DATE = re.compile(r'^\d{4}(-\d{2}){2}$')


def is_empty(value) -> bool:
    """
    Return True for NoneType and emtpy strings
    @param value: Any - value to check
    @return: True for NoneType or emtpy strings. False otherwise
    """
    return (value is None) or (isinstance(value, str) and (len(value.strip()) == 0))


def verified_boolean(value) -> bool:
    """
    Only returns True if the input variable is a bool with the True value
    @param value: Any
    @return: True if the input value is a bool with True value, False otherwise
    """
    if isinstance(value, bool) and value:
        return True
    else:
        return False


def string2date(str_value: str) -> datetime:
    """
    Convert a string into a datetime object
    @param str_value: str - the input in the format yyyy-mm-dd [HH:MM:SS.msec]
    @return: datetime - the converted time
    @raises ValueError if the input string cannot be converted
    """
    if not isinstance(str_value, str):
        raise ValueError('Invalid argument type in string2date(). Must be a string.')
    if RE_IS_DATE_TIME_MS.match(str_value):
        return datetime.strptime(str_value[:19], '%Y-%m-%d %H:%M:%S.%f')
    elif RE_IS_DATE_TIME.match(str_value):
        return datetime.strptime(str_value[:19], '%Y-%m-%d %H:%M:%S')
    elif RE_IS_DATE.match(str_value):
        return datetime.strptime(str_value[:10], '%Y-%m-%d')
    else:
        msg = 'Invalid time format. Must be yyyy-mm-dd HH:MMM:SS. Found: ({})'.format(str_value)
        raise ValueError(msg)


def encode(key, clear):
    enc = []
    for i in range(len(clear)):
        key_c = key[i % len(key)]
        enc_c = chr((ord(clear[i]) + ord(key_c)) % 256)
        enc.append(enc_c)
    return urlsafe_b64encode("".join(enc).encode()).decode()


def decode(key, enc):
    dec = []
    enc = urlsafe_b64decode(enc).decode()
    for i in range(len(enc)):
        key_c = key[i % len(key)]
        dec_c = chr((256 + ord(enc[i]) - ord(key_c)) % 256)
        dec.append(dec_c)
    return "".join(dec)


if __name__ == '__main__':
    from argparse import ArgumentParser, RawTextHelpFormatter
    from hashlib import md5

    def md5_encode(key):
        m = md5()
        m.update(key.encode())
        return m.hexdigest()

    parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='''Command line utility to encode or decode a string.
    If decoding works, you get the decoded string.
    In all other cases the input is encoded.''')

    parser.add_argument('key',
                        help='Encoding key.')

    parser.add_argument('data',
                        help='String to encode or decode.')

    args = parser.parse_args()

    mkey = md5_encode(args.key)
    # noinspection PyBroadException
    try:
        dat = decode(mkey, args.data)
    except Exception:
        dat = ''
    if dat.startswith(mkey[:4]):
        print('Decoding: ' + dat[4:])
    else:
        print('Encoded: ' + encode(mkey, mkey[:4] + args.data))
