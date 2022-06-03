"""
    Main jdbc connection
"""

import sys

from collections import OrderedDict
from decimal import Decimal

from jpype import JPackage
from jaydebeapi import Cursor, Error, DatabaseError, connect

from .config_parser import JDBC_DRIVERS, JAR_FILES, parse_login, parse_dummy_login
from .exceptions import DriverNotFoundException, SQLExcecuteException, CommitException
from .runtime_statistics import RuntimeStatistics
from .utils import *

# marker (attribute) to trace chained connections
PARENT_CONNECTION = '_lwetl_jdbc'

# Handled column types
COLUMN_TYPE_NUMBER = 'number'
COLUMN_TYPE_FLOAT = 'float'
COLUMN_TYPE_DATE = 'date'
COLUMN_TYPE_STRING = 'str'
COLUMN_TYPE_BINARY = "byte"

DEC_ZERO = Decimal(0.0)

JAVA_STRING = None


def default_cursor(default_result):
    """
    Decorator: adds check on the cursor.
    The function will return the default_result if the specified cursor does not exist
    or current cursor is not defined.
    @param default_result: Any - the default value the function should return if the cursor is not found
    @return: decorated function

    @see http://www.artima.com/weblogs/viewpost.jsp?thread=240845
    """

    def wrap(func):
        def func_wrapper(*args, **kwargs):
            if len(args) < 1:
                raise LookupError('Illegal function for default_cursor decorator')
            self = args[0]
            argl = list(args)
            cursor = kwargs.get('cursor', None)
            if isinstance(cursor, Cursor):
                del kwargs['cursor']
            else:
                if (len(argl) < 2) or (argl[1] is None):
                    cursor = self.current
                elif isinstance(argl[1], Cursor):
                    cursor = argl[1]

            if isinstance(cursor, Cursor):
                if cursor not in self.cursors:
                    raise LookupError('Specified cursor not found in this instance.')
            elif cursor is not None:
                raise ValueError('Illegal cursor specifier.')

            if cursor is None:
                return default_result
            elif len(argl) == 1:
                argl.append(cursor)
            else:
                argl[1] = cursor

            return func(*tuple(argl), **kwargs)

        return func_wrapper

    return wrap


# noinspection PyProtectedMember
def get_columns_of_cursor(cursor: Cursor) -> OrderedDict:
    """
    Retrieve the column information of the specified cursor
    @param cursor: Cursor
    @return: OrderedDict of columns - key: name of the column, value: type of the column
    """

    upper_case = False
    if isinstance(cursor, Cursor):
        if hasattr(cursor, PARENT_CONNECTION):
            upper_case = getattr(cursor, PARENT_CONNECTION).upper_case
    else:
        raise TypeError('cursor must be of type Cursor, found: ' + type(cursor).__name__)

    columns = OrderedDict()
    if cursor.description is not None:
        for x in range(cursor._meta.getColumnCount()):
            name = cursor._meta.getColumnLabel(x + 1)
            if upper_case:
                name = name.upper()

            ctype = cursor.description[x][1]
            if ctype is None:
                columns[name] = COLUMN_TYPE_STRING
            elif len({'INTEGER', 'DECIMAL', 'NUMERIC'}.intersection(ctype.values)) > 0:
                columns[name] = COLUMN_TYPE_NUMBER
            elif len({'FLOAT', 'REAL', 'DOUBLE'}.intersection(ctype.values)) > 0:
                columns[name] = COLUMN_TYPE_FLOAT
            elif 'TIMESTAMP' in ctype.values:
                columns[name] = COLUMN_TYPE_DATE
            else:
                columns[name] = COLUMN_TYPE_STRING
    return columns


