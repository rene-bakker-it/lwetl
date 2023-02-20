"""
    Functions to upload SQLs to a server

"""
import copy
import logging
import os
import sys

from collections import OrderedDict
from decimal import Decimal

from jaydebeapi import DatabaseError
from jpype import JPackage

from .exceptions import SQLExecuteException, CommitException
from .jdbc import Jdbc, DummyJdbc, COLUMN_TYPE_DATE, COLUMN_TYPE_FLOAT, COLUMN_TYPE_NUMBER
from .utils import *

# define a logger
LOGGER = logging.getLogger(os.path.basename(__file__).split('.')[0])

UPLOAD_MODE_DRYRUN = 'dryrun'
UPLOAD_MODE_PIPE = 'pipe'
UPLOAD_MODE_COMMIT = 'commit'
UPLOAD_MODE_ROLLBACK = 'rollback'

DEFAULT_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DEFAULT_TIME_FORMAT_MS = '%Y-%m-%d %H:%M:%S.%f'
DEFAULT_DATE_FORMAT = '%Y-%m-%d'

# PK_COUNTERS
# For update of integer primary keys without database IO
#
# Structure:
# login->table->column_name
#
PK_COUNTERS = dict()


def get_pk_counter(jdbc: (Jdbc, DummyJdbc), table_name: str, column_name: str, increment=1) -> int:
    """
    Internal factory to keep track of PK table counters over multiple Jdbc Instances

    @param jdbc: Jdbc - database connection, fines the database scheme
    @param table_name: str - name of the able
    @param column_name: str - name of the PK column
    @param increment: int - increment on call. Defaults to 1
    @return: int - the next value (incremented by increment)
    """

    global PK_COUNTERS
    login = jdbc.login
    if login not in PK_COUNTERS:
        PK_COUNTERS[login] = dict()
    if table_name not in PK_COUNTERS[login]:
        PK_COUNTERS[login][table_name] = dict()
    if column_name not in PK_COUNTERS[login][table_name]:
        PK_COUNTERS[login][table_name][column_name] = jdbc.get_int(
            "SELECT MAX({}) FROM {}".format(column_name, table_name))
    PK_COUNTERS[login][table_name][column_name] += increment
    return PK_COUNTERS[login][table_name][column_name]


class NativeExpression:
    """
    Class to store native SQL expressions as variable
    """

    def __init__(self, expression):
        self.expression = expression


