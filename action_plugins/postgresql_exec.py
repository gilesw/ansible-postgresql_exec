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

boolean = C.mk_boolean

class ActionModule(ActionBase):

    TRANSFERS_FILES = True

    def run(self, tmp=None, task_vars=None):

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)

        if result.get('skipped'):
            return result

        # parse task_vars that will decide action choices
        source  = self._task.args.get('src', None)
        content = self._task.args.get('content', None)
        remote_src = boolean(self._task.args.get('remote_src', False))

        # add some basic condition checks for arguments
        result['failed'] = True
        if (source is None and content is None):
            result['msg'] = "src (or content) are required"
        elif (remote_src is True and source is None):
            result['msg'] = "remote_src needs a src to be specified"
        else:
            del result['failed']


        # if remote_src is used pycog module itself reads file from the remote server with no templating
        if remote_src:
            result.update(self._execute_module(task_vars=task_vars))
            return result
        # take our source file, parse with jinja2 and inject the content into the content variable
        elif source is not None:
            try:
                source = self._find_needle('files', source)
                src = open(source)
                template_data = to_text(src.read())
                resultant = self._templar.do_template(template_data, preserve_trailing_newlines=True, escape_backslashes=False)
                content = resultant
                src.close
            except AnsibleError as e:
                result['failed'] = True
                result['msg'] = to_text(e)
                return result

        # inject content into arguments passed to postgresql_exec
        new_module_args = self._task.args.copy()
        new_module_args.update(
            dict(
                content=content,
            )
        )

        # Execute the postgresql_exec module with templated file content
        module_return = self._execute_module(module_name='postgresql_exec',
                module_args=new_module_args,
                task_vars=task_vars,
                tmp=tmp)
        return module_return