class DataTransformer:
    """
        Row types returned by jaydebeapi are not always of a python compatible type.
        This transformer class makes corrections.
    """

    # noinspection PyProtectedMember
    def __init__(self, cursor: Cursor, return_type=tuple, upper_case: bool = True, include_none: bool = False):
        """
        Instantiate a DataTransformer

        @param cursor: Cursor containing query data.
        @param return_type: (optional) return type of the transformation. May be list, tuple (default), dict,
            OrderedDict (see collections), or a string ['int', 'float', 'bool', 'any']. The latter implies
            that only the first value of each row is returned and casted to the specified type.
        @param upper_case: bool - transform column names in upper case (defaults to True)
        @param include_none: bool - include None values in dictionary return types. Defaults to False
        @return DataTransformer

        @raise ValueError if the cursor has no data
        @raise TypeError on a wrong cursor type, or wrong return type
        """
        global JAVA_STRING

        if not isinstance(cursor, Cursor):
            raise TypeError('Variable for the DataTransformer must be a Cursor. Found: ' + type(cursor).__name__)
        elif cursor.description is None:
            raise ValueError('Cannot create a DataTransformer on a cursor without data.')

        expected_types = [list, tuple, dict, OrderedDict]

        self.force_transformation = False
        if isinstance(return_type, str):
            return_type = tuple([return_type])
            self.force_transformation = True
        elif isinstance(return_type, tuple):
            for x, rt in enumerate(return_type, start=1):
                if not isinstance(rt, str):
                    raise TypeError(
                        'Specified return type is not a tuple of strings: element {} is a {}'.format(
                            x, type(rt).__name__))
            self.force_transformation = True

        elif return_type not in expected_types:
            str_types = [str(t).split("'")[1] for t in expected_types]
            raise TypeError(
                'Specified return type must me one of: {} or a (list) of string identifiers. Found: {}'.format(
                    ', '.join(str_types), type(return_type).__name__))
        self.return_type = return_type
        self.include_none = verified_boolean(include_none)

        upper_case = verified_boolean(upper_case)

        columns = []
        column_types = []
        for x in range(cursor._meta.getColumnCount()):
            name = cursor._meta.getColumnLabel(x + 1)
            if upper_case:
                name = name.upper()
            columns.append(name)
            type_def = cursor.description[x][1]
            if type_def is None:
                column_types.append(COLUMN_TYPE_STRING)
            elif len({'INTEGER', 'DECIMAL', 'NUMERIC'}.intersection(type_def.values)) > 0:
                column_types.append(COLUMN_TYPE_NUMBER)
            elif len({'FLOAT', 'REAL', 'DOUBLE'}.intersection(type_def.values)) > 0:
                column_types.append(COLUMN_TYPE_FLOAT)
            elif 'TIMESTAMP' in type_def.values:
                column_types.append(COLUMN_TYPE_DATE)
            else:
                column_types.append(COLUMN_TYPE_STRING)
        self.columns = tuple(columns)
        self.transformer = column_types
        self.nr_of_columns = len(columns)

        if JAVA_STRING is None:
            # JVM must have started for this
            JAVA_STRING = JPackage('java').lang.String

    @staticmethod
    def byte_array_to_bytes(array):
        return bytes([(lambda i: (256 + i) if i < 0 else i)(b) for b in array])

    @staticmethod
    def default_transformer(v):
        if isinstance(v, str):
            # Bugfix: jpype for some multibyte characters parses the surrogate unicode escape string
            #         most notably 4-byte utf-8 for emoji
            return v.encode('utf-16', errors='surrogatepass').decode('utf-16')
        if type(v) == 'java.lang.String':
            return v.getBytes().decode()
        else:
            return v

    def oracle_lob_to_bytes(self, lob):
        # print(type(lob).__name__)
        return self.byte_array_to_bytes(lob.getBytes(1, int(lob.length())))

    # noinspection PyMethodMayBeStatic
    def oracle_clob(self, clob):
        return clob.stringValue()

    @staticmethod
    def parse_number(number):
        if isinstance(number, int):
            return number
        else:
            dval = Decimal(str(number))
            if (dval % 1) == DEC_ZERO:
                return int(number)
            else:
                return dval

    # noinspection PyTypeChecker
    def __call__(self, row):
        """
        Transform a row of data
        @param row: list or tuple
        @return: the transformed row in the return type specified when the class was instantiated
        """

        if row is None:
            return None
        try:
            row_length = len(row)
        except TypeError:
            row = [row]
            row_length = 1
        if row_length != self.nr_of_columns:
            raise ValueError('Invalid row. Expected {} elements but found {}.'.format(self.nr_of_columns, row_length))
        if row_length == 0:
            return self.return_type()

        values = []
        for x in range(row_length):
            value = row[x]
            if value is None:
                values.append(None)
                continue

            func = self.transformer[x]
            if isinstance(func, str):
                # first time use
                vtype = type(value).__name__
                if vtype == 'oracle.sql.BLOB':
                    self.transformer[x] = self.oracle_lob_to_bytes
                elif vtype == 'oracle.sql.CLOB':
                    self.transformer[x] = self.oracle_clob
                elif vtype.startswith('java') or vtype.startswith('oracle'):
                    self.transformer[x] = (lambda vv: vv.toString())
                elif vtype == 'byte[]':
                    self.transformer[x] = self.byte_array_to_bytes
                elif func == COLUMN_TYPE_FLOAT:
                    self.transformer[x] = (lambda vv: vv if isinstance(vv, float) else float(vv))
                elif func == COLUMN_TYPE_NUMBER:
                    self.transformer[x] = self.parse_number
                else:
                    self.transformer[x] = self.default_transformer
                func = self.transformer[x]

            if type(value).__name__ in ['int', 'bool', 'float']:
                # might return from java without a toString method
                values.append(value)
            else:
                parse_exception = None
                try:
                    # noinspection PyCallingNonCallable
                    values.append(func(value))
                except Exception as e:
                    print('ERROR - cannot parse {}: {}'.format(value, str(e)))
                    parse_exception = e
                if parse_exception is not None:
                    raise parse_exception
        if self.return_type == list:
            return values
        elif self.return_type == tuple:
            return tuple(values)
        elif self.force_transformation:
            single_value_transformers = dict(
                str=(lambda vv: vv if isinstance(vv, str) else str(vv)),
                int=(lambda vv: vv if isinstance(vv, int) else int(vv)),
                bool=(
                    lambda vv: vv if isinstance(vv, bool) else bool(vv) if not isinstance(vv, str) else vv.lower() in [
                        'true', '1', 'yes', 'si', 'y', 's']),
                float=(lambda vv: vv if isinstance(vv, float) else float(vv)),
                date=(lambda vv: vv if isinstance(vv, datetime) else string2date(vv)))

            transformed_values = []
            for rt in self.return_type:
                if len(values) > 0:
                    v = values.pop(0)
                    if rt in single_value_transformers:
                        transformed_values.append(single_value_transformers[rt](v))
                    elif '%' in rt:
                        transformed_values.append(datetime.strptime(v, rt))
                    else:
                        transformed_values.append(v)
            if len(transformed_values) == 0:
                return None
            if len(transformed_values) == 1:
                return transformed_values.pop()
            return tuple(transformed_values)
        else:
            dd = self.return_type()
            for x in range(row_length):
                if self.include_none or (values[x] is not None):
                    # noinspection PyUnresolvedReferences
                    dd[self.columns[x]] = values[x]
            return dd


