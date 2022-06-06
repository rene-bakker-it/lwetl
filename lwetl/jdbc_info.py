import sys

from jpype import isJVMStarted, startJVM, shutdownJVM, getDefaultJVMPath, JPackage
from lwetl.config_parser import parse_login, JDBC_DRIVERS, JAR_FILES


class JdbcInfo:
    """
    Print information on the JDBC driver specified by the login credentials
    """

    def __init__(self, login: str):
        self.login = login
        self.credentials, self.type, self.schema, self.url, self.always_escape = parse_login(login)

    # noinspection PyPep8Naming
    def __call__(self, *args, **kwargs):
        def fprint(fstream, fmt: str, *fargs):
            print(fmt.format(*fargs), file=fstream)

        def print_description(description, m_width: int):

            if description is None:
                return ''
            if (' ' not in description) or len(description) < m_width:
                return description
            else:
                lines = []
                line = []
                for word in description.split():
                    if len(' '.join(line)) + len(word) > m_width:
                        lines.append(' '.join(line))
                        line = []
                    line.append(word)
                if len(line) > 0:
                    lines.append(' '.join(line))
            return "\n{:75}".format('').join(lines)

        no_errors = True

        file = kwargs.get('file', sys.stdout)
        max_width = kwargs.get('max_width', 55)

        started_by_me = False
        if not isJVMStarted():
            startJVM(getDefaultJVMPath(), "-Djava.class.path={}".format(':'.join(JAR_FILES)))
            started_by_me = True

        driver_class = JDBC_DRIVERS[self.type]['class']
        print('Info for: {} ({})'.format(self.type, driver_class), file=file)
        print('- URL ----------------------------------------------------------------------')
        print(self.url)
        print('----------------------------------------------------------------------------')

        try:
            properties = JPackage('java').util.Properties()
            if self.credentials is not None:
                if isinstance(self.credentials, str):
                    properties.put('user', self.credentials)
                else:
                    properties.put('user', self.credentials[0])
                    properties.put('password', self.credentials[1])

            domains = driver_class.split('.')
            Driver = JPackage(domains.pop(0))
            for domain in domains:
                Driver = getattr(Driver, domain)
            driver = Driver()

            meta_data = JPackage('java').sql.DriverManager.getConnection(self.url, properties).getMetaData()

            fprint(file, '{:.<20} {}.{}', 'Version', driver.getMajorVersion(), driver.getMinorVersion())
            fprint(file, '{:.<20} {}', 'JDBC compliant', driver.jdbcCompliant())
            fprint(file, '{:.<20} {}', 'Product name', meta_data.getDatabaseProductName())
            fprint(file, '{:.<20} {}', 'Product version', meta_data.getDatabaseProductVersion())
            fprint(file, '{:.<20} {}', 'Driver name', meta_data.getDriverName())
            fprint(file, '{:.<20} {}', 'Driver version', meta_data.getDriverVersion())

            for x, info in enumerate(driver.getPropertyInfo(self.url, properties), start=1):
                val = info.value if info.value else 'ndef'
                required = 'R' if info.required else ''
                if info.description is None:
                    fprint(file, "{:3}. {:2} {:.<60} {}", x, required, info.name, val)
                elif len(info.description) > 21:
                    fprint(file, "{:3}. {:2} {:.<60} {}\n{:74} {}",
                           x, required, info.name, val, '', print_description(info.description, max_width))
                else:
                    fprint(file, '{:3}. {:2} {:.<60} {:20} | {}', x, required, info.name, val,
                           print_description(info.description, max_width))
                if info.choices:
                    fprint(file, '{:74} {}'.format('choices: ', ', '.join(info.choices)))

        except Exception as e:
            print('ERROR retrieving JDBC information.', file=sys.stderr)
            print(e, file=sys.stderr)
            no_errors = False
        if started_by_me:
            shutdownJVM()
        return no_errors
