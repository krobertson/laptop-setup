#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

__version__ = '0.3.0'

DOCUMENTATION = '''
---
module: ssh_config
short_description: Manage a users ssh config
description:
  - Configures ssh hosts with special IdentityFiles and hostnames
options:
  state:
    description:
      - Whether a host entry should exist or not
    default: present
    choices: [ 'present', 'absent' ]
  user:
    description:
      - Which user account this configuration file belongs to.
        If none given /etc/ssh/ssh_config. If a user is given then
        `~/.ssh/config`.
    default: root
    choices: []
  host:
    description:
      - The endpoint this configuration is valid for. Can be an actual
        address on the internet or an alias that will connect to the value
        of `hostname`.
    required: true
    choices: []
  hostname:
    description:
      - The actual host to connect to when connecting to the host defined.
    choices: []
  port:
    description:
      - The actual port to connect to when connecting to the host defined.
    required: false
  remote_user:
    description:
      - Specifies the user to log in as.
    choices: []
  identity_file:
    description:
      - The path to an identitity file (ssh private) that will be used
        when connecting to this host.
        File need to exist and be 0600 to be valid.
    choices: []
  user_known_hosts_file:
    description:
      - Sets the user known hosts file option
  strict_host_key_checking:
    description:
      - Whether to strictly check the host key when doing connections to the remote host
    choices: ['yes', 'no', 'ask']
  proxycommand:
    description:
      - Sets the ProxyCommand option.
    required: false
'''

EXAMPLES = '''
---
- config:
    user=deploy
    host=internal-library.github.com
    hostname=github.com
    identity_file=id_rsa.internal-library
    state=present
- config:
    user=deploy
    host=old-internal.github.com
    remote_user=git
    state=absent
- config:
    user=deploy
    host=old-internal.github.com
    port=2222
'''

# The following block of code is part of paramiko.

