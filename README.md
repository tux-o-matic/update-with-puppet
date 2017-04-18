# Update with Puppet 
[![Build Status](https://travis-ci.org/DanskSupermarked/update-with-puppet.svg?branch=master)](https://travis-ci.org/DanskSupermarked/update-with-puppet)

Would like to know which packages should be updated on a node?

Would like that list of packages to be fed directly to Puppet?

Then this is the tool for you.

## How it Works
This program will fetch from the package provider the updates available for the specified package repositories.
A list of [Puppet Package](https://docs.puppet.com/puppet/latest/type.html#package) resource will be generated (For now as Hiera JSON).
Some packages and their associated libs should be updated as once and for this they will be updated as an Exec resource created along the Package resources.

This list can be committed to a GIT repository where your Puppet configuration is.
You're then free to have those Package resources updated by Puppet.


## Use Case
Schedule a [CRON](https://docs.puppet.com/puppet/latest/type.html#cron) job on a node or pool of servers.
This tool will collect packages to update and create a GIT PR to be reviewed, eventually edited, and finally merged in your Puppet configuration to have the packages updated during the next Puppet run. 

## OS Support
- RPM based Linux: RHEL, Centos, Scientific, older Fedora,...
- DNF based Linux: newer Fedora.

## Repository Support
- GIT.
- BitBucket API for pull request creation.

## TODO
- Publish Puppet module to manage setup and CRON job.
- Support other package providers.
- Support creation of resource list as Yaml or .pp files.
- Support other GIT hosting API for PR.
- Load package bundle list outside of code.

#### Copyright

Copyright 2017 [Dansk Supermarked Group](https://dansksupermarked.com/) and released under the terms of the [GPL version 3 license](https://www.gnu.org/licenses/gpl-3.0-standalone.html).
