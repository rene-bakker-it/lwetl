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

    def __call__(self, *args, **kwargs):
        no_errors = True

        def print_description(description,max_width):
            if description is None:
                return ''
            if (' ' not in description) or len(description) < max_width:
                return description
            else:
                lines = []
                line = []
                for word in description.split():
                    if len(' '.join(line)) + len(word) > max_width:
                        lines.append(' '.join(line))
                        line = []
                    line.append(word)
                if len(line)> 0:
                    lines.append(' '.join(line))
            sep = '\n%75s' % ''
            return sep.join(lines)

        file = kwargs.get('file',sys.stdout)
        max_width = kwargs.get('max_width',55)

        started_by_me = False
        if not isJVMStarted():
            startJVM(getDefaultJVMPath(), "-Djava.class.path=%s" % ':'.join(JAR_FILES))
            started_by_me = True

        driver_class = JDBC_DRIVERS[self.type]['class']
        print('Info for: %s (%s)' % (self.type, driver_class),file=file)
        print('- URL ----------------------------------------------------------------------')
        print(self.url)
        print('----------------------------------------------------------------------------')

        try:
            properties = JPackage('java').util.Properties()
            if self.credentials is not None:
                if isinstance(self.credentials, str):
                    properties.put('user', self.credentials);
                else:
                    properties.put('user', self.credentials[0]);
                    properties.put('password', self.credentials[1]);

            domains = driver_class.split('.')
            Driver = JPackage(domains.pop(0))
            for domain in domains:
                Driver = getattr(Driver, domain)
            driver = Driver()

            meta_data = JPackage('java').sql.DriverManager.getConnection(self.url, properties).getMetaData()

            print('Version:         %d.%d' % (driver.getMajorVersion(), driver.getMinorVersion()),file=file)
            print('JDBC compliant:  %s' % driver.jdbcCompliant(),file=file)

            print('Product name:    %s' % meta_data.getDatabaseProductName(),file=file)
            print('Product version: %s' % meta_data.getDatabaseProductVersion(),file=file)
            print('Driver name:     %s' % meta_data.getDriverName(),file=file)
            print('Driver version:  %s' % meta_data.getDriverVersion(),file=file)

            indx = 0
            for info in driver.getPropertyInfo(self.url, properties):
                indx += 1
                if (info.value is not None) and (len(info.value) > 21):
                    print('%3d. %2s %-45s %s' % (indx, info.required, info.name, info.value),file=file)
                    print('%74s %s' % ('', print_description(info.description,max_width)),file=file)
                else:
                    print('%3d. %2s %-45s %-20s %s' %
                          (indx, info.required, info.name, info.value,
                           print_description(info.description,max_width)),file=file)
                if info.choices:
                    print('%74s %s' % ('choices: ', ', '.join(info.choices)),file=file)

        except Exception as e:
            print('ERROR retrieving JDBC information.',file=sys.stderr)
            print(e,file=sys.stderr)
            no_errors = False
        if started_by_me:
            shutdownJVM()
        return no_errors
