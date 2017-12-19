Introduction
************

The module `lwetl` is a light-weight database client to transfer data between various
databases, or inbetween tables of the same database.

It is intended as a administrative-, or development-tool to script quick modifications to
an existing database. It uses python 3 in combination with the
JayDeBeApi_  module and JDBC jar files.

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
This project is in a pre-pre-alpha stage. It has been tested with drivers for mysql, sqlserver,
oracle, postgresql, and sqlite:

- Linux Mint (Ubuntu, Debian) with python 3.5.
- CentOS Linux (Redhat, Fedora) with python 3.4.
- Windows 10 Home with Anaconda_ python 3.6.

.. warning::

    some database serves (e.g., MySQL) may make a distincion between upper-case and
    lower-case table-names and/or column-names. This might cause errors, since all current tests have
    been performed in environments where such a distinction does not exist.

.. _JayDeBeApi: https://pypi.python.org/pypi/JayDeBeApi
.. _Anaconda: https://www.anaconda.com/download/#windows
