import io
import lwetl
import os
import pytest
import sys

from tests import TEST_CONFIGURATION, OUTPUT_DIR, TEST_DIR, I_CAN_EAT_GLASS

from contextlib import redirect_stdout
from decimal import Decimal

from lwetl.queries import content_queries

DRIVER_KEYS = sorted(TEST_CONFIGURATION.keys())

# I do not want a new connection for each test
JDBC_CONNECTIONS = dict()
for k in DRIVER_KEYS:
    JDBC_CONNECTIONS[k] = lwetl.Jdbc('scott_' + k, auto_commit=False, upper_case=True)

@pytest.fixture(params=DRIVER_KEYS)
def jdbc(request):
    alias = 'scott_' + request.param
    print('CONNECTING WITH: ' + alias)
    return JDBC_CONNECTIONS[request.param]


def get_tables(jdbc: lwetl.Jdbc) -> list:
    """
    Get the tables defined in the connected database schema
    @param jdbc: lwetl.Jdbc - database connection
    @return: list  of table names in uppercase
    """

    if jdbc.type not in content_queries:
        raise LookupError('Database type %s not supported.' % jdbc.type)
    sql = content_queries[jdbc.type]
    if '@SCHEMA@' in sql:
        sql = sql.replace('@SCHEMA@', jdbc.schema)

    tables = []
    error = None
    try:
        jdbc.query(sql)
        for r in jdbc.get_data():
            if (len(r) > 0) and (r[0].upper() not in tables):
                tables.append(r[0].upper())
    except lwetl.SQLExcecuteException as exec_error:
        print('ERROR in get_tables()', sys.stderr)
        error = exec_error

    if error is None:
        return tables
    else:
        raise lwetl.SQLExcecuteException(str(error))


def get_test_configuration(jdbc: lwetl.Jdbc) -> dict:
    """
    Return the test configuration for the driver associated with the jdbc connection
    @param jdbc: - the database connection.
    @return: dict - test configurations, see sql_statements.yml for details.
    @raise LookupError if the driver type is not supported.
    """
    return TEST_CONFIGURATION[jdbc.type]


def test_connection_noservice():
    """
    Test a connection to an undefined server. Should raise the appropriate exceptions
    """
    with pytest.raises(lwetl.ServiceNotFoundException):
        lwetl.Jdbc('scott/tiger@noservice')


def test_connection_noconnection(jdbc: lwetl.Jdbc):
    """
    Test a connection to a known jdbc server, with an erroneous username.
    """
    wrong_alias = 'xscott/tiger@scott_' + jdbc.type
    print('\nTest login fail (connection failed) with: ' + wrong_alias)
    error = None
    try:
        lwetl.Jdbc(wrong_alias)
    except Exception as e:
        print('******' + str(e) + '********')
        error = e
    if (error is not None) and (not isinstance(error, (ConnectionError, lwetl.ServiceNotFoundException))):
        raise error


def test_driver_info(jdbc: lwetl.Jdbc):
    print('\nRunning lwetl.JdbcInfo test: ' + jdbc.type)
    info = lwetl.JdbcInfo(jdbc.login)
    # set to False for less stdout
    verbose = True
    with io.StringIO() as f:
        with redirect_stdout(f):
            result = info(max_width=75)
        if verbose:
            print(f.getvalue())
        else:
            print('jdbc_info produced %d lines.' % len(f.getvalue().split("\n")))
    assert result