# Copyright (C) 2006-2007  Robey Pointer <robeypointer@gmail.com>
# Copyright (C) 2012  Olle Lundberg <geek@nerd.sh>
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
L{SSHConfig}.
"""

import copy
import fnmatch
import os
import re
import socket
import pwd

SSH_PORT = 22
proxy_re = re.compile(r"^(proxycommand)\s*=*\s*(.*)", re.I)


SSH_KEYWORDS = (
    'AddressFamily',
    'BatchMode',
    'BindAddress',
    'ChallengeResponseAuthentication',
    'CheckHostIP',
    'Cipher',
    'Ciphers',
    'ClearAllForwardings',
    'Compression',
    'CompressionLevel',
    'ConnectTimeout',
    'ConnectionAttempts',
    'ControlMaster',
    'ControlPath',
    'ControlPersist',
    'DynamicForward',
    'EnableSSHKeysign',
    'EscapeChar',
    'ExitOnForwardFailure',
    'ForwardAgent',
    'ForwardX11',
    'ForwardX11Timeout',
    'ForwardX11Trusted',
    'GSSAPIAuthentication',
    'GSSAPIClientIdentity',
    'GSSAPIDelegateCredentials',
    'GSSAPIKeyExchange',
    'GSSAPIRenewalForcesRekey',
    'GSSAPIServerIdentity',
    'GSSAPITrustDNS',
    'GSSAPITrustDns',
    'GatewayPorts',
    'GlobalKnownHostsFile',
    'HashKnownHosts',
    'HostKeyAlgorithms',
    'HostKeyAlias',
    'HostName',
    'HostbasedAuthentication',
    'IPQoS',
    'IdentitiesOnly',
    'IdentityFile',
    'KbdInteractiveAuthentication',
    'KbdInteractiveDevices',
    'KexAlgorithms',
    'LocalCommand',
    'LocalForward',
    'LogLevel',
    'MACs',
    'NoHostAuthenticationForLocalhost',
    'NumberOfPasswordPrompts',
    'PKCS11Provider',
    'PasswordAuthentication',
    'PermitLocalCommand',
    'Port',
    'PreferredAuthentications',
    'Protocol',
    'ProxyCommand',
    'PubkeyAuthentication',
    'RSAAuthentication',
    'RekeyLimit',
    'RemoteForward',
    'RequestTTY',
    'RhostsRSAAuthentication',
    'SendEnv',
    'ServerAliveCountMax',
    'ServerAliveInterval',
    'SmartcardDevice',
    'StrictHostKeyChecking',
    'TCPKeepAlive',
    'Tunnel',
    'TunnelDevice',
    'UseBlacklistedKeys',
    'UsePrivilegedPort',
    'User',
    'UserKnownHostsFile',
    'VerifyHostKeyDNS',
    'VisualHostKey',
    'XAuthLocation'
)


class LazyFqdn(object):
    """
    Returns the host's fqdn on request as string.
    """

    def __init__(self, config, host=None):
        self.fqdn = None
        self.config = config
        self.host = host

    def __str__(self):
        if self.fqdn is None:
            #
            # If the SSH config contains AddressFamily, use that when
            # determining  the local host's FQDN. Using socket.getfqdn() from
            # the standard library is the most general solution, but can
            # result in noticeable delays on some platforms when IPv6 is
            # misconfigured or not available, as it calls getaddrinfo with no
            # address family specified, so both IPv4 and IPv6 are checked.
            #

            # Handle specific option
            fqdn = None
            address_family = self.config.get('addressfamily', 'any').lower()
            if address_family != 'any':
                try:
                    family = socket.AF_INET if address_family == 'inet' \
                        else socket.AF_INET6
                    results = socket.getaddrinfo(
                        self.host,
                        None,
                        family,
                        socket.SOCK_DGRAM,
                        socket.IPPROTO_IP,
                        socket.AI_CANONNAME
                    )
                    for res in results:
                        af, socktype, proto, canonname, sa = res
                        if canonname and '.' in canonname:
                            fqdn = canonname
                            break
                # giaerror -> socket.getaddrinfo() can't resolve self.host
                # (which is from socket.gethostname()). Fall back to the
                # getfqdn() call below.
                except socket.gaierror:
                    pass
            # Handle 'any' / unspecified
            if fqdn is None:
                fqdn = socket.getfqdn()
            # Cache
            self.fqdn = fqdn
        return self.fqdn


class SSHConfig (object):
    """
    Representation of config information as stored in the format used by
    OpenSSH. Queries can be made via L{lookup}. The format is described in
    OpenSSH's C{ssh_config} man page. This class is provided primarily as a
    convenience to posix users (since the OpenSSH format is a de-facto
    standard on posix) but should work fine on Windows too.

    @since: 1.6
    """

    def __init__(self):
        """
        Create a new OpenSSH config object.
        """
        self._config = []

    def parse(self, file_obj):
        """
        Read an OpenSSH config from the given file object.

        @param file_obj: a file-like object to read the config file from
        @type file_obj: file
        """
        host = {"host": ['*'], "config": {}}
        for line in file_obj:
            line = line.rstrip('\n').lstrip()
            if (line == '') or (line[0] == '#'):
                continue
            if '=' in line:
                # Ensure ProxyCommand gets properly split
                if line.lower().strip().startswith('proxycommand'):
                    match = proxy_re.match(line)
                    key, value = match.group(1).lower(), match.group(2)
                else:
                    key, value = line.split('=', 1)
                    key = key.strip().lower()
            else:
                # find first whitespace, and split there
                i = 0
                while (i < len(line)) and not line[i].isspace():
                    i += 1
                if i == len(line):
                    raise Exception('Unparsable line: %r' % line)
                key = line[:i].lower()
                value = line[i:].lstrip()

            if key == 'host':
                self._config.append(host)
                value = value.split()
                host = {key: value, 'config': {}}
            #identityfile, localforward, remoteforward keys are special cases, since they are allowed to be
            # specified multiple times and they should be tried in order
            # of specification.

            elif key in ['identityfile', 'localforward', 'remoteforward']:
                if key in host['config']:
                    host['config'][key].append(value)
                else:
                    host['config'][key] = [value]
            elif key not in host['config']:
                host['config'].update({key: value})
        self._config.append(host)

    def lookup(self, hostname):
        """
        Return a dict of config options for a given hostname.

        The host-matching rules of OpenSSH's C{ssh_config} man page are used,
        which means that all configuration options from matching host
        specifications are merged, with more specific hostmasks taking
        precedence. In other words, if C{"Port"} is set under C{"Host *"}
        and also C{"Host *.example.com"}, and the lookup is for
        C{"ssh.example.com"}, then the port entry for C{"Host *.example.com"}
        will win out.

        The keys in the returned dict are all normalized to lowercase (look for
        C{"port"}, not C{"Port"}. The values are processed according to the
        rules for substitution variable expansion in C{ssh_config}.

        @param hostname: the hostname to lookup
        @type hostname: str
        """

        matches = [config for config in self._config if
                   self._allowed(hostname, config['host'])]

        ret = {}
        for match in matches:
            for key, value in match['config'].iteritems():
                if key not in ret:
                    # Create a copy of the original value,
                    # else it will reference the original list
                    # in self._config and update that value too
                    # when the extend() is being called.
                    ret[key] = value[:]
                elif key == 'identityfile':
                    ret[key].extend(value)
        ret = self._expand_variables(ret, hostname)
        return ret

    def _allowed(self, hostname, hosts):
        match = False
        for host in hosts:
            if host.startswith('!') and fnmatch.fnmatch(hostname, host[1:]):
                return False
            elif fnmatch.fnmatch(hostname, host):
                match = True
        return match

    def _expand_variables(self, config, hostname):
        """
        Return a dict of config options with expanded substitutions
        for a given hostname.

        Please refer to man C{ssh_config} for the parameters that
        are replaced.

        @param config: the config for the hostname
        @type hostname: dict
        @param hostname: the hostname that the config belongs to
        @type hostname: str
        """

        if 'hostname' in config:
            config['hostname'] = config['hostname'].replace('%h', hostname)
        else:
            config['hostname'] = hostname

        if 'port' in config:
            port = config['port']
        else:
            port = SSH_PORT

        user = os.getenv('USER')
        if 'user' in config:
            remoteuser = config['user']
        else:
            remoteuser = user

        host = socket.gethostname().split('.')[0]
        fqdn = LazyFqdn(config, host)
        homedir = os.path.expanduser('~')
        replacements = {'controlpath':
                        [
                            ('%h', config['hostname']),
                            ('%l', fqdn),
                            ('%L', host),
                            ('%n', hostname),
                            ('%p', port),
                            ('%r', remoteuser),
                            ('%u', user)
                        ],
                        'identityfile':
                        [
                            ('~', homedir),
                            ('%d', homedir),
                            ('%h', config['hostname']),
                            ('%l', fqdn),
                            ('%u', user),
                            ('%r', remoteuser)
                        ],
                        'proxycommand':
                        [
                            ('%h', config['hostname']),
                            ('%p', port),
                            ('%r', remoteuser)
                        ]
                        }

        for k in config:
            if k in replacements:
                for find, replace in replacements[k]:
                    if isinstance(config[k], list):
                        for item in range(len(config[k])):
                            config[k][item] = config[k][item].\
                                replace(find, str(replace))
                    else:
                        config[k] = config[k].replace(find, str(replace))
        return config

####################
# End copy Paramiko
####################


# The following code block is from Storm ssh
# Licensed under the MIT license by Emre Yilmaz

from os import makedirs
from os import chmod
from os.path import dirname
from os.path import expanduser
from os.path import exists
from operator import itemgetter


class StormConfig(SSHConfig):
    def parse(self, file_obj):
        """
        Read an OpenSSH config from the given file object.

        @param file_obj: a file-like object to read the config file from
        @type file_obj: file
        """
        order = 1
        host = {"host": ['*'], "config": {}, }
        for line in file_obj:
            line = line.rstrip('\n').lstrip()
            if line == '':
                self._config.append({
                    'type': 'empty_line',
                    'value': line,
                    'host': '',
                    'order': order,
                })
                order += 1
                continue

            if line.startswith('#'):
                self._config.append({
                    'type': 'comment',
                    'value': line,
                    'host': '',
                    'order': order,
                })
                order += 1
                continue

            if '=' in line:
                # Ensure ProxyCommand gets properly split
                if line.lower().strip().startswith('proxycommand'):
                    proxy_re = re.compile(r"^(proxycommand)\s*=*\s*(.*)", re.I)
                    match = proxy_re.match(line)
                    key, value = match.group(1).lower(), match.group(2)
                else:
                    key, value = line.split('=', 1)
                    key = key.strip().lower()
            else:
                # find first whitespace, and split there
                i = 0
                while (i < len(line)) and not line[i].isspace():
                    i += 1
                if i == len(line):
                    raise Exception('Unparsable line: %r' % line)
                key = line[:i].lower()
                value = line[i:].lstrip()
            if key == 'host':
                self._config.append(host)
                value = value.split()
                host = {key: value, 'config': {}, 'type': 'entry', 'order': order}
                order += 1
            #identityfile is a special case, since it is allowed to be
            # specified multiple times and they should be tried in order
            # of specification.
            elif key in ['identityfile', 'localforward', 'remoteforward']:
                if key in host['config']:
                    host['config'][key].append(value)
                else:
                    host['config'][key] = [value]
            elif key not in host['config']:
                host['config'].update({key: value})
        self._config.append(host)


class ConfigParser(object):
    """
    Config parser for ~/.ssh/config files.
    """

    def __init__(self, ssh_config_file=None):
        if not ssh_config_file:
            ssh_config_file = self.get_default_ssh_config_file()

        self.ssh_config_file = ssh_config_file

        if not exists(self.ssh_config_file):
            if not exists(dirname(self.ssh_config_file)):
                makedirs(dirname(self.ssh_config_file))
            open(self.ssh_config_file, 'w+').close()
            chmod(self.ssh_config_file, 0o600)

        self.config_data = []

    def get_default_ssh_config_file(self):
        return expanduser("~/.ssh/config")

    def load(self):
        config = StormConfig()

        config.parse(open(self.ssh_config_file))
        for entry in config.__dict__.get("_config"):
            if entry.get("type") in ["comment", "empty_line"]:
                self.config_data.append(entry)
                continue

            host_item = {
                'host': entry["host"][0],
                'options': entry.get("config"),
                'type': 'entry',
                'order': entry.get("order"),
            }

            if len(entry["host"]) > 1:
                host_item.update({
                    'host': " ".join(entry["host"]),
                })

            # minor bug in paramiko.SSHConfig that duplicates
            #"Host *" entries.
            if entry.get("config") and len(entry.get("config")) > 0:
                self.config_data.append(host_item)
        return self.config_data

    def add_host(self, host, options):
        self.config_data.append({
            'host': host,
            'options': options,
            'order': self.get_last_index(),
        })

        return self

    def update_host(self, host, options):
        for index, host_entry in enumerate(self.config_data):
            if host_entry.get("host") == host:
                self.config_data[index]["options"] = options

        return self

    def search_host(self, search_string):
        results = []
        for host_entry in self.config_data:
            if host_entry.get("type") != 'entry':
                continue

            searchable_information = host_entry.get("host")
            for key, value in host_entry.get("options").items():
                if isinstance(value, list):
                    value = " ".join(value)
                if isinstance(value, int):
                    value = str(value)

                searchable_information += " " + value

            if search_string in searchable_information:
                results.append(host_entry)

        return results

    def delete_host(self, host):
        found = 0
        for index, host_entry in enumerate(self.config_data):
            if host_entry.get("host") == host:
                del self.config_data[index]
                found += 1

        if found == 0:
            raise StormValueError('No host found')
        return self

    def delete_all_hosts(self):
        self.config_data = []
        self.write_to_ssh_config()

        return self

    def dump(self):
        if len(self.config_data) < 1:
            return

        file_content = ""
        self.config_data = sorted(self.config_data, key=itemgetter("order"))

        replacements = {}
        for keyword in SSH_KEYWORDS:
            replacements[keyword.lower()] = keyword

        for host_item in self.config_data:
            if host_item.get("type") in ['comment', 'empty_line']:
                file_content += host_item.get("value") + "\n"
                continue
            host_item_content = "Host {0}\n".format(host_item.get("host"))
            for key, value in host_item.get("options").iteritems():
                if key in replacements:
                    key = replacements[key]
                if isinstance(value, list):
                    sub_content = ""
                    for value_ in value:
                        sub_content += "    {0} {1}\n".format(
                            key, value_
                        )
                    host_item_content += sub_content
                else:
                    host_item_content += "    {0} {1}\n".format(
                        key, value
                    )
            file_content += host_item_content

        return file_content

    def write_to_ssh_config(self):
        with open(self.ssh_config_file, 'w+') as f:
            data = self.dump()
            if data:
                f.write(data)
        return self

    def get_last_index(self):
        last_index = 0
        indexes = []
        for item in self.config_data:
            if item.get("order"):
                indexes.append(item.get("order"))
        if len(indexes) > 0:
            last_index = max(indexes)

        return last_index


#################
# End copy Storm
#################

# The following code is by Björn Andersson for Ansible


def change_host(options, **kwargs):
    options = copy.deepcopy(options)
    changed = False
    for k, v in kwargs.items():
        if '_' in k:
          k = k.replace('_', '')

        if not v:
            if options.get(k):
                del options[k]
                changed = True
        elif options.get(k) != v:
            options[k] = v
            changed = True

    return changed, options


def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(default='present', choices=['present', 'absent']),
            host=dict(required=True, type='str'),
            hostname=dict(type='str'),
            port=dict(type='str'),
            remote_user=dict(type='str'),
            identity_file=dict(type='str'),
            user=dict(default=None, type='str'),
            user_known_hosts_file=dict(default=None, type='str'),
            proxycommand=dict(default=None, type='str'),
            strict_host_key_checking=dict(
                default=None,
                choices=['yes', 'no', 'ask']
            ),
        ),
        supports_check_mode=True
    )

    user = module.params.get('user')
    host = module.params.get('host')
    args = dict(
        hostname=module.params.get('hostname'),
        port=module.params.get('port'),
        identity_file=module.params.get('identity_file'),
        user=module.params.get('remote_user'),
        strict_host_key_checking=module.params.get('strict_host_key_checking'),
        user_known_hosts_file=module.params.get('user_known_hosts_file'),
        proxycommand=module.params.get('proxycommand'),
    )
    state = module.params.get('state')
    config_changed = False
    hosts_changed = []
    hosts_removed = []
    hosts_added = []

    if user is None:
        config_file = '/etc/ssh/ssh_config'
        user = 'root'
    else:
        config_file = os.path.join(
            os.path.expanduser('~{0}'.format(user)), '.ssh', 'config'
        )

    # See if the identity file exists or not, relative to the config file
    if os.path.exists(config_file) and args['identity_file']:
        dirname = os.path.dirname(config_file)
        identity_file = args['identity_file']
        if(not identity_file.startswith('/') and
           not identity_file.startswith('~')):
            identity_file = os.path.join(dirname, identity_file)

        if(not os.path.exists(identity_file) and
           not os.path.exists(os.path.expanduser(identity_file))):
            module.fail_json(
                msg='IdentityFile "{0}" does not exist'.format(identity_file)
            )

    config = ConfigParser(config_file)
    config.load()

    results = config.search_host(host)
    if results:
        for h in results:
            # Anything to remove?
            if state == 'absent':
                config_changed = True
                hosts_removed.append(h['host'])
                config.delete_host(h['host'])
            # Anything to change?
            else:
                changed, options = change_host(h['options'], **args)

                if changed:
                    config_changed = True
                    config.update_host(h['host'], options)
                    hosts_changed.append({
                        h['host']: {
                            'old': h['options'],
                            'new': options,
                        }
                    })
    # Anything to add?
    elif state == 'present':
        changed, options = change_host(dict(), **args)

        if changed:
            config_changed = True
            hosts_added.append(host)
            config.add_host(host, options)

    if config_changed and not module.check_mode:
        config.write_to_ssh_config()
        gid = pwd.getpwnam(user).pw_gid
        # MAKE sure the file is owned by the right user
        module.set_owner_if_different(config_file, user, False)
        module.set_group_if_different(config_file, gid, False)
        module.set_mode_if_different(config_file, '0600', False)

    module.exit_json(changed=config_changed,
                     hosts_changed=hosts_changed,
                     hosts_removed=hosts_removed,
                     hosts_added=hosts_added)

# this is magic, see lib/ansible/module_common.py
#<<INCLUDE_ANSIBLE_MODULE_COMMON>>

main()
