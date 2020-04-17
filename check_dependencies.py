#!/usr/bin/env python3

# just import all python3 modules used by osmo-gsm-tester to make sure they are
# installed.



import os
import sys
import argparse
import pprint
import subprocess

feature_module_map = {
    'powersupply_intellinet' : ['powersupply_intellinet'],
    'powersupply_sispm' : ['powersupply_sispm'],
    'rfemu_amarisoftctrl': ['rfemu_amarisoftctrl'],
    'rfemu_minicircuits': ['rfemu_minicircuits'],
}

def skip_features_to_skip_modules(skip_features):
    skip_obj_modules = []

    for skip_feature in skip_features:
        if skip_feature not in feature_module_map:
            raise Exception('feature %s doesn\'t exist!' % skip_feature)
        for skip_module in feature_module_map[skip_feature]:
            skip_obj_modules.append(skip_module)
    return skip_obj_modules

def import_runtime_dependencies():
    # we don't have any right now, but in the future if we import a module during runtime (eg inside a function), then we need to place it here:
    # import foobar
    pass

def import_all_py_in_dir(rel_path, skip_modules=[]):
    selfdir = os.path.dirname(os.path.abspath(__file__))
    dir = os.path.join(selfdir, rel_path)
    print('importing files in directory %s' % dir)
    for entry in os.listdir(dir):
        full_entry = os.path.join(selfdir, rel_path, entry)
        if not os.path.isfile(full_entry):
            if args.verbose:
                print('skipping entry %s' % full_entry)
            continue
        if not full_entry.endswith('.py'):
            if args.verbose:
                print('skipping file %s' % full_entry)
            continue
        modulename =  entry[:-3]
        if modulename in skip_modules:
            if args.verbose:
                print('skipping module %s' % modulename)
            continue
        modulepath = rel_path.replace('/', '.') + '.' + modulename
        print('importing %s' % modulepath)
        __import__(modulepath, globals(), locals())

def get_module_names():
    all_modules=sys.modules.items()
    all_modules_filtered = {}
    for mname, m in all_modules:
        if not hasattr(m, '__file__'):
            continue # skip built-in modules
        if mname.startswith('_'):
            continue # skip internal modules
        if mname.startswith('src.osmo_') or 'osmo_gsm_tester' in mname or 'osmo_ms_driver' in mname:
            continue # skip our own local modules
        mname = mname.split('.')[0] # store only main module
        if m not in all_modules_filtered.values():
            all_modules_filtered[mname] = m
    return all_modules_filtered

def print_deb_packages(modules):
    packages_deb = []
    modules_err = []
    for mname, m in modules.items():
        proc = subprocess.Popen(["dpkg", "-S", m.__file__], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        outs, errs = proc.communicate()
        if args.verbose:
            print('out: %s, err: %s' %(outs, errs))
        if len(errs): # error -> package not found (installed through pip?)
            modules_err.append((mname, errs.decode('utf-8')))
        elif len(outs):
            outs = outs.decode('utf-8')
            outs = outs.split()[0].rstrip(':') # first part is debian package name
            if not outs in packages_deb:
                packages_deb.append(outs)
        else:
            print('WARNING: dpkg returns empty!')

    print('Debian packages:')
    for pkgname in packages_deb:
        print("\t" + pkgname)
    print()
    print('Modules without debian package (pip or setuptools?):')
    for mname, err in modules_err:
        print("\t" + mname.ljust(20) + " [" + err.rstrip() +"]")

parser = argparse.ArgumentParser(epilog=__doc__, formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('-s', '--skip-feature', dest='skip_features', choices=feature_module_map.keys(), action='append',
                    help='''All osmo-gsm-tester features not used by the user running the script''')
parser.add_argument('-p', '--distro-packages', dest='distro_packages', action='store_true',
        help='Print distro packages installing modules')
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
        help='Print a lot more information')
args = parser.parse_args()

skip_obj_modules = skip_features_to_skip_modules(list(args.skip_features or []))

print('Skip checking modules: %r' % skip_obj_modules)

# We need to add it for cross-references between osmo_ms_driver and osmo_gsm_tester to work:
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src/'))
import_all_py_in_dir('src/osmo_ms_driver')
import_all_py_in_dir('src/osmo_gsm_tester/core')
import_all_py_in_dir('src/osmo_gsm_tester/obj', skip_obj_modules)
import_all_py_in_dir('src/osmo_gsm_tester')
import_runtime_dependencies()
print('Importing dependencies ok, all installed')

print('Retreiving list of imported modules...')
modules = get_module_names()
if args.verbose:
    for mname, m in modules.items():
        print('%s --> %s' %(mname, m.__file__))

if args.distro_packages:
    print('Generating distro package list from imported module list...')
    print_deb_packages(modules)
