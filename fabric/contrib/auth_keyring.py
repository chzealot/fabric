#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Zealot Ke <chzealot@gmail.com>
# Copyright (C) losthit.com 2012

''' get/set password with keyring(keychain in Mac OS X)
'''

import os
import sys

import keyring

def _get_sudo_service_and_user():
    service = ''
    user = ''

    from fabric.state import env
    args = {}
    args['host'] = env.host_string
    args['user'] = env.sudo_user
    if not args['user']:
        args['user'] = env.user
    if not args['user']:
        import getpass
        args['user'] = getpass.getuser()

    user = args['user']
    service = 'fabric_sudo_%(user)s_%(host)s' % args

    return (service, user)

def _get_ssh_service_and_user():
    service = ''
    user = ''

    from fabric.state import env
    args = {}
    args['host'] = env.host_string
    args['user'] = env.user
    if not args['user']:
        import getpass
        args['user'] = getpass.getuser()

    user = args['user']
    # TODO: support key file
    service = 'fabric_ssh_%(user)s_%(host)s' % args

    return (service, user)


def get_sudo_password():
    from fabric.state import env
    service, user = _get_sudo_service_and_user()
    password = keyring.get_password(service, user)
    if password:
        return password
    return env.password

def set_sudo_password(password):
    from fabric.state import env
    service, user = _get_sudo_service_and_user()
    keyring.set_password(service, user, password)

def get_ssh_password():
    from fabric.state import env
    service, user = _get_ssh_service_and_user()
    password = keyring.get_password(service, user)
    if password:
        return password
    return env.password

def set_ssh_password(password):
    from fabric.state import env
    service, user = _get_ssh_service_and_user()
    keyring.set_password(service, user, password)

def get_app_password(app, user='default'):
    from fabric.state import env

    args = {
            'app': app,
            'host': env.host_string or 'global',
            'user': user,
            }
    service = 'fabric_%(app)s_%(user)s_%(host)s' % args
    return keyring.get_password(service, user)

def set_app_password(app, user, password):
    from fabric.state import env
    args = {
            'app': app,
            'host': env.host_string or 'global',
            'user': user,
            }
    service = 'fabric_%(app)s_%(user)s_%(host)s' % args
    keyring.set_password(service, user, password)

def get_valid_app_password(app, user='default', again=True):
    password = get_app_password(app, user)
    if password:
        return password
    import getpass

    if not again:
        while not password:
            password = getpass.getpass('Enter password for %s@%s: ' % (user, app))
    else:
        def get2pass():
            password = None
            password2 = None
            while not password:
                password = getpass.getpass('Enter password for %s@%s: ' % (user, app))
            while not password2:
                password2 = getpass.getpass('Enter password for %s@%s (again): ' % (user, app))
            if password != password2:
                return False
            return password
        while not password:
            if password == False:
                print 'not match, try again'
            password = get2pass()
    if not password:
        sys.exit('no valid password')

    set_app_password(app, user, password)
    return password

def main():
    ''' main function
    '''
    print 'Done'

if __name__ == '__main__':
    print _get_sudo_service_and_user()
    print _get_ssh_service_and_user()
    main()
