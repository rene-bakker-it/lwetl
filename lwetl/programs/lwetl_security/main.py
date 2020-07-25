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

Credentials = namedtuple('Credentials', 'username password server')

parser = argparse.ArgumentParser(
    prog='lwetl-security',
    description='Encrypt/Decrypt passwords stored in the lwetl configuration file')

parser.add_argument('output_file', nargs='?', default=None,
                    help='Name of the output file (stdout if not specified).')

parser.add_argument('-c', '--change', action='store_true',
                    help='Change the master password. You will be prompted to enter a new password.')
parser.add_argument('-r', '--remove', action='store_true',
                    help='Remove encryption on storage.')
parser.add_argument('-t', '--test', action='store_true',
                    help='Test the connection to all databases found in the configuration.')
parser.add_argument('--version', action='store_true')


def parse_credentials(s, pw_encrypted=True):
    try:
        user_name_password, server = s.split('@')
        username, password = user_name_password.split('/')
    except ValueError:
        return s
    else:
        if pw_encrypted:
            password = decrypt(password)
    return Credentials(username, password, server)

def show_version():
    """
    Display the version info of this module
    @return 0
    """
    print('%s, version: %s' % (os.path.basename(sys.argv[0]), __version__))
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
    for fn in [f for f in CFG_FILES if os.path.isfile(f)]:
        try:
            with open(fn) as fh:
                cfg = yaml.load(fh, Loader=yaml.FullLoader)
                configuration = merge(cfg, configuration)
                count_cfg_files += 1
        except PermissionError:
            pass
        except yaml.YAMLError as pe:
            print('ERROR: cannot parse the configuration file %s' % fn, file=sys.stderr)
            print(pe, file=sys.stderr)
            sys.exit(1)

    pw_encrypted = configuration.get('encrypt', True)
    if not isinstance(pw_encrypted, bool):
        pw_encrypted = True
    for a in configuration.get('alias',{}).keys():
        configuration['alias'][a] = parse_credentials(configuration['alias'][a], pw_encrypted)

    if args.test:
        keys = sorted(configuration.get('alias',{}).keys())
        for indx, k in enumerate(keys, start=1):
            try:
                jdbc = lwetl.Jdbc(k)
                if jdbc.type in table_count_queries:
                    sql = table_count_queries[jdbc.type].replace('@SCHEMA', jdbc.schema)
                    r   = 'OK: {:>4} tables found.'.format(jdbc.get_int(sql))
                else:
                    r = 'Unsupported db type: {}'.format(jdbc.type)
            except Exception as e:
                r = 'Failed: {}'.format(e)
            print('{:>3}/{}. {:.<30} {}'.format(indx, len(keys), k, r))
    else:
        if args.change:
            print('Enter new password: ')
            init_key(getpass.getpass())
            configuration['encrypt'] = True
        elif args.remove:
            configuration['encrypt'] = False

        new_alias = dict()
        for a, c in configuration.get('alias',{}).items():
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
