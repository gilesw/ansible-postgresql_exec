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

#from ansible import utils
#from ansible.utils import template

import datetime
import os
import pwd
import time

from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.module_utils.six import string_types
from ansible.module_utils._text import to_bytes, to_native, to_text
from ansible.plugins.action import ActionBase
from ansible.utils.hashing import checksum_s


# fixes https://github.com/ansible/ansible/issues/3518
import sys
reload(sys)
sys.setdefaultencoding('utf8')
import pipes

boolean = C.mk_boolean

class ActionModule(ActionBase):

    TRANSFERS_FILES = True

    def run(self, tmp=None, task_vars=None):

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)

        if result.get('skipped'):
            return result

        database  = self._task.args.get('database', None)
        source  = self._task.args.get('src', None)
        content = self._task.args.get('content', None)
        force   = boolean(self._task.args.get('force', 'yes'))
        remote_src = boolean(self._task.args.get('remote_src', False))


        # If content is defined make a temp file and write the content into it.
        if content is not None:
            try:
                # If content comes to us as a dict it should be decoded json.
                # We need to encode it back into a string to write it out.
                if isinstance(content, dict) or isinstance(content, list):
                    content_tempfile = self._create_content_tempfile(json.dumps(content))
                else:
                    content_tempfile = self._create_content_tempfile(content)
                source = content_tempfile
            except Exception as err:
                result['failed'] = True
                result['msg'] = "could not write content temp file: %s" % to_native(err)
                return result

        # if we have first_available_file in our vars
        # look up the files and use the first one we find as src
        elif remote_src:
            result.update(self._execute_module(task_vars=task_vars))
            return result
        else:  # find in expected paths
            try:
                source = self._find_needle('files', source)
            except AnsibleError as e:
                result['failed'] = True
                result['msg'] = to_text(e)
                return result

        # Execute the file module.
        module_return = self._execute_module(module_name='postgresql_exec',
                task_vars=task_vars,
                tmp=tmp)

        return module_return


