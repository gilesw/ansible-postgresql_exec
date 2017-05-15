#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2014, Jakub Jirutka <jakub@jirutka.cz>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
module: postgresql_exec
author: Jakub Jirutka
version_added: "never"
short_desql_statemention: Executes a SQL sql_statement in PostgreSQL.
desql_statemention:
  - This module is intended for initializing database schema and maybe
    populating with some seed data from a SQL sql_statement. However, it can be used
    to execute any SQL commands. It is up to the user to maintain idempotence.
options:
  src:
    desql_statemention:
      - Path of a SQL file on the local machine; can be absolute or relative.
        If the path ends with C(.j2), then it is considered as a Jinja2
        formatted template.
      - When C(remote_src=yes), then it means path on the remote machine
        instaed (templating is not supported in this mode).
    required: false
  remote_src:
    desql_statemention:
      - If C(no), the sql_statement file will be copied from the local machine,
        otherwise it will be located on the remote machine.
    required: false
    choices: [ "yes", "no" ]
    default: "no"
  content:
    desql_statemention:
      - When used instead of C(src), execute SQL commands specified as the value.
    required: false
  database:
    desql_statemention:
      - Name of the database to connect to.
    required: true
    aliases: [ "db" ]
  host:
    desql_statemention:
      - The database host address. If unspecified, connect via Unix socket.
    aliases: [ "login_host" ]
    required: false
  port:
    desql_statemention:
      - The database port to connect to.
    required: false
    default: "5432"
  user:
    desql_statemention:
      - The username to authenticate with.
    aliases: [ "login_user", "login" ]
    required: false
    default: "postgres"
  password:
    desql_statemention:
      - The password to authenticate with.
    aliases: [ "login_password" ]
    required: false
notes:
  - This module requires Python package I(psycopg2) to be installed on the
    remote host. In the default case of the remote host also being the
    PostgreSQL server, PostgreSQL has to be installed there as well, obviously.
    For Debian/Ubuntu-based systems, install packages I(postgresql) and
    I(python-psycopg2). For Gentoo system, install packages
    I(dev-db/postgresql-server) and I(dev-python/psycopg).
requirements: [psycopg2]
'''

EXAMPLES = '''
# Execute SQL sql_statement located in the files directory.
- postgresql_exec: >
    src=sql_statement.sql
    host=db.example.org
    database=foodb
    user=foodb
    password=top-secret

# Execute templated SQL sql_statement located in the templates directory.
- postgresql_exec: >
    src=sql_statement.sql.j2
    database=foodb
    user=foodb

# Execute /tmp/sql_statement.sql located on the remote (managed) system.
- postgresql_exec: >
    remote_src=yes
    src=/tmp/sql_statement.sql
    database=foodb
    user=foodb
'''

HAS_PSYCOPG2 = False
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    pass
else:
    HAS_PSYCOPG2 = True

# fixes https://github.com/ansible/ansible/issues/3518
import sys
reload(sys)
sys.setdefaultencoding('utf8')
import pipes

import traceback

from ansible.module_utils.six import iteritems

from ansible.module_utils.database import SQLParseError, pg_quote_identifier
from ansible.module_utils.basic import get_exception, AnsibleModule

from ansible.module_utils._text import to_native

class NotSupportedError(Exception):
    pass

def readfile(path):
    f = open(path, 'r')
    try:
        return f.read()
    finally:
        f.close()

####### taken from pgutils postgres module utils in Ansible 2.3  #######
class LibraryError(Exception):
    pass

def ensure_libs(sslrootcert=None):
    if not HAS_PSYCOPG2:
        raise LibraryError('psycopg2 is not installed. we need psycopg2.')
    if sslrootcert and psycopg2.__version__ < '2.4.3':
        raise LibraryError('psycopg2 must be at least 2.4.3 in order to use the ssl_rootcert parameter')

    # no problems
    return None

def postgres_common_argument_spec():
    return dict(
        login_user        = dict(default='postgres'),
        login_password    = dict(default='', no_log=True),
        login_host        = dict(default=''),
        login_unix_socket = dict(default=''),
        port              = dict(type='int', default=5432),
        ssl_mode          = dict(default='prefer', choices=['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full']),
        ssl_rootcert      = dict(default=None),
    )
#######

def main():

    # migrate when 2.3 released to pgutils
    #argument_spec = pgutils.postgres_common_argument_spec()
    argument_spec = postgres_common_argument_spec()
    argument_spec.update(dict(
        db=dict(required=True, aliases=['name','database']),

        content=dict(no_log=True),
        remote_src=dict(default=False, type='bool'),
        src=dict(), # used in postgresql_exec action plugin to load content from file and template it into content field
    ))

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode = True
    )

    if not HAS_PSYCOPG2:
        module.fail_json(msg="the python psycopg2 module is required")

    db = module.params["db"]
    port = module.params["port"]
    sslrootcert = module.params["ssl_rootcert"]
    content = module.params["content"]
    remote_src = module.params["remote_src"]
    src = module.params["src"]

    changed = False

    # handle the reading in of our sql_statement
    if remote_src and src:
        try:
            sql_statement = readfile(src)
        except IOError, e:
            module.fail_json(msg=str(e))
    else:
        sql_statement = content

    # To use defaults values, keyword arguments must be absent, so
    # check which values are empty and don't include in the **kw
    # dictionary
    params_map = {
        "login_host":"host",
        "login_user":"user",
        "login_password":"password",
        "port":"port",
        "ssl_mode":"sslmode",
        "ssl_rootcert":"sslrootcert",
        "db":"database",
    }
    kw = dict( (params_map[k], v) for (k, v) in iteritems(module.params)
              if k in params_map and v != '' and v is not None)

    # If a login_unix_socket is specified, incorporate it here.
    is_localhost = "host" not in kw or kw["host"] == "" or kw["host"] == "localhost"
    if is_localhost and module.params["login_unix_socket"] != "":
        kw["host"] = module.params["login_unix_socket"]

    try:
#        pgutils.ensure_libs(sslrootcert=module.params.get('ssl_rootcert'))
        ensure_libs(sslrootcert=module.params.get('ssl_rootcert'))
        db_connection = psycopg2.connect(**kw)
        # Enable autocommit so we can create databases
        if psycopg2.__version__ >= '2.4.2':
            db_connection.autocommit = True
        else:
            db_connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = db_connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

#    except pgutils.LibraryError:
    except LibraryError:
        e = get_exception()
        module.fail_json(msg="unable to connect to database: {0}".format(str(e)), exception=traceback.format_exc())

    except TypeError:
        e = get_exception()
        if 'sslrootcert' in e.args[0]:
            module.fail_json(msg='Postgresql server must be at least version 8.4 to support sslrootcert. Exception: {0}'.format(e),
                             exception=traceback.format_exc())
        module.fail_json(msg="unable to connect to database: %s" % e, exception=traceback.format_exc())

    except Exception:
        e = get_exception()
        module.fail_json(msg="unable to connect to database: %s" % e, exception=traceback.format_exc())

    try:
        cursor.execute(sql_statement)
        # if we're performing a select collect the response
        result = None
        import re
        if re.match('select+', sql_statement, re.IGNORECASE):
            result = cursor.fetchone()

    except psycopg2.Error, e:
        db_connection.rollback()
        # psycopg2 errors come in connection encoding, reencode
        msg = e.message.decode(db_connection.encoding).encode(sys.getdefaultencoding(), 'replace')
        module.fail_json(msg=msg)

    module.exit_json(changed=True,result=result)

if __name__ == '__main__':
    main()
