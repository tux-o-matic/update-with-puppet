#!/usr/bin/env python

from __future__ import print_function
import argparse
import base64
import datetime
import json
import os
import sys

__author__ = 'Benjamin Merot <benjamin.merot@dsg.dk>'
__copyright__ = "Copyright (C) 2017 Dansk Supermarked Group"
__license__ = "GPL version 3"


def create_pr(repo_url, repo_email, repo_pwd, https_proxy, work_branch, dest_branch, description, reviewers, title,
              git_account, git_repo_name):
    # Nasty way of handling Python 2/3 when 'requests' isn't installed.
    try:
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError
    except ImportError:
        from urllib2 import urlopen, Request, HTTPError

    if https_proxy:
        os.environ['https_proxy'] = https_proxy

    json_reviewers = {'reviewers': []}
    if len(reviewers) > 0:
        if ',' in reviewers:
            for reviewer in reviewers.split(','):
                json_reviewers['reviewers'].append({'username': reviewer})
        else:
            json_reviewers['reviewers'].append({'username': reviewers})

    json_pr = {'title': title, 'description': description,
               'source': {'branch': {'name': work_branch},
                          'repository': {'full_name': git_account + '/' + git_repo_name}},
               'destination': {'branch': {'name': dest_branch}}, 'close_source_branch': True}
    json_pr.update(json_reviewers)

    # https://confluence.atlassian.com/bitbucket/pullrequests-resource-423626332.html
    # As per https://developer.atlassian.com/bitbucket/api/2/reference/meta/authentication
    # without 2 factor auth we can use HTTP Basic Auth
    try:
        b64auth = base64.b64encode('%s:%s' % (repo_email.strip(), repo_pwd.strip()))
        request = Request(repo_url.strip(), data=json.dumps(json_pr))
        request.add_header("Authorization", "Basic %s" % b64auth)
        request.add_header('Content-Type', 'application/json')
        response = urlopen(request).read()
    except Exception as e:
        print(str(e))
        print(json.dumps(json_pr, indent=4, sort_keys=True))


if __name__ == '__main__':
    try:
        from configparser import ConfigParser
    except ImportError:
        print("Python 3's configparser or its backport to Python 2 is needed")  # ver. < 3.0
    conf = ConfigParser()

    parser = argparse.ArgumentParser(description='GIT PR generator for Hiera JSON resources')
    parser.add_argument('-c', '--conf-file', dest='conf_file', help='Configuration file', required=True)
    args = parser.parse_args()

    with open(args.conf_file, 'r') as conf_file:
        conf.read_file(conf_file)

    if conf['GIT']['work_branch'] != '':
        working_branch = conf['GIT']['work_branch'] + '_' + conf['GIT']['src_branch']
    else:
        working_branch = 'OS_Update_' + datetime.datetime.now().strftime("%B_%Y") + '_' + conf['GIT']['src_branch']

    create_pr(conf['PR']['api_url'], conf['GIT']['email'],conf['GIT']['password'], conf['General']['proxy'],
              working_branch, conf['GIT']['dest_branch'], conf['PR']['description'],
              conf['PR']['reviewers'], conf['PR']['title'], conf['GIT']['account_name'], conf['GIT']['repo_name'])
