import jaydebeapi


class ServiceNotFoundException(RuntimeError):
    """
    Thrown when the configured database server cannot be configured.
    """
    pass


class DriverNotFoundException(RuntimeError):
    """
    Thrown when the JDBC driver cannot be loaded into the JVM
    """

    def __init__(self, message):
        super(DriverNotFoundException, self).__init__('Jar file for JDBC not found: ' + message)


class SQLExcecuteException(Exception):
    """
    Thrown when the SQL cannot be parsed
    """
    pass


class DatabaseError(jaydebeapi.DatabaseError):
    pass


class CommitException(Exception):
    """
    Thrown when jdbc.commmit() fails
    """
    pass


class UnsupportedDatabaseTypeException(Exception):
    pass


class EmptyFileError(Exception):
    """
    Thrown if an input data buffer is empty
    """
    pass


class DecryptionError(Exception):
    """
    Thrown data cannot be decrypted
    """
    pass
