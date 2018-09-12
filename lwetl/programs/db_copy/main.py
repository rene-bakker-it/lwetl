"""
Utility: copy tables between database instances
"""
import lwetl
import os
import sys

from collections import OrderedDict
from datetime import datetime

from .cmdline import \
    DRIVER_SINGLE, DRIVER_MULTI, UPLOADERS, \
    COPY_EMPTY, COPY_AND_UPDATE, COPY_AND_SYNC, parser

from lwetl.version import __version__
from lwetl.queries import content_queries
from lwetl.runtime_statistics import timedelta_to_string, tag_connection, get_execution_statistics
from lwetl.utils import is_empty

SRC = "src"
TRG = "trg"

# find common tables
COMMON, EMPTY, IGNORED, MISSING, NO_SOURCE = 'common', 'empty', 'ignored', 'missing', 'no_source'

CNT_COPIED_TABLES = 'copied tables'
CNT_FAIL = 'fails'


def referring_tables(table_list: list, table_dict: dict, excluded=None):
    """
    Scan for tables, which are both in the input list and referenced by
    other tables in the table_list (FK reference)
    Exclude tables in the exluded list

    @param table_list: list of tables to scan
    @param table_dict: dict with FK reference info of all tables
    @param excluded: list of excluded tables
    @return: list of tables, which are referenced
    """
    if excluded is None:
        excluded = []
    assert isinstance(table_list, list)
    assert isinstance(excluded, list)
    assert isinstance(table_dict, dict)

    fk_tables = []
    for table in table_list:
        for column_info in table_dict[table].values():
            if (column_info[0] not in fk_tables) and (table != column_info[0]) and (column_info[0] not in excluded):
                fk_tables.append(column_info[0])
    return sorted(fk_tables)


def print_list(label, table_list, tc=None):
    """
    Nice printout to stdout of the input table list
    @param label: str - label of the printout
    @param table_list: list - list of tables
    @param tc: dictionary of row counts for each table (optional)
    """
    nt = len(table_list)
    if nt == 0:
        return
    print('%s (n=%d):' % (label, nt))
    for x in range(nt):
        table = table_list[x]
        if isinstance(tc, dict) and table in tc:
            if tc[table][0] == tc[table][1]:
                marker = ''
            else:
                n = tc[table][0] if tc[table][0] > 0 else 1
                marker = '%15d' % (tc[table][1]-tc[table][0])
                f = abs(100.0*(tc[table][1]-tc[table][0])/n)
                if f <= 999.0:
                    marker += ' %5.1f %%' % f
            print('%3d. %-35s n(src) = %9d, n(trg) = %9d %s' % (x + 1, table, tc[table][0], tc[table][1], marker))
        else:
            print('%3d. %-35s' % (x + 1, table))


def estimate_remaining(t0, rc, n):
    if rc <= 0:
        return '??:??:??'
    elif rc >= n:
        return '00:00:00'
    else:
        return timedelta_to_string(((1.0 * n / rc) - 1.0) * (datetime.now() - t0))


def clean_exit(jdbc_connections, args, exit_code):
    if args.statistics:
        print(get_execution_statistics())
    jdbc_connections[SRC].close()
    jdbc_connections[TRG].close()
    sys.exit(exit_code)


class TooMayErrorsException(Exception):
    pass


