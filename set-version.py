#!/usr/bin/env python

import argparse
import os
import sys

try:
    import git
except ImportError:
    print("git module not found. Try: pip install gitpython (development use only).")
    sys.exit(1)

version_file = os.path.join(os.path.dirname(__file__), 'lwetl', 'version.py')
repo = git.Repo(search_parent_directories=True)

active_branch = repo.active_branch
sha = repo.head.object.hexsha

version_dict = dict()
try:
    with open(version_file, 'r') as vf:
        exec(vf.read(), version_dict)
except (FileNotFoundError, PermissionError):
    pass
vlist = version_dict.get('__version__', '').split('.')
while len(vlist) < 4:
    vlist.append('0')

for x in range(3):
    try:
        vlist[x] = int(vlist[x])
    except ValueError:
        vlist[x] = 0
vlist[3] = '%s-%s' % (active_branch, sha)


def check_positive(value):
    try:
        ivalue = int(value)
    except ValueError:
        ivalue = -1
    if ivalue <= 0:
        raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
    return ivalue


parser = argparse.ArgumentParser(
    prog='set-version',
    description='Set version tag for this module, including git tag.',
    formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument('--major', nargs='?', const=vlist[0] + 1, type=check_positive,
                    help='Increase the major version number (or specifiy). ' +
                         'Resets the minor version number and revision number to 0.')

parser.add_argument('--minor', nargs='?', const=vlist[1] + 1, type=check_positive,
                    help='Increase the minor version number (or specifiy). ' +
                         'Resets the revision number to 0.')

parser.add_argument('--revision', nargs='?', const=vlist[2] + 1, type=check_positive,
                    help='Increase the revision number (or specifiy). ')

parser.add_argument('-p','--push',action='store_true',
                    help='Push a tag to the remove repository.')

args = parser.parse_args()

if args.major:
    vlist[0] = args.major
    vlist[1] = 0
    vlist[2] = 0
elif args.minor:
    vlist[1] = args.minor
    vlist[2] = 0
elif args.revision:
    vlist[2] = args.revision

version_str = '.'.join([str(v) for v in vlist[:4]])
with open(version_file, 'w') as f:
    print("__version__ = '%s'" % version_str,file=f)

if args.push:
    tag = 'V' + version_str
    git_tag = repo.create_tag(tag,message='Auto-generated tag "{0}"'.format(tag))
    repo.remotes.origin.push(git_tag)

print('Version set to: ' + version_str)
