import os

from setuptools import setup, find_packages

'''
To install: pip3 install .
see man pip3
'''

version_dict = dict()
version_file = os.path.join(os.path.dirname(__file__), 'lwetl', 'version.py')
with open(version_file, 'r') as vf:
    exec(vf.read(), version_dict)

__version__ = version_dict.get('__version__', '0.0.0')
try:
    int(__version__.split('.')[-1])
except ValueError:
    __version__ = '.'.join(__version__.split('.')[:-1])

setup(
    name='lwetl',
    description='Access multiple DB servers simultaneously with JDBC (using JayDeBeApi)',
    keywords='database client jdbc scripting',
    version=__version__,
    url='https://github.com/rene-bakker-it/lwetl',
    author='R.J. Bakker',
    author_email='rene.bakker.it@gmail.com',
    license='GNU LESSER GENERAL PUBLIC LICENSE',
    python_requires='>=3',
    packages=find_packages(exclude=["tests", "examples"]),
    package_data={'': ['../config.yml', '../config-example.yml']},
    install_requires=[
        'jaydebeapi', 'psutil', 'pyyaml', 'openpyxl', 'cryptography',  'regex', 'requests', 'python-dateutil' ],
    entry_points={
        'console_scripts': [
            'sql-query=lwetl.programs.sql_query.main:main',
            'db-copy=lwetl.programs.db_copy.main:main',
            'table-cardinality=lwetl.programs.table_cardinality.main:main',
            'lwetl-security=lwetl.programs.lwetl_security.main:main'
        ],
    },
)
