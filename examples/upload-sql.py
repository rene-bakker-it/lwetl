#!/usr/bin/env python

"""
    Upload a sequence of sql commands to a database

    Example:
        first run (-a omitted -> dryrun with rollback only):
            ./upload-csv.py --log upl.sql scott_mysql lwetl_product ../tests/resources/price_list.csv
        then:
            cat upl.sql | ./upload-sql.py -a scott_mysql
"""

import argparse
import sys

from lwetl import Jdbc, InputParser

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description='Upload sql commands to a database.')

parser.add_argument('login',
                    help='''login credentials or alias of the source database. 
Use 'sql-query list' to view possible options.
Credentials are in ORACLE format: <username>/<password>@server''')

parser.add_argument('sql',nargs='?', default = sys.stdin,
                    help='SQLs to upload. May be a string or a filename. Use stdin if omitted.')

parser.add_argument('-a','--activate', action='store_true',
                    help='Activate commit. Use rollback otherwise.')

parser.add_argument('-n','--commit_nr', type=int, default = 1000,
                    help='Commit to database every nth statement. Defaults to 1000.')

args = parser.parse_args()

jdbc = Jdbc(args.login)
print('Connected to: ' + jdbc.type)

if args.activate:
    rollback_msg = ''
    commit = jdbc.commit
else:
    rollback_msg = ' (with rollback)'
    commit = jdbc.rollback

with InputParser(args.sql) as inp:
    cnt = 0
    cur = None
    for sql in inp.parse():
        cnt += 1
        cur = jdbc.execute(sql,cursor=cur)
        if cur.rowcount >= args.commit_nr:
            commit()
    commit()

# Alternative method
# parser = InputParser()
# inp = parser.open(args.sql)
# cnt = 0
# cur = None
# for sql in inp.parse():
#     cnt += 1
#     cur = jdbc.execute(sql, cursor=cur)
#     if cur.rowcount >= args.commit_nr:
#        commit()
# inp.close()
# commit()

print('Done: uploaded %d sql commands.%s' % (cnt,rollback_msg))
