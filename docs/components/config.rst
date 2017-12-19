The configuration file (config.yml)
***********************************

Locations
=========

The configuration-file (``config.yml``) may be stored at the following locations:

1. in the root of the module (always present),
2. for Linux systems in the system directory ``/etc/lwetl/config.yml``,
3. in the user-home directory ``$HOME/.lwetl/config.yml`` (auto-created),
4. in the current directory

Upon invocation the program scans the locations in the order given above, and identical definitions are successively overwritten.

Format
======

The configuration must in yaml_ markup format and may contain any of the following sections:

env:
  a section to specify or change system environment variables

drivers:
  to specify the used jdbc drivers and their configuration

servers:
  to specify database servers and the database schemes (instances)

alias:
  containing access credentials and references to database servers, which were specified in the ``servers`` section.

**Note:** access credentials in the alias section are stored in plain text. If security is an issue, make sure that the configuration file is properly read-protected. Alternatively this section can be skipped and access credentials may be entered in the appropriate methods.

Example
=======

::

    # user defined environment variables
    env:
        ORACLE_HOME:   /usr/lib/oracle/12.1/client64
        TNS:           /usr/lib/oracle/12.1/client64/network/admin/tnsnames.ora

    # jdbc drivers identified by a type (used as type in the next section)
    #
    # required parameters:
    # - jar:    url to download the jdbc jar file if not found on the module library
    #           may either be an url or a fixed reference to a file on the file-system
    # - class:  name of the class to use in the jar file
    # - url:    start of the connection url, will be extended with the url defined in the section 'servers'
    #
    # optional parameters:
    # - attr:   additional attributes to add at the end of the generated connection url
    # - escape: boolean - if set to true, all column names will be escaped in the uploader routines. Permits the
    #           use of reserved words as column names.
    #           WARNING: not implemented for postgresql
    #
    # WARNING: the strings used to define the driver types below are also used in the python code and should not be changed.
    drivers:
        sqlserver:
            # binary upload for jtds driver not supported
            jar:   'http://central.maven.org/maven2/com/microsoft/sqlserver/mssql-jdbc/6.3.5.jre8-preview/mssql-jdbc-6.3.5.jre8-preview.jar'
            class: 'com.microsoft.sqlserver.jdbc.SQLServerDriver'
            url:   'jdbc:sqlserver://'

        mysql:
            jar:   'http://central.maven.org/maven2/mysql/mysql-connector-java/5.1.39/mysql-connector-java-5.1.39.jar'
            class: 'com.mysql.jdbc.Driver'
            url:   'jdbc:mysql://'
            attr:  '?autoReconnect=true&useSSL=false'
            escape: true

        oracle:
            jar:   'https://maven.atlassian.com/3rdparty/com/oracle/ojdbc6/12.1.0.1-atlassian-hosted/ojdbc6-12.1.0.1-atlassian-hosted.jar'
            class: 'oracle.jdbc.OracleDriver'
            url:   'jdbc:oracle:thin:@'

        postgresql:
            # jar:   'http://central.maven.org/maven2/org/postgresql/postgresql/42.1.4.jre7/postgresql-42.1.4.jre7.jar'
            jar:   'https://maven.atlassian.com/3rdparty/postgresql/postgresql/9.4.1208-jdbc42-atlassian-hosted/postgresql-9.4.1208-jdbc42-atlassian-hosted.jar'
            class: 'org.postgresql.Driver'
            url:   'jdbc:postgresql://'

    # servers
    # defines database servers on the schema (instance) level
    #
    # required parameters:
    # - type - must be one of the types defined in drivers
    # - url  - connection url. The complete url is <url_driver><url server><attr driver>
    #
    # NOTE: for ORACLE additional server names may be obtained from the file tnsnames.ora
    servers:
        scott_mysql:
            type: mysql
            url:  "192.168.7.33:3306/scott"
        scott_postgresql:
            type: postgresql
            url:  "172.56.11.41:5432/scott"
        scott_sqlserver:
            type: sqlserver
            url:  '172.56.11.41\scott:1534'

    # alias for connections, in ORACLE credentials format
    # <username>/<password>@<servername>
    alias:
        scott_mysql:      "scott/tiger@scott_mysql"
        scott_postgresql: "scott/tiger@scott_postgresql"
        scott_sqlserver:  "scott/tiger@scott_sqlserver"
        scott_oracle:     "scott/tiger@scott_oracle"
        scot:             "scot/xxxxxxxx@tns_entry"


Sections
========

env - environment
-----------------

Function:

- specify the jre/jdk for the jdbc drivers
- specify the location of ORACLE configurations

By default this section is empty.

**Example**

::

    env:
        # Windows
        JAVA_HOME:     'C:\Progra~1\Java\jre1.8.0_65'
        ORACLE_HOME:   'C:\Oracle\product\11.2.0'
        # Linux
        TNS:           /usr/lib/oracle/12.1/client64/network/admin/tnsnames.ora

**Note 1:**
  if only ORACLE_HOME is specified, the program will search for the file ``$ORACLE_HOME/network/admin/tnsnames.ora``. If also TNS is specified, the program will first look at the location specified by ``$TNS``. Only if this section is not found, it will look at the previous location.

**Note 2:**
  On Windows 64-bit systems:

::

    Progra~1 = 'Program Files'
    Progra~2 = 'Program Files(x86)'

drivers - Jdbc driver definitions
---------------------------------

Function - associate a unique tag to a database server type:

- specify a source location of a jdbc jar file (url or file)
- specify the jdbc driver class of the jar file
- specify the base of the connection url

servers - Database server definitions
-------------------------------------

Function - associate a unique tag to a database connection:

- the driver driver used (see previous section)
- main connection URL specifying:
  - the IP address of the database server
  - the scheme/instance of the database 

alias - Connection aliases
--------------------------

Function:

- specify the jre/jdk for the jdbc drivers


.. _yaml: http://yaml.org/