class Uploader:
    """
    Base uploader class
    """

    def __init__(self, jdbc: Jdbc, table: str, fstream=None, commit_mode=UPLOAD_MODE_DRYRUN,
                 exit_on_fail=True, **kwargs):
        """
        Base uploader class
        @param jdbc: Jdbc - JDBC connection wrapper
        @param table: str - name of the destination table in the database

        """

        self.jdbc = jdbc
        self.cursor = None
        self.row_count = 0
        self.total_row_count = 0
        self.pipe_buffer = []

        self.table = table
        self.fstream = fstream
        self.commit_mode = self.set_commit_mode(commit_mode)
        self.exit_on_fail = exit_on_fail
        self.has_sql_errors = False

        # internal counter for integer primary keys
        self.counters = dict()

        # retrieve column names of the specified table
        self.columns = None
        error_message = None
        if ('columns' in kwargs) and (isinstance(kwargs['columns'], OrderedDict)):
            self.columns = copy.deepcopy(kwargs['columns'])
        else:
            try:
                c = jdbc.execute('SELECT * FROM {} WHERE 0=1'.format(table), None, cursor=None,
                                 use_current_cursor=False)
                self.columns = jdbc.get_columns(c)
                jdbc.close(c)
            except DatabaseError as db_error:
                error_message = str(db_error).strip() + ': ' + table

        if error_message is not None:
            raise SQLExecuteException(error_message)
        if self.columns is None:
            msg = 'Columns of table {} could not be retrieved.'.format(table)
            raise SQLExecuteException(msg)

    def __enter__(self):
        if self.row_count > 0:
            LOGGER.warning('WARNING: {} commands erased from {}.'.format(self.row_count, type(self).__name__))
            if self.commit_mode in [UPLOAD_MODE_COMMIT, UPLOAD_MODE_ROLLBACK]:
                self.jdbc.rollback()

        self.row_count = 0
        self.has_sql_errors = False
        self.pipe_buffer = []
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()

    def _insert_or_update(self, sql, parameters=None):
        """
        Internal function handling either an insert, or an update command
        @param sql: str - generated sql for insert or update
        @param parameters: list or None, associated parameters, if any
        """
        if self.commit_mode in [UPLOAD_MODE_COMMIT, UPLOAD_MODE_ROLLBACK]:
            exec_error = None
            try:
                self.cursor = self.jdbc.execute(sql, parameters, self.cursor, use_current_cursor=False)
                n = self.cursor.rowcount
                # except DatabaseError as db_error:
            except Exception as db_error:
                LOGGER.error(db_error)
                exec_error = db_error
                n = 0
            if self.exit_on_fail and (exec_error is not None):
                self.has_sql_errors = True
                raise SQLExecuteException('Insert command failed: ' + str(exec_error))
        elif self.commit_mode in [UPLOAD_MODE_DRYRUN, UPLOAD_MODE_PIPE]:
            n = 1
            if isinstance(parameters, list) and (len(parameters) > 0) and isinstance(parameters[0], list):
                n = len(parameters)
            if self.commit_mode == UPLOAD_MODE_PIPE:
                self.pipe_buffer.append((sql, parameters))
        else:
            supported_modes = [UPLOAD_MODE_COMMIT, UPLOAD_MODE_ROLLBACK, UPLOAD_MODE_DRYRUN, UPLOAD_MODE_PIPE]
            msg = 'Illegal mode. Supported: {}. Found: {}'.format(supported_modes, self.commit_mode)
            raise ValueError(msg)

        if n > 0:
            self.row_count += n
            self.total_row_count += n
        if self.fstream is not None:
            if parameters is not None:
                sql = '{} {}'.format(sql, str(parameters))
            print(sql + ";", file=self.fstream)

    @staticmethod
    def set_commit_mode(commit_mode):
        if isinstance(commit_mode, str) and (
                commit_mode.strip().lower() in [UPLOAD_MODE_DRYRUN, UPLOAD_MODE_COMMIT, UPLOAD_MODE_ROLLBACK,
                                                UPLOAD_MODE_PIPE]):
            return commit_mode.strip().lower()
        else:
            return UPLOAD_MODE_DRYRUN

    def add_counter(self, columns: (str, list, set, tuple)):
        """
        Mark columns as counters. Assumes the column type is a number.
        Queries the maximum number of each column and then adds the next value (+1) in the column on each insert.

        @param columns: columns to mark as a counter. May be a (comma-separated) string, a list, set, or a tuple
        """
        if isinstance(columns, str):
            if ',' in columns:
                columns = [c.strip() for c in columns.split(',')]
            else:
                columns = [columns]
        elif not isinstance(columns, (list, set, tuple)):
            raise ValueError('Method add_counter requires a string, tuple or list')

        for name in columns:
            name = name.upper()
            if name not in self.counters:
                self.counters[name] = get_pk_counter(self.jdbc, self.table, name, 0)

    @staticmethod
    def capitalize_keys(d: dict):
        """
        Sets all keys of the dictionary in upper case
        @param d: input dictionary
        @return: output dictionary with all keys in uppercase
        """
        result = {}
        for k, v in d.items():
            result[k.upper()] = v
        return result

    @staticmethod
    def _split_where_value(value, is_null):
        if is_empty(value):
            return is_null
        elif isinstance(value, str):
            if ' ' not in value:
                return '=', value
            else:
                slist = value.split()
                if slist[0].upper() in ['=', '<', '>', '<=', '>=', '<>', 'IS', 'LIKE', 'IN']:
                    operator = slist.pop(0)
                    return operator.upper(), ' '.join(slist)
                else:
                    return '=', value
        elif isinstance(value, (tuple, list, set)):
            n_elements = len(value)
            if n_elements == 0:
                return is_null
            elif n_elements == 1:
                return '=', value[0]
            else:
                return value[0], value[1]
        else:
            return '=', value

    def escape_column_names(self, column_names: list) -> list:
        if self.jdbc.always_escape:
            if self.jdbc.type == 'oracle':
                return ['"{0}"'.format(c) for c in column_names]
            elif self.jdbc.type == 'mysql':
                return ['`{0}`'.format(c) for c in column_names]
            elif self.jdbc.type == 'sqlserver':
                return ['[{0}]'.format(c) for c in column_names]
            else:
                return [c for c in column_names]
        else:
            return [c for c in column_names]

    def escape_column_name(self, column_name):
        return self.escape_column_names([column_name])[0]

    def commit(self):
        if self.row_count <= 0:
            return

        error = None
        if self.commit_mode in [UPLOAD_MODE_COMMIT, UPLOAD_MODE_ROLLBACK]:
            try:
                if (self.commit_mode == UPLOAD_MODE_COMMIT) and (not self.has_sql_errors):
                    self.jdbc.commit()
                else:
                    self.jdbc.rollback()
            except (SQLExecuteException, LookupError, CommitException) as commit_exception:
                error = commit_exception
        elif (self.commit_mode == UPLOAD_MODE_DRYRUN) and (self.fstream is not None):
            print('DRY-RUN COMMIT {} } rows.'.format(self.table, self.row_count), file=self.fstream)

        self.cursor = None
        self.row_count = 0
        if error is not None:
            msg = '{}: {}'.format(type(error).__name__, error)
            raise CommitException(msg)
        if self.commit_mode == UPLOAD_MODE_PIPE:
            buffer = [e for e in self.pipe_buffer]
            self.pipe_buffer = []
            return buffer


