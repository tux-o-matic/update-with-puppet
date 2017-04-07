#!/usr/bin/env python

from __future__ import print_function
import argparse
import base64
import datetime
import json
import os
import platform
import shutil
import socket
import subprocess
import sys

__author__ = 'Benjamin Merot'
__copyright__ = "Copyright (C) 2017 Dansk Supermarked Group"
__license__ = "GPL version 3"

# See https://access.redhat.com/solutions/27943
pkg_requiring_reboot = ['glibc', 'hal', 'kernel', 'kernel-firmware', 'linux-firmware', 'systemd', 'udev']


def get_linux_dist():
    if sys.version_info[0] >= 3 and sys.version_info[1] > 6:
        raise NotImplementedError  # 'distro' module returns different names
    else:
        return platform.linux_distribution()


def parse_hiera(filename, root_key):
    pkg_count = 0
    pkg_with_reboot = False
    with open(filename) as json_file:
        json_hiera = json.load(json_file)
        packages = {}
        if not json_hiera and root_key in json_hiera:
            packages = json_hiera[root_key]
        elif not json_hiera and root_key not in json_hiera:
            packages = json_hiera

        for pkg in packages:
            pkg_count += 1
            if pkg in pkg_requiring_reboot:
                pkg_with_reboot = True

    return pkg_count, pkg_with_reboot


