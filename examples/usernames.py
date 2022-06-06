#!/usr/bin/env python

"""
    Scenario:
    Create or update a table (TST_USERNAMES) in the target DB, which associates the ID of a client with its username(s)
    used for web-authentication.

    Clients may have several credentials. If this is the case, the field USERSNAME in TST_USERNAMES must be a
    comma-separated list of usernames.

    Premises:
    A. db1 (source) contains two large tables (> 1M entries):
       1. A table (PERSONS) with information on persons.
          Each person has a unique record in this table.
       2. A table (CREDENTIALS) with authentication credentials for web-services has a FK to the table PERSONS
          Several usernames may be associated to the same person.

    B. db2 (target) uses the ID of the table db1.PERSONS to uniquely identify clients. For this contains a
       a table (db2.CLIENTS), which contains a column ID_PERSON with reference to db1.PERSONS.ID.
       The table db2.CLIENTS only references a fraction of the persons stored in db1.PERSONS (< 1M records, not all
       persons are clients). For historical reasons, not all clients are associated to a person (those who never
       authenticated as client on the current service). Authentication credentials are not present in this database.

    C. Both databases run on different servers and direct communication between them is prohibited.

    The procedure below works as follows:
    1. Reading of the defined clients in db2 with their associated ID_PERSON
       to create a dictionary key: ID_CLIENT, value: ID_PERSON
    2. Each time the dictionary reaches a size of BATCH_SIZE (command line  parameter, default 1000)
       the associated usernames are retrieved from db1 and the result is written in a dictionary 'usernames'
    3. After reading all clients it reads the stored usernames from db2.TST_USERNAMES
       - non modified entries are untouched.
       - modified entries are updated
       - removed items are deleted
       - new associations are added.
"""

import argparse
import sys

from lwetl import Jdbc, NativeUploader, get_execution_statistics, tag_connection, SQLExecuteException, \
    UPLOAD_MODE_COMMIT
from lwetl.utils import is_empty

# SQL definitions
# =====================================================================================================================

TARGET_TABLE = "TST_USERNAMES"

# retrieve DB2.PERSONS.ID with its associated db1.PERSONAL_RECORD.ID,
SQL_DB2_CLIENTS = '''
    SELECT ID, ID_PERSON 
    FROM  CLIENTS
    WHERE ID_PERSON IS NOT NULL 
    ORDER BY ID;'''
# bG5yw4xfw5jClsKhw47CksKXwpZcWcKteMKUwod1wobCtMKBwrRXwpHChV7CgMKowo_CuXnChF5iwpTCo8OLwqHCncODwpTCmVlbdcKwfXrChcKE
# wofCiF7ChlfCrsKpfMKFwrh5wqrCgXl4wpPCr8KAwrR2WMKL

# test if the target table exists
SQL_EXISTS = "SELECT * FROM {0} WHERE 0=1".format(TARGET_TABLE)

# retrieve the usernames already retrieved in a previous run
SQL_DB2_KNOWN_ASSOICATIONS = '''
    SELECT ID, USERNAME 
    FROM  {0}
    ORDER BY ID;'''.format(TARGET_TABLE)

# SQL to retrieve the usernames from db1
SQL_GET_USERNAME = '''
SELECT 
    ID_PERSON, 
    USERNAME 
FROM 
    CREDENTIALS
WHERE 
    ID_PERSON IN ({0})'''
# bG5yw4xfw5jClsKhw47CksKXwpZcWcKteMKUwod1wobCtMKBwrRXwpHChV7CgMKowo_CpcKGd37Ci8Knd8KvdHLCiVpiwqPCmcKiw5DClcKYwpxYW8K
# kwoTCq3TCqsKzwovCgMKlfMK3X2Jewo7Cp3_DhcKGwoTCp8KDW1o=

