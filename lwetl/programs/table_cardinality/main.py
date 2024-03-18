"""
Utility: use aggregate counters on the columns of a specified table

"""

import argparse
import lwetl
import os
import sys

from lwetl.version import __version__
from lwetl.exceptions import SQLExecuteException


def count(login, table, filename, max_rows):
    error = None
    try:
        jdbc = lwetl.Jdbc(login)
    except (lwetl.ServiceNotFoundException, lwetl.DriverNotFoundException, ConnectionError) as login_error:
        print('ERROR: ' + str(login_error))
        error = login_error

    if error is not None:
        return

    cur = None
    # noinspection PyBroadException
    try:
        # noinspection PyUnboundLocalVariable
        cur = jdbc.execute("SELECT * FROM {} WHERE 0=1".format(table))
        columns = jdbc.get_columns()
    except Exception:
        columns = None
        jdbc.close()

    if columns is None:
        print('ERROR: cannot find information on table: ' + table)
        return 1

    sql_base = 'SELECT {0}, COUNT(*) AS N FROM {1} WHERE {0} IS NOT NULL GROUP BY {0} HAVING COUNT(*) > 1 ORDER BY ' \
               'COUNT(*) DESC,{0} '
    sql_count = 'SELECT COUNT(*) AS N FROM {1} WHERE {0} IS NOT NULL'

    with lwetl.XlsxFormatter(cursor=cur, filename_or_stream=filename, pretty=True) as xls:
        sheet1 = xls.sheet
        sheet1.append(['COLUMN NAME', 'DISTINCT', 'TOTAL', 'TOTAL NON DISTINCT'])
        for column_name in columns.keys():
            tot = jdbc.get_int(sql_count.format(column_name, table))
            try:
                cur = jdbc.execute(sql_base.format(column_name, table))
                tds = 0
                cnt = 0
                new_table = True
                for row in jdbc.get_data(cur):
                    cnt += 1
                    tds += int(row[1])
                    if (max_rows <= 0) or (cnt <= max_rows):
                        if new_table:
                            xls.next_sheet(cur, column_name)
                            xls.header()
                            new_table = False
                        xls.write(row)
                print('Parsed: {:<30} d = {:6}, t = {:6}, s = {:6}'.format(column_name, cnt, tot, tds))
            except SQLExecuteException:
                cnt = None
                tds = None
            sheet1.append([column_name, cnt, tot, tds])
    print('Done.')
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog='table-cardinality',
        description='Use aggregate counters to view cardinality of columns in a table.',
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('login', help='''login credentials or alias, use 'list' to view possible options.
    Credentials are in ORACLE format: <username>/<password>@server''')

    parser.add_argument('table', nargs='?', help='Specify the table')

    parser.add_argument(
        'filename', nargs='?', default=None,
        help='Specify the output file. Defaults to <table name>.xlsx in the current directory.')

    parser.add_argument(
        '-m', '--max_rows', action='store', type=int,
        dest='max_rows',
        default=50,
        help='Limit the maximum number of rows in the output table. Use <= 0 for all. Defaults to 50.')

    parser.add_argument('--version', action='store_true')

    if (len(sys.argv) > 1) and (sys.argv[1].lower() == '--version'):
        print('{}, version: {}'.format(os.path.basename(sys.argv[0]), __version__))
        sys.exit(0)

    args = parser.parse_args()

    if args.version:
        print('{}, version: {}'.format(os.path.basename(sys.argv[0]), __version__))
        sys.exit(0)

    if args.login.lower() == 'list':
        lwetl.print_info()
        sys.exit(0)

    if args.table is None:
        print('ERROR: table not specified.')
        sys.exit(1)

    if args.filename is None:
        args.filename = args.table.lower() + '.xlsx'
        print('INFO - output file: ' + args.filename)

    count(args.login, args.table, args.filename, args.max_rows)


if __name__ == '__main__':
    main()