if __name__ == '__main__':
    try:
        from configparser import ConfigParser
    except ImportError:
        print("Python 3's configparser or its backport to Python 2 is needed")  # ver. < 3.0
    conf = ConfigParser()

    support_distros = ['CentOS', 'Fedora', 'Red Hat Enterprise Linux Server']
    if platform.system() != 'Linux' or get_linux_dist()[0] not in support_distros:
        raise OSError('This OS is not supported')
    default_file_name = get_linux_dist()[0] + '_' + get_linux_dist()[1] + '.json'

    parser = argparse.ArgumentParser(description='Setup workplace for GIT interaction')
    parser.add_argument('-c', '--conf-file', dest='conf_file', help='Configuration file', required=True)
    args = parser.parse_args()

    with open(args.conf_file, 'r') as conf_file:
        conf.read_file(conf_file)

    local_repo_exists = False
    local_repo_path = os.path.join(conf['General']['cwd'], conf['GIT']['name'])
    if os.path.isdir(os.path.join(local_repo_path)):
        if os.path.exists(os.path.join(local_repo_path, '.git', 'index')):
            local_repo_exists = True
        else:
            path_split = os.path.split(local_repo_path)
            if local_repo_path.startswith('/tmp') and len(path_split) >= 2:
                """ Want to be sure that a sensitive folder cannot be passed to the program"""
                shutil.rmtree(local_repo_path)

    cmd_out = subprocess.PIPE
    if conf['General']['proxy'] != '':
        print(subprocess.Popen(['git', 'config', '--global', 'http.proxy', conf['General']['proxy']],
                               cwd=conf['General']['cwd'], stdout=cmd_out).communicate()[0])
        print(subprocess.Popen(['git', 'config', '--global', 'https.proxy', conf['General']['proxy']],
                               cwd=conf['General']['cwd'], stdout=cmd_out).communicate()[0])
        os.environ['https_proxy'] = conf['General']['proxy']

    if not local_repo_exists:
        assembled_git_url = conf['GIT']['url'].replace('https://', 'https://' + conf['GIT']['user'] + ':' +
                                                       conf['GIT']['password'] + '@')
        print(subprocess.Popen(['git', 'clone', assembled_git_url],
                               cwd=conf['General']['cwd'], stdout=cmd_out).communicate()[0])

    if conf['GIT']['work_branch'] != '':
        working_branch = conf['GIT']['work_branch'] + '_' + conf['GIT']['src_branch']
    else:
        working_branch = 'OS_Update_' + datetime.datetime.now().strftime("%B_%Y") + '_' + conf['GIT']['src_branch']
    print(subprocess.Popen(['git', 'checkout', conf['GIT']['src_branch']],
                           cwd=local_repo_path, stdout=cmd_out).communicate()[0])
    print(subprocess.Popen(['git', 'checkout', working_branch], cwd=local_repo_path, stdout=cmd_out).communicate()[0])
    branches = subprocess.Popen(['git', 'branch'], cwd=local_repo_path, stdout=cmd_out).communicate()[0].split('\n')
    for i, v in enumerate(branches):
        branches[i] = v.strip('*').strip()

    new_branch = False
    if working_branch not in branches:
        new_branch = True

    if new_branch:
        print(subprocess.Popen(['git', 'checkout', '-b', working_branch, conf['GIT']['src_branch']],
                               cwd=local_repo_path, stdout=cmd_out).communicate()[0])
    else:
        print(subprocess.Popen(['git', 'checkout', working_branch],
                               cwd=local_repo_path, stdout=cmd_out).communicate()[0])
        print(subprocess.Popen(['git', 'pull'], cwd=local_repo_path, stdout=cmd_out).communicate()[0])

    working_file = os.path.join(local_repo_path, 'hiera', conf['General']['file'])
    generate_list = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'generate_list.py')
    generate_list_cmd = ['python', generate_list, '-c', args.conf_file]

    commit_message = working_branch + ' from ' + socket.getfqdn()
    existing_pkg_count = 0

    if os.path.exists(working_file):
        existing_pkg_count = parse_hiera(working_file, conf['Package']['root_key'])[0]
    print(subprocess.Popen(generate_list_cmd, cwd=conf['General']['cwd'], stdout=cmd_out).communicate()[0])

    if os.path.exists(working_file):
        latest_pkg_parsed = parse_hiera(working_file, conf['Package']['root_key'])
        if existing_pkg_count == 0 and latest_pkg_parsed[0] > 0:
            commit_message = 'Found ' + str(latest_pkg_parsed[0]) + ' packages to update on ' + socket.getfqdn()
        elif 0 < existing_pkg_count < latest_pkg_parsed[0]:
            commit_message = 'Added ' + str(latest_pkg_parsed[0] - existing_pkg_count)\
                             + ' packages to update on ' + socket.getfqdn()

        if latest_pkg_parsed[1]:
            commit_message += ', system restart recommended'

    print(subprocess.Popen(['git', 'config', '--global', 'user.name', conf['GIT']['username']],
                           cwd=local_repo_path, stdout=cmd_out).communicate()[0])
    print(subprocess.Popen(['git', 'config', '--global', 'user.email', conf['GIT']['email']],
                           cwd=local_repo_path, stdout=cmd_out).communicate()[0])
    print(subprocess.Popen(['git', 'add', '.'], cwd=local_repo_path, stdout=cmd_out).communicate()[0])
    print(subprocess.Popen(['git', 'commit', '-m', commit_message],
                           cwd=local_repo_path, stdout=cmd_out).communicate()[0])
    print(subprocess.Popen(['git', 'push', '-u', 'origin', working_branch],
                           cwd=local_repo_path, stdout=cmd_out).communicate()[0])

    pr_exists = False

    try:
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError
    except ImportError:
        from urllib2 import urlopen, Request, HTTPError

    b64auth = base64.b64encode('%s:%s' % (conf['GIT']['user'], conf['GIT']['password']))
    request = Request(conf['PR']['api_url'] + '?state=OPEN')
    request.add_header("Authorization", "Basic %s" % b64auth)
    response = urlopen(request).read()
    try:
        if conf['PR']['title'] in response.decode('utf-8'):
            pr_exists = True
    except Exception as e:
        print(str(e))
        if str(conf['PR']['title']) in str(response):
            pr_exists = True

    if not pr_exists and os.path.exists(working_file):
        send_pull_request = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'send_pull_request.py')
        send_pull_request_cmd = ['python', send_pull_request, '-c', args.conf_file]
        print(subprocess.Popen(send_pull_request_cmd, stdout=cmd_out).communicate()[0])
