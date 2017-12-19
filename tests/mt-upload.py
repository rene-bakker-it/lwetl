#!/usr/bin/env python

"""
    Test for muliprocessing upload
    Fails for all database types

    Some connection error occurs at a fixed interval. Size of the interval depends on the jdbc driver,
    the target database, and the number of threads.

    It looks like the jdbc connection remains busy. But I did not find a way to query this. There is also
    no exception thrown.

"""
import argparse
import multiprocessing
import psutil
import os

from time import sleep

from lwetl import Jdbc, SQLExcecuteException, get_execution_statistics

TABLE_NAME = 'T2_CX_STRINGS'

WORD = 'word'
ASCII = 'ascii'
LATIN_1 = 'latin-1'
LATIN_2 = 'latin-2'
CHAR_TYPES = [WORD, ASCII, LATIN_1, LATIN_2]

# load test dictionaries
TEST_STRINGS = dict()
output_dir = os.path.join(os.path.dirname(__file__),'output')

N_WORDS = dict()
COUNTER = dict()
nr_of_words = 0
for char_type in CHAR_TYPES:
    COUNTER[char_type] = 0
    with open(os.path.join(output_dir,char_type + '.txt'),'r') as f:
        TEST_STRINGS[char_type] = [s.strip() for s in f.readlines()]
        N_WORDS[char_type] = len(TEST_STRINGS[char_type])
        nr_of_words += N_WORDS[char_type]
print('Loaded: %d words into memory.' % nr_of_words)

N_TYPES = len(CHAR_TYPES)
def get_word(batch_nr, n_switch):
    global COUNTER

    if n_switch == 0:
        ct = WORD
    else:
        ct = CHAR_TYPES[int(batch_nr/n_switch) % N_TYPES]
    n = COUNTER[ct] % N_WORDS[ct]
    COUNTER[ct] += 1
    return TEST_STRINGS[ct][n]


def upload_batch(jdbc:Jdbc, batch_nr, id_start, word_list, use_paramers):
    cursor = None
    pk = id_start
    n_ascii = 0
    n_other = 0
    for w in word_list:
        try:
            w.encode().decode('ascii')
            n_ascii += 1
        except UnicodeDecodeError:
            n_other += 1
    if use_paramers:
        for w in word_list:
            pk += 1
            # if batch_nr == 37: print('%8d %s' % (pk,w))
            cursor=jdbc.execute("INSERT INTO {0} (ID,STR_VALUE) VALUES(?,?)".format(TABLE_NAME),[pk,w],cursor=cursor)
    else:
        for w in word_list:
            pk += 1
            # if batch_nr == 37: print('%8d %s' % (pk,w))
            cursor=jdbc.execute("INSERT INTO %s (ID,STR_VALUE) VALUES(%d,'%s')" % (TABLE_NAME,pk,w.replace("'","''")),cursor=cursor)
    jdbc.commit(cursor)
    print('%4d. done ascii = %4d, other = %4d.' % (batch_nr, n_ascii, n_other))
    return n_ascii, n_other

CONNECTIONS = dict()
def upload_batch_mt(login, batch_nr, id_start, word_list, use_paramers, lock):
    global CONNECTIONS

    name = multiprocessing.current_process().name
    if name not in CONNECTIONS:
        CONNECTIONS[name] = Jdbc(login)
    lock.acquire()
    r = upload_batch(CONNECTIONS[name], batch_nr, id_start, word_list, use_paramers)
    lock.release()
    return r

def get_pool_results(results: dict, max_no_result=5):
    try_count = 0
    nrc_count = 0
    while (len(results) > 0) and (nrc_count < max_no_result):
        sleep(0.5)
        try_count += 1
        nrc_count += 1
        not_processed = sorted(results.keys())
        post_fix = ', ...' if len(results) > 20 else ''
        print('%2d.%d Fetching for result: %s%s' %
              (try_count,nrc_count,', '.join([str(x) for x in not_processed[:20]]), post_fix))
        for x in not_processed:
            try:
                results[x].get(0.1)
            except multiprocessing.TimeoutError:
                pass
            else:
                print('%3d. Finished' % x)
                del results[x]
                nrc_count = 0
    return len(results)

def reap_children(timeout=3):
    procs = psutil.Process().children()
    # send SIGKILL
    for p in procs:
        p.kill()
    gone, alive = psutil.wait_procs(procs, timeout=timeout)
    if alive:
        for p in alive:
            print("process {} survived SIGKILL; giving up".format(p))


