Import into a database
**********************

Import comes either as a sql import reader or as objects to read tablels of data.

SQL Import
==========

.. class:: InputParser(sql_or_filename_or_stream=None, sql_terminator:str=';'):

    Class to parse SQL input, either from file or from a stream (e.g., stdin)
    Assumes that all SQLs are terminated with an sql_terminator character
    (defaults to a semi-colon) at the end of a line.

    .. warning::
        This class may fail on multi-line string inputs that use the same character and the and of a CRLF.

    **Example:**

        .. code:: python

            import sys

            from lwetl Jdbc, InputParser

            jdbc = Jdbc('scott/tiger@osrv01')
            with InputParser(sys.stdin) as parser:
                for sql in parser.parse():
                    jdbc.execute(sql)


    .. function:: set_sql_terminator(sql_terminator):

        Specifies the SQL terminator.

    :arg str sql_terminator:

        The specified SQL terminator

    .. function:: open(sql_fn_stream=None):

        Opens a TextIOWrapper for input

        :arg TextIOWrapper sql_fn_stream:
            the stream to open

    .. function:: close():
        Closes the input stream


    .. function:: parse(array_size=1)->iterator:

        parses the input stream.

        :arg int array_size: buffer size of the iterator

        :returns:
            an iterator of SQL commands


Data Readers
============

.. class:: CsvImport(filename_or_stream=None, delimiter: str = "\t")

    Open a CSV file and extract data by row in the form of a dictionary
    Expects the first row if the dictionary to contain the column names.

    :arg filename_or_stream:
        if the argument is a string, the program will try to open the file with this name. For streams, it will
        use the stream as-is. Defaults to the stdin.

    :arg str delimiter:
        specifies the column delimiter of the CSV file. Defaulst to the TAB character.


    .. function:: open(filename_or_stream=None, delimiter: str = None)


        :arg filename_or_stream:

            specifies the input. If not specified, it takes the specifier when the class object was created.

        :arg str delimiter:

            specifies the column deliter. If not specified, it takes the delimiter specified when the object was
            created.

    .. function:: close():

            closes the input stream. Only has an effect, if the input was specified as a filename.

    .. function:: get_data(max_rows=1000)->iterator

        :arg int max_rows:

            retrieve the data as an generator/iterator. The parameter specifies the buffer size.


.. class:: XlsxImport(self, file_name: str, sheet_name: str = None)

    Open an xls worksheet and extract the data by row in the form of a dictionary
    Expects the first row of the worksheet to contain the column names

    .. function:: open(file_name: str = None, sheet_name: str = None):

    .. function:: close()

    .. function:: get_data(max_rows=1000)


Examples
--------

Import from the ``stdin`` in CSV format and upload in native query format (see next section).

.. code:: python

        import sys

        from lwetl import Jdbc, CsvImport, NativeUploader

        jdbc = Jdbc('scott')

        with NativeUploader(jdbc,'TARGET_TABLE', commit_mode=lwetl.UPLOAD_MODE_COMMIT) as upl:
            # read CSV from stdin
            with CsvImport(sys.stdin) as csv:
                for r in csv.get_data():
                    upl.insert(r)


Import from an excel 2007+ spreadsheet and upload using parameterized SQL syntax (see next section).

.. code:: python

        import sys

        from lwetl import Jdbc, XlsxImport, ParameterUploader

        jdbc = Jdbc('scott')

        table = 'TARGET_TABLE'
        # alternative to with statement
        xls = XlsxImport()
        xls.open(table + '.xlsx')
        with ParameterUploader(jdbc,table, commit_mode=lwetl.UPLOAD_MODE_COMMIT) as upl:
            for r in xls.get_data():
                upl.insert(r)
                if upl.rowcount > 1000:
                    upl.commit()
            if upl.rowcount > 0:
                upl.commit()
        xls.close()

Upload models
=============

.. _`Operational modes`:

Operational modes
-----------------

Import into a database has the following modes of operation:

UPLOAD_MODE_DRYRUN
    SQL statements are generated, but not send to the database.

UPLOAD_MODE_PIPE
    SQL statements are generated and piped for futher processing. The database itself is not touched.

UPLOAD_MODE_ROLLBACK
    SQL statements are generated and executed to the database. However, the commit statement performs
    a rollback instead.

    .. warning::
        This mode is not compatible with a database connection in auto-commit mode. It will also
        fail if the user sends commit commands independently.

