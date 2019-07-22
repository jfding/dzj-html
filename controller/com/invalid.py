#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@desc: 首页
@time: 2018/6/23
"""

from operator import itemgetter
from os import path
from controller.task.base import TaskHandler
from controller.role import get_route_roles
import re
import inspect


class InvalidPageHandler(TaskHandler):
    def prepare(self):
        pass  # ignore roles

    def get(self):
        if '/api/' in self.request.path:
            self.set_status(404, reason='Not found')
            return self.finish()
        if path.exists(path.join(self.get_template_path(), self.request.path.replace('/', ''))):
            return self.render(self.request.path.replace('/', ''))
        self.set_status(404, reason='Not found')
        self.render('_404.html')

    def post(self):
        self.get()


class ApiTable(TaskHandler):
    URL = '/api'

    def get(self):
        """ 显示后端API和前端路由 """

        def get_doc():
            assert func.__doc__, str(func) + ' no comment'
            return func.__doc__.strip().split('\n')[0]

        handlers = []
        for cls in self.application.handlers:
            handler = cls(self.application, self.request)
            file = 'controller' + re.sub(r'^.+controller', '', inspect.getsourcefile(cls))
            file += '\n' + inspect.getsource(cls).split('\n')[0][:-1]
            for method in handler._get_methods().split(','):
                method = method.strip()
                if method != 'OPTIONS':
                    func = cls.__dict__[method.lower()]
                    func_name = re.sub(r'<|function |at .+$', '', str(func)).strip()
                    self.add_handlers(cls, file, func_name, get_doc, handlers, method)
        handlers.sort(key=itemgetter(0))
        self.render('_api.html', version=self.application.version, handlers=handlers)

    @staticmethod
    def add_handlers(cls, file, func_name, get_doc, handlers, method):
        def show_roles():
            if 'MyTaskHandler.' in func_name:
                return '普通用户'
            return ','.join(r for r in roles if not re.search(r'员|专家', r) or '普通用户' not in roles)

        if isinstance(cls.URL, list):
            for i, url in enumerate(cls.URL):
                roles = get_route_roles(url, method)
                handlers.append((url, func_name, i + 1, file, get_doc(), show_roles()))
        else:
            added = 0
            if '@box_type' in cls.URL:
                for i, box_type in enumerate(['block', 'char', 'column']):
                    url = cls.URL.replace('@box_type', box_type)
                    roles = get_route_roles(url, method)
                    if roles:
                        added += len(roles)
                        handlers.append((url, func_name, i + 1, file, get_doc(), show_roles()))
            if not added:
                roles = get_route_roles(cls.URL, method)
                handlers.append((cls.URL, func_name, 0, file, get_doc(), show_roles()))


class ApiSourceHandler(TaskHandler):
    URL = '/api/code/(.+)'

    def get(self, name):
        """ 显示后端API的源码 """
        for cls in self.application.handlers:
            handler = cls(self.application, self.request)
            for method in handler._get_methods().split(','):
                method = method.strip()
                if method != 'OPTIONS':
                    func = cls.__dict__[method.lower()]
                    func_name = re.sub(r'<|function |at .+$', '', str(func)).strip()
                    if func_name == name:
                        file = 'controller' + re.sub(r'^.+controller', '', inspect.getsourcefile(cls))
                        src = inspect.getsource(cls).strip()
                        return self.render('_api_src.html', name=name, file=file, src=src)
        self.render('_error.html', code=404, message=name + '不存在')
