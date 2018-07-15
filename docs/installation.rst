Installation
************

The module depends on Jpype1_ and optionally regex_. Both need access to a compiler for installation, if installed with ``pip``.

*Note:*
  the regex_ module is used to parse the ORACLE connection configuration (``tnsnames.ora``). If you do not intend to access ORACLE through the settings of this file, the module may be ignored.

Operating Systems
=================

Linux
-----

The module may in installed in a python virtual environment, for example like:

::

        virtualenv --no-site-packages -p /usr/bin/python3 $HOME/my_virtual_envs/jdbc
        source $HOME/my_virtual_envs/jdbc/bin/activate

The module can be installed with ``pip`` from github_:

::

        pip install git+https://github.com/rene-bakker-it/lwetl.git

Alternatively the repository may first be cloned:

::

        git clone https://github.com/rene-bakker-it/lwetl.git
        cd lwetl
        pip install .

Windows
-------

From the Anaconda_ command prompt:

::

        conda install -c conda-forge jpype1
        conda install regex

        (assuming the lwetl package in the current directory):
        pip install .

Dependencies
============

The module depends on the following packages:

- et-xmlfile_,
- JayDeBeApi_,
- jdcal_,
- Jpype1_,
- openpyxl_,
- psutil_,
- PyYAML_, and
- regex_ (optionally).

Tests in the ``tests`` directory are based on pytest_, whichalso requires: pytest-html_, pytest-metadata_, and pytest-progress_.

Documentation in the ``docs`` directory is based on Sphinx_ and the `read the docs`_ theme.

Developers, who want to use the utility function ``set-version.py`` in the main directectory of the source code, should also install GitPython_.


.. _Jpype1: https://pypi.python.org/pypi/JPype1
.. _regex: https://pypi.python.org/pypi/regex
.. _github: https://github.com/rene-bakker-it/lwetl.git
.. _Anaconda: https://www.anaconda.com/download/#windows
.. _et-xmlfile: https://pypi.python.org/pypi/et_xmlfile
.. _JayDeBeApi: https://pypi.python.org/pypi/JayDeBeApi
.. _jdcal: https://pypi.python.org/pypi/jdcal
.. _openpyxl: https://openpyxl.readthedocs.io/en/default
.. _psutil: https://pypi.python.org/pypi/psutil
.. _PyYAML: https://pypi.python.org/pypi/PyYAML
.. _pytest: https://pypi.python.org/pypi/pytest
.. _pytest-html: https://pypi.python.org/pypi/pytest-html
.. _pytest-metadata: https://pypi.python.org/pypi/arcpy_metadata
.. _pytest-progress: https://pypi.python.org/pypi/pytest-progres
.. _Sphinx: http://www.sphinx-doc.org/en/stable
.. _`read the docs`: https://github.com/rtfd/sphinx_rtd_theme
.. _GitPython: https://pypi.python.org/pypi/GitPython
