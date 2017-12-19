lwetl - Light Weigth Extraction Transform Load tool
***************************************************

The module `lwetl` is a light-weight database client to transfer data between various
databases, or inbetween tables of the same database.

It is intended as a administrative-, or development-tool to script quick modifications to
an existing database. It uses python 3 in combination with the
JayDeBeApi_  module and JDBC jar files.

Detailed documentation may be found on `read the docs`_.

Typical usage
=============
- extract data from a database, either through a command-line interface, or through python classes.
- upload table rows into a target database.
- transfer of (modified) data to files or pipes in common formats such as: text, csv, xml, xlsx, or sql.
- extract or upload binary data (not supported by all JDBC drivers).

Key features
============
- A centralized configuration file for database connections:
    - choice of the JDBC driver.
    - definitions of the JDBC connection URLs.
    - optionally parsing of ORACLE's `tnsnames.ora` for access through JDBC thin client.
    - optionally saving database access credentials as an alias.
- Direct command-line access to a database for upload and download.
- Command-line transfer of tables between independent database instances, possibly of a different server-type.
- Python classes for encapsulated transfer of data.

Due to its nature, the tool is suited for small- or medium-sized transformation-, import-, or
extraction-tasks (a throughput rate up to 4000 records per second).

Multi-threading of the database connection is not supported.

Requirements
============
- A python 3 environment with permission to install modules (system-wide or as virtual environment).
- A Java 1.7+ runtime environment
- Write-access to the user home-directory (a configuration directory $HOME/.lwetl is auto-created).

Status
======
This project is in a pre-alpha stage. It has been tested with drivers for mysql, sqlserver,
oracle, postgresql, and sqlite:

- Linux Mint (Ubuntu, Debian) with python 3.5.
- CentOS Linux (Redhat, Fedora) with python 3.4.
- Windows 10 Home with Anaconda_ python 3.6.

Examples
========

Transfer a table over an ssh pipe from oracle to mysql from the command prompt.

::

  sql-query -f sql -t mysql?NEW_TABLE 'scott/tiger@orasrv' "SELECT * FROM THE_TABLE ORDER BY ID" |
     ssh other_user@other_machine "cat > sql-query 'scott/tiger@local_mysql'"

Dump a table into a xlsx file.

::

  sql-query -f xlsx -o my_file.xlsx 'scott/tiger@orasrv' "SELECT * FROM THE_TABLE ORDER BY ID"

Read in xlsx file and insert the rows into a table.

::

  import sys

  from lwetl import Jdbc, XlsxImport, ParameterUploader, UPLOAD_MODE_COMMIT

  jdbc = Jdbc('scott/tiger@mysql_server')

  table = 'TARGET_TABLE'
  xls = XlsxImport()
  xls.open('mydata.xlsx')
  with ParameterUploader(jdbc,table, commit_mode=UPLOAD_MODE_COMMIT) as upl:
      for r in xls.get_data():
          upl.insert(r)
          if upl.rowcount > 1000:
              # commit every 1000 rows
              upl.commit()
      if upl.rowcount > 0:
          upl.commit()
  xls.close()


Calculate an md5 checksum of each row of a table

- read all rows from MY_TABLE, which contains the columns ID, AND HASH_VALUE
- for each row calculate a new md5 checksum based on the content of the row.
- the order of the elements is determined by the database

::

    from collections import OrderedDict
    from hashlib import md5
    from lwetl import Jdbc

    jdbc = Jdbc('scott/tiger@mysql_server')

    cursor = None
    for odict in jdbc.query("SELECT * FROM MY_TABLE ORDER BY ID",return_type=OrderedDict):
        odict['HASH_VALUE'] = None
        hash = md5(';'.join([str(v) for v in odict.values() if v is not None]).encode())
        cursor = jdbc.execute("UPDATE MY_TABLE SET HASH_VALUE = ? WHERE ID = ?",(hash.hexdigest(),odict['ID']),cursor=cursor)
        if cursor.rowcount >= 1000:
            # commit every 1000 rows
            jdbc.commit()
            cursor = None
    if cursor.rowcount > 0:
        jdbc.commit()

.. _JayDeBeApi: https://pypi.python.org/pypi/JayDeBeApi
.. _Anaconda: https://www.anaconda.com/download/#windows
.. _read the docs: http://lwetl.readthedocs.io/en/latest/index.html