class NativeUploader(Uploader):
    """
        Upload data into a table with native SQL (no parameters in the jdbc execute command)
        Supports:
        - insert  - insert a new row
        - update  - update rows
        - delete  - delete rows

        Todo: implementation of defaults
    """

    def __init__(self, jdbc: Jdbc, table: str, fstream=None, commit_mode=UPLOAD_MODE_DRYRUN,
                 exit_on_fail=True,
                 **kwargs):
        super(NativeUploader, self).__init__(jdbc, table, fstream=fstream, commit_mode=commit_mode,
                                             exit_on_fail=exit_on_fail, **kwargs)
        # default values, if not present in the input row
        self.database_type = kwargs.get('type', jdbc.type)
        self.defaults = dict()

    def __enter__(self):
        return super(NativeUploader, self).__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        super(NativeUploader, self).__exit__(exc_type, exc_val, exc_tb)

    def _filter_data(self, data: dict, add_defaults: bool):
        """
        Filters the input data and only passes the columns present in the specified table (self.table)
        Default values and counters are added if: add_defaults is set to True, and the value is not
        specified in put input dictionary

        @param data: dict - input data. Keys specify the column name
        @param add_defaults: bool - activate adding default values and counters if set to True
        @return: dict - the filtered data
        """

        uc_data = self.capitalize_keys(data)
        column_names = list(uc_data.keys())

        dd = dict()
        if add_defaults:
            for column_name in [k for k in self.defaults.keys() if k not in column_names]:
                dd[column_name] = self.defaults[column_name]
        for column_name in [k for k in self.columns.keys() if k in uc_data]:
            value = uc_data[column_name]
            if (column_name in column_names) and (not is_empty(value)):
                if isinstance(value, NativeExpression):
                    dd[column_name] = value.expression
                elif self.columns[column_name] == 'number':
                    dd[column_name] = str(value)
                elif self.columns[column_name] == 'date':
                    dd[column_name] = self._convert_date(value)
                elif isinstance(value, str):
                    dd[column_name] = "'{0}'".format(value.replace("'", "''"))
                else:
                    dd[column_name] = "'{0}'".format(value)
        if add_defaults:
            for column_name in [k for k in self.counters.keys() if k not in dd]:
                self.counters[column_name] = get_pk_counter(self.jdbc, self.table, column_name)
                dd[column_name] = str(self.counters[column_name])
        return dd

    def _process_where_clause(self, where_clause):
        if is_empty(where_clause):
            where_data = ''
        elif isinstance(where_clause, dict):
            where_list = []
            for column_name, value in self._filter_data(where_clause, False).items():
                operator, value = self._split_where_value(value, ('IS', 'NULL'))
                where_list.append('{} {} {}'.format(column_name, operator, value))
            if len(where_list) == 0:
                where_data = ''
            else:
                where_data = 'WHERE ' + ' AND '.join(where_list)
        elif isinstance(where_clause, str):
            if where_clause.strip().upper().startswith('WHERE '):
                where_data = where_clause.strip()
            else:
                where_data = 'WHERE ' + where_clause.strip()
        else:
            raise ValueError('The where_clause is not a string or a dictionary.')
        return where_data

    def _convert_date(self, value):
        """
        Converts value into a date object, which may be used in an SQL
        @param value: str, time, or date object
        @return: native SQL representation of the date
        """
        if isinstance(value, str):
            pass
        elif isinstance(value, float):
            value = datetime.fromtimestamp(int(value)).strftime(DEFAULT_TIME_FORMAT)
        elif isinstance(value, datetime):
            value = value.strftime(DEFAULT_TIME_FORMAT_MS)
        else:
            raise ValueError('Value cannot be converted to a time object.')

        if RE_IS_DATE.match(value):
            value = value + ' 00:00:00'
        if RE_IS_DATE_TIME_MS.match(value):
            if self.database_type == 'oracle':
                return "TO_TIMESTAMP('{}','YYYY-MM-DD HH24:MI:SS.FF3')".format(value[:23])
            else:
                return "'{}'".format(value[:23] + '000')
        if RE_IS_DATE_TIME.match(value):
            if self.database_type == 'oracle':
                return "TO_DATE('{}','yyyy-mm-dd hh24:mi:ss')".format(value[:19])
            else:
                return "'{}'".format(value[:19])
        else:
            raise ValueError(
                'Value ({}) cannot be converted to a time object.'.format(value))

    def insert(self, data: dict):
        """
        Insert into the table
        @param data: dict of values, keys are the column name. Non-existing column names are ignored.
        """
        dd = self._filter_data(data, True)

        used_columns = []
        values = []
        for column_name in [k for k in self.columns.keys() if k in dd]:
            used_columns.append(column_name)
            values.append(dd[column_name])
        if len(used_columns) > 0:
            sql = 'INSERT INTO {0} ({1}) VALUES ({2})'.format(self.table,
                                                              ','.join(self.escape_column_names(used_columns)),
                                                              ','.join(values))
            self._insert_or_update(sql, None)

    def update(self, data: dict, where_clause):
        """
        Update an existing row in the table
        @param data: dict of values, keys are the column name. Non-existing column names are ignored.
        @param where_clause: None, str, or dict.
           - None - Updates all columns.
           - str  - RAW SQL WHERE clause (the keyword WHERE may be omitted).
           - dict - keys are column names. Non-existing column names are ignored. Multiple columns are
                    combined with the AND statement. The value may be:
                    - a raw value (results in COLUMN_NAME = VALUE)
                    - a string with an operator and value (e.g., LIKE 'ABC%')
                    - a tuple (operator,value)
        """
        insert_data = self._filter_data(data, False)
        if len(insert_data) == 0:
            return

        data_list = []
        for column_name, value in insert_data.items():
            data_list.append('{} = {}'.format(column_name, value))

        where_data = self._process_where_clause(where_clause)
        sql = 'UPDATE {} SET {} {}'.format(self.table, ', '.join(data_list), where_data)
        self._insert_or_update(sql, None)

    def delete(self, where_clause):
        """
        Delete rows in the table
        @param where_clause: None, str, or dict.
           - None - Updates all columns.
           - str  - RAW SQL WHERE clause (the keyword WHERE may be omitted).
           - dict - keys are column names. Non-existing column names are ignored. Multiple columns are
                    combined with the AND statement. The value may be:
                    - a raw value (results in COLUMN_NAME = VALUE)
                    - a string with an operator and value (e.g., LIKE 'ABC%')
                    - a tuple (operator,value)
        """
        where_data = self._process_where_clause(where_clause)
        sql = 'DELETE FROM {0} {1}'.format(self.table, where_data)
        self._insert_or_update(sql, None)

    def commit(self):
        buffer = super(NativeUploader, self).commit()
        if self.commit_mode == UPLOAD_MODE_PIPE:
            if buffer is None:
                return []
            else:
                return [el[0] for el in buffer]


