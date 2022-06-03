"""
    Add some runtime statistics to monitor resource usage
"""
import os
import psutil

from collections import OrderedDict
from datetime import datetime, timedelta
from time import time

from .utils import is_empty

MARKED_CONNECTIONS = OrderedDict()


def time_to_string(time_value: float) -> str:
    """
    Internal function, which converts a fload into a string time duration
    @param time_value: float duration in seconds
    @return: duration in format h:mm:ss
    """
    rtime = int(time_value)
    nanos = int(round(1000.0*(time_value - rtime)))

    seconds = rtime % 60
    minutes = int((rtime - seconds) / 60) % 60
    hours = int((rtime - (60 * minutes) - seconds) / 3600)
    return '{:02d}:{:02d}:{:02d}.{:03d}'.format(hours, minutes, seconds, nanos)


def timedelta_to_string(dt: timedelta) -> str:
    """
    @return timedelta as a string in the format HH:MM:SS
    """
    s = str(dt).split('.')[0]
    if len(s.split(':')[0]) == 1:
        s = '0' + s
    return s


class Statistics:
    def __init__(self):
        self.start_time = datetime.now()
        self.query_time = 0.0
        self.row_count = 0
        self.exec_count = 0

    def add_query_time(self, dt: float):
        """
        Add query time to the global counter
        @param dt: float - time to add (seconds)
        @return the new query time
        """
        self.query_time += dt
        return self.query_time

    def add_row_count(self, n: int = 1):
        """
        Add to the global commit counter
        @param n: int counter to add
        @return the new commit count
        """
        self.row_count += n
        return self.row_count

    def add_exec_count(self, n: int = 1):
        """
        Add to the global exec counter
        @param n: int counter to add
        @return the new exec count
        """
        self.exec_count += n
        return self.exec_count

    def get_query_time(self) -> str:
        """
        @return: str the query time as a string in the format HH:MM:SS
        """
        return time_to_string(self.query_time)

    def get_statistics(self, tag: str = '') -> str:
        return '+ {:9<}   {:11<},  nq = {:8d}, rc = {:8d}'.format(
            'db ' + tag + ':', self.get_query_time(), self.exec_count, self.row_count)


GLOBAL_STATISTICS = Statistics()


class RuntimeStatistics(Statistics):
    def __init__(self):
        super(RuntimeStatistics, self).__init__()
        self.t0 = 0.0

    def __enter__(self):
        self.t0 = time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.add_query_time(time() - self.t0)

    def add_query_time(self, dt: float):
        """
        Add query time to the global counter
        @param dt: float - time to add (seconds)
        @return the new query time
        """
        GLOBAL_STATISTICS.add_query_time(dt)
        return super(RuntimeStatistics, self).add_query_time(dt)

    def add_row_count(self, n: int = 1):
        """
        Add to the global commit counter
        @param n: int counter to add
        @return the new commit count
        """
        GLOBAL_STATISTICS.add_row_count(n)
        return super(RuntimeStatistics, self).add_row_count(n)

    def add_exec_count(self, n: int = 1):
        """
        Add to the global exec counter
        @param n: int counter to add
        @return the new exec count
        """
        GLOBAL_STATISTICS.add_exec_count(n)
        return super(RuntimeStatistics, self).add_exec_count(n)


def tag_connection(tag: str, jdbc):
    """
    Tag a connection for statistics collection
    @param tag: str name of the tag
    @param jdbc: the connection to monitor
    """
    global MARKED_CONNECTIONS

    if is_empty(tag):
        raise ValueError('Tag not specified')
    if type(jdbc).__name__ != 'Jdbc':
        raise TypeError('The connection must be of the type Jdbc. Found: ' + type(jdbc).__name__)
    MARKED_CONNECTIONS[tag] = jdbc


def get_execution_statistics() -> str:
    current_process = psutil.Process(os.getpid())
    cpu_info = current_process.cpu_times()

    str_list = [
        'Execution statistics:',
        '+ Total time: {}'.format(timedelta_to_string(datetime.now() - GLOBAL_STATISTICS.start_time)),
        '+ CPU user    {}'.format(time_to_string(cpu_info.user)),
        '+ CPU system: {}'.format(time_to_string(cpu_info.system)),
        GLOBAL_STATISTICS.get_statistics('TOTAL')]
    for tag, jdbc in MARKED_CONNECTIONS.items():
        str_list.append(jdbc.get_statistics(tag))
    return "\n".join(str_list)
