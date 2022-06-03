The main connection
*******************

The class ``Jdbc`` creates a connection to a database, which remains open until the object isdestroyed.


.. Class:: Jdbc(login, auto_commit=False, upper_case=True)

    Creates a connection. :exc:`Raises` an exception if the connection fails, see the example below.

    :arg str login:
        login alias defined in ``config.yml``, or authentication credentials like:

        username/password@service

        The parser assumes that the name of the service does not contain the '@' character. The password should
        not contain a '/'.

    :arg bool auto_commit bool:
        specifies the auto-commit mode of the connection at startup. Defaults to False (auto-commit disabled).

    :arg bool upper_case:
        specifies if the column names of SQL queries are converted into upper-case. Convenient if the result of
        queries is converted into dictionaries.

    **Example:**

    .. code:: python

        from lwetl import Jdbc, ServiceNotFoundException, DriverNotFoundException

        # create a connection to 'scott' with password 'tiger' to oracle server 'osrv1'
        # (as defined in tnsnames.ora)

        try:
            jdbc = Jdbc('scott/tiger@osrv01')
        except (ServiceNotFoundException, DriverNotFoundException) as nfe:
            print('ERROR - could initialize: ' + str(nfe))
        except ConnectionError as ce:
            print('ERROR - failed to connect: ' + str(ce))


    .. py:attribute:: connection

        The connection to the database as returned by ``jaydebeapi.connect``. See PEP249_  for further details.


    .. function:: execute(sql: str, parameters: (list, tuple) = None, cursor: object = None) -> Cursor

        Execute a query, optionally with list of parameters, or a list of a list of parameters. :exc:`Raises` an
        `SQLExecutionException` if the query fails, see the example below.

        :arg str sql:
            query to execute

        :arg tuple,list,None parameters:
            parameters specified in the sql query. May also be None (no parameters), or a list of lists

        :arg Cursor,None cursor:
            the cursor to use for exection. Create a new one if None (default), or if the cursor is not an open cursor
            associated to the current connection

        :returns:
            a  :class:`jaydebeapi.connect.Cursor` for further processing.

        **Example:**

        .. code:: python

            from lwetl import Jdbc, SqlExecutionException

            jdbc = Jdbc('scott/tiger@osrv01')

            try:
                cur = jdbc.execte("INSERT INTO TST_NAMES (ID, USERNAME) VALUES (17,'scott')")
            except SQLExectionException as sqle:
                print('ERROR - could not execute: ' + str(sqle))


    .. function:: close(cursor=None):

        Closes the specified cursor. Use the current if not specified. Cursors which are aleady closed, or are not
        associated to the jdbc conection are silently ignored.


    .. function:: get_columns(cursor=None) -> OrderedDict:

        :arg Cursor cursor:
            the cursor to query. Uses the last used (current) cursor, if not specified.

        :returns:
            the column associated to the cursor as an OrderedDict, or an empty dictionary if no columns were found.


    .. function:: commit(cursor=None):

        Commits pending modifications of the specified cursor to the database. If not specified, the current corsor
        is assumed.

        :arg Cursor cursor:
            the cursor to query. Uses the last used (current) cursor, if not specified.

        .. warning:: This may also commit pending modifications of other cursors associated to the connection.


    .. function:: rollback(cursor=None):

        Rolls back pending modifications of the specified cursor to the database. If not specified, the current
        corsor is assumed.

        :arg Cursor cursor:
            the cursor to query. Uses the last used (current) cursor, if not specified.

        .. warning:: This may also commit pending modifications of other cursors associated to the connection.


    .. function:: get_data(cursor: Cursor = None, return_type=tuple, include_none=False, max_rows: int = 0, array_size: int = 1000)-> iterator:

        Get the data retrieved from a :func:`execute()` command.

        :arg Cursor cursor:
            cursor to query, use current if not specified

        :arg Any return_type:
            the return type of the method. Defaults to :class:`tuple`. Other valid options are :class:`list`,
            :class:`dict`, :class:`OrderedDict`, or a (tuple of) stings.
            In case of the latter, the output is casted to the specified types. Supported types are :class:`Any`
            (no casting), :class:`str`, :class:`int`, :class:`bool`, :class:`float`, :class:`date`,
            or a format string compatible with :class:'datetime.strptime()'. The format string for 'date' is
            '%Y-%m-%d [%H:%M:%S]'. If a single string is specified, the returned row will only be the first value of
            each row. Otherwise the output is a tuple of values with a maximum length of the specified input tuple.
            This option is particularly useful for connections to a sqlite, where the auto-casting casting of the types
            in the jdbc driver may fail.

        :arg bool include_none:
            if set to :data:`True`, also returns :class:`None` values in dictionaries. Defaults to :data:`False`. For
            :class:`tuple`, or :class:`list`, all elements are always returned.

        :arg int max_rows:
            maximum number of rows to return before closing the cursor. Negative or zero implies all rows

        :arg int array_size:
            the buffer size to retrieve batches of data.

        :returns:
            an iterator with rows of data obtained from an SQL with the data-type specified with the `return_type`
            parameter.


    .. function:: query(sql: str, parameters=None, return_type=tuple, max_rows=0, array_size=1000)->iterator:

        Combines the :func:`execute()` and :func:`get_data()` into a single statement.


    .. function:: query_single(sql: str, parameters=None, return_type=tuple) -> (tuple, list, dict, OrderedDict):

        :returns:
            only the first row from :func:`query()`


    .. function:: query_single_value(sql: str, parameters=None):

        :returns:
            the first column from :func:`query_single()`

    .. function:: get_int(sql: str, parameters=None):

        A short-cut for::

            int(query_single_value(sql, parameters))

Exceptions
==========

.. class:: SQLExcecuteException

Raised when an :func:`execute()` command cannot be parsed.

.. class:: ServiceNotFoundException

Raised when a database connection cannot be reach the database server.

.. class:: DriverNotFoundException

Raised when the jdbc driver, associated to the database connection, cannot be retrieved.

.. class:: CommitException

Raised when a :func:`commit()` command fails.


Utility functions and classes
=============================


.. class:: JdbcInfo(login: str)

    Displays parameter information of the jdbc driver.

    :arg str login:
        login alias defined in ``config.yml``, or authentication credentials.

**Example:**

.. code:: python

    from lwetl JdbcInfo

    jdbc_info = JdbcInfo('scott')
    jdbc_info()


.. function:: get_execution_statistics()->str

    Retrieves some timing statistics on the established connections.

    :rtype: multi-line string


.. function:: tag_connection(tag:str, jdbc:Jdbc)

    Marks specific connections, such that the function :func:`get_execution_statistics()` provides more detail.

    :arg str tag:
        a tag for a connection

    :arg Jdbc jdbc:
        an established database connection

    **Example:**

    .. code:: python

        from import Jdbc, get_execution_statistics, tag_connection

        jdbc = {
            'SRC': Jdbc('scott_source'),
            'TRG': Jdbc('scott_target')
        }
        for tag, con in jdbc.items():
            tag_connection(tag,con)

        # do lots of work

        print(get_execution_statistics())

    .. _PEP249: https://www.python.org/dev/peps/pep-0249/