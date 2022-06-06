"""
    Parse sql to a database, either to extract data or to insert it
    Supports multiple io formats.
"""

import lwetl
import os
import sys

from collections import OrderedDict

from lwetl.version import __version__
from lwetl.queries import content_queries
from lwetl.utils import is_empty
from lwetl.config_parser import JDBC_DRIVERS
from lwetl.programs.sql_query.cmdline import FORMATTERS, parser


def show_version():
    """
    Display the version info of this module
    @return 0
    """
    print('{}, version: {}'.format(os.path.basename(sys.argv[0]), __version__))
    return 0


def show_jdbc_info(login):
    """
    Show jdbc parameter settings and options
    @param login: login credentials or alias
    @return: 0
    """
    from lwetl.jdbc_info import JdbcInfo

    jdbc_info = JdbcInfo(login)
    jdbc_info()
    return 0


def get_table_info_sql(jdbc: lwetl.Jdbc) -> str:
    """
    Retrieve an SQL to dump the database tables and columns
    @param jdbc: lwetl.Jdbc the database connection
    @return: str the SQL to use
    @raise LookupError if the database type is not supported for this function
    """
    # Dump the database tables and columns
    if jdbc.type in content_queries:
        sql = content_queries[jdbc.type]
        if '@SCHEMA@' in sql:
            sql = sql.replace('@SCHEMA@', jdbc.schema)
        return sql
    else:
        raise LookupError("Database type '{}' not supported.".format(jdbc.type))


def upload_table(jdbc: lwetl.Jdbc, commit_mode: str, commit_nr: int, max_rows: int,
                 table_name: str, file_name: str, file_format: str, separator: str, log_file: str) -> int:
    if file_format not in ['xlsx', 'csv']:
        # guess by file extension
        lc_filename = file_name.lower()
        if '.' in lc_filename:
            f_extension = lc_filename.split('.')[-1]
            if f_extension == 'xlsx':
                file_format = 'xlsx'
            elif f_extension in ['csv', 'dat', 'txt']:
                file_format = 'csv'
        if file_format not in ['xls', 'csv']:
            def is_binary_string(bts, text_chars):
                return bool(bts.translate(None, text_chars))

            # guess by file type: binary/text
            with open(file_name, 'rb') as f:
                if is_binary_string(f.read(1024),
                                    bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})):
                    file_format = 'xlsx'
                else:
                    file_format = 'csv'

    if file_format == 'xlsx':
        importer = lwetl.XlsxImport(file_name)
    elif file_format == 'csv':
        importer = lwetl.CsvImport(file_name, delimiter=separator)
    else:
        print('ERROR: formatter {} is not supported for file upload. Valid choices: csv, xlsx'.format(file_format))
        return 1

    row_count = 0
    importer.open()
    with lwetl.ParameterUploader(jdbc, table_name, fstream=log_file, commit_mode=commit_mode,
                                 commit_count=commit_nr) as uploader:
        for row in importer.get_data():
            row_count += 1
            uploader.insert(row)
            if (max_rows > 0) and (row_count >= max_rows):
                break
    importer.close()
    print('Done: {} rows uploaded.'.format(row_count))
    return 0


# noinspection PyBroadException
def parse_output(cursors: list, args):
    if len(cursors) < 1:
        return

    kwargs = {
        'append': False,
        'filename_or_stream': args.output_file
    }
    if args.format == 'csv':
        kwargs['delimiter'] = args.separator
    elif args.format == 'text':
        kwargs['column_width'] = args.column_width
    elif args.format == 'xmlp':
        kwargs['pretty_print'] = True
    elif args.format == 'xlsx':
        kwargs['pretty'] = True
    elif args.format == 'sql':
        jdbc = getattr(cursors[0], lwetl.jdbc.PARENT_CONNECTION)
        kwargs['connection'] = jdbc
        kwargs['columns'] = jdbc.get_columns(cursors[0])
        if args.target_db is not None:
            if '?' in args.target_db:
                lst = args.target_db.split('?')
                alias = lst.pop(0)
                if alias in JDBC_DRIVERS:
                    kwargs['type'] = alias
                else:
                    try:
                        jdbc2 = lwetl.Jdbc(alias)
                        kwargs['connection'] = jdbc2
                    except Exception:
                        try:
                            jdbc2 = lwetl.jdbc.DummyJdbc(alias)
                            kwargs['connection'] = jdbc2
                        except Exception:
                            pass
                table_spec = '?'.join(lst)
            else:
                table_spec = args.target_db
            if ',' in table_spec:
                lst = [s.strip() for s in table_spec.split(',')]
                kwargs['table'] = lst.pop(0)
                columns = OrderedDict()
                for col in lst:
                    columns[col] = lwetl.jdbc.COLUMN_TYPE_STRING
                kwargs['columns'] = columns
            else:
                kwargs['table'] = table_spec
    if args.cast is None:
        return_type = tuple
    else:
        return_type = tuple([s.strip() for s in args.cast.split(',')])

    sql_count = 0
    f = FORMATTERS[args.format](**kwargs)
    for cursor in cursors:
        sql_count += 1
        jdbc = getattr(cursor, lwetl.jdbc.PARENT_CONNECTION, None)
        if not isinstance(jdbc, lwetl.Jdbc):
            raise ValueError('Cursor is not created by a Jdbc connection.')

        kwargs['cursor'] = cursor
        if sql_count == 1:
            f.open(**kwargs)
        elif args.format in ['xlsx', 'xml', 'xmlp']:
            f.next_sheet(cursor, 'Sheet{}'.format(sql_count))
        else:
            f.close()
            kwargs['append'] = True
            f.open(**kwargs)

        rc = 0
        rc_max = args.max_rows
        f.header()
        try:
            single_cast = isinstance(return_type, tuple) and (len(return_type) == 1)
            for row in jdbc.get_data(cursor, return_type=return_type):
                if single_cast and (not isinstance(row, tuple)):
                    row = tuple([row])
                f.write(row)
                rc += 1
                if (rc_max > 0) and (rc >= rc_max):
                    print('Output truncated on user request.', file=sys.stdout)
                    jdbc.close(cursor)
                    break
            f.footer()
        except lwetl.SQLExcecuteException as exec_error:
            print('ERROR: cannot retrieve the data: ' + str(exec_error))
    f.close()


