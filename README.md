ansible-postgresql\_exec [![Build Status](https://travis-ci.org/gilesw/ansible-postgresql_exec.png?branch=master)](https://travis-ci.org/gilesw/ansible-postgresql_exec)
=======================

This role is only to test the action plugin and module postgresql exec and to demonstrate how idempotence can be developed at the Ansible task level.

Postgresql\_exec allows SQL statements to be run against a Postgresql server using the psycopg2 Python library.

However, it is up to the user to maintain idempotence as the statements will be run on every run.

Installation
------------

Copy the library directory and action plugins to your Ansible directories.

The paths for these plugins are set in ansible.cfg

e.g:-

    action_plugins=./action_plugins
    library=./library

Requirements
------------
This module is used to install postgres

    https://github.com/ANXS/postgresql

Role Variables
--------------


Dependencies
------------


Example Playbook
----------------


Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - hosts: servers
      roles:
         - { role: username.rolename, x: 42 }

License
-------

GPL3

Author Information
------------------

https://github.com/gilesw

https://github.com/jirutka

