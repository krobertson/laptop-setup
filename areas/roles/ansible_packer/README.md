coxley.packer
=============

[![Do what the fuck you want](http://www.wtfpl.net/wp-content/uploads/2012/12/wtfpl-badge-2.png)](http://www.wtfpl.net/)

Note: This is Archlinux `packer`, not Hashicorp

The purpose of this role is to install pre-reqs for ansible-packer and expose
this module for use.

This is glue around:

* [ansible-aur-pkg-installer](https://gist.github.com/wrecker/39ecb1eb1ab8ee1d0ce1)
* [ansible-packer](https://github.com/austinhyde/ansible-packer)

The former is used to install packer pre-reqs in favor of the more fleshed out
packer module.

Example Playbook
----------------

Ideal way to use this is within another role, declaring this as a role
dependency.

Assuming you have role `common`, edit `meta/main.yml`:

```yaml

---
dependencies:
  - { role: 'coxley.packer', when: ansible_os_family == 'Archlinux' }
```

Then in the following dependencies and the role itself you will have access to
`ansible-packer` which looks something like:

```yaml

---
# Install package foo
- packer: name=foo state=present

# Remove packages foo and bar
- packer: name=foo,bar state=absent

# Recursively remove package baz
- packer: name=baz state=absent recurse=yes

```

Requirements
------------

You must have httplib2 for Python installed where you are running Ansible
*from*

License
-------

WTFPL

Author Information
------------------

Codey Oxley <codey.a.oxley+os@gmail.com>