UPLOAD_MODE_COMMIT
    SQL statements are generated and executed to the database. However, the commit statement performs
    a rollback instead.

Classes
-------

.. _NativeUploader:

.. class:: NativeUploader(jdbc: Jdbc, table: str, fstream=None, commit_mode=UPLOAD_MODE_DRYRUN, exit_on_fail=True)

    Upload data into a table with native SQL (no parameters in the jdbc execute command).

    :arg Jdbc jdbc:
        The target database connection

    :arg str table:
        Name of the table in the database to insert the data

    :arg fstream:

    :arg str commit_mode:
        The upload mode, see `Operational modes`_.

    :arg bool exit_on_fail:
        Clear the commit buffer and exit if an insert, update, or delete command fails.



    .. function:: insert(data: dict):

        Insert into the table

        :arg dict data:

            a dictionary of key (column name) and values. Keys, which do not correspond to an existing
            column names are ignored.


    .. function:: update(data: dict, where_clause):

        Update an existing row in the table

        :arg dict data:
            a dictionary of key (column name) and values. Keys, which do not correspond to an existing
            column names are ignored.

        :arg None,str,dict where_clause:

            filter for column selection. Valid formats for the where clause are:

            :class:`None`
                updates all columns.
            :class:`str`
                raw SQL WHERE clause (the keyword WHERE may be omitted).
            :class:`dict`
                keys are column names. Non exisiting column names are ignored. Multiple columns are combined
                with the AND statement. The value may be:

                - a value (results in COLUMN_NAME = VALUE)
                - a string with an operator and value, e.g.,  ``LIKE 'ABC%'``
                - a tuple (operator,value), e.g., ``('>=', 7)``


    .. function:: delete(where_clause):

        Delete rows in the table

        :arg None,str,dict where_clause:

            filter for the columns to delete. Formats are identical to the ``update`` statement.


    .. function:: commit()

        Processes previous insert/update/delete statements depending on the `Operational modes`_ of the instance.

        UPLOAD_MODE_COMMIT
            sends a commit statement to the database

        UPLOAD_MODE_ROLLBACK
            sends a rollback statement to the database

        UPLOAD_MODE_DRYRUN
            does nothing

        UPLOAD_MODE_PIPE
            work in progress

        .. warning::
            This mode is not compatible with a database connection in auto-commit mode. It will also
            fail if the user sends commit commands independently.


    .. function:: add_counter(columns: (str, list, set, tuple)):

        Mark columns as counters. Assumes the column type is a number.
        Queries the maximum number of each column and then adds the next value (+1) in the column on each insert.

        :arg str,list,set,tuple columns:

            names of the columns to add. May be a (comma-separated) string, or a list type.



.. class:: ParameterUploader(self, jdbc: Jdbc, table: str, fstream=None, commit_mode=UPLOAD_MODE_DRYRUN, exit_on_fail=True)

    Upload data into a table using parameterized SQL commands. See the section NativeUploader_ for details on the
    command line arguments.



    .. function:: insert(data: dict):

        Insert into the table, see the NativeUploader_ for details.


    .. function:: update(data: dict, where_clause):

        Update an existing row in the table, see the NativeUploader_ for details.


    .. function:: delete(where_clause):

        Delete existing rows from the table, see the NativeUploader_ for details.


    .. function:: commit()

        Processes previous insert/update/delete statements depending on the `Operational modes`_ of the instance.
        See the NativeUploader_ for details


    .. function:: add_counter(columns: (str, list, set, tuple)):

        Mark columns as counters. Assumes the column type is a number.
        Queries the maximum number of each column and then adds the next value (+1) in the column on each insert.
        See the NativeUploader_ for details


.. class:: MultiParameterUploader(jdbc: Jdbc, table: str, fstream=None, commit_mode=UPLOAD_MODE_DRYRUN, exit_on_fail=True)

    Upload data into a table using the jdbc executemany parameterized command.


    .. function:: insert(data: dict):

        Insert into the table, see the NativeUploader_ for details.


    .. function:: commit()

        Processes previous insert/update/delete statements depending on the `Operational modes`_ of the instance.
        See the NativeUploader_ for details

    .. function:: add_counter(columns: (str, list, set, tuple)):

        Mark columns as counters. Assumes the column type is a number.
        Queries the maximum number of each column and then adds the next value (+1) in the column on each insert.
        See the NativeUploader_ for details


