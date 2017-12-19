"""
    Table importer classes to extract dictionaries from eithr a CSV file, or and xls worksheet
"""

import os
import re
import sys

from csv import reader
from openpyxl import load_workbook

from .exceptions import EmptyFileError
from .utils import is_empty

RE_START_WITH_CHAR = re.compile('^[A-Z_].*')


def get_xls_row_values(row):
    return [cell.value for cell in row]


def unique_column_name(name, defined_columns: list) -> str:
    """
    Makes sure column names are unique in upper case
    @param name: str|None - suggested name
    @param defined_columns: list of defined columns
    @return: str - modified suggested names (upper case + counter, if required)
    @rtype: str
    """
    if is_empty(name):
        name = 'C%d' % (len(defined_columns) + 1)
    else:
        if not isinstance(name, str):
            name = str(name)
        name = name.strip().upper()
        if RE_START_WITH_CHAR.match(name) is None:
            name = 'C%d' % (len(defined_columns) + 1)

    x = 0
    v = name
    while v in defined_columns:
        x += 1
        v = '%s%d' % (name, x)
    return name


class CsvImport:
    """
    Open a CSV file and extract data by row in the form of a dictionary
    Expects the first row if the dictionary to contain the column names
    """

    def __init__(self, filename_or_stream=None, delimiter: str = "\t"):
        self.fname = None
        self.fstream = None
        self.csv = None
        self._check_input_type(filename_or_stream)

        self.delimiter = self._check_delimiter(delimiter)
        self.columns = None
        self.n_columns = 0
        self.row_count = 0

    def _check_input_type(self, filename_or_stream):
        if is_empty(filename_or_stream):
            self.fstream = sys.stdin
            self.fname = None
        elif isinstance(filename_or_stream, str):
            self.fname = filename_or_stream
            self.fstream = None
        elif type(filename_or_stream).__name__ in ['TextIOWrapper', 'StringIO', 'EncodedFile']:
            self.fname = None
            self.fstream = filename_or_stream
        else:
            raise ValueError('The input specifier must be a string (filename) or stream. Found: ' +
                             type(filename_or_stream).__name__)

    @staticmethod
    def _check_delimiter(delimiter):
        if is_empty(delimiter):
            delimiter = "\t"
        elif not isinstance(delimiter, str):
            raise ValueError('The delimiter specifier must be a string. Found: ' + type(delimiter).__name__)
        return delimiter

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self, filename_or_stream=None, delimiter: str = None):
        if filename_or_stream is not None:
            self._check_input_type(filename_or_stream)
        if self.fname is not None:
            if os.path.isfile(self.fname):
                self.fstream = open(self.fname, 'r')
            else:
                raise FileNotFoundError("No such file: '%s'" % self.fname)
        elif self.fstream is None:
            self.fstream = sys.stdin

        if delimiter is not None:
            delimiter = self._check_delimiter(delimiter)
        else:
            delimiter = self.delimiter
        self.csv = reader(self.fstream, delimiter=delimiter)

        self.row_count = 0
        for row in self.csv:
            self.row_count += 1
            self.columns = []
            for value in row:
                self.columns.append(unique_column_name(value, self.columns))
            break

        if self.columns is None:
            if self.fname is None:
                input_spec = 'input stream'
            else:
                input_spec = self.fname
            raise EmptyFileError("No data found for: '%s'" % input_spec)
        else:
            self.n_columns = len(self.columns)
            self.row_count += 1

        return self

    def close(self):
        if self.csv is not None:
            self.csv = None
        if self.fname is not None:
            self.fstream.close()
            self.fstream = None
        self.columns = None
        self.n_columns = 0
        self.row_count = 0

    def get_data(self, max_rows=1000):
        if self.csv is None:
            raise ValueError('I/O operation on a closed CSV reader.')
        if (not isinstance(max_rows, int)) or (max_rows < 1):
            max_rows = 1000

        while True:
            rows = []
            for row in self.csv:
                rows.append(row)
                if len(rows) >= max_rows:
                    break

            for row in rows:
                self.row_count += 1
                dd = dict()
                indx = 0
                for value in row:
                    if indx < self.n_columns:
                        key = self.columns[indx]
                    elif not is_empty(value):
                        key = unique_column_name(None, self.columns)
                        self.columns.append(key)
                        self.n_columns += 1
                    indx += 1
                    if is_empty(value):
                        continue
                    dd[key] = value
                if len(dd) > 0:
                    yield dd
            if len(rows) < max_rows:
                break


class XlsxImport:
    """
    Open an xls worksheet and extract the data by row in the form of a dictionary
    Expects the first row of the worksheet to contain the column names
    """

    def __init__(self, file_name: str, sheet_name: str = None):
        self.file_name = file_name
        self.sheet_name = sheet_name
        self.work_book = None
        self.work_sheet = None
        self.columns = None
        self.n_columns = 0
        self.row_count = 0

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self, file_name: str = None, sheet_name: str = None):
        if file_name is None:
            file_name = self.file_name
        if file_name is None:
            raise ValueError('Input filename not specified')
        elif not isinstance(file_name, str):
            raise TypeError('Filename specifier of wrong type: ' + type(file_name).__name__)
        if not os.path.isfile(file_name):
            raise FileNotFoundError("No such file: '%s'" % file_name)

        self.work_book = load_workbook(file_name, read_only=True, data_only=True)

        sheet_names = self.work_book.get_sheet_names()
        if len(sheet_names) == 0:
            raise EmptyFileError("Workbook '%s' has no data." % file_name)

        self.work_sheet = None
        if sheet_name is None:
            sheet_name = self.sheet_name
        if is_empty(sheet_name):
            sheet_name = None

        if sheet_name is None:
            self.work_sheet = self.work_book.get_sheet_by_name(sheet_names[0])
        elif isinstance(sheet_name, str):
            valid_sheets = [n for n in sheet_names if n.upper() == sheet_name.upper()]
            if len(valid_sheets) > 0:
                self.work_sheet = self.work_book.get_sheet_by_name(valid_sheets[0])
        else:
            raise ValueError('Sheet name must be string. Found: ' + type(sheet_name).__name__)

        if self.work_sheet is None:
            raise LookupError("Cannot find work sheet: '%s'" % sheet_name)
        self.row_count = 0
        for row in self.work_sheet.rows:
            self.columns = []
            for v in get_xls_row_values(row):
                self.columns.append(unique_column_name(v, self.columns))
            self.n_columns = len(self.columns)
            self.row_count += 1
            break
        if self.columns is None:
            raise EmptyFileError("Worksheet '%s' has no data." % sheet_name)
        return self

    def close(self):
        self.work_book = None
        self.work_sheet = None
        self.columns = None
        self.n_columns = 0
        self.row_count = 0

    def get_data(self, max_rows=1000):
        if self.work_sheet is None:
            raise LookupError('No active worksheet for data.')
        if (not isinstance(max_rows, int)) or (max_rows < 1):
            max_rows = 1000

        while True:
            rows = []
            n = self.row_count + 1
            for row in self.work_sheet.iter_rows(min_row=n, max_row=n + max_rows):
                rows.append(row)
            for row in rows:
                self.row_count += 1

                dd = dict()
                indx = 0
                for value in get_xls_row_values(row):
                    if indx < self.n_columns:
                        key = self.columns[indx]
                    else:
                        key = 'C%d' % indx
                    indx += 1
                    if is_empty(value):
                        continue
                    dd[key] = value
                if len(dd) > 0:
                    yield dd
            if len(rows) < max_rows:
                break
