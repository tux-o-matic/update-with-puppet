# Update with Puppet
Would like to know which packages should be updated on a node?

Would like that list of packages to be fed directly to Puppet?

Then this is the tool for you.

## How it Works
This program will fetch from the package provider the updates available for the specified package repositories.
A list of [Puppet Package](https://docs.puppet.com/puppet/latest/type.html#package) resource will be generated (For now as Hiera JSON).
This list can be committed to a GIT repository where your Puppet configuration is.
You're then free to have those Package resources updated by Puppet.

## OS Support
- RPM based Linux: RHEL, Centos, Scientific, older Fedora,...
- DNF based Linux: newer Fedora.

## Repository Support
- GIT.
- BitBucket API for pull request creation.

## TODO
- Publish Puppet module to manage setup and CRON job.
- Support other package providers.
- Support other GIT hosting API for PR.

#### Copyright

Copyright 2017 [Dansk Supermarked Group](https://dansksupermarked.com/) and released under the terms of the [GPL version 3 license](https://www.gnu.org/licenses/gpl-3.0-standalone.html).