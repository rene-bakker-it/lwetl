"""
The configuration is a yaml file and
its base name is defined in CONFIGURATION_FILE_NAME (lwetl by default)
and scanned in 3 locations (exist and readable) in the following order:
     - config.yml in the module directory
     - /etc/lwetl/config.yml
     - .lwetl/config.yml in the user home directory

     Identical definitions are substituted.

     Each yaml file may contain 4 sections:
     env:      for replacement or addition of environment variables
     drivers:  defines the drivers used for the connection.
     servers:  defines the server to connect to. May be omitted for
               connections defined in tnsnames.ora
               For each server the following must be specified:
               - type: type of server (mysql, sqlserver, oracle)
                      THESE NAMES SHOULD BE THE SAME AS THE ONES USED IN
                      THE DRIVERS SECTION
               - url:  the connection url
     alias     login aliases (maps to oracle style login string)

     This module:
      - verifies the configuration content
      - downloads JDBC jar files, if not present
      - stores all info in the following dictionaries:
        + JDBC_DRIVERS
        + JDBC_SERVERS
        + LOGIN_ALIAS
"""

import logging
import os
import sys
import yaml

from urllib.request import urlretrieve
from urllib.error import HTTPError, URLError

from .exceptions import ServiceNotFoundException
from .utils import verified_boolean
from .security import decrypt

# define a logger
LOGGER = logging.getLogger(os.path.basename(__file__).split('.')[0])

MODULE_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.pardir))
HOME_DIR = os.path.expanduser('~')
WORK_DIR = os.getcwd()
MOD_NAME = '.lwetl'

# search path for configuration files
CFG_FILE = 'config.yml'
CFG_EXAMPLE_FILE = 'config-example.yml'
CFG_DIRS = [d for d in [
    os.path.join(MODULE_DIR),
    '/etc/lwetl',
    os.path.join(HOME_DIR, MOD_NAME)] if os.path.isdir(d)]

CFG_FILES = [os.path.join(WORK_DIR, CFG_FILE)] + [os.path.join(d, CFG_FILE) for d in CFG_DIRS]

# Encrypt passwords
CFG_ENCRYPT = True


def merge(source: dict, destination: dict) -> dict:
    """
    merge source into destination. Values in source take precedence

    @param source: dict source
    @param destination: dict destination
    @return: dict destination with source merged into it
    """
    if isinstance(source, dict):
        for k, v in source.items():
            if isinstance(v, dict):
                # get node or create one
                node = destination.setdefault(k, {})
                merge(v, node)
            else:
                destination[k] = v

    return destination


def parse_login(login: str):
    """
    Parse the login string against the configuration
    @param login: str login credentials in oracle format: username/password@service, or,
                  in the case of a non-encrypted sqlite local file, as sqlite:<filename>
    @return: Tuple (login credentials (tuple of username, password), database type,
                        connection url, column_escape option)
    """

    # sqlite can be called directly
    if login.startswith('sqlite:') and ('sqlite' in JDBC_DRIVERS):
        db_file = login[7:]
        url = JDBC_DRIVERS['sqlite']['url'] + db_file
        return None, 'sqlite', db_file, url, False

    login_credentials = LOGIN_ALIAS.get(login, login)
    if '@' in login_credentials:
        username_password, service_name = login_credentials.rsplit('@', 1)
        if '/' in username_password:
            user_name, password = username_password.rsplit('/', 1)
            if CFG_ENCRYPT:
                # noinspection PyBroadException
                try:
                    pw = decrypt(password, raise_error=True)
                except Exception:
                    pass
                else:
                    password = pw
            credentials = user_name, password
        else:
            user_name = username_password
            credentials = username_password
    else:
        user_name = None
        service_name = login_credentials
        credentials = None

    service_name = service_name.strip().lower()
    if service_name not in JDBC_SERVERS:
        known_services = ', '.join(list(JDBC_SERVERS.keys()))
        msg = 'Service ({}) not found in list ({})'.format(service_name, known_services)
        raise ServiceNotFoundException(msg)

    db_type = JDBC_SERVERS[service_name]['type']
    if db_type not in JDBC_DRIVERS:
        known_types = ', '.join(list(JDBC_DRIVERS.keys()))
        raise ServiceNotFoundException('Database type ({}) not found in list ({})'.format(db_type, known_types))

    url = JDBC_DRIVERS[db_type]['url'] + JDBC_SERVERS[service_name]['url']
    if 'attr' in JDBC_DRIVERS[db_type]:
        url += JDBC_DRIVERS[db_type]['attr']
    if db_type == 'oracle':
        schema = user_name
    else:
        schema = JDBC_SERVERS[service_name]['url'].split('/')[-1]

    if (db_type == 'sqlite') and (credentials is not None):
        if os.path.isdir(url):
            url = os.path.join(url, credentials[0])
        credentials = None
    return credentials, db_type, schema, url, verified_boolean(JDBC_DRIVERS[db_type].get('escape', False))