class DummyJdbc:
    """
    Dummy JDBC connection.
    Only stores configuration parameters of the connection, there is no real connection
    """

    def __init__(self, login_or_drivertype: str, upper_case=True):
        self.login = 'nobody'
        self.upper_case = upper_case
        self.type, self.always_escape = parse_dummy_login(login_or_drivertype)

    def commit(self):
        pass

    def rollback(self):
        pass

    # noinspection PyUnusedLocal,PyMethodMayBeStatic
    def execute(self, sql, parametes=None, cursor=None):
        return cursor

    # noinspection PyUnusedLocal,PyMethodMayBeStatic
    def get_int(self, sql, parameters=None):
        return 0


class Jdbc:
    """
    Jdbc connection manager.

    The class loads general connection settings from a configuration file (see below).

    """

    def __init__(self, login: str, auto_commit=False, upper_case=True):
        """
        Init the jdbc connection.
        @param login: str - login credentials or alias as defined in config.yml
        @param auto_commit: bool - auto-commit each sql statement. Defaults to False
                                   (changes are only committed with the jdbc.commit() command)
        @param upper_case: bool
        @raises (ConnectionError,DriverNotFoundException) if het connection could not be established
        """
        self.login = login
        self.auto_commit = verified_boolean(auto_commit)
        self.upper_case = verified_boolean(upper_case)
        self.connection = None

        self.credentials, self.type, self.schema, self.url, self.always_escape = parse_login(login)

        connection_error = None
        try:
            self.connection = connect(JDBC_DRIVERS[self.type]['class'],
                                      self.url, driver_args=self.credentials, jars=JAR_FILES)
            self.connection.jconn.setAutoCommit(auto_commit)
        except Exception as error:
            error_msg = str(error)
            if ('Class' in error_msg) and ('not found' in error_msg):
                connection_error = DriverNotFoundException(error_msg)
            elif 'Could not create connection to database server' in error_msg:
                connection_error = ConnectionError('Failed to connect to: ' + self.url)
            else:
                connection_error = ConnectionError(error_msg)
            if ':' in error_msg:
                error_msg = error_msg.split(':', 1)[-1]
            print('ERROR - jdbc connection failed: ' + error_msg, file=sys.stderr)

        if connection_error is not None:
            raise connection_error

        # for statistics
        self.statistics = RuntimeStatistics()

        # cursor handling
        self.counter = 0
        self.cursors = []
        self.current = None

    # noinspection PyBroadException
    def __del__(self):
        if self.connection:
            for cursor in self.cursors:
                try:
                    cursor.close()
                except Exception:
                    pass
            try:
                self.connection.close()
            except Exception:
                pass

    @default_cursor(False)
    def close(self, cursor=None):
        """
        Closes the specified cursor. Use the current if not specified.
        @param cursor: Cursor|str - cursor or id of the cursor
        @return bool: true on success
        """

        try:
            cursor.close()
            close_ok = True
        except Error:
            close_ok = False
        else:
            self.cursors.remove(cursor)
            if cursor == self.current:
                if len(self.cursors) > 0:
                    self.current = self.cursors[-1]
                else:
                    self.current = None
            # noinspection PyBroadException
            try:
                # for garbage collection
                del cursor
            except Exception:
                pass
        return close_ok

    def execute(self, sql: str, parameters: (list, tuple) = None, cursor: object = None) -> Cursor:
        """
        Execute a query
        @param sql: str query to execute
        @param parameters: list of parameters specified in the sql query. May also be None (no parameters), or
            a list of lists (execute many)
        @param cursor: to use for exection. Create a new one if None (default)
        @return: Cursor of the execution

        @raise SQLExecutionError on an execution exception
        """

        def string2java_string(sql_or_list):
            # Bugfix: 4-byte UTF-8 is not parsed correctly into jpype

            global JAVA_STRING
            if JAVA_STRING is None:
                # JVM must have started for this
                JAVA_STRING = JPackage('java').lang.String

            if sql_or_list is None:
                return None
            elif isinstance(sql_or_list, str):
                return JAVA_STRING(sql_or_list.encode(), 'UTF8')
            elif isinstance(sql_or_list, (list, tuple)):
                parms = []
                for p in sql_or_list:
                    if isinstance(p, str):
                        parms.append(JAVA_STRING(p.encode(), 'UTF8'))
                    else:
                        parms.append(p)
                return parms

        if is_empty(sql):
            raise ValueError('Query string (sql) may not be empty.')
        elif not isinstance(sql, str):
            raise TypeError('Query (sql) must be a string.')

        if (cursor is not None) and (cursor not in self.cursors):
            cursor = None
        if cursor is None:
            self.counter += 1
            cursor = self.connection.cursor()
            self.cursors.append(cursor)
        self.current = cursor

        while sql.strip().endswith(';'):
            sql = sql.strip()[:-1]
        error_message = None
        with self.statistics as stt:
            try:
                if isinstance(parameters, (list, tuple)) and (len(parameters) > 0) and (
                        isinstance(parameters[0], (list, tuple, dict))):
                    stt.add_exec_count(len(parameters))
                    cursor.executemany(sql, [string2java_string(p) for p in parameters])
                else:
                    stt.add_exec_count()
                    if parameters is None:
                        cursor.execute(string2java_string(sql), None)
                    else:
                        cursor.execute(sql, string2java_string(parameters))
            except Exception as execute_exception:
                self.close(cursor)
                error_message = str(execute_exception)
                for prefix in ['java.sql.']:
                    if error_message.startswith(prefix):
                        error_message = error_message[len(prefix):]
            if error_message is not None:
                print(sql, file=sys.stderr)
                if isinstance(parameters, (list, tuple)):
                    print(parameters, file=sys.stderr)
                raise SQLExcecuteException(error_message)

        if not hasattr(cursor, PARENT_CONNECTION):
            # mark myself for column retrieval, see get_columns_of_cursor()
            setattr(cursor, PARENT_CONNECTION, self)
        return cursor

    @default_cursor(None)
    def get_cursor(self, cursor=None):
        """
        Get the current cursor if not specified. Return None if the provided cursor
        is either closed or not handled by the current instance
        @param cursor: Cursor - the cursor of interest
        @return: Cursor|None
        """
        return cursor

    @default_cursor([])
    def get_columns(self, cursor=None) -> OrderedDict:
        """
        Get the column associated to the cursor
        @param cursor: cursor to query. Current if not specified
        @return: OrderedDict of the defined columns:
         - key name of the column (in uppercase if self.upper_case=True)
         - value type of the column: one of the COLUMN_TYPE defined above
        """
        return get_columns_of_cursor(cursor)

    @default_cursor(None)
    def get_data(self, cursor: Cursor = None, return_type=tuple,
                 include_none=False, max_rows: int = 0, array_size: int = 1000):
        """
        An iterator using fetchmany to keep the memory usage reasonable
        @param cursor: Cursor to query, use current if not specified
        @param return_type: (optional) return type of the transformation. May be list, tuple (default), dict,
            OrderedDict (see collections), or a string ['int', 'float', 'bool', 'any']. The latter implies
            that only the first value of each row is returned and casted to the specified type.
        @param include_none: bool return None values in dictionaries, if True. Defaults to False
        @param max_rows: int maximum number of rows to return before closing the cursor. Negative or zero implies
            all rows
        @param array_size: int - the buffer size
        @return: iterator
        """
        if (not isinstance(array_size, int)) or array_size < 1:
            array_size = 1
        if (not isinstance(max_rows, int)) or max_rows < 0:
            max_rows = 0

        batch_nr = 0
        row_count = 0
        transformer = DataTransformer(cursor,
                                      return_type=return_type, upper_case=self.upper_case, include_none=include_none)
        while True:
            batch_nr += 1
            fetch_error = None
            results = []
            try:
                results = cursor.fetchmany(array_size)
            except Error as error:
                fetch_error = error

            if fetch_error is not None:
                print('Fetch error in batch {} of size {}.'.format(batch_nr, array_size), file=sys.stderr)
                error_msg = str(fetch_error)
                print(error_msg, file=sys.stderr)
                raise SQLExcecuteException('Failed to fetch data in batch {}: {}'.format(batch_nr, error_msg))

            if len(results) == 0:
                self.close(cursor)
                break
            for result in results:
                row_count += 1
                yield transformer(result)
                if (max_rows > 0) and (row_count >= max_rows):
                    self.close(cursor)
                    break

    @default_cursor([])
    def commit(self, cursor=None):
        commit_error = None
        with self.statistics as stt:
            for c in [cc for cc in self.cursors if cc.rowcount > 0]:
                stt.add_row_count(c.rowcount)
            if not self.auto_commit:
                try:
                    self.connection.commit()
                except DatabaseError as dbe:
                    commit_error = dbe
            self.close(cursor)
        if commit_error is not None:
            raise CommitException(str(commit_error))

    @default_cursor([])
    def rollback(self, cursor=None):
        if not self.auto_commit:
            self.connection.rollback()
        self.close(cursor)

    def query(self, sql: str, parameters=None, return_type=tuple, max_rows=0, array_size=1000):
        """
        Send an SQL to the database and return rows of results
        @param sql: str - single sql statement
        @param parameters: list - list of parameters specified in the SQL (defaults to None)
        @param return_type: (optional) return type of the transformation. May be list, tuple (default), dict,
            OrderedDict (see collections), or a string ['int', 'float', 'bool', 'any']. The latter implies
            that only the first value of each row is returned and casted to the specified type.
        @param max_rows: maximum number of rows to return. Zero or negative imply all
        @param array_size: batch size for which results are buffered when retrieving from the database
        @return: iterator of the specified return type, or the return type if max_rows=1
        """
        cur = self.execute(sql, parameters, cursor=None)
        if cur.rowcount >= 0:
            raise ValueError('The provided SQL is for updates, not to query. Use Execute method instead.')
        return self.get_data(cur, return_type=return_type, include_none=False, max_rows=max_rows, array_size=array_size)

    def query_single(self, sql: str, parameters=None, return_type=tuple) -> (tuple, list, dict, OrderedDict):
        """
        Send an SQL to the database and only return the first row.

        @param sql: str - single sql statement
        @param parameters: list - list of parameters specified in the SQL (defaults to None)
        @param return_type: (optional) return type of the transformation. May be list, tuple (default), dict,
            OrderedDict (see collections), or a string ['int', 'float', 'bool', 'any']. The latter implies
            that only the first value of each row is returned and casted to the specified type.
        @return: first row of the specified return type
        """
        result = None
        for r in self.query(sql, parameters=parameters, return_type=return_type, max_rows=1):
            result = r
            break
        return result

    def query_single_value(self, sql: str, parameters=None):
        result = self.query_single(sql, parameters, tuple)
        if len(result) > 0:
            return result[0]
        else:
            return None

    def get_int(self, sql: str, parameters=None):
        value = self.query_single_value(sql, parameters)
        if value is None:
            return 0
        elif isinstance(value, int):
            return value
        else:
            return int(value)

    def get_statistics(self, tag=None) -> str:
        """
        Return the query time of this instance as a string
        @return: query time of this instance as hh:mm:ss
        """
        if tag is None:
            tag = self.login
        return self.statistics.get_statistics(tag)
