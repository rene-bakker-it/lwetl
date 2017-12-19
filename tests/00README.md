# Tests

Tests are run with the user `scott` and the password `tiger`. The test script assumes the presence
of a login alias in the file [config.yml](file://~/.lwetl/config.yml) with the syntax:

        scott_<driver name>
        
E.g., `scott_mysql` for mysql.

SQL commands for the tests are stored in the file `sql_statements.yml`. By default all database 
types, which are defined in this file, are tested unless the parameter `disabled` is set to true. 

## Creating a test database and user

#### MySQL

        create database scott;
        create user scott;
        grant select, insert, delete, update, create, drop, alter, references
            on scott.* to 'scott'@'localhost' identified by 'tiger'; 
        flush privileges;