def test_access(jdbc: lwetl.Jdbc):
    class Upload:
        def __init__(self, jdbc: lwetl.Jdbc):
            self.stm_count = 0
            self.row_count = 0
            self.jdbc = jdbc

        def __call__(self, sql, raise_error_on_error=True):
            print(sql)
            error_msg = None
            try:
                c = self.jdbc.execute(sql, cursor=None)
            except lwetl.SQLExcecuteException as sql_error:
                self.jdbc.rollback()
                error_msg = str(sql_error)
            else:
                self.stm_count += 1
                if c.rowcount > 0:
                    self.row_count += c.rowcount
                self.jdbc.commit()
            if error_msg is not None:
                if raise_error_on_error:
                    raise lwetl.SQLExcecuteException(error_msg)
                else:
                    print('SQL ERROR ignored: ' + error_msg)

    cfg = get_test_configuration(jdbc)

    upload = Upload(jdbc)
    for key in [k for k in ['drop', 'create', 'insert'] if k in cfg]:
        raise_error = (key != 'drop')
        for skey in sorted(cfg[key].keys()):
            upload(cfg[key][skey], raise_error)
        jdbc.connection.commit()

    if 'check' in cfg:
        sql_1 = cfg['check']['sql_1']
        sql_n = cfg['check']['sql_n']
        d1 = jdbc.query_single_value(sql_1)
        if isinstance(d1, float):
            d1 = Decimal(str(d1))

        d2 = Decimal('0.0')
        for r in jdbc.query(sql_n):
            price = r[0]
            if isinstance(price, str):
                price = Decimal(price)
            d2 += price
        print('Test found d1,d2 = {0},{1}'.format(d1, d2))
        assert d1 == d2
    del jdbc


def test_table_import(jdbc: lwetl.Jdbc):
    importers = {
        'xls': (lwetl.XlsxImport, lwetl.MultiParameterUploader),
        'csv': (lwetl.CsvImport, lwetl.NativeUploader),
        'ldif': (lwetl.LdifImport, lwetl.ParameterUploader)
    }
    print('\nRunning table import test: (%s,%s)' % (jdbc.login, jdbc.type))

    cfg = get_test_configuration(jdbc)
    for key in ['xls', 'csv', 'ldif']:
        import_cfg = importers[key]
        if key not in cfg:
            print('No definition for inport of format: ' + key)
            continue
        fname = os.path.join(TEST_DIR, 'resources', cfg[key]['file'])
        table = cfg[key]['table']

        importer, uploader = import_cfg
        with importer(fname) as imp:
            with uploader(jdbc, table, fstream=sys.stdout,
                          commit_mode=lwetl.UPLOAD_MODE_COMMIT) as upl:
                if key == 'ldif':
                    for rec in imp.get_data():
                        dd = {
                            'PRICE': float(rec['price'])
                        }
                        if ('photo' in rec) and (jdbc.type in ['oracle', 'mysql', 'sqlserver']):
                            dd['PHOTO'] = rec['photo']
                        upl.update(dd, {'NAME': rec['name']})
                else:
                    if jdbc.type in ['oracle', 'sqlite']:
                        upl.add_counter('ID')
                    for r in imp.get_data():
                        print(r)
                        upl.insert(r)
                upl.commit()


# Encoding test skipped: first needs update of JPype to 0.7
def test_encoding(jdbc: lwetl.Jdbc):
    print('\nRunning ldif insert encoding test: (%s,%s)' % (jdbc.login, jdbc.type))
    table = 'LWETL_ENC'

    # read ldif and dump in table
    fn = os.path.join(os.path.dirname(__file__), 'resources', 'utf8.ldif')
    cnt = 0
    with lwetl.ParameterUploader(jdbc, table, commit_mode=lwetl.UPLOAD_MODE_COMMIT) as upl:
        with lwetl.LdifImport(fn) as ldif:
            for rec in ldif.get_data():
                dd = {
                    'ID': int(rec['indx']),
                    'LANG1': rec['sn'],
                    'VAL': rec['value']
                }
                if 'cn' in rec:
                    dd['LANG2'] = rec['cn']
                upl.insert(dd)
                cnt += 1
        upl.commit()

    # check if the number of rows is currect
    cnt2 = jdbc.get_int("SELECT COUNT(1) FROM {0}".format(table))
    print('Inserted %d of %d values' % (cnt2,cnt))
    assert cnt == cnt2

    # reread the table and verify with origininal
    cnt_ok = 0
    cnt_fail = 0
    for lg1, lg2, val in jdbc.query("SELECT LANG1, LANG2, VAL FROM {0} ORDER BY LANG1, LANG2".format(table)):
        if lg2:
            r = '%s.%s' % (lg1,lg2)
            s = I_CAN_EAT_GLASS.get(lg1,dict()).get(lg2,'NN')
        else:
            r = lg1
            s = I_CAN_EAT_GLASS.get(lg1,'NN')

        if val == s:
            cnt_ok += 1
        else:
            cnt_fail += 1
            print('FAILED %s s=(%s) db=(%s)' % (r,s,val))
    assert cnt_fail == 0