def main():
    if (len(sys.argv) > 1) and (sys.argv[1].lower() == '--version'):
        print('%s, version: %s' % (os.path.basename(sys.argv[0]), __version__))
        sys.exit(0)

    args = parser.parse_args()

    if args.version:
        print('%s, version: %s' % (os.path.basename(sys.argv[0]), __version__))
        sys.exit(0)

    included_tables = []
    if args.tables is not None:
        for t in args.tables.split(','):
            t = t.strip().upper()
            if (len(t) > 0) and (t not in included_tables):
                included_tables.append(t)
    excluded_tables = []
    n_excluded = 0
    if args.exclude is not None:
        try:
            n_excluded = int(args.exclude)
        except ValueError:
            for t in args.exclude.split(','):
                t = t.strip().upper()
                if (len(t) > 0) and (t not in excluded_tables):
                    excluded_tables.append(t)

    jdbc = {
        SRC: args.login_source,
        TRG: args.login_target
    }

    # information on table constraints and references
    table_info = dict()
    # information on the primary keys of tables
    pk_info = dict()
    for key in [SRC, TRG]:
        login = jdbc[key]
        try:
            con = lwetl.Jdbc(login)
        except (lwetl.ServiceNotFoundException, lwetl.DriverNotFoundException, ConnectionError) as login_error:
            print("ERROR for '%s': %s" % (jdbc[key], str(login_error)))
            sys.exit(1)

        jdbc[key] = con
        tag_connection(key, con)
        if con.type not in content_queries:
            print("ERROR: database type '%s' not supported." % con.type)
            sys.exit(1)

        sql = content_queries[con.type]
        if '@SCHEMA@' in sql:
            sql = sql.replace('@SCHEMA@', con.schema)

        print('Query %s database: %s' % (key.upper(), login))
        try:
            con.execute(sql)
        except lwetl.SQLExcecuteException as exec_error:
            print('ERROR: cannot retrieve database info for: ' + login)
            print(exec_error)
            sys.exit(1)

        tables = dict()
        pk_col = dict()
        for d in con.get_data(return_type=OrderedDict):
            table_name = d['TABLE_NAME'].upper()
            if table_name not in tables:
                tables[table_name] = dict()
            if not is_empty(d.get('FK_TABLE', None)):
                tables[table_name][d['COLUMN_NAME'].upper()] = d['FK_TABLE'].upper(), d['CONSTRAINT_NAME'].upper()
            if d.get('KEY_TYPE', None) == 'PK':
                pk_col[table_name] = d['COLUMN_NAME'].upper()
        table_info[key] = tables
        pk_info[key] = pk_col

    table_admin = dict()
    for t in [COMMON, EMPTY, IGNORED, MISSING, NO_SOURCE]:
        table_admin[t] = []

    table_count = dict()
    for t in sorted([k for k in table_info[SRC].keys() if k in table_info[TRG]]):
        sql = 'SELECT COUNT(*) FROM ' + t
        n1 = jdbc[SRC].get_int(sql)
        n2 = jdbc[TRG].get_int(sql)
        table_count[t] = n1, n2
        if (t not in excluded_tables) and \
                ((len(included_tables) == 0) or (t in included_tables)):
            if n1 == 0:
                table_admin[EMPTY].append(t)
            else:
                if (n2 == 0) or (args.mode != COPY_EMPTY):
                    table_admin[COMMON].append(t)
                else:
                    table_admin[IGNORED].append(t)
        else:
            table_admin[IGNORED].append(t)

    print_list('Tables to copy', table_admin[COMMON], table_count)
    print_list('Tables ignored (not empty or marked)', table_admin[IGNORED], table_count)
    print_list('Empty source', table_admin[EMPTY], table_count)

    missing_tables = sorted([k for k in table_info[SRC].keys() if k not in table_info[TRG]])
    print_list('Tables not defined on target', missing_tables)

    nosource_tables = sorted([k for k in table_info[TRG].keys() if k not in table_info[SRC]])
    print_list('Missing source:', nosource_tables)

    common_tables = table_admin[COMMON]
    if len(common_tables) < 2:
        copy_list = common_tables
    else:
        # re-order the list of tables, to avoid FK violations
        copy_list = []
        while len(copy_list) < len(common_tables):
            not_added = [t for t in common_tables if t not in copy_list]
            refered_tables = referring_tables(not_added, table_info[TRG], copy_list)
            while len(refered_tables) > 0:
                not_added = [t for t in refered_tables]
                refered_tables = referring_tables(not_added, table_info[TRG], copy_list)
            copy_list += not_added

    if n_excluded > 0:
        print_list('Skipped tables', copy_list[:n_excluded], table_count)
        copy_list = copy_list[n_excluded:]
    print_list('Copy process will use the following order', copy_list, table_count)

    if args.list:
        clean_exit(jdbc, args, 0)
    elif len(copy_list) == 0:
        print('No tables to copy found: exiting.')
        clean_exit(jdbc, args, 0)

    commit_mode = lwetl.UPLOAD_MODE_ROLLBACK
    if args.activate:
        print('Activating upload.')
        commit_mode = lwetl.UPLOAD_MODE_COMMIT

    if (args.mode in [COPY_AND_UPDATE, COPY_AND_SYNC]) and (args.driver == DRIVER_MULTI):
        print('WARNING: multi mode not supported for updates. Switching to single.')
        args.mode = DRIVER_SINGLE

    counters = {
        CNT_COPIED_TABLES: 0,
        CNT_FAIL: 0
    }

    too_many_errors = False
    is_update = args.mode in [COPY_AND_UPDATE, COPY_AND_SYNC]
    for t in [tt for tt in copy_list if tt not in table_admin[IGNORED]] :
        counters[CNT_COPIED_TABLES] += 1
        n, n2 = table_count[t]
        print("CC %3d. of %d: copy %-30s n = %6d values (PK = %s) ......." % (
            counters[CNT_COPIED_TABLES], len(copy_list), t, n, pk_info[SRC][t]))

        existing_records = []
        # target primary key
        pk_trg = pk_info[TRG][t]
        if (n2 > 0) and (args.mode != COPY_EMPTY):
            for r in jdbc[TRG].query("SELECT {0} FROM {1} ORDER BY {0}".format(pk_trg, t)):
                existing_records.append(r[0])
            print('Found %d existing records from %s to %s' % (
                len(existing_records), min(existing_records), max(existing_records)))
        existing_records = set(existing_records)

        try:
            cursor = jdbc[SRC].execute('SELECT * FROM {0} ORDER BY {1}'.format(t, pk_info[SRC][t]),cursor=None)
        except lwetl.SQLExcecuteException as exec_error:
            print('ERROR: table %s skipped on SQL retrieve error: ' + str(exec_error))
            too_many_errors = True
            cursor = None
        if too_many_errors:
            break

        row_count = 0
        skp_count = 0
        upd_count = 0
        new_count = 0
        found_records = []
        t0_table = datetime.now()
        try:
            with UPLOADERS[args.driver](jdbc[TRG], t.lower(), commit_mode=commit_mode) as uploader:
                for d in jdbc[SRC].get_data(cursor=cursor, return_type=dict, include_none=is_update):
                    row_count += 1

                    pk = d[pk_trg]
                    if args.mode == COPY_AND_SYNC:
                        found_records.append(pk)
                    record_exists = (pk in existing_records)
                    if record_exists and (not is_update):
                        skp_count += 1
                    else:
                        try:
                            if record_exists:
                                del d[pk_trg]
                                uploader.update(d, {pk_trg: pk})
                                upd_count += 1
                            else:
                                if is_update:
                                    none_keys = [c for c, v in d.items() if v is None]
                                    for k in none_keys:
                                        del d[k]
                                uploader.insert(d)
                                new_count += 1
                        except lwetl.SQLExcecuteException as insert_exception:
                            counters[CNT_FAIL] += 1
                            print('Insert error (%d) on row %d: %s' % (
                                counters[CNT_FAIL], row_count, str(insert_exception)))
                            if (args.max_fail >= 0) and (counters[CNT_FAIL] > args.max_fail):
                                print('Too many errors: terminating.')
                                too_many_errors = True
                        if too_many_errors:
                            raise TooMayErrorsException('Insert or Update failed %d times' % counters[CNT_FAIL])

                    has_commit = False
                    if uploader.row_count >= args.commit_nr:
                        uploader.commit()
                        has_commit = True
                    if has_commit or ((row_count % args.commit_nr) == 0):
                        print(
                            '%8d. %5.1f %% of %d records, new: %8d, upd: %8d, ign: %8d. %s. Est. remaining time: %s' %
                            (row_count, (100.0 * row_count / n), n, new_count, upd_count, skp_count, t,
                             estimate_remaining(t0_table, row_count, n)))
                    if (args.max_rows > 0) and ((new_count + upd_count) > args.max_rows):
                        print('Terminating after %d uploads on user request.' % row_count)
                        break
                if uploader.row_count > 0:
                    uploader.commit()
                if (new_count + upd_count) > 0:
                    dt = datetime.now() - t0_table
                    dt_sec = dt.total_seconds()
                    if dt_sec > 0:
                        rec_per_sec = int(round(1.0 * n / dt_sec))
                    else:
                        rec_per_sec = 0
                    print(
                        '%8d. %5.1f %% of %d records, new: %8d, upd: %8d, ign: %8d. %s. Used time: %s (%d rec/s)' %
                        (row_count, (100.0 * row_count / n), n, new_count, upd_count, skp_count, t,
                         timedelta_to_string(dt), rec_per_sec))

            if args.mode == COPY_AND_SYNC:
                to_delete = list(existing_records - set(found_records))
                if len(to_delete) > 0:
                    print('Sync: removing %d obsolete records in %s (target)' % (len(to_delete), t))
                    while len(to_delete) > 0:
                        if len(to_delete) > 500:
                            delete_list = to_delete[0:500]
                            to_delete = to_delete[500:]
                        else:
                            delete_list = [pk for pk in to_delete]
                            to_delete = []
                        par_list = ['?'] * len(delete_list)
                        sql = 'DELETE FROM {0} WHERE {1} IN ({2})'.format(t, pk_trg, ','.join(par_list))
                        try:
                            jdbc[TRG].execute(sql, delete_list, cursor=None)
                        except lwetl.SQLExcecuteException as delete_exception:
                            counters[CNT_FAIL] += len(delete_list)
                            print(delete_exception)
                            print('Delete error (%d) in table %s on rows %s' %
                                  (counters[CNT_FAIL], t, ', '.join([str(pk) for pk in delete_list])))
                            if (args.max_fail >= 0) and (counters[CNT_FAIL] > args.max_fail):
                                print('Too many errors: terminating.')
                                too_many_errors = True
                            if too_many_errors:
                                raise TooMayErrorsException(
                                    'Insert, Update, and Delete failed %d times' % counters[CNT_FAIL])
                    if commit_mode == lwetl.UPLOAD_MODE_COMMIT:
                        jdbc[TRG].commit()
                    else:
                        jdbc[TRG].rollback()

        except lwetl.CommitException as ce:
            counters[CNT_FAIL] += 1
            if not (args.ignore_commit_errors and (args.max_fail > 0) and (counters[CNT_FAIL] <= args.max_fail)):
                print('Upload encountered a commit exception row {}. Further processing ignored: {}'.format(row_count, str(ce)),
                      file=sys.stderr)
                too_many_errors = True
        except TooMayErrorsException as tee:
            print('Upload encountered on row {}. Further processing ignored: {}'.format(row_count,str(tee)),
                  file=sys.stderr)
            too_many_errors = True
        if too_many_errors:
            break

    if counters[CNT_FAIL] > 0:
        print('WARNING: not all data has been transfered. Errors = %d' % counters[CNT_FAIL])
    rc = 1 if too_many_errors else 0
    clean_exit(jdbc, args, rc)


if __name__ == '__main__':
    main()
