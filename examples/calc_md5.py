"""
    Example:
        - read all rows from MY_TABLE, which contains the columns ID, AND HASH_VALUE
        - for each row calculate a new md5 checksum based on the content of the row.
        - the order of the elements is determined by the database
"""
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