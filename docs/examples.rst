Examples and use
****************

General
=======

Make sure the java JRE (or JDK) are known to the system. If this is not the case, add ``JAVA_HOME`` to the system environemnt, or specify it in the ``env`` section of hte configuration file (see below).

If successful the command `sql-query list` should run without errors. You may see messages like:

::

    INFO: ojdbc6-12.1.0.1-atlassian-hosted.jar downloaded to: ./jdbc/lib/python3.4/site-packages/lib
    INFO: postgresql-9.4.1208-jdbc42-atlassian-hosted.jar downloaded to: ./jdbc/lib/python3.4/site-packages/lib
    INFO: sqlite-jdbc-3.21.0.jar downloaded to: ./jdbc/lib/python3.4/site-packages/lib
    INFO: mysql-connector-java-5.1.39.jar downloaded to: ./jdbc/lib/python3.4/site-packages/lib
    INFO: mssql-jdbc-6.3.5.jre8-preview.jar downloaded to: ./jdbc/lib/python3.4/site-packages/lib

These are downloads, which typically take place once only. The origin of these file may be found in:

::

    $HOME/.lwetl/config-example.yml

To connect to a database, server definitions must be added to the YAML file ``$HOME/.lwetl/config.yml``, see the file ``$HOME/.lwetl/config-example.yml`` for some examples.

Invocation from the command-line
================================

A correctly configured connection may then be used like:

::

    sql-query <username/password@server> "SQL statement"

or with a configured alias:

::

    sql-query <alias> "SQL statement"

Implemented command line options are (use the -h option for help):

sql-query
  as a general purpose command-line sql parser, up-loader, or down-loader.

db-copy
  to quickly copy entire tables between database instances.

table-cardinality
  to dump cardinality data of a table into an xlsx spreadsheet.

Alternatively they may be invoced as a module, for example:

::

      python -m lwetl.programs.sql_query.main


Invocation inside python
========================

The repository directory ``examples`` is intended for a collection of simple example scripts. The module directories ``lwetl/programs`` provides more advanced examples.

An example to dump binary images from the database into the current directory:

::

    from lwetl import Jdbc

    jdbc = Jdbc('login alias')
    for fname, img in jdbc.query("SELECT file_name, image_field FROM MY_TABLE"):
        with open(fname,'wb') as f:
            f.write(img)