def parse_dummy_login(login_or_driver_type: str):
    """
    Parse the input string against the configuration, to retrieve the database type. Not intended for a real
    connection.

    @param login_or_driver_type: str login credentials in oracle format: username/password@service, or just the
        driver type as defined in config.yml.
    @return: Tuple (database type, column_escape option)
    """
    db_type = LOGIN_ALIAS.get(login_or_driver_type, login_or_driver_type)
    if '@' in db_type:
        db_type = db_type.split('@')[-1]
    db_type = db_type.strip().lower()

    if db_type in JDBC_SERVERS:
        db_type = JDBC_SERVERS[db_type]['type']
    elif db_type not in JDBC_DRIVERS:
        known_types = ', '.join(list(JDBC_DRIVERS.keys()))
        msg = 'Database type ({}) not found in list ({})'.format(db_type, known_types)
        raise ServiceNotFoundException(msg)
    return db_type, verified_boolean(JDBC_DRIVERS[db_type].get('escape', False))


def print_info():
    """
    Human-readable output to stdout of the defined servers and aliases
    as defined in config.yml
    """
    print("Known servers:")
    for k, s in JDBC_SERVERS.items():
        url = s['url']
        if ('oracle' == s['type']) and ('DESCRIPTION' in url.strip().upper()):
            url = 'TNS'
        print("   - {:<20} {:<15} {}".format(k, s['type'], url))
    print("Known aliases:")
    rec = regex.compile('/.*@')
    for k, a in LOGIN_ALIAS.items():
        print("   - {:<20} {}".format(k, rec.sub('@', a)))


# load the configuration file
configuration = dict()
count_cfg_files = 0
for fn in [f for f in CFG_FILES if os.path.isfile(f)]:
    try:
        with open(fn) as fh:
            cfg = yaml.load(fh, Loader=yaml.FullLoader)
            configuration = merge(cfg, configuration)
            count_cfg_files += 1
    except PermissionError:
        pass
    except yaml.YAMLError as pe:
        LOGGER.error('Cannot parse the configuration file {}: {}'.format(fn, pe))
        sys.exit(1)

if (len(configuration) == 0) or (count_cfg_files <= 1):
    # count_cfg_files == 1 implies that only the default example inside the installed
    # module was found.
    # Action: create a home cfg directory
    from stat import S_IREAD, S_IWRITE, S_IEXEC

    home_cfg_dir = os.path.join(HOME_DIR, MOD_NAME)
    if not os.path.isdir(home_cfg_dir):
        try:
            os.mkdir(home_cfg_dir, S_IREAD | S_IWRITE | S_IEXEC)
        except (PermissionError, FileNotFoundError, FileExistsError):
            home_cfg_dir = None
        if home_cfg_dir is None:
            LOGGER.critical('FATAL: no configuration found. Looked for:\n- ' + '\n- '.join(CFG_FILES))
            sys.exit(1)
        else:
            from shutil import copyfile

            src_file = os.path.join(MODULE_DIR, 'config-example.yml')
            for trg_file in [os.path.join(home_cfg_dir, f) for f in ['config-example.yml', 'config.yml']]:
                copyfile(src_file, trg_file)
                os.chmod(trg_file, S_IREAD | S_IWRITE)
            LOGGER.info('Sample configuration files installed in: ' + home_cfg_dir)

# add environment variables
for var_name, value in configuration.get('env', {}).items():
    os.environ[var_name] = str(value)

# encryption of db passwords
CFG_ENCRYPT = configuration.get('encrypt', True)
if not isinstance(CFG_ENCRYPT, bool):
    CFG_ENCRYPT = True

