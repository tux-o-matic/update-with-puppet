#!/usr/bin/env python

from __future__ import print_function
import argparse
import json
import os
import platform
import sys

__author__ = 'Benjamin Merot <benjamin.merot@dsg.dk>'
__copyright__ = "Copyright (C) 2017 Dansk Supermarked Group"
__license__ = "GPL version 3"

package_provider_name = 'yum'

multilib_pkg = {'glibc': ['i686', 'x86_64'], 'glibc-devel': ['i686', 'x86_64'], 'gnutls': ['x86_64'],
                'libgcc': ['i686', 'x86_64'], 'libstdc++': ['i686', 'x86_64']}
multi_ver_pkg = ['kernel', 'kernel-core', 'kernel-devel', 'kernel-modules']


def get_linux_dist():
    if sys.version_info[0] >= 3 and sys.version_info[1] > 6:
        raise NotImplementedError  # 'distro' module returns different names
    else:
        return platform.linux_distribution()


def query_yum(repos_filter):
    dist = get_linux_dist()
    if dist[0] == 'Fedora' and int(dist[1]) >= 23:
        import dnf
        pkg_provider = dnf.Base()
        pkg_provider.cleanMetadata()
        pkg_provider.read_all_repos()
        pkg_provider.fill_sack()
        package_list = list(pkg_provider.sack.query().upgrades())
        global package_provider_name
        package_provider_name = 'dnf'
    else:
        import yum
        pkg_provider = yum.YumBase()
        pkg_provider.setCacheDir()
        pkg_provider.cleanMetadata()
        if repos_filter:
            for repo in repos_filter.split(','):
                pkg_provider.repos.enableRepo(repo)
            pkg_provider.repos.doSetup()
        package_list = pkg_provider.doPackageLists(pkgnarrow='updates', patterns='', ignore_case=True)

    clean_list = []
    try:
        for rpm in package_list:
            if repos_filter == '' or rpm.repo.id in repos_filter:
                clean_list.append({'name': rpm.name, 'repo': rpm.repo.id, 'version': rpm.version + '-' + rpm.release})
    except:
        print('Have you thought about exporting the http_proxy/https_proxy ENV?')

    return clean_list


def get_package_resource(pkg, require, filter_repo, install_from_cache):
    """
    :type pkg: dict The package payload.
    :type require: bool Adds the origin repository as a required Puppet resource.
    :type filter_repo: bool Filters the package repository to target a specific source.
    :type install_from_cache: bool Marks the resource as meant to be installed from cache only.
    """
    if pkg['name'] in multi_ver_pkg:
        pkg['name'] += '-' + pkg['version']
        pkg['version'] = 'installed'
    pkg_resource = {pkg['name']: {'ensure': pkg['version']}}
    if require:
        pkg_resource[pkg['name']]['require'] = 'YumRepo[' + pkg['repo'] + ']'
    if filter_repo or install_from_cache:
        pkg_resource[pkg['name']]['install_options'] = []
    if filter_repo:
        pkg_resource[pkg['name']]['install_options'].append({'--disablerepo': '*', '--enablerepo': pkg['repo']})
    if install_from_cache:
        pkg_resource[pkg['name']]['install_options'].append('--cacheonly')
    return pkg_resource


def build_hash(pkg_list, wrap, require, filter_repo, install_from_cache, root_key):
    """
    :type pkg_list: list A list of package resource dict.
    :type wrap: bool Place all resources under a common root key.
    :type require: bool Adds the origin repository as a required Puppet resource.
    :type filter_repo: bool Filters the package repository to target a specific source.
    :type install_from_cache: bool Marks the resource as meant to be installed from cache only.
    """
    resources = {}
    if wrap:
        resources.update({root_key: {}})
        for rpm in pkg_list:
            resources[root_key].update(get_package_resource(rpm, require, filter_repo, install_from_cache))
    else:
        for rpm in pkg_list:
            resources.update(get_package_resource(rpm, require, filter_repo, install_from_cache))

    return resources


def merge_resources(existing_file, new_resources, root_key):
    with open(existing_file) as json_file:
        existing_resources = json.load(json_file)
        if root_key in existing_resources:
            merged_resources = existing_resources[root_key]
        else:
            merged_resources = existing_resources

        if root_key in new_resources:
            new_resources = new_resources[root_key]

        for key in new_resources:
            if key in merged_resources:
                if merged_resources[key]['ensure'] not in [new_resources[key]['ensure'], 'installed']:
                    merged_resources[key]['ensure'] = new_resources[key]['ensure']
            else:
                merged_resources.update({key: new_resources[key]})

        if root_key in existing_resources:
            merged_resources = {root_key: merged_resources}
        return merged_resources