def commit(jdbc: lwetl.Jdbc, cursor, mode, row_count, tot_count):
    if mode == lwetl.UPLOAD_MODE_COMMIT:
        jdbc.commit(cursor)
        n_rollback = 0
    else:
        jdbc.rollback(cursor)
        n_rollback = row_count
    print('{} for {:3d} rows ({:6d} total)'.format(mode.upper(), row_count, tot_count))
    return n_rollback


def parse_sql_commands(jdbc: lwetl.Jdbc, sql_input, args) -> int:
    has_error = False
    with lwetl.InputParser(sql_input) as inp:
        row_count = 0
        tot_count = 0
        tot_rollb = 0
        has_update = False
        cursors = []
        cursor = None
        for sql in inp.parse():
            if len(cursors) > 20:
                print('WARNING: you can only parse a maximum of 20 queries with a table result. Terminating buffer.')
                break

            try:
                cursor = jdbc.execute(sql, cursor=cursor)
            except lwetl.SQLExcecuteException as exec_error:
                print("ERROR in parsing: " + sql, file=sys.stderr)
                print(exec_error)
                has_error = True
                break
            else:
                if cursor.rowcount < 0:
                    cursors.append(cursor)
                    cursor = None
                else:
                    has_update = True
                    rc = cursor.rowcount
                    row_count += rc
                    tot_count += rc
                    if row_count >= args.commit_nr:
                        tot_rollb += commit(jdbc, cursor, args.commit_mode, row_count, tot_count)
                        row_count = 0
                        cursor = None
        if row_count > 0:
            tot_rollb += commit(jdbc, cursor, args.commit_mode, row_count, tot_count)
        if has_update:
            print('Finished. {:6d} rows updated.'.format(tot_count - tot_rollb))
        if len(cursors) > 0:
            parse_output(cursors, args)
    return has_error


def main():
    if (len(sys.argv) > 1) and (sys.argv[1].lower() == '--version'):
        # skip parsing
        return show_version()

    args = parser.parse_args()

    if args.version:
        return show_version()

    if args.activate:
        args.commit_mode = lwetl.UPLOAD_MODE_COMMIT

    if args.login.strip().lower() == 'list':
        lwetl.print_info()
        return 0

    # check input command or login alias
    if len(args.login.strip()) == 0:
        print('ERROR: login credentials not defined.')
        parser.print_help()
        return 1

    try:
        jdbc = lwetl.Jdbc(args.login)
    except (lwetl.ServiceNotFoundException, lwetl.DriverNotFoundException, ConnectionError) as login_error:
        print('ERROR - {} - {}'.format(type(login_error).__name__, str(login_error)), file=sys.stderr)
        return 1

    sql = None
    if is_empty(args.command_or_sql):
        print('Command or SQL not specified: using the stdin')
    elif args.command_or_sql.strip().lower() == 'jdbc_info':
        return show_jdbc_info(args.login)
    elif args.command_or_sql.strip().lower() == 'table_info':
        try:
            sql = get_table_info_sql(jdbc)
        except LookupError as le:
            print(le)
            return 1
    elif os.path.isfile(args.command_or_sql):
        pass
    elif ' ' not in args.command_or_sql.strip():
        # the input might be a table name -> test this
        table_name = args.command_or_sql.strip()
        try:
            jdbc.query("SELECT * FROM {0} WHERE 0=1".format(table_name))
        except lwetl.SQLExcecuteException:
            table_name = None
        if table_name is not None:
            if args.file_name is None:
                sql = 'SELECT * FROM ' + table_name
            elif os.path.isfile(args.file_name):
                return upload_table(jdbc, args.commit_mode, args.commit_nr, args.max_rows,
                                    table_name, args.file_name, args.format, args.separator, args.log_file)
            else:
                print('ERROR: specified input file not found: ' + args.file_name)
                return 1
    else:
        sql = args.command_or_sql

    if sql is None:
        sql = sys.stdin
    return parse_sql_commands(jdbc, sql, args)


if __name__ == '__main__':
    main()