# The target table may be created by this program.
# the sql is differently on each server type
CREATE_TABLE = {
    'oracle': '''
CREATE TABLE {0} (
    ID NUMBER(10) NOT NULL,
    USERNAME VARCHAR2(2000) NOT NULL,
    PRIMARY KEY(ID)
);''',

    'mysql': '''
CREATE TABLE {0} (
    ID INT(10) UNSIGNED NOT NULL PRIMARY KEY,
    USERNAME VARCHAR(2000) NOT NULL
);''',

    'sqlserver': '''
CREATE TABLE {0} (
    ID BIGINT NOT NULL,
    USERNAME NVARCHAR(2000),
    CONSTRAINT PK_{0} PRIMARY KEY CLUSTERED (ID ASC)
);''',

    'postgresql': '''
CREATE TABLE {0} (
    ID INT NOT NULL PRIMARY KEY,
    USERNAME VARCHAR(2000)
);''',

    'sqlite': '''
CREATE TABLE {0} (
    ID INTEGER PRIMARY KEY,
    USERNAME TEXT
);'''
}


class Counter:
    """
        Makes counting shorter below
    """

    def __init__(self, c=None):
        self.inserted = 0
        self.updated = 0
        self.deleted = 0
        self.ignored = 0
        self.rowcount = 0
        self.committed = 0
        if isinstance(c, Counter):
            self._add(c)

    def _add(self, c):
        self.inserted += c.inserted
        self.updated += c.updated
        self.deleted += c.deleted
        self.ignored += c.ignored
        self.rowcount += c.rowcount
        self.committed += c.committed

    def __str__(self):
        return 'pr = %6d, ins =%6d, upd =%6d, del =%6d, ign =%6d, com =%6d' % (
            self.rowcount, self.inserted, self.updated, self.deleted, self.ignored, self.committed)

    def __add__(self, c):
        cc = Counter(self)
        if isinstance(c, Counter):
            cc._add(c)
        return cc

    def __iadd__(self, c):
        if isinstance(c, Counter):
            self._add(c)
        return self


def create_target_table(jdbc: Jdbc):
    """
    Creates the target table if it dows not exist
    @param jdbc: target database connection
    @return: True if created, False otherwise
    """
    try:
        jdbc.execute(SQL_EXISTS)
        created = False
    except SQLExecuteException:
        if jdbc.type not in CREATE_TABLE:
            raise LookupError('Database type %s not in known list: %s' % (jdbc.type, ', '.join(CREATE_TABLE.keys())))
        print('CREATING TABLE:' + TARGET_TABLE)
        jdbc.execute(CREATE_TABLE[jdbc.type].format(TARGET_TABLE))
        jdbc.commit()
        created = True
    return created

def init_connections(login_source, login_target):
    # no handling of wrong credentials
    src = Jdbc(login_source)
    tag_connection('SRC',src)
    trg = Jdbc(login_target)
    tag_connection('TRG',trg)

    # create the target table if not existing
    create_target_table(trg)

    return src, trg

def process_clients(jdbc: Jdbc, batch_nr: int, clients: dict(), usernames: dict):
    row_count = 0
    ign_count = 0
    n_users_1 = len(usernames)

    if len(clients) > 0:
        inverse_lookup = dict()
        for id_client, id_person in clients.items():
            if id_person in inverse_lookup:
                inverse_lookup[id_person].append(id_client)
            else:
                inverse_lookup[id_person] = [id_client]

        sql = SQL_GET_USERNAME.format(','.join([str(k) for k in inverse_lookup.keys()]))

        for id_person, username in jdbc.query(sql):
            row_count += 1
            for id_client in inverse_lookup[int(id_person)]:
                if id_client in usernames:
                    if username in usernames[id_client]:
                        ign_count += 1
                    else:
                        usernames[id_client].append(username)
                else:
                    usernames[id_client] = [username]

    n_users_2 = len(usernames)
    print('Batch %3d finished: rows = %4d, ignored = %4d, users: %6d, delta = %4d' %
          (batch_nr, row_count, ign_count, n_users_2, n_users_2 - n_users_1))
    return row_count, ign_count