def get_pkg_fqdn(pkg_name, pkg_version):
    try:
        if conf.getboolean('Package', 'install_multilib') and conf.getboolean('Package', 'install_multilib'):
            if pkg_name in multilib_pkg:
                exec_cmd = ''
                for lib_variant in multilib_pkg[pkg_name]:
                    exec_cmd += ' ' + pkg_name + '-' + pkg_version + '.' + lib_variant
                return exec_cmd
    except Exception as e:
        pass
    return ' ' + pkg_name + '-' + pkg_version


def bundle_package(resources, root_key, package_bundle):
    packages = resources
    execs = {}

    if root_key in resources:
        packages = resources[root_key]

    for pkg in packages:
        for bundle in package_bundle:
            if pkg in package_bundle[bundle]:
                exec_key = 'update_' + bundle
                if exec_key in execs:
                    execs[exec_key]['command'] += get_pkg_fqdn(pkg, packages[pkg]['ensure'])
                else:
                    command = package_provider_name + ' -y install' + get_pkg_fqdn(pkg, packages[pkg]['ensure'])
                    execs.update({exec_key: {'command': command, 'path': '/bin:/usr/bin/',
                                             'unless': 'rpm -q ' + pkg + '-' + packages[pkg]['ensure']}})
                packages[pkg]['require'] = 'Exec[' + exec_key + ']'

    if len(execs) > 0:
        return {root_key: packages, 'execs': execs}
    else:
        return {root_key: packages}


def strip_resources(base_file, computed_file, root_key):
    with open(base_file) as base_json_file:
        base_resources = json.load(base_json_file)
        with open(computed_file) as computed_json_file:
            computed_resources = json.load(computed_json_file)
            if root_key in computed_resources:
                stripped_resourced = dict(computed_resources[root_key])
            else:
                stripped_resourced = dict(computed_resources)
            for key in stripped_resourced:
                if stripped_resourced[key] in [base_resources[root_key][key], base_resources[key]]:
                    if root_key in computed_resources:
                        del computed_resources[root_key][key]
                    else:
                        del computed_resources[key]
            return computed_resources


if __name__ == '__main__':
    try:
        from configparser import ConfigParser
    except ImportError:
        print("Python 3's configparser or its backport to Python 2 is needed")  # ver. < 3.0
    conf = ConfigParser()

    parser = argparse.ArgumentParser(description='YUM update parser for Puppet resource')
    parser.add_argument('-c', '--conf-file', dest='conf_file', help='Configuration file')
    args = parser.parse_args()

    if args.conf_file and os.path.exists(args.conf_file):
        with open(args.conf_file, 'r') as conf_file:
            conf.read_file(conf_file)

    if conf.has_option('Package', 'root_key'):
        root_key = conf['Package']['root_key']
    else:
        root_key = 'packages'

    if conf.has_option('General', 'proxy'):
        os.environ['http_proxy'] = conf['General']['proxy']
        os.environ['https_proxy'] = conf['General']['proxy']

    if conf.has_option('Package', 'pkg_repos'):
        packages_found = query_yum(conf['Package']['pkg_repos'])
    else:
        packages_found = query_yum('')

    if len(packages_found) > 0:
        if args.conf_file:
            resources = build_hash(packages_found, conf.getboolean('Package', 'wrap'),
                                   conf.getboolean('Package', 'require'),
                                   conf.getboolean('Package', 'repo_in_resource'),
                                   conf.getboolean('Package', 'install_from_cache'), root_key)
        else:
            resources = build_hash(packages_found, True, False, False, False, root_key)
        if conf.has_option('Package', 'save') and conf.getboolean('Package', 'save'):
            working_file = os.path.join(conf['General']['cwd'], conf['GIT']['name'], conf['General']['hiera_folder'],
                                        conf['General']['file'])
            if conf.getboolean('Package', 'merge') and os.path.exists(working_file):
                resources = merge_resources(working_file, resources, root_key)

            if conf.has_option('General', 'base_file') and conf['General']['file'] != conf['General']['base_file']:
                base_file = os.path.join(conf['General']['cwd'], conf['GIT']['name'], conf['General']['hiera_folder'],
                                         conf['General']['base_file'])
                if os.path.exists(base_file):  # If node is first in group, base_file might not exist or be outdated
                    resources = strip_resources(base_file, working_file, root_key)

        if not (conf.has_option('Package', 'bundle') and not conf.getboolean('Package', 'bundle')):
            package_bundle = {}
            try:
                if conf.has_option('Package', 'bundle_list'):
                    with open(conf['Package']['bundle_list']) as json_file:
                        package_bundle = json.load(json_file)
            except Exception as e:
                pass
            resources = bundle_package(resources, root_key, package_bundle)

        if conf.has_option('Package', 'save') and conf.getboolean('Package', 'save') and working_file:
            with open(working_file, 'w') as outfile:
                json.dump(resources, outfile, indent=4, sort_keys=True)
        else:
            print(json.dumps(resources, indent=4, sort_keys=True))
    else:
        print('No package to update')
