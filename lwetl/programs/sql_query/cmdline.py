"""
Defines the command line arguments for sql-query

"""

import argparse
import sys

import lwetl


FORMATTERS = {
    'text': lwetl.TextFormatter,
    'csv': lwetl.CsvFormatter,
    'xml': lwetl.XmlFormatter,
    'xmlp': lwetl.XmlFormatter,
    'xlsx': lwetl.XlsxFormatter,
    'sql': lwetl.SqlFormatter
}

parser = argparse.ArgumentParser(
    prog='sql-query',
    description='Command line interface for database manipulation.')

parser.add_argument('login', nargs='?', default='',
                    help='''login credentials or alias.
Credentials are in ORACLE format: <username>/<password>@server
Use 'list' for known login aliases.
''')

parser.add_argument(
    'command_or_sql', nargs='?', default=None,
    help='''May be one of:
- a command (see below)
- a string of (multiple) SQL statements (may also be piped from the stdin)
- a name of a table
  triggers an upload if combined with a data file name as next argument

Valid commands:
- jdbc_info  - provide information on the JDBC driver used for the database connection.
- table_info - provides information on the tables defined in the specified login schema.''')

parser.add_argument(
    'file_name', nargs='?', default=None,
    help='Specify an input file (sql or table data)')

parser.add_argument('-a', '--activate', action='store_true', dest='activate',
                    help='Activate. Shortcut for -c COMMIT')

parser.add_argument(
    '-c', '--commit_mode', action='store',
    default=lwetl.UPLOAD_MODE_ROLLBACK,
    dest='commit_mode',
    choices=[lwetl.UPLOAD_MODE_DRYRUN, lwetl.UPLOAD_MODE_ROLLBACK, lwetl.UPLOAD_MODE_COMMIT],
    help='''Specify the commit mode:
    - {0} generate the SQLs for upload but do not send them.
          produces no output with combined with a SELECT statement
    - {1} (DEFAULT) send SQLs but perform a rollback instead of a commit.
    - {2} commit uploads to the database'''.format(lwetl.UPLOAD_MODE_DRYRUN, lwetl.UPLOAD_MODE_ROLLBACK,
                                                   lwetl.UPLOAD_MODE_COMMIT)
)

parser.add_argument(
    '-f', '--format', action='store',
    choices=list(FORMATTERS.keys()),
    default='csv',
    dest='format',
    help='Specify the input or output format. Defaults to csv. SQL output also requires the -t option!'
)

parser.add_argument(
    '-m', '--max_rows', action='store', type=int,
    dest='max_rows',
    default=0,
    help='Maximum number of rows of output. Use <= 0 for all (default)')

parser.add_argument(
    '-n', '--commit', action='store', type=int,
    dest='commit_nr',
    default=50,
    help='''commit uploads every nr rows. Defaults to 50.
set to 1 if there are self refering FK (very slow)''')

parser.add_argument(
    '-o', '--output', action='store',
    dest='output_file',
    default=sys.stdout,
    help='Specify an output file.')

parser.add_argument(
    '--noheader', action='store_true',
    dest='noheader',
    help='quiet: suppress header info in output'
)

parser.add_argument(
    '-s', '--separator', action='store',
    default=";",
    dest='separator',
    help='specify the column separator for CSV data, defaults to ;'
)

parser.add_argument(
    '-w', '--width', action='store', type=int,
    default=20,
    dest='column_width',
    help='specify the column width for TEXT data, defaults to 20'
)

parser.add_argument('--log', action='store', nargs='?', type=str,
                    dest='log_file', const=sys.stdout, default=None,
                    help='Log generated sql statements. Defaults to stdout, if set.')

parser.add_argument('-t', '--target', action='store', nargs='?', type=str,
    dest='target_db', default=None,
    help='''Defines the destination: [login_or_databasetype?]table_name[,columns]
- login_or_databasetype 
  May be a login alias defined in the config.yml or a database type defined in this file.
  If omitted, the current database connection is assumed. 
- table_name
  the target table name
- columns
  A comma-separated list of column names. Only columns in this list will be exported.
  Exports all columns if not specified''')

parser.add_argument('--version', action='store_true')
