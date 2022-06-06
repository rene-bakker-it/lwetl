"""
    Input parsing input, either from a stream or a file
    See class InputParser for details
"""

import io
import os
import sys


class InputParser:
    """
    Class to parse SQL input, either from file or from a stream (e.g., stdin)
    Assumes that all SQLs are terminated with a sql_terminator character
    (defaults to a semicolon) at the end of a line.

    WARNING: may fail on multi-line string inputs that use the same character
    and the and of a CRLF.
    """

    def __init__(self, sql_or_filename_or_stream=None, sql_terminator: str = ';'):
        """
        Instantiator
        @param sql_or_filename_or_stream: str|streamType|None - the input source to use. Defaults to sys.stdin
        @param sql_terminator: str the terminator for an SQL command (must be at the end of a line). Defaults
                               to a semi-colon (;)
        """
        self.sql_or_filename_or_stream = sql_or_filename_or_stream
        if not isinstance(sql_terminator, str):
            sql_terminator = ";"
        self.sql_terminator = sql_terminator
        self.sql_terminator_length = len(sql_terminator)
        self.fstream = None
        self.fname = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def set_sql_terminator(self, sql_terminator):
        if sql_terminator is None:
            sql_terminator = ";"
        self.sql_terminator = sql_terminator
        self.sql_terminator_length = len(sql_terminator)

    def open(self, sql_fn_stream=None):
        """
        Opens a TextIOWraper for input
        @param sql_fn_stream: None|str|TextIOWrapper
        @return: self
        """

        if sql_fn_stream is None:
            sql_fn_stream = self.sql_or_filename_or_stream
        if sql_fn_stream is None:
            self.fstream = sys.stdin
            self.fname = None
        elif isinstance(sql_fn_stream, str):
            if os.path.isfile(sql_fn_stream):
                self.fstream = open(sql_fn_stream, "r")
                self.fname = sql_fn_stream
            else:
                self.fstream = io.StringIO(sql_fn_stream)
                self.fname = None
        elif type(sql_fn_stream).__name__ == 'TextIOWrapper':
            self.fstream = sql_fn_stream
            self.fname = None
        else:
            raise ValueError('Illegal type for input specifier: ' + type(sql_fn_stream).__name__)
        return self

    def close(self):
        if (self.fname is not None) and (self.fstream is not None):
            self.fstream.close()
            self.fstream = None
            self.fname = None

    def parse(self, array_size=1):
        def add_sql(lst, res):
            sql = "\n".join(lst).strip()
            if len(sql) > 0:
                res.append(sql)

        if array_size < 1:
            array_size = 1

        results = []
        lines = []
        while self.fstream is not None:
            line = self.fstream.readline()
            if line:
                line = line.rstrip('\n\r')
                if line.rstrip().endswith(self.sql_terminator):
                    line = line.rstrip()[:-self.sql_terminator_length]
                    lines.append(line)
                    add_sql(lines, results)
                    lines = []
                    if len(results) >= array_size:
                        for result in results:
                            yield result
                        results = []
                else:
                    lines.append(line)
            else:
                if len(lines) > 0:
                    add_sql(lines, results)
                for result in results:
                    yield result
                break
