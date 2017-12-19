#!/usr/bin/env python

"""
    This is a multi-threaded attempt of the procedure described in usernames.py

    It is a pure test crashes.

    Mothod:
    - each thread has its own, isolated connection (OK)
    - uploads are in raw SQL
      strange: non-multithreaded uploads are OK but in multi-threaded mode strings with some non-ascii
               characters cause a crash.

               E.g., INSERT INTO TST_USERNAMES (ID,USERNAME) VALUES (932328,'MariaRączkowska')
               + works fine for single-threaded mode
               + jpype connection fails for multi-threaded mode (becomes non-responsive).
"""

import io
import os
import multiprocessing

from time import sleep

from usernames import CommandLineParser, Counter, init_connections, process_clients, \
    SQL_DB2_CLIENTS, SQL_DB2_KNOWN_ASSOICATIONS, TARGET_TABLE

from lwetl import Jdbc, NativeUploader, InputParser, get_execution_statistics, UPLOAD_MODE_PIPE
from lwetl.utils import is_empty

DWN_POOL_CONNECTIONS = dict()
def mt_process_clients(login, batch_nr: int, clients: dict(), usernames: dict):
    global DWN_POOL_CONNECTIONS

    name = multiprocessing.current_process().name
    if name not in DWN_POOL_CONNECTIONS:
        print('CREATING SRC DB CONNECTION FOR: ' + name)
        DWN_POOL_CONNECTIONS[name] = Jdbc(login)

    return process_clients(DWN_POOL_CONNECTIONS[name], batch_nr, clients, usernames)

UPL_POOL_CONNECTIONS = dict()
def mt_upload(login, batch_nr, sqls):
    global UPL_POOL_CONNECTIONS

    if is_empty(sqls):
        print('UPL: %3d, sqls = %4d, rows = %6d' % (batch_nr, -1, -1))
        return 0, 0

    name = multiprocessing.current_process().name
    if name not in UPL_POOL_CONNECTIONS:
        print('CREATING TRG DB CONNECTION FOR: ' + name)
        UPL_POOL_CONNECTIONS[name] = Jdbc(login)

    jdbc = UPL_POOL_CONNECTIONS[name]
    rc1 = 0
    rc2 = 0
    with InputParser(sqls) as parser:
        cursor = None
        for sql in parser.parse():
            rc1 += 1
            try:
                sql.encode().decode('ascii')
                c = jdbc.execute(sql, cursor=cursor)
                cursor = c
            except Exception as ex:
                rc2 += 1
                print('%2d %3d %s' % (batch_nr,rc1,sql))
    #if cursor is not None:
    #    rc2 = cursor.rowcount
    print('UPL: %3d, sqls = %4d, rows = %6d' % (batch_nr, rc1, rc2))

    if cursor is not None:
        jdbc.commit()

    return rc1, rc2

def get_pool_results(results: dict, max_no_result=10):
    count1 = 0
    count2 = 0
    try_count = 0
    nrc_count = 0
    while (len(results) > 0) and (nrc_count <= max_no_result):
        try_count += 1
        nrc_count += 1
        not_processed = sorted(results.keys())
        post_fix = ', ...' if len(results) > 20 else ''
        print('%2d. Fetching for result: %s%s' % (try_count,', '.join([str(x) for x in not_processed[:20]]), post_fix))
        for x in not_processed:
            try:
                c1, c2 = results[x].get(0.5)
            except multiprocessing.TimeoutError:
                pass
            else:
                count1 += c1
                count2 += c2
                del results[x]
                nrc_count = 0
        if len(results) > 0:
            sleep(1)

    if len(results) > 0:
        pool.terminate()
        os._exit(1)
    return count1, count2

class MtCommandLineParser(CommandLineParser):

    def __init__(self):
        super(MtCommandLineParser, self).__init__()
        self.parser.add_argument('-t', '--threads', type=self.check_batch_range, default=1,
             help='Number of threads to use. Must be between [1,2000]. Defaults to 1.')

    def __call__(self):
        self.args = self.parser.parse_args()
        return self.args.login_source, self.args.login_target, self.set_log_stream(), \
               self.args.batch_size, self.args.threads


if __name__ == "__main__":
    # Command line parsing
    # =====================================================================================================================
    parser = MtCommandLineParser()
    login_source, login_target, log_stream, batch_size, nr_of_threads = parser()

    src, trg = init_connections(login_source, login_target)

    print('Creating a pool of %d threads' % nr_of_threads)
    pool = multiprocessing.Pool(nr_of_threads)
    mngr = multiprocessing.Manager()

    # dictionary of found usernames
    # key - id of client
    # value - list of usernames associated to the client
    client_usernames = mngr.dict()

    print('Parsing clients .........')
    clients = dict()
    batches = dict()
    row_nr = 0
    batch_nr = 0
    for id_client, id_person in trg.query(SQL_DB2_CLIENTS):
        row_nr += 1
        clients[int(id_client)] = int(id_person)
        if len(clients) >= batch_size:
            batch_nr += 1
            batches[batch_nr] = pool.apply_async(mt_process_clients,
                                        (login_source, batch_nr,clients, client_usernames))
            clients = dict()
    if len(clients) > 0:
        batch_nr += 1
        batches[batch_nr] = pool.apply_async(mt_process_clients,
                                        (login_source, batch_nr, clients, client_usernames))
    del clients

    print('Done: parsed %d rows. Now fetching results .......' % row_nr)
    row_count, ign_count = get_pool_results(batches)
    print('Parsing clients done: rows(src) = %6d, rows(trg) = %6d, ignored = %6d, clients = %6d' %
          (row_count, row_nr, ign_count, len(client_usernames)))


    uploader = NativeUploader(trg, TARGET_TABLE, io.StringIO(), UPLOAD_MODE_PIPE)

    # update the known associations
    commit_nr = 0
    counter = Counter()
    commits = dict()
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
            commits[commit_nr] = pool.apply_async(mt_upload,(login_target, commit_nr, uploader.commit()))

    # insert the new associations
    for id_client, found_names in client_usernames.items():
        uploader.insert({'ID': id_client, 'USERNAME': '|'.join(sorted(set(found_names)))})
        counter.inserted += 1
        if uploader.row_count >= batch_size:
            commit_nr += 1
            commits[commit_nr] = pool.apply_async(mt_upload,(login_target, commit_nr, uploader.commit()))

    sqls = uploader.commit()
    if not is_empty(sqls):
        commit_nr += 1
        commits[commit_nr] = pool.apply_async(mt_upload, (login_target, commit_nr, sqls))

    sql_count, row_count = get_pool_results(commits)

    counter.committed += sql_count
    counter.rowcount += row_count
    print('Done: ' + str(counter))

    print(get_execution_statistics())
