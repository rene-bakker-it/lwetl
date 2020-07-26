"""
Command line arguments for the application db-copy
"""

import argparse
import lwetl

from collections import OrderedDict

DRIVER_NATIVE = 'native'
DRIVER_SINGLE = 'single'
DRIVER_MULTI = 'multi'

UPLOADERS = OrderedDict()
UPLOADERS[DRIVER_NATIVE] = lwetl.NativeUploader
UPLOADERS[DRIVER_SINGLE] = lwetl.ParameterUploader
UPLOADERS[DRIVER_MULTI] = lwetl.MultiParameterUploader

COPY_EMPTY = 'empty'
COPY_NEW = 'new'
COPY_AND_UPDATE = 'update'
COPY_AND_SYNC = 'sync'

COPY_MODE = OrderedDict()
COPY_MODE[COPY_EMPTY] = 'only copy tables, which are emtpy in the target table (default).'
COPY_MODE[COPY_NEW] = 'only copy records, which do not exist in the target table.'
COPY_MODE[COPY_AND_UPDATE] = 'like new. Then update existing records with the contents found in the source table.'
COPY_MODE[COPY_AND_SYNC] = 'additionally remove records that where deleted in the source table.'

# noinspection PyTypeChecker
parser = argparse.ArgumentParser(
    prog='db-copy',
    description='''Copy tables between database instances.
IMPORTANT:
1. By default only tables, which are empty in the target database, are copied (see -m option).
2. No changes to the target database are made unless the -a option is specified.
3. No checks are made on data consistency between source and target. For example, missing column names
   in the target database are silently ignored.
4. The copy process follows an ascending order of the primary key. This may cause problems for self-referencing
   tables, which do not have an ordered primary key such as an UUID.''',
    formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument('login_source',
                    help='''login credentials or alias of the source database.
Use 'sql-query list' to view possible options.
Credentials are in ORACLE format: <username>/<password>@server''')

parser.add_argument('login_target',
                    help='login credentials or alias of the target database.')

parser.add_argument('tables', nargs='?', default=None,
                    help='Comma separated list of tables to include. Use all common tables if not defined.')

parser.add_argument(
    '-a', '--activate', action='store_true',
    help='Activates changes on the target database. Otherwise runs in roll_back mode.')

parser.add_argument(
    '-e', '--exclude', action='store', default=None,
    help='''A number of a comma-separated list of tables to exclude.
Uses all common tables except for the onws specified in the list.
If a number, the first n tables are excluded for import.''')

parser.add_argument(
    '-f', '--fail', action='store', type=int,
    dest='max_fail',
    default=0,
    help='''Specify the number of fails on insert allowed on insert or update before the progream exits.
Useful for copying live databases where reference tables are updated during the copy process of multiple tables.
A negative number implies no fail limit. Defaults to 0 (no failure allowed).
For ignoring commit errors, also add the --ignore flag. This may result in undesired behaviour.''')

parser.add_argument(
    '-l', '--list', action='store_true',
    help='Only list the commit tables and exit.')

parser.add_argument(
    '-n', '--commit', action='store', type=int,
    dest='commit_nr',
    default=2000,
    help='''commit uploads every nr rows. Defaults to 2000.
set to 1 if there are self refering FK (very slow)''')

parser.add_argument(
    '-r', '--rows', action='store', type=int,
    dest='max_rows',
    default=0,
    help='Limit the maximum number of rows to copy or update per table. Use <= 0 for all (default).')

parser.add_argument(
    '-s', '--statistics', action='store_true',
    help='Print some timing statisics on exit.')

parser.add_argument(
    '-m', '--mode', action='store',
    default='emtpy',
    choices=list(COPY_MODE.keys()),
    help='Specity the copy mode:' + ''.join([('\n- %-10s %s' % (k+':', v)) for k, v in COPY_MODE.items()])
)

parser.add_argument(
    '--driver', action='store', type=str,
    dest='driver',
    default='single',
    choices=list(UPLOADERS.keys()),
    help='''Specify the upload mode:
- native: use native SQL (does not permit transfer of binary data)
- single: parse single parameterized sqls to the target server (DEFAULT).
- multi:  parse an sql with multiple parameter rows in a single commit 
          (not compatible with update mode 'update' and 'sync').''')

parser.add_argument(
    '--ignore', action='store_true',
    dest='ignore_commit_errors',
    help='Also ignore commit errors to the specified fail-count.')

parser.add_argument(
    '--reverse', action='store_true',
    dest='reverse_insert',
    help='Insert in reverse order')

parser.add_argument(
    '--fast', action='store_true',
    dest='update_fast',
    help='Huristic fast update with reverse insert')

parser.add_argument('--version', action='store_true')