# parse the driver section
# download new drivers, if required.
JDBC_DRIVERS = dict()
for jdbc_type, cfg in configuration.get('drivers', {}).items():
    if 'jar' not in cfg:
        LOGGER.error('Error in definition of driver type {}: jar file not specified.'.format(jdbc_type))
    elif 'class' not in cfg:
        LOGGER.error('Error in definition of driver type {}: driver class not specified.'.format(jdbc_type))
    elif 'url' not in cfg:
        LOGGER.error('Error in definition of driver type {}: url not specified.'.format(jdbc_type))
    elif os.path.isfile(cfg['jar']):
        JDBC_DRIVERS[jdbc_type] = cfg
    else:
        if cfg['jar'].lower().startswith('http://') or cfg['jar'].lower().startswith('https://'):
            url_source = True
            jar_file = cfg['jar'].split('/')[-1]
        else:
            url_source = False
            jar_file = os.path.basename(cfg['jar'])
        for fn in [os.path.join(d, 'lib', jar_file) for d in CFG_DIRS]:
            if os.path.isfile(fn):
                JDBC_DRIVERS[jdbc_type] = merge({'jar': fn}, cfg)
                break
        if (jdbc_type not in JDBC_DRIVERS) and url_source:
            for lib_dir in [os.path.join(d, 'lib') for d in [MODULE_DIR, os.path.join(HOME_DIR, MOD_NAME)] if
                            os.path.isdir(d)]:
                if not os.path.isdir(lib_dir):
                    try:
                        os.mkdir(lib_dir, 0o755)
                    except (PermissionError, FileNotFoundError, FileExistsError):
                        lib_dir = None
                if lib_dir:
                    dst_file = os.path.join(lib_dir, jar_file)
                    try:
                        urlretrieve(cfg['jar'], dst_file)
                        LOGGER.info('{} downloaded to: {}'.format(jar_file, lib_dir))
                    except (HTTPError, URLError) as http_error:
                        LOGGER.error('Failed to retrieve {}: {}'.format(cfg['jar'], http_error))
                    if os.path.isfile(dst_file):
                        JDBC_DRIVERS[jdbc_type] = merge({'jar': dst_file}, cfg)
                        break
        if jdbc_type not in JDBC_DRIVERS:
            LOGGER.warning('No driver found for: ' + jdbc_type)

JAR_FILES = []
for cfg in JDBC_DRIVERS.values():
    if cfg['jar'] not in JAR_FILES:
        JAR_FILES.append(cfg['jar'])

# retrieve defined services
JDBC_SERVERS = dict()
for service, cfg in configuration.get('servers', {}).items():
    if 'type' not in cfg:
        LOGGER.error('Error in definition of service {}: database type not specified.'.format(service))
    elif cfg['type'] not in JDBC_DRIVERS:
        LOGGER.error('Error in definition of service {}: unknown driver type {}.'.format(service, cfg['type']))
    elif 'url' not in cfg:
        LOGGER.error('Error in definition of service {}: url not specified.'.format(service))
    else:
        JDBC_SERVERS[service.lower()] = cfg

# extract servers from ORACLE tnsnames.ora (if exists)
if 'oracle' in JDBC_DRIVERS and (os.environ.get('IGNORE_TNS', '').lower() not in ['1', 'true']):
    tns = os.environ.get('TNS', '')
    if (not os.path.isfile(tns)) and ('ORACLE_HOME' in os.environ.keys()):
        tns = os.path.join(os.environ['ORACLE_HOME'], 'network', 'admin', 'tnsnames.ora')
    if os.path.isfile(tns):
        try:
            import regex
        except ImportError:
            regex = None
            LOGGER.warning('''tnsnames.ora can only be parsed if the regex module is installed.
Use 'pip install regex' to install.
This message may be removed by setting the environment variable IGNORE_TNS to true 
(either in the system, or in the env section of the configuration file).''')

        if regex:
            with open(tns, 'r') as fh:
                tnsnames = fh.read()

            # strip empty and comment lines
            lines = []
            for line in tnsnames.splitlines():
                if (len(line.strip()) > 0) and not line.strip().startswith('#'):
                    lines.append(line)
            tnsnames = "\n".join(lines)

            r = regex.compile(r'(\(([^())]|(?R))*\))')
            while True:
                m = r.search(tnsnames, regex.MULTILINE)
                if m:
                    lbl = tnsnames[:m.start()].split('=')[0].strip()
                    lbl = lbl.lower()
                    if lbl not in JDBC_SERVERS:
                        JDBC_SERVERS[lbl] = {
                            'type': 'oracle',
                            'url': tnsnames[m.start():m.end()]
                        }
                    tnsnames = tnsnames[m.end():]
                else:
                    break

# Store connection aliases
LOGIN_ALIAS = configuration.get('alias', {})
