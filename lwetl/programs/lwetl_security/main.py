"""
    Helper program to encrypt/decrypt the database passwords stored in the aliases
    of the main configuration file
"""

import argparse
import getpass
import lwetl
import os
import sys
import yaml

from collections import namedtuple

from lwetl.version import __version__
from lwetl.config_parser import CFG_FILES, merge
from lwetl.security import encrypt, decrypt, init_key
from lwetl.queries import table_count_queries
from lwetl.exceptions import DecryptionError

Credentials = namedtuple('Credentials', 'username password server')

# noinspection PyTypeChecker
parser = argparse.ArgumentParser(
    prog='lwetl-security',
    description='Encrypt/Decrypt passwords stored in the lwetl configuration file',
    formatter_class=argparse.RawTextHelpFormatter)

commands = {
    'set': 'impose a new password',
    'remove': 'remove the password encryption.',
    'test': 'test the connections (alias) in the configuration file.'
}

parser.add_argument('command', default=None, choices=list(commands.keys()),
                    help="Commands:\n  - {}".format(
                        "\n  - ".join(['{:8} {}'.format(k, v) for k, v in commands.items()])))
parser.add_argument('filename', nargs='?', default=None,
                    help='specify the configuration file. Use default if not specified.')
parser.add_argument('-o', '--output_file', action='store', default=None,
                    help="Name of the output file. Uses stdout if not specified. Use '-' to overwrite the input file.")
parser.add_argument('-n', '--no_interaction', action='store_true',
                    help='Take encryption password from the environment variable LWETL')
parser.add_argument('--version', action='store_true', help='Show version number and exit')


def parse_credentials(s, pw_encrypted=True):
    try:
        user_name_password, server = s.split('@')
        username, password = user_name_password.split('/')
    except ValueError:
        return s
    else:
        if pw_encrypted:
            try:
                password = decrypt(password, raise_error=True)
            except DecryptionError:
                print('WARNING: failed to decrypt password for {}'.format(username), file=sys.stderr)
    return Credentials(username, password, server)


def show_version():
    """
    Display the version info of this module
    @return 0
    """
    print('{}, version: {}'.format(os.path.basename(sys.argv[0]), __version__))
    return 0


def main():
    if (len(sys.argv) > 1) and (sys.argv[1].lower() == '--version'):
        # skip parsing
        return show_version()

    args = parser.parse_args()

    if args.version:
        return show_version()

    # load the configuration file
    configuration = dict()
    count_cfg_files = 0
    input_files = set()
    for fn in [f for f in CFG_FILES if os.path.isfile(f)]:
        try:
            with open(fn) as fh:
                cfg = yaml.load(fh, Loader=yaml.FullLoader)
                configuration = merge(cfg, configuration)
                count_cfg_files += 1
            input_files.add(fn)
        except PermissionError:
            pass
        except yaml.YAMLError as pe:
            print('ERROR: cannot parse the configuration file {}'.format(fn), file=sys.stderr)
            print(pe, file=sys.stderr)
            sys.exit(1)
    if len(input_files) == 0:
        print('ERROR: no input files found.')
        sys.exit(1)
    if args.output_file == '-':
        args.output_file = sorted(input_files, key = lambda _fn: os.path.getsize(_fn), reverse=True).pop(0)

    pw_encrypted = configuration.get('encrypt', True)
    if not isinstance(pw_encrypted, bool):
        pw_encrypted = True
    for a in configuration.get('alias', {}).keys():
        configuration['alias'][a] = parse_credentials(configuration['alias'][a], pw_encrypted)

    if args.command == 'test':
        keys = sorted(configuration.get('alias', {}).keys())
        for indx, k in enumerate(keys, start=1):
            try:
                jdbc = lwetl.Jdbc(k)
                if jdbc.type in table_count_queries:
                    sql = table_count_queries[jdbc.type].replace('@SCHEMA', jdbc.schema)
                    r = 'OK: {:>4} tables found.'.format(jdbc.get_int(sql))
                else:
                    r = 'Unsupported db type: {}'.format(jdbc.type)
            except Exception as e:
                r = 'Failed: {}'.format(e)
            print('{:>3}/{}. {:.<30} {}'.format(indx, len(keys), k, r))
        return

    if args.command == 'set':
        new_password = None
        if args.no_interaction:
            new_password = os.environ.get('LWETL')
        if new_password is None:
            print('Enter new password: ')
            new_password = getpass.getpass()
        init_key(new_password)
        configuration['encrypt'] = True
    elif args.command == 'remove':
        configuration['encrypt'] = False
    else:
        print('ERROR: unsupported command: {}'.format(args.command))
        sys.exit(1)

    new_alias = dict()
    for a, c in configuration.get('alias', {}).items():
        if isinstance(c, Credentials):
            if configuration['encrypt']:
                c = Credentials(c.username, encrypt(c.password), c.server)
            new_alias[a] = '{}/{}@{}'.format(c.username, c.password, c.server)
        else:
            new_alias[a] = c
    configuration['alias'] = new_alias

    if args.output_file is None:
        print(yaml.dump(configuration))
    else:
        with open(args.output_file, 'w') as f:
            yaml.dump(configuration, f)
        print('Configuration written to: ' + args.output_file)


if __name__ == '__main__':
    main()
