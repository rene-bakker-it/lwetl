"""
    pytest general

    - Defines the test directory and test output directory
    - loads the test configuration from sql_statements.yml in the script directory
"""

import os
import pytest

from yaml import load as yaml_load

from .generate_complex_utf8 import I_CAN_EAT_GLASS

TEST_DIR = os.path.dirname(os.path.realpath(__file__))
OUTPUT_DIR = os.path.join(TEST_DIR, 'output')

# make sure the test output dir exists
if not os.path.isdir(OUTPUT_DIR):
    if os.path.exists(OUTPUT_DIR):
        os.remove(OUTPUT_DIR)
    os.mkdir(OUTPUT_DIR)

# load the test configuration
cfg_error = None
try:
    cfg_file = os.path.join(TEST_DIR, 'sql_statements.yml')
    with open(cfg_file, 'r') as f:
        TEST_CONFIGURATION = yaml_load(f)
except Exception as e:
    cfg_error = e
else:
    keys = list(TEST_CONFIGURATION.keys())
    for key in keys:
        if TEST_CONFIGURATION[key].get('disabled',False):
            del TEST_CONFIGURATION[key]
    print('\nLoaded the test configuratin from: ' + cfg_file)
    print('Drivers to test: ' + ', '.join(TEST_CONFIGURATION.keys()))


if cfg_error is not None:
    pytest.exit('\nFATAL ERROR - initialization of tests failed ' + str(cfg_error))
