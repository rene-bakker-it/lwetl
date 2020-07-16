#!/usr/bin/env python3

"""
Scan the defined sequences in an ORACLE DB:
  - see if they match with a PK in a table
  - check if the sequence value is larger then the max ID value
"""

import argparse
import sys

from lwetl import Jdbc, SQLExcecuteException
from collections import namedtuple

Sequence = namedtuple('Sequence', 'name value')

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description='Update sequences.')

parser.add_argument('login',
                    help='''login credentials or alias of the source database. 
Use 'sql-query list' to view possible options.
Credentials are in ORACLE format: <username>/<password>@server''')

parser.add_argument('-a', '--activate', action='store_true',
                    help='Activate commit. Use rollback otherwise.')

parser.add_argument('-l', '--list', action='store_true',
                    help='List the affected sequences only.')

parser.add_argument('-n', '--commit_nr', type=int, default=1000,
                    help='Commit to database every nth statement. Defaults to 1000.')

args = parser.parse_args()

jdbc = Jdbc(args.login)
print('Connected to: ' + jdbc.type)

SQL_LIST_SEQUENCES = '''
SELECT 
    SEQUENCE_NAME, LAST_NUMBER 
FROM 
    USER_SEQUENCES
ORDER BY SEQUENCE_NAME'''

SQL_LIST_TABLES_COLUMNS = '''
SELECT
    c.table_name, 
    c.column_name
FROM 
    user_constraints s
    INNER JOIN  all_cons_columns c ON s.constraint_name = c.constraint_name
        AND s.constraint_type = 'P' AND s.STATUS = 'ENABLED' '''

SQL_SINGLE_PK_TABLES = '''
SELECT table_name 
FROM ({}) t
GROUP BY table_name
HAVING COUNT(*)=1
ORDER BY t.table_name'''.format(SQL_LIST_TABLES_COLUMNS)

# Tables with a single column PK
tables = [t[0].upper() for t in jdbc.query(SQL_SINGLE_PK_TABLES)]

# get sequences with a name that starts with the table name
sequences = {}
for name, value in jdbc.query(SQL_LIST_SEQUENCES):
    name = name.upper()
    for t in tables:
        if name.startswith(t):
            sequences[t] = Sequence(name, value)
            break

# Now do the job
for t, c in jdbc.query(SQL_LIST_TABLES_COLUMNS):
    if t not in sequences:
        continue
    sql = 'SELECT MAX({}) FROM {}'.format(c, t)
    try:
        max_value = jdbc.get_int(sql)
        if max_value > sequences[t].value:
            sname = sequences[t].name
            print('Updating {:_<30s} from {:8d} to {:8d} '.format(sname, sequences[t].value, max_value + 1))
            nextv = 'SELECT {}.NEXTVAL FROM DUAL;'.format(sname)
            cursor = None

            for sql in [
                'DROP SEQUENCE {};'.format(sname),
                'CREATE SEQUENCE {} START WITH 1 MINVALUE 1 INCREMENT BY {};'.format(sname, max_value),
                nextv, nextv,
                'ALTER SEQUENCE {} INCREMENT BY 1;'.format(sname),
                nextv]:
                cursor = jdbc.execute(sql, cursor=cursor)
            if args.activate:
                jdbc.commit(cursor)
            else:
                jdbc.rollback(cursor)
    except SQLExcecuteException as se:
        print('ERROR with {}: {}'.format(sql, str(se)))
        print('IGNORED: {}'.sname)