class ParameterUploader(Uploader):
    """
        Upload data into a table using parameterized SQL commands
        Supports:
        - insert  - insert a new row
        - update  - update rows
        - delete  - delete rows
    """

    def __init__(self, jdbc: Jdbc, table: str,
                 fstream=None, commit_mode=UPLOAD_MODE_DRYRUN, exit_on_fail=True, **kwargs):
        super(ParameterUploader, self).__init__(jdbc, table, fstream=fstream, commit_mode=commit_mode,
                                                exit_on_fail=exit_on_fail, **kwargs)
        self.sqlDate = JPackage('java').sql.Timestamp

    def __enter__(self):
        return super(ParameterUploader, self).__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        super(ParameterUploader, self).__exit__(exc_type, exc_val, exc_tb)

    def _filter_data(self, data: dict, export_null=False):
        column_names = [k.upper() for k in data.keys()
                        if (k.upper() in self.columns) and k.upper()]

        data_dict = dict()
        null_list = list()
        for column_name, value in data.items():
            column_name = column_name.upper()
            if (column_name in column_names) and (not is_empty(value)):
                data_dict[column_name] = value
            else:
                null_list.append(column_name)
        if export_null:
            return data_dict, null_list
        else:
            return data_dict

    def _process_where_clause(self, where_clause):
        if is_empty(where_clause):
            where_data = None
        elif isinstance(where_clause, dict):
            where_data = self._filter_data(where_clause)
        else:
            raise ValueError('The where clause must either be emtpy or a dictionary')
        return where_data

    def _convert(self, column_name: str, value):
        """
        Convert a value into an object suited for the one associated to the column name
        @param column_name: str - name of the associated column
        @param value: value to convert
        @return: converted value
        """
        if isinstance(value, datetime):
            return self.sqlDate((int(value.strftime("%s"))*1000) + (value.microsecond // 1000))
        elif type(value).__name__ in ['bytes', 'bytearray']:
            error_msg = None
            try:
                blob = self.jdbc.connection.jconn.createBlob()
                blob.setBytes(1, value)
            except Exception as e:
                error_msg = str(e)
                blob = None
            if error_msg is not None:
                raise SQLExecuteException('Binary upload not supported by driver: ' + error_msg)
            return blob
        elif type(value).__name__ in ['int', 'float']:
            return value
        elif isinstance(value, str):
            if self.columns[column_name] == COLUMN_TYPE_DATE:
                if RE_IS_DATE_TIME_MS.match(value):
                    date = datetime.strptime(value[:23], DEFAULT_TIME_FORMAT_MS)
                elif RE_IS_DATE_TIME.match(value):
                    date = datetime.strptime(value[:19], DEFAULT_TIME_FORMAT)
                elif RE_IS_DATE.match(value):
                    date = datetime.strptime(value[:10], DEFAULT_DATE_FORMAT)
                else:
                    msg = 'Invalid time format. Must be {}. Found: ({})'.format(DEFAULT_TIME_FORMAT_MS, value)
                    raise ValueError(msg)
                return self.sqlDate((int(date.strftime("%s"))*1000) + (date.microsecond // 1000))
            elif self.columns[column_name] == COLUMN_TYPE_NUMBER:
                return int(value)
            elif self.columns[column_name] == COLUMN_TYPE_FLOAT:
                return Decimal(value)
            else:
                return value
        else:
            return str(value)

    def insert(self, data: dict):
        """
        Insert into the table
        @param data: dict of values, keys are the column name. Non-existing column names are ignored.
        """
        cols = []
        values = []
        dd = self._filter_data(data)
        for column_name in [k for k in self.columns.keys() if k in dd]:
            cols.append(column_name)
            values.append(self._convert(column_name, dd[column_name]))

        for column_name in [k for k in self.counters.keys() if k not in cols]:
            self.counters[column_name] = get_pk_counter(self.jdbc, self.table, column_name)
            cols.append(column_name)
            values.append(self.counters[column_name])

        if len(cols) > 0:
            sql = 'INSERT INTO {0} ({1}) VALUES ({2})'.format(
                self.table, ','.join(self.escape_column_names(cols)), ','.join(['?'] * len(values)))
            self._insert_or_update(sql, values)

    def update(self, data: dict, where_clause):
        """
        Update an existing row in the table
        @param data: dict of values, keys are the column name. Non-existing column names are ignored.
        @param where_clause: None, str, or dict.
           - None - Updates all columns.
           - dict - keys are column names. Non-existing column names are ignored. Multiple columns are
                    combined with the AND statement. The value may be:
                    - a raw value (results in COLUMN_NAME = VALUE)
                    - a string with an operator and value (e.g., LIKE 'ABC%')
                    - a tuple (operator,value)
        """
        update_data, null_list = self._filter_data(data, True)
        if (len(update_data) + len(null_list)) == 0:
            return

        values = []
        s_list = []
        w_list = []
        for column_name in [k for k in self.columns.keys() if k in update_data]:
            values.append(self._convert(column_name, update_data[column_name]))
            s_list.append('{} = ?'.format(self.escape_column_name(column_name)))
        for column_name in null_list:
            s_list.append('{} = NULL'.format(self.escape_column_name(column_name)))

        where_data = self._process_where_clause(where_clause)
        if where_data:
            for column_name in [k for k in self.columns.keys() if k in where_data]:
                operator, value = self._split_where_value(where_data[column_name], ('IS', None))
                values.append(self._convert(column_name, value))
                w_list.append('{} {} ?'.format(column_name, operator))
        if len(w_list) > 0:
            where_str = 'WHERE {}'.format(' AND '.join(w_list))
        else:
            where_str = ''
        sql = 'UPDATE {} SET {} {}'.format(self.table, ', '.join(s_list), where_str)
        self._insert_or_update(sql, values)

    def delete(self, where_clause):
        """
        Delete existing rows from the table
        @param where_clause: None, str, or dict.
           - None - Updates all columns.
           - dict - keys are column names. Non-existing column names are ignored. Multiple columns are
                    combined with the AND statement. The value may be:
                    - a raw value (results in COLUMN_NAME = VALUE)
                    - a string with an operator and value (e.g., LIKE 'ABC%')
                    - a tuple (operator,value)
        """

        values = []
        w_list = []
        where_data = self._process_where_clause(where_clause)
        if where_data:
            for column_name in [k for k in self.columns.keys() if k in where_data]:
                operator, value = self._split_where_value(where_data[column_name], ('IS', None))
                values.append(self._convert(column_name, value))
                w_list.append('{} {} ?'.format(column_name, operator))
        if len(w_list) > 0:
            where_str = 'WHERE {}'.format(' AND '.join(w_list))
        else:
            where_str = ''
            values = None
        sql = 'DELETE FROM {} {}'.format(self.table, where_str)
        self._insert_or_update(sql, values)

    def commit(self):
        buffer = super(ParameterUploader, self).commit()
        if self.commit_mode == UPLOAD_MODE_PIPE:
            return buffer


class MultiParameterUploader(ParameterUploader):
    """
        Upload data into a table using the jdbc executemany parameterized command.
        Supports:
        - insert
    """

    def __init__(self, jdbc: Jdbc, table: str, fstream=None, commit_mode=UPLOAD_MODE_DRYRUN,
                 exit_on_fail=True, **kwargs):
        super(MultiParameterUploader, self).__init__(jdbc, table, fstream=fstream, commit_mode=commit_mode,
                                                     exit_on_fail=exit_on_fail, **kwargs)
        self.data_buffer = []
        self.used_keys = []
        if self.commit_mode == UPLOAD_MODE_PIPE:
            msg = "Commit mode '{}' not allowed for this class.".format(self.commit_mode)
            raise ValueError(msg)

    def __enter__(self):
        super(MultiParameterUploader, self).__enter__()
        self.data_buffer = []
        self.used_keys = []
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super(MultiParameterUploader, self).__exit__(exc_type, exc_val, exc_tb)

    def insert(self, data: dict):
        dd = dict()
        for column_name, value in self._filter_data(data).items():
            dd[column_name] = self._convert(column_name, value)
        for column_name in [k for k in self.counters if k not in dd]:
            dd[column_name] = get_pk_counter(self.jdbc, self.table, column_name)
        if len(dd) > 0:
            self.used_keys += [k for k in dd.keys() if k not in self.used_keys]
            self.data_buffer.append(dd)
            self.row_count += 1

    def commit(self):
        if len(self.data_buffer) == 0:
            return

        keys = [k for k in self.columns.keys() if k in self.used_keys]
        parameters = []
        for data in self.data_buffer:
            values = []
            for column_name in keys:
                values.append(data.get(column_name, None))
            parameters.append(values)

        sql = 'INSERT INTO {0} ({1}) VALUES ({2})'.format(self.table, ','.join(self.escape_column_names(keys)),
                                                          ','.join(['?'] * len(keys)))
        self._insert_or_update(sql, parameters)
        self.data_buffer = []
        self.used_keys = []
        super(ParameterUploader, self).commit()