class CommandLineParser:
    @staticmethod
    def check_batch_range(arg_value):
        try:
            ivalue = int(arg_value)
        except ValueError:
            ivalue = -1
        if (ivalue <= 0) or (ivalue > 2000):
            raise argparse.ArgumentTypeError("%s is not an integer in the range [1,2000]" % arg_value)
        return ivalue

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter,
            description='Copy usernames from the source database to the target database.')

        self.parser.add_argument('login_source',
                                 help='Login credentials or alias of the source database.')

        self.parser.add_argument('login_target',
                                 help='''Login credentials or alias of the target database. 
            Use 'sql-query list' to view possible options.
            Credentials are in ORACLE format: <username>/<password>@server''')

        self.parser.add_argument('-b', '--batch_size', type=self.check_batch_range, default=1000,
                                 help='Batch size for processing. Must be between [1,2000]. Defaults to 1000.')

        self.parser.add_argument('--log', type=str,
                                 help='Log generated SQL commands to file or stdin/stdout')

        self.args = None

    def set_log_stream(self):
        if is_empty(self.args.log):
            return None
        elif self.args.log.lower() == 'stdin':
            return sys.stdin
        elif self.args.log.lower() == 'stdout':
            return sys.stdout
        else:
            return open(self.args.log, 'w')

    def __call__(self):
        self.args = self.parser.parse_args()
        return self.args.login_source, self.args.login_target, self.set_log_stream(), self.args.batch_size


if __name__ == "__main__":
    # Command line parsing
    # =====================================================================================================================
    parser = CommandLineParser()
    login_source, login_target, log_stream, batch_size = parser()

    src, trg = init_connections(login_source, login_target)

    # dictionary of found usernames
    # key - id of client
    # value - list of usernames associated to the client
    client_usernames = dict()

    batch_nr = 0
    row_nr = 0
    clients = dict()
    row_count = 0
    ign_count = 0
    print('Parsing clients .........')
    for id_client, id_person in trg.query(SQL_DB2_CLIENTS):
        row_nr += 1

        clients[int(id_client)] = int(id_person)
        if len(clients) >= batch_size:
            batch_nr += 1
            rc, ic = process_clients(src, batch_nr, clients, client_usernames)
            row_count += rc
            ign_count += ic
            clients = dict()
    if len(clients) > 0:
        batch_nr += 1
        rc, ic = process_clients(src, batch_nr, clients, client_usernames)
        row_count += rc
        ign_count += ic
    del clients

    print('Parsing clients done: rows(src) = %6d, rows(trg) = %6d, ignored = %6d, clients = %6d' %
          (row_count, row_nr, ign_count, len(client_usernames)))

    uploader = NativeUploader(trg, TARGET_TABLE, log_stream, UPLOAD_MODE_COMMIT)

    # update the known associations
    commit_nr = 0
    counter = Counter()
    for id_client, stored_names in trg.query(SQL_DB2_KNOWN_ASSOICATIONS):
        counter.rowcount += 1
        id_client = int(id_client)
        found_names = '|'.join(sorted(set(client_usernames[id_client])))
        if id_client in client_usernames:
            if found_names == stored_names:
                counter.ignored += 1
            else:
                uploader.update({'USERNAME': found_names}, {'ID': id_person})
                counter.updated += 1
            del client_usernames[id_client]
        else:
            uploader.delete({'ID': id_person})
            counter.deleted += 1
        if uploader.row_count >= batch_size:
            commit_nr += 1
            counter.committed += uploader.row_count
            uploader.commit()
            print('%4d: %s' % (commit_nr,str(counter)))

    # insert the new associations
    for id_client, found_names in client_usernames.items():
        uploader.insert({'ID': id_client, 'USERNAME': '|'.join(sorted(set(found_names)))})
        counter.inserted += 1
        if uploader.row_count >= batch_size:
            commit_nr += 1
            counter.committed += uploader.row_count
            uploader.commit()
            print('%4d: %s' % (commit_nr,str(counter)))

    counter.committed += uploader.row_count
    uploader.commit()
    print('Done: ' + str(counter))

    print(get_execution_statistics())
