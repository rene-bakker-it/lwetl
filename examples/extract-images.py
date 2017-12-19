#!/usr/bin/env python

"""
Extracts images to file based on an SQL with two parameters
"""

import argparse
from lwetl import Jdbc

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description='Extract image files from a database into the current directory.')

parser.add_argument('login',
                    help='''login credentials or alias of the source database. 
Use 'sql-query list' to view possible options.
Credentials are in ORACLE format: <username>/<password>@server''')

parser.add_argument('sql',
                    help='''SQL to extract the images returning two columns: 
1. the file-name for the image, 
2. the field with the image content.
Example: 
   SELECT FILE_NAME, PHOTO FROM MY_PHOTOS ORDER BY FILE_NAME''')

args = parser.parse_args()

jdbc = Jdbc(args.login)
print('Connected to: ' + jdbc.type)

cnt1 = 0
cnt2 = 0
for fname, logo in jdbc.query(args.sql):
    cnt1 += 1
    print('%6d. Parsing %s' % (cnt1, fname))
    if isinstance(fname, str) and (len(fname.strip()) > 0):
        with open(fname.strip(), 'wb') as f:
            f.write(logo)
        cnt2 += 1

print('Done: extracted %d files (%d skipped).' % (cnt1, (cnt1 - cnt2)))