# The target table may be created by this program.
# the sql is differently on each server type
CREATE_TABLE = {
    'oracle': '''
CREATE TABLE {0} (
    ID NUMBER(10) NOT NULL,
    STR_VALUE VARCHAR2(50) NOT NULL,
    PRIMARY KEY(ID)
);''',

    'mysql': '''
CREATE TABLE {0} (
    ID INT(10) UNSIGNED NOT NULL PRIMARY KEY,
    STR_VALUE VARCHAR(50) NOT NULL
);''',

    'sqlserver': '''
CREATE TABLE {0} (
    ID BIGINT NOT NULL,
    STR_VALUE NVARCHAR(50),
    CONSTRAINT PK_{0} PRIMARY KEY CLUSTERED (ID ASC)
);''',

    'postgresql': '''
CREATE TABLE {0} (
    ID INT NOT NULL PRIMARY KEY,
    STR_VALUE VARCHAR(50)
);''',

    'sqlite': '''
CREATE TABLE {0} (
    ID INTEGER PRIMARY KEY,
    STR_VALUE TEXT
);'''
}


def check_positive(arg_value):
    try:
        ivalue = int(arg_value)
    except ValueError:
        ivalue = -1
    if ivalue < 0:
        raise argparse.ArgumentTypeError("%s is not a zero or positive integer" % arg_value)
    return ivalue


parser = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    description='Copy a long list of short strings into the database.')

parser.add_argument('login', help='''Login credentials or alias of the target database. 
    Use 'sql-query list' to view possible options.
    Credentials are in ORACLE format: <username>/<password>@server''')

parser.add_argument('-b', '--batch_size', type=check_positive, default=1000,
    help='Batch size for processing. Must be between [1,2000]. Defaults to 1000.')

parser.add_argument('-m', '--max', type=check_positive, default=nr_of_words,
    help='Number words to upload. Defaults to %d.' % nr_of_words)

parser.add_argument('-n', '--n_switch', type=check_positive, default=5,
    help='Number of batches before switching to the next word type. Defaults to 5.')

parser.add_argument('-t', '--threads',  type=check_positive, default=0,
    help='Number of threads. Defaults to 0 (no threadpool used)')

parser.add_argument('-p', '--parameters',  action='store_true',
    help='Use parameters in SQL.')

args = parser.parse_args()

login = args.login
jdbc = Jdbc(login)

try:
    id_start = jdbc.get_int("SELECT MAX(ID) FROM {0}".format(TABLE_NAME))
    print('Start inserting with: %d' % id_start)
except SQLExcecuteException:
    if jdbc.type not in CREATE_TABLE:
        raise LookupError('Database type %s not in known list: %s' % (jdbc.type, ', '.join(CREATE_TABLE.keys())))
    print('CREATING TABLE:' + TABLE_NAME)
    jdbc.execute(CREATE_TABLE[jdbc.type].format(TABLE_NAME))
    jdbc.commit()
    id_start = 0

batch_size = args.batch_size
n_switch = args.n_switch
use_parameters = args.parameters
nr_of_threads = args.threads

if nr_of_threads > 0:
    pool = multiprocessing.Pool(args.threads)
    mngr = multiprocessing.Manager()
    lock = mngr.Lock()
    results = dict()

batch_nr = 0
word_list = []
word_count = 0
for x in range(args.max):
    word_list.append(get_word(batch_nr, n_switch))
    word_count += 1
    if word_count >= batch_size:
        batch_nr += 1
        if nr_of_threads == 0:
            upload_batch(jdbc, batch_nr, id_start, word_list, use_parameters)
        else:
            results[batch_nr] = pool.apply_async(upload_batch_mt,(login, batch_nr, id_start, [w for w in word_list], use_parameters, lock))
        id_start += word_count
        word_count = 0
        word_list = []
if word_count > 0:
    batch_nr += 1
    if nr_of_threads == 0:
        upload_batch(jdbc, batch_nr+1, id_start, word_list, use_parameters)
    else:
        results[batch_nr] = pool.apply_async(upload_batch_mt,(login, batch_nr, id_start, [w for w in word_list], use_parameters, lock))

if nr_of_threads > 0:
    n = get_pool_results(results)
    if n > 0:
        print('ERROR: %d batches not processed.' % n)
        reap_children()

print(get_execution_statistics())