# depricated? @pytest.mark.slow
def test_binary_io(jdbc: lwetl.Jdbc):
    print('\nRunning binary insert test: (%s,%s)' % (jdbc.login, jdbc.type))
    cfg = get_test_configuration(jdbc).get('binary', None)
    if cfg is None:
        print('No binary io test defined. Skipping test.')
        return

    fname = os.path.join(TEST_DIR, 'resources', cfg['file'])
    print('Testing upload from: ' + fname)
    with open(fname, mode='rb') as file:
        img = file.read()

    table = cfg['table']
    column = cfg['column']
    id_pk = cfg['id']

    uploader = lwetl.ParameterUploader(jdbc, table, fstream=sys.stdout, commit_mode=lwetl.UPLOAD_MODE_COMMIT)
    error = None
    try:
        uploader.update({column: img}, {'ID': id_pk})
        uploader.commit()
    except lwetl.SQLExcecuteException as exec_error:
        error = exec_error
        print('TEST SKIPPED: unsupported feature.')
        print(exec_error)
    else:
        fname = os.path.join(OUTPUT_DIR, '%s.%s.jpg' % (jdbc.type, table.lower()))
        print('Testing download to: ' + fname)
        with open(fname, 'wb') as g:
            g.write(jdbc.query_single_value('SELECT {0} FROM {1} WHERE ID = {2}'.format(column, table, id_pk)))
    # assert error is None


def test_jdbc_query(jdbc: lwetl.Jdbc):
    print('\nRunning Schema query test: (%s,%s)' % (jdbc.login, jdbc.type))
    try:
        tables = get_tables(jdbc)
    except LookupError as lookup_error:
        print(lookup_error)
    else:
        if len(tables) == 0:
            print('No tables found.')
        else:
            if len(tables) > 1:
                tables = sorted(tables)
            print('%d tables found: %s' % (len(tables), ', '.join(tables)))


def test_formatters(jdbc: lwetl.Jdbc):
    print('\nRunning formatter test: (%s,%s)' % (jdbc.login, jdbc.type))

    formatters = {
        'txt': lwetl.TextFormatter,
        'csv': lwetl.CsvFormatter,
        'xml': lwetl.XmlFormatter,
        'xlsx': lwetl.XlsxFormatter,
        'sql': lwetl.SqlFormatter
    }

    output_dir = os.path.join(TEST_DIR, 'output', jdbc.type)
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)
    extensions = sorted(formatters.keys())
    has_errors = False
    for table in [t.upper() for t in get_tables(jdbc) if t.upper().startswith('LWETL')]:
        if has_errors:
            break
        print('\nQuery: ' + table)
        sql = "SELECT * FROM {0}".format(table)
        for ext in extensions:
            formatter = formatters[ext]
            print("\n\nTesting (1): " + formatter.__name__)
            kwargs = {
                'cursor': jdbc.execute(sql),
                'filename_or_stream': os.path.join(output_dir, '%s-1.%s' % (table, ext))
            }
            if ext == 'sql':
                kwargs['connection'] = jdbc
                kwargs['table'] = table
            elif ext == 'xml':
                kwargs['pretty_print'] = True

            with formatter(**kwargs) as f:
                f.header()
                for r in jdbc.get_data():
                    f.write(r)
                f.footer()
        for ext in extensions:
            kwargs = {
                'jdbc': jdbc,
                'sql': sql,
                'filename_or_stream': os.path.join(output_dir, '%s-2.%s' % (table, ext))
            }
            if ext == 'sql':
                kwargs['connection'] = jdbc
                kwargs['table'] = table
            elif ext == 'xml':
                kwargs['pretty_print'] = True
            formatter = formatters[ext]()
            print("\n\nTesting (2): " + type(formatter).__name__)
            formatter(**kwargs)
