#!/usr/bin/env python

"""
    Upload a CSV file to a table in the database

    Example (test environemnt for mysql isntalled):
    ./upload-csv.py -a --log upl.sql scott_mysql lwetl_product ../tests/resources/price_list.csv
"""

import argparse
import sys

from lwetl import Jdbc, CsvImport, NativeUploader,\
    UPLOAD_MODE_COMMIT, UPLOAD_MODE_ROLLBACK

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description='Upload a CSV file to a table in a database.')

parser.add_argument('login',
                    help='''login credentials or alias of the target database. 
Use 'sql-query list' to view possible options.
Credentials are in ORACLE format: <username>/<password>@server''')

parser.add_argument('table',
                    help='Name to the table to store the data in the database.')

parser.add_argument('csv',nargs='?', default = sys.stdin,
                    help='''CSV file to upload. Use stdin if omitted.
    IMPORTANT: the first row of the CSV file must contain the column names!''')

parser.add_argument('-a','--activate', action='store_true',
                    help='Activate commit. Use rollback otherwise.')

parser.add_argument('-d','--delimiter', default = "\t",
                    help='CSV column delimiter. Defaults to TAB.')

parser.add_argument('-n','--commit_nr', type=int, default = 1000,
                    help='Commit to database every nth statement. Defaults to 1000.')

parser.add_argument('--log', type=str,
                    help='Log generated SQL commands to file or stdin/stdout')
args = parser.parse_args()

# set the commit mode
commit_mode = UPLOAD_MODE_COMMIT if args.activate else UPLOAD_MODE_ROLLBACK

# enable logging, if desired
logf = None
if args.log is not None:
    if args.log.lower() == 'stdin':
        logf = sys.stdin
    elif args.log.lower() == 'stdout':
        logf = sys.stdout
    else:
        logf = open(args.log,'w')

jdbc = Jdbc(args.login)
print('Connected to: ' + jdbc.type)

with NativeUploader(jdbc,args.table, fstream=logf, commit_mode=commit_mode, exit_on_fail=True) as upl:
    with CsvImport(args.csv, delimiter=args.delimiter) as inp:
        cnt = 0
        for row in inp.get_data():
            cnt += 1
            upl.insert(row)
        if upl.row_count >= args.commit_nr:
            upl.commit()
    upl.commit()

# close logging, if enabled.
if logf not in [None,sys.stdin,sys.stdout]:
    logf.close()


print('Done: uploaded %d rows of data into %s.' % (cnt,args.table))
